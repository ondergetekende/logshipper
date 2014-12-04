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

import codecs
import datetime
import logging
import re
import socket
import sys

import eventlet
from eventlet.green import subprocess
from eventlet.green import time
import eventlet.tpool
import six


LOG = logging.getLogger(__name__)


class BaseInput(object):
    handler = None
    should_run = False
    thread = None

    def set_handler(self, handler):
        self.handler = handler

    def emit(self, message):
        message.setdefault('timestamp', datetime.datetime.utcnow())
        message.setdefault('hostname', socket.gethostname())

        assert six.PY3 or isinstance(message['message'], six.text_type)
        assert isinstance(message['timestamp'], datetime.datetime)
        assert message['timestamp'].tzinfo is None

        self.handler(message)

    def start(self):
        self.should_run = True
        if self.thread is None:
            self.thread = eventlet.spawn(self._run)

    def stop(self):
        self.should_run = False
        thread = self.thread
        if thread:
            thread.kill()
        self.thread = None

    def _run(self):
        try:
            self.run()
        except Exception:
            LOG.exception("Encountered exception while running %s", self)

    def run(self):
        raise NotImplementedError  # pragma: no cover


class Command(BaseInput):
    r"""Processes the output from a output, line by line

    Start a process, and generated the lines from both stderr and stdout as
    a message. For one-shot processes (such as uptime), ``interval`` means
    the number of seconds between two calls. For longer running processes,
    such as ``iostat -w1``, interval functions like a respawn limiter.

    Example pipeline:

    .. code:: yaml

        inputs:
        - command:
            commandline: uptime
            interval: 60
        steps:
        - match: >
            (?x)
            load\saverage:\s
            (?P<uptime_1m>\d+\.\d+),\s
            (?P<uptime_5m>\d+\.\d+),\s
            (?P<uptime_15m>\d+\.\d+)
        - match: (?P<users>\d+) users
        - unset: message
        - debug:
    """

    def __init__(self, commandline, interval=60, env=None, separator='\n'):
        self.commandline = commandline
        self.interval = int(interval)
        self.env = {"LC_ALL": "C"}
        if env:
            self.env.update(env)
        self.separator = separator
        self.process = None

    def stop(self):
        if self.process:
            self.process.terminate()
        super(Command, self).stop()

    def run(self):
        while self.should_run:
            start_time = time.time()
            if isinstance(self.commandline, six.string_types):
                self.process = subprocess.Popen(self.commandline,
                                                close_fds=True,
                                                env=self.env, shell=True,
                                                stdin=subprocess.PIPE,
                                                stdout=subprocess.PIPE,
                                                stderr=subprocess.PIPE)
            else:
                self.process = subprocess.Popen(self.commandline,
                                                close_fds=True, env=self.env,
                                                stdin=subprocess.PIPE,
                                                stdout=subprocess.PIPE,
                                                stderr=subprocess.PIPE)

            self.process.stdin.close()

            if self.separator == '\n':
                def process_pipe(pipe):
                    while not pipe.closed:
                        line = pipe.readline()
                        if not line:
                            break

                        line = line.decode('utf8')
                        self.emit({"message": line.rstrip('\n')})
            else:
                def process_pipe(pipe):
                    buf = u""
                    for chunk in codecs.iterdecode(pipe, 'utf8'):
                        buf += chunk
                        messages = buf.split(self.separator)
                        buf = messages[-1]
                        messages = messages[:-1]
                        for message in messages:
                            self.emit({"message": message})
                    if buf:
                        self.emit({"message": buf})

            stdout_thread = eventlet.spawn(process_pipe, self.process.stdout)
            stderr_thread = eventlet.spawn(process_pipe, self.process.stderr)

            self.process.wait()
            self.process = None

            stdout_thread.wait()
            stderr_thread.wait()

            took = time.time() - start_time
            time.sleep(self.interval - took)


class Stdin(BaseInput):
    """Reads messages from stdin

    Messages are separated by newlines. Whitespace at the end of a message
    will get stripped.

    Example for ``input.yml``:

    .. code:: yaml

        - stdin: {}
    """
    def run(self):
        while self.should_run:
            line = eventlet.tpool.execute(sys.stdin.readline)
            self.emit({"message": line.rstrip()})


SYSLOG_PRIORITIES = ['emergency', 'alert', 'critical', 'error', 'warning',
                     'notice', 'informational', 'debug']
