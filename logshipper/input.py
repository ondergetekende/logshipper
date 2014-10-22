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

import datetime
import logging
import re
import sys

import eventlet
from eventlet.green import subprocess
from eventlet.green import time
import eventlet.tpool


LOG = logging.getLogger(__name__)


class BaseInput():
    handler = None
    should_run = False
    thread = None

    def set_handler(self, handler):
        self.handler = handler

    def start(self):
        self.should_run = True
        if not self.thread:
            self.thread = eventlet.spawn(self._run)

    def stop(self):
        self.should_run = False
        thread = self.thread
        self.thread = None
        thread.kill()

    def _run(self):
        raise NotImplementedError


class Command(BaseInput):
    """Processes the output from a output, line by line

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

    def __init__(self, commandline, interval=60, env={}):
        self.commandline = commandline
        self.interval = int(interval)
        self.env = {"LC_ALL": "C"}
        self.env.update(env)

    def _run(self):
        while self.should_run:
            start_time = time.time()
            p = subprocess.Popen(self.commandline, stdin=None,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 env=self.env)

            def process_pipe(pipe):
                while not pipe.closed:
                    line = pipe.readline()
                    if not line:
                        break
                    self.handler({"message": line.rstrip()})

            stdout_thread = eventlet.spawn(process_pipe, p.stdout)
            stderr_thread = eventlet.spawn(process_pipe, p.stderr)

            p.wait()

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
    def _run(self):
        while self.should_run:
            line = eventlet.tpool.execute(sys.stdin.readline)
            self.handler({"message": line.rstrip()})


SYSLOG_PRIORITIES = ['emergency', 'alert', 'critical', 'error', 'warning',
                     'notice', 'informational', 'debug']
SYSLOG_FACILITIES = ([
    'kern', 'user', 'mail', 'daemon', 'auth', 'syslog', 'lpr', 'news',
    'uucp', 'cron', 'authpriv', 'ftp', 'ntp', 'audit', 'alert', 'local', ]
    + ['local%i' % i for i in range(8)]
    + ['unknown%02i' % i for i in range(12)]
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
    ``

    Example for ``input.yml``:

    .. code:: yaml

        - syslog:
            bind: 127.0.0.1
            port: 1514
    """

    class rfc5424_tz(datetime.tzinfo):
        def __init__(self, offset):
            self.offset = offset

        def utcoffset(self):
            return self.offset

        def dst(self, dt):
            return datetime.timedelta(0)

        def tzname(self, dt):
            return "unnamed"

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

        if protocol == 'rfc5424':
            self.regexes = [Syslog.rfc5424_matcher]
        elif protocol == 'rfc3164':
            self.regexes = [Syslog.rfc3164_matcher]
        elif protocol == 'auto':
            self.regexes = [Syslog.rfc5424_matcher, Syslog.rfc3164_matcher]
        else:
            raise Exception('protocol must be either rfc3164, rfc5424 or auto')

    def _run(self):
        self.server = eventlet.listen((self.bind, self.port))
        eventlet.serve(self.server, self.handle)

    def handle(self, socket, address):
        fileobj = socket.makefile('r', 4096, encoding='utf-8')

        for line in fileobj:
            self.process_message(line)

    def process_message(self, line):
        line = line.rstrip('\r\n')

        for r in self.regexes:
            match = r.match(line)
            if not match:
                continue

            message = match.groupdict()

            prival = int(message.pop('prival'))
            if prival <= 255:
                message['facility'] = SYSLOG_FACILITIES[prival // 8]
                message['severity'] = SYSLOG_PRIORITIES[prival % 8]

            structured_data = message.pop('sd', '-')
            if structured_data != '-':
                # TODO(KvdV): Parse structured data
                message['structured_data'] = structured_data

            timestamp = message.pop('timestamp', '-')
            if timestamp != '-':
                if timestamp.endswith('Z'):
                    tz_offset = datetime.timedelta(0)
                    timestamp = timestamp[:-1]
                else:
                    direction = 1 if timestamp[-6] == '+' else -1
                    tz_offset = datetime.timedelta(
                        hours=direction * int(timestamp[-5:-3]),
                        minutes=direction * int(timestamp[-2:]),
                    )
                    timestamp = timestamp[:-6]

                timestamp = timestamp.split('.')
                ts = datetime.datetime.strptime(timestamp[0],
                                                "%Y-%m-%dT%H:%M:%S")
                if len(timestamp) == 2:
                    seconds = float("."+timestamp[1])
                    ts = ts + datetime.timedelta(seconds=seconds)
                ts = ts.replace(tzinfo=Syslog.rfc5424_tz(tz_offset))
                message['timestamp'] = ts

            message['message'] = line[match.end():]

            self.handler(message)
            return

        LOG.warning("dropping message, not RFC compliant")
