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
import random
import unittest

import eventlet
import eventlet.green.socket as socket

import logshipper.input

LOG = logging.getLogger(__name__)


class Syslog(unittest.TestCase):

    def test_rfc3164(self):
        msg = [None]

        def handler(m):
            msg[0] = m

        syslog = logshipper.input.Syslog()
        syslog.set_handler(handler)

        syslog.process_message(u"<132>Foo", 'fakehost')

        self.assertEqual(msg[0]['message'], "Foo")
        self.assertEqual(msg[0]['facility'], "local0")
        self.assertEqual(msg[0]['severity'], "warning")
        self.assertEqual(msg[0]['hostname'], "fakehost")

        self.assertSetEqual(set(msg[0]),
                            set(["message", "facility", "severity",
                                 "hostname", "timestamp"]))

    def test_rfc5424(self):
        msg = []

        def handler(m):
            LOG.debug("msg received: %r", m)
            msg.append(m)

        syslog = logshipper.input.Syslog(protocol='rfc5424')
        syslog.set_handler(handler)

        syslog.process_message(
            u"<165>1 2003-10-11T22:14:15.003Z machine.example.com evntslog - "
            u"ID47 [exampleSDID@32473 iut=\"3\" eventSource=\"Application\" "
            u"eventID=\"1011\"] Actual event text", 'fakehost')
        syslog.process_message(
            u"<165>1 2003-10-11T22:14:15.003+01:00 - - - - - event text 1",
            'fakehost')
        syslog.process_message(
            u"<165>1 2003-10-11T22:14:15.003-01:00 - - - - - event text 2",
            'fakehost')

        self.assertEqual(msg[0]['message'], 'Actual event text')

        self.assertEqual(msg[0]['procid'], '-')
        self.assertEqual(msg[0]['severity'], 'notice')
        self.assertEqual(msg[0]['appname'], 'evntslog')
        self.assertEqual(msg[0]['msgid'], 'ID47')
        self.assertEqual(msg[0]['hostname'], 'machine.example.com')
        self.assertEqual(msg[0]['facility'], 'local4')
        self.assertEqual(msg[0]['timestamp'].year, 2003)
        self.assertEqual(msg[0]['timestamp'].month, 10)
        self.assertEqual(msg[0]['timestamp'].day, 11)
        self.assertEqual(msg[0]['timestamp'].hour, 22)
        self.assertEqual(msg[0]['timestamp'].minute, 14)
        self.assertEqual(msg[0]['timestamp'].second, 15)
        self.assertEqual(msg[0]['timestamp'].microsecond, 3000)
        self.assertEqual(msg[0]['structured_data'],
                         ('[exampleSDID@32473 iut="3" '
                          'eventSource="Application" eventID="1011"]'))
        # self.assertEqual(
        #     msg[0]['exampleSDID@32473'],
        #     {'iut': "3",  'eventSource': "Application", 'eventID': "1011"})

        self.assertSetEqual(set(msg[0]),
                            set(["message", "facility", "severity",
                                 "procid", "appname", 'structured_data',
                                 'hostname', 'timestamp', 'msgid']))

        self.assertEqual(msg[1]['timestamp'],
                         datetime.datetime(2003, 10, 11, 23, 14, 15, 3000))
        self.assertEqual(msg[2]['timestamp'],
                         datetime.datetime(2003, 10, 11, 21, 14, 15, 3000))

    def test_autorfc(self):
        msg = []

        def handler(m):
            LOG.debug("msg received: %r", m)
            msg.append(m)

        syslog = logshipper.input.Syslog()
        syslog.set_handler(handler)

        syslog.process_message(u"<132>Foo", "fakehost")
        syslog.process_message(
            u"<165>1 2003-10-11T22:14:15.003Z - - - - - Actual event text",
            "fakehost")

        self.assertEqual(msg[0]['message'], "Foo")
        self.assertEqual(msg[1]['message'], 'Actual event text')

    def test_socket(self):
        msg = []

        def handler(m):
            LOG.debug("msg received: %r", m)
            msg.append(m)

        port = random.randint(32768, 65536)
        syslog = logshipper.input.Syslog(port=port)
        syslog.set_handler(handler)

        syslog.start()
        eventlet.sleep(0.01)

        c = socket.socket()
        c.connect(('127.0.0.1', port))
        c.sendall(b'<73>Hello\n')
        c.close()
        eventlet.sleep(0.01)

        self.assertEqual(len(msg), 1)
        self.assertEqual(msg[0]['message'], 'Hello')