SYSLOG_FACILITIES = (
    ['kern', 'user', 'mail', 'daemon', 'auth', 'syslog', 'lpr', 'news',
     'uucp', 'cron', 'authpriv', 'ftp', 'ntp', 'audit', 'alert', 'local'] +
    ['local%i' % i for i in range(8)] +
    ['unknown%02i' % i for i in range(12)]
)


class Syslog(BaseInput):
    """Reads messages from syslog

    Listens for syslog messages on a TCP socket. Note that if you want to
    bind the (default) syslog port, you'll need to run logshipper as root.

    Sets the ``facility`` and ``severity`` as defined by rfc3164.

    ``bind``
        Ip address or hostname to bind to. Defaults to ``127.0.0.1``
    ``port``
        Port to bind to. Defaults to ``514``
    ``protocol``
        If set to ``rfc5424``, RFC-5424 matching will be tried,
        and non-compliant messages will silently be dropped.
        If set to ``rfc3164``, the much simpler RFC-3164 will be used.
        If set to ``auto``, RFC-5424 messages will be detected and disected,
        while non-RFC-5424 messages will be processed as RFC-3164.

    Example for ``input.yml``:

    .. code:: yaml

        - syslog:
            bind: 127.0.0.1
            port: 1514
    """

    rfc3164_matcher = re.compile(r'<(?P<prival>\d{1,3})>')

    rfc5424_matcher = re.compile(r"""
        <(?P<prival>\d{1,3})>1
        \s
        (?P<timestamp>-|\d\d\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?
            (Z|[+-]\d\d:\d\d))
        \s
        (?P<hostname>-|\S{1,255})
        \s
        (?P<appname>-|\S{1,48})
        \s
        (?P<procid>-|\S{1,128})
        \s
        (?P<msgid>-|\S{1,32})
        \s
        (?P<sd>-|\[[^\]]+\])
        \s*
        """, re.X)  # <134>

    def __init__(self, bind="127.0.0.1", port=514, protocol='auto'):
        self.bind = bind
        self.port = int(port)
        self.server = None

        if protocol == 'rfc5424':
            self.regexes = [Syslog.rfc5424_matcher]
        elif protocol == 'rfc3164':
            self.regexes = [Syslog.rfc3164_matcher]
        elif protocol == 'auto':
            self.regexes = [Syslog.rfc5424_matcher, Syslog.rfc3164_matcher]
        else:
            raise ValueError(
                'protocol must be either rfc3164, rfc5424 or auto')

    def run(self):
        self.server = eventlet.listen((self.bind, self.port))
        eventlet.serve(self.server, self.handle)

    def handle(self, sock, address):
        LOG.info("Accepted syslog connection from %r", address[0])
        fileobj = sock.makefile('r')

        for line in fileobj:
            self.process_message(line.decode('utf8'), address[0])

        LOG.info("%r closed connection to syslog", address[0])

    def process_message(self, line, peer):
        line = line.rstrip('\r\n')

        for regex in self.regexes:
            match = regex.match(line)
            if not match:
                continue

            message = match.groupdict()
            message.setdefault('hostname', peer)

            prival = int(message.pop('prival'))
            if prival <= 255:
                message['facility'] = SYSLOG_FACILITIES[prival // 8]
                message['severity'] = SYSLOG_PRIORITIES[prival % 8]

            structured_data = message.pop('sd', '-')
            if structured_data != '-':
                # TODO(KvdV): Parse structured data
                message['structured_data'] = structured_data

            timestampstr = message.pop('timestamp', '-')
            if timestampstr != '-':
                if timestampstr.endswith('Z'):
                    tz_offset = datetime.timedelta(0)
                    timestampstr = timestampstr[:-1]
                else:
                    direction = 1 if (timestampstr[-6] == '+') else -1
                    tz_offset = datetime.timedelta(
                        hours=direction * int(timestampstr[-5:-3]),
                        minutes=direction * int(timestampstr[-2:]),
                    )
                    timestampstr = timestampstr[:-6]

                timestampstr = timestampstr.split('.')
                timestamp = datetime.datetime.strptime(timestampstr[0],
                                                       "%Y-%m-%dT%H:%M:%S")
                if len(timestampstr) == 2:
                    seconds = float("." + timestampstr[1])
                    timestamp += datetime.timedelta(seconds=seconds)

                if tz_offset:
                    timestamp += tz_offset

                message['timestamp'] = timestamp

            message['message'] = line[match.end():]

            self.emit(message)
            return

        LOG.warning("dropping message, not RFC compliant")
