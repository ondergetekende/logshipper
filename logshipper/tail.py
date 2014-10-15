# Copyright 2014 Koert van der Veer
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


import glob

import eventlet
import eventlet.tpool
import pyinotify
import six
import os


class Tail:
    class FileTail:
        __slots__ = ['fd', 'buffer']
        ctime = None
        fd = None
        buffer = ""

    def __init__(self, filename):
        if isinstance(filename, six.string_types):
            filename = [filename]

        self.handler = None
        self.globs = [os.path.abspath(f) for f in filename]
        self.updater_thread = None
        self.watch_manager = pyinotify.WatchManager()
        self.tails = {}
        mask = sum([pyinotify.IN_MODIFY,
                    pyinotify.IN_CLOSE_WRITE,
                    pyinotify.IN_CREATE,
                    pyinotify.IN_DELETE,
                    pyinotify.IN_DELETE_SELF])

        for fileglob in self.globs:
            self.watch_manager.add_watch(fileglob, mask, do_glob=True,
                                         auto_add=True)

        notifier = pyinotify.Notifier(self.watch_manager, self._inotify)
        self.notifier = eventlet.tpool.Proxy(notifier)

    def _inotify(self, event):
        self.process_tail(event.path)

    def set_handler(self, handler):
        self.handler = handler

    def start(self):
        self.should_run = True
        self.update_tails(self.globs, do_read_all=False)
        eventlet.spawn(self.notifier.loop, lambda _: not self.should_run)

    def stop(self):
        self.should_run = False
        self.notifier.stop()
        self.update_tails([])

    def process_tail(self, path, do_read_all=True):
        try:
            tail = self.tails[path]
        except KeyError:
            self.tails[path] = tail = Tail.FileTail()
            tail.fd = os.open(path, os.O_RDONLY)
            stat = os.lstat(path)
            tail.ctime = stat.st_ctime
            if not do_read_all:
                os.lseek(tail.fd, 0, os.SEEK_END)

        while True:
            buff = os.read(tail.fd, 1024)
            if not buff:
                return

            if tail.buffer:
                buff = tail.buff + buff
                tail.buff = ""

            lines = buff.splitlines(True)
            if lines[-1][-1] != "\n":  # incomplete line in buffer
                tail.buffer = lines[-1][-1]
                lines = lines[:-1]

            for line in lines:
                self.handler({'message': line[:-1]})

    def update_tails(self, globs, do_read_all=True):
        watches = set()

        for fileglob in globs:
            for path in glob.iglob(fileglob):
                self.process_tail(path, do_read_all)
                watches.add(path)

        for vanished in (set(self.tails) - watches):
            tail = self.tails.pop(vanished)
            if tail.buffer:
                self.handler({'message': tail.buffer})
            os.close(tail.fd)
