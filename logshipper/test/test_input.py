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

import logging
import unittest

import eventlet
import mock

import logshipper.input

LOG = logging.getLogger(__name__)


class Test(unittest.TestCase):

    def test_thread_start(self):
        input_handler = logshipper.input.BaseInput()
        input_handler.run = mock.Mock()

        input_handler.start()
        input_handler.start()
        eventlet.sleep()

        input_handler.run.assert_called_once_with()

    def test_thread_lifecycle(self):

        status = ["not started"]

        def thread_runner():
            assert status[0] == "not started"
            status[0] = "started"

            try:
                while True:
                    eventlet.sleep()
            finally:
                status[0] = "stopped"

        input_handler = logshipper.input.BaseInput()
        input_handler.run = thread_runner

        self.assertEqual(status[0], "not started")
        input_handler.start()
        eventlet.sleep()
        self.assertEqual(status[0], "started")
        eventlet.sleep()
        input_handler.stop()
        eventlet.sleep()
        self.assertEqual(status[0], "stopped")
