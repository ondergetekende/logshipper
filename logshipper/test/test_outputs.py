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
import sys
import unittest

import mock
import statsd

import logshipper.context
import logshipper.outputs


class Tests(unittest.TestCase):
    def test_stdout(self):
        message = {
            "message": "This is a test.",
            "timestamp": datetime.datetime(2008, 10, 19, 14, 40, 0, 9),
        }
        context = logshipper.context.Context(message, None)

        with mock.patch.object(sys.stdout, 'write') as mock_method:
            handler = logshipper.outputs.prepare_stdout({})

            handler(message, context)

            mock_method.assert_called_once_with("This is a test.\n")

    def test_statsd_counter(self):
        message = {
            "message": "This is a test.",
            "timestamp": datetime.datetime(2008, 10, 19, 14, 40, 0, 9),
        }
        context = logshipper.context.Context(message, None)

        with mock.patch.object(statsd.Client, '_send') as mock_method:
            handler = logshipper.outputs.prepare_statsd({'name': "FOO",
                                                         'host': '127.0.1.1'})

            handler(message, context)

            self.assertEqual(mock_method.call_args[0][1],
                             {"FOO": '1|c'})

            self.assertEqual(mock_method.call_args[0][0].connection._host,
                             "127.0.1.1")

    def test_statsd_gauge(self):
        message = {
            "message": "This is a test.",
            "timestamp": datetime.datetime(2008, 10, 19, 14, 40, 0, 9),
        }
        context = logshipper.context.Context(message, None)

        with mock.patch.object(statsd.Client, '_send') as mock_method:
            handler = logshipper.outputs.prepare_statsd({'name': "FOO",
                                                         "type": "gauge"})

            handler(message, context)

            self.assertEqual(mock_method.call_args[0][1],
                             {"FOO": '1.0|g'})

    def test_statsd_timer(self):
        message = {
            "message": "This is a test.",
            "timestamp": datetime.datetime(2008, 10, 19, 14, 40, 0, 9),
        }
        context = logshipper.context.Context(message, None)

        with mock.patch.object(statsd.Client, '_send') as mock_method:
            handler = logshipper.outputs.prepare_statsd({'name': "FOO",
                                                         "type": "timer",
                                                         "multiplier": 0.1})

            handler(message, context)

            self.assertEqual(mock_method.call_args[0][1],
                             {"FOO": '100.00000000|ms'})
