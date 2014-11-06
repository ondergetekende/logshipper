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


import unittest
from eventlet.green import time

import logshipper.input


class Command(unittest.TestCase):

    def test_shell1(self):
        msg = []

        def handler(m):
            msg.append(m)

        cmd = logshipper.input.Command(["echo", "'\""])
        cmd.set_handler(handler)

        cmd.start()
        time.sleep(0.1)
        cmd.stop()

        self.assertEqual(msg[0]['message'], "'\"")

    def test_shell2(self):
        msg = []

        def handler(m):
            msg.append(m)

        cmd = logshipper.input.Command("echo \"'\\\"\"")
        cmd.set_handler(handler)

        cmd.start()
        time.sleep(0.1)
        cmd.stop()

        self.assertEqual(msg[0]['message'], "'\"")

    def test_unicode1(self):
        msg = []

        def handler(m):
            msg.append(m)

        cmd = logshipper.input.Command(["echo", u"\u2713"])  # unicode checkmark
        cmd.set_handler(handler)

        cmd.start()
        time.sleep(0.1)
        cmd.stop()

        self.assertEqual(msg[0]['message'], u"\u2713")

    def test_unicode2(self):
        msg = []

        def handler(m):
            msg.append(m)

        cmd = logshipper.input.Command(u"echo \u2713")  # unicode checkmark
        cmd.set_handler(handler)

        cmd.start()
        time.sleep(0.1)
        cmd.stop()

        self.assertEqual(msg[0]['message'], u"\u2713")

    def test_oneshot(self):
        msg = []

        def handler(m):
            msg.append(m)

        cmd = logshipper.input.Command("echo 123")
        cmd.set_handler(handler)

        cmd.start()
        time.sleep(0.1)
        cmd.stop()

        self.assertEqual(len(msg), 1)

    def test_repeat(self):
        msg = []

        def handler(m):
            msg.append(m)

        cmd = logshipper.input.Command("echo 123", interval=.1)
        cmd.set_handler(handler)

        cmd.start()
        time.sleep(0.3)
        cmd.stop()

        self.assertGreater(len(msg), 1)

    def test_kill(self):
        msg = []

        def handler(m):
            msg.append(m)

        cmd = logshipper.input.Command("sleep .2; echo 123")
        cmd.set_handler(handler)

        cmd.start()
        time.sleep(0.01)
        cmd.stop()
        time.sleep(0.3)

        self.assertEqual(len(msg), 0)
