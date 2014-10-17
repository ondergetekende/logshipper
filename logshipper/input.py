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


import re
import sys

import eventlet
import eventlet.tpool


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


class Stdin(BaseInput):
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
    pri_matcher = re.compile(r'<(\d{1,3})>')  # <134>

    def __init__(self, bind="127.0.0.1", port=514):
        self.bind = bind
        self.port = int(port)

    def _run(self):
        self.server = eventlet.listen((self.bind, self.port))
        eventlet.serve(self.server, self.handle)

    def handle(self, socket, address):
        fileobj = socket.makefile('r', 4096)

        for line in fileobj:
            line = line.rstrip('\r\n').decode('utf-8')

            priority = Syslog.pri_matcher.match(line)
            if priority:
                prio = int(priority.group(1))

                message = {
                    'message': line[priority.end():],
                    'source_transport': 'syslog',
                    'facility': SYSLOG_FACILITIES[prio / 8],
                    'severity': SYSLOG_PRIORITIES[prio % 8],
                }

                self.handler(message)
