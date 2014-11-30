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

from eventlet.green import time

import logshipper.input


LOG = logging.getLogger(__name__)


class Command(unittest.TestCase):

    def setUp(self):
        self.messages = []

    def handler(self, message):
        LOG.debug("Produced message %r", message)
        self.messages.append(message)

    def test_shell1(self):
        cmd = logshipper.input.Command(["echo", "'\""])
        cmd.set_handler(self.handler)

        cmd.start()
        time.sleep(0.1)
        cmd.stop()

        self.assertEqual(self.messages[0]['message'],
                         "'\"")

    def test_shell2(self):
        cmd = logshipper.input.Command("echo \"'\\\"\"")
        cmd.set_handler(self.handler)

        cmd.start()
        time.sleep(0.01)
        cmd.stop()

        self.assertEqual(self.messages[0]['message'], "'\"")

    def test_alt_separator(self):
        cmd = logshipper.input.Command(commandline="echo test__test2_boo",
                                       separator="__")
        cmd.set_handler(self.handler)

        cmd.start()
        time.sleep(0.1)
        cmd.stop()
        time.sleep(0.1)

        self.assertEqual(self.messages[0]['message'], "test")
        self.assertEqual(self.messages[1]['message'], "test2_boo\n")

    def test_unicode1(self):
        test_string = u"\u2713"  # unicode checkmark

        cmd = logshipper.input.Command(["echo", test_string])
        cmd.set_handler(self.handler)

        cmd.start()
        time.sleep(0.1)
        cmd.stop()

        self.assertEqual(self.messages[0]['message'], test_string)

    def test_unicode2(self):
        cmd = logshipper.input.Command(u"echo \u2713")  # unicode checkmark
        cmd.set_handler(self.handler)

        cmd.start()
        time.sleep(0.1)
        cmd.stop()

        self.assertEqual(self.messages[0]['message'], u"\u2713")

    def test_oneshot(self):
        cmd = logshipper.input.Command("echo 123")
        cmd.set_handler(self.handler)

        cmd.start()
        time.sleep(0.1)
        cmd.stop()

        self.assertEqual(len(self.messages), 1)

    def test_repeat(self):
        cmd = logshipper.input.Command("echo 123", interval=.1)
        cmd.set_handler(self.handler)

        cmd.start()
        time.sleep(0.3)
        cmd.stop()

        self.assertGreater(len(self.messages), 1)

    def test_kill(self):
        cmd = logshipper.input.Command("sleep .2; echo 123")
        cmd.set_handler(self.handler)

        cmd.start()
        time.sleep(0.01)
        cmd.stop()
        time.sleep(0.3)

        self.assertEqual(len(self.messages), 0)
