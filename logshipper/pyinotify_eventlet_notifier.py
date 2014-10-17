# Copyright 2014 Koert van der Veer
# Adapted from pyeventlet, which is MIT licensed
#
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


# Import directives
import array
import collections
import errno
import fcntl
import logging
import struct
import termios

from eventlet.green import os
from eventlet.green import select
from eventlet.green import time
import pyinotify

LOG = logging.getLogger(__name__)


class Notifier:

    def __init__(self, watch_manager, default_proc_fun=None, read_freq=0,
                 threshold=0, timeout=None):
        # Watch Manager instance
        self._watch_manager = watch_manager
        # File descriptor
        self._fd = self._watch_manager.get_fd()
        # Poll object and registration
        # This pipe is correctely initialized and used by ThreadedNotifier
        self._pipe = (-1, -1)
        # Event queue
        self._eventq = collections.deque()
        # System processing functor, common to all events
        self._sys_proc_fun = pyinotify._SysProcessEvent(self._watch_manager,
                                                        self)
        # Default processing method
        self._default_proc_fun = default_proc_fun
        if default_proc_fun is None:
            self._default_proc_fun = pyinotify.PrintAllEvents()
        # Loop parameters
        self._read_freq = read_freq
        self._threshold = threshold
        self._timeout = timeout

    def append_event(self, event):
        self._eventq.append(event)

    def proc_fun(self):
        return self._default_proc_fun

    def check_events(self, timeout=None):
        while True:
            try:
                # blocks up to 'timeout' milliseconds
                if timeout is None:
                    timeout = self._timeout
                ret = select.select([self._fd], [self._fd], [self._fd])
            except select.error as err:
                if err[0] == errno.EINTR:
                    continue  # interrupted, retry
                else:
                    raise
            else:
                break

        # only one fd is polled
        return bool(ret[0])

    def read_events(self):
        buf_ = array.array('i', [0])
        # get event queue size
        if fcntl.ioctl(self._fd, termios.FIONREAD, buf_, 1) == -1:
            return
        queue_size = buf_[0]
        if queue_size < self._threshold:
            LOG.debug('(fd: %d) %d bytes available to read but threshold is '
                      'fixed to %d bytes', self._fd, queue_size,
                      self._threshold)
            return

        try:
            # Read content from file
            r = os.read(self._fd, queue_size)
        except Exception as msg:
            raise pyinotify.NotifierError(msg)
        LOG.debug('Event queue size: %d', queue_size)
        rsum = 0  # counter
        while rsum < queue_size:
            s_size = 16
            # Retrieve wd, mask, cookie and fname_len
            wd, mask, cookie, fname_len = struct.unpack('iIII',
                                                        r[rsum:rsum+s_size])
            # Retrieve name
            fname, = struct.unpack('%ds' % fname_len,
                                   r[rsum + s_size:rsum + s_size + fname_len])
            rawevent = pyinotify._RawEvent(wd, mask, cookie, fname)
            self._eventq.append(rawevent)
            rsum += s_size + fname_len

    def process_events(self):
        while self._eventq:
            raw_event = self._eventq.popleft()  # pop next event
            watch_ = self._watch_manager.get_watch(raw_event.wd)
            if ((watch_ is None) and
                    (raw_event.mask & ~pyinotify.IN_Q_OVERFLOW)):
                if not (raw_event.mask & pyinotify.IN_IGNORED):
                    # Not really sure how we ended up here, nor how we should
                    # handle these types of events and if it is appropriate to
                    # completly skip them (like we are doing here).
                    LOG.warning(
                        "Unable to retrieve Watch object associated to %s",
                        repr(raw_event))
                continue
            revent = self._sys_proc_fun(raw_event)  # system processings
            if watch_ and watch_.proc_fun:
                try:
                    watch_.proc_fun(revent)  # user processings
                except Exception:  # noqa
                    import traceback
                    traceback.print_exc()
            else:
                self._default_proc_fun(revent)
        self._sys_proc_fun.cleanup()  # remove olds MOVED_* events records

    def _sleep(self, ref_time):
        # Only consider sleeping if read_freq is > 0
        if self._read_freq > 0:
            cur_time = time.time()
            sleep_amount = self._read_freq - (cur_time - ref_time)
            if sleep_amount > 0:
                LOG.debug('Now sleeping %d seconds', sleep_amount)
                time.sleep(sleep_amount)

    def loop(self, callback=None, daemonize=False, **args):
        if daemonize:
            self.__daemonize(**args)

        # Read and process events forever
        while 1:
            try:
                self.process_events()
                try:
                    if (callback is not None) and (callback(self) is True):
                        break
                except Exception:  # noqa
                    import traceback
                    traceback.print_exc()
                ref_time = time.time()
                # check_events is blocking
                if self.check_events():
                    self._sleep(ref_time)
                    self.read_events()
            except KeyboardInterrupt:
                # Stop monitoring if sigint is caught (Control-C).
                LOG.debug('Pyinotify stops monitoring.')
                break
        # Close internals
        self.stop()

    def stop(self):
        os.close(self._fd)
