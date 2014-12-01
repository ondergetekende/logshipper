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
import shutil
import tempfile
import unittest

import eventlet

import logshipper.tail

LOG = logging.getLogger(__name__)


class Tail(unittest.TestCase):

    def test_prexist(self):
        messages = []

        def message_handler(m):
            LOG.debug('event generated %s', m['message'])
            messages.append(m)

        with tempfile.NamedTemporaryFile() as f:
            f.write(b"test123\n")
            f.flush()

            tail = logshipper.tail.Tail(f.name)
            tail.set_handler(message_handler)
            tail.start()
            eventlet.sleep(0.01)  # give thread a chance to open the file

            f.write(b"second line\n")
            f.flush()
            eventlet.sleep(0.01)  # give thread a chance to read the line

            tail.stop()
            eventlet.sleep(0.01)  # give thread a chance to close the line

        self.assertEqual(messages, [{"message": "second line"}])

    def test_wildcard(self):
        messages = []

        def message_handler(m):
            LOG.debug('event generated %s', m['message'])
            messages.append(m)

        try:
            path = tempfile.mkdtemp()
            tail = logshipper.tail.Tail(path + "/*.log")
            tail.set_handler(message_handler)
            tail.start()
            eventlet.sleep(0.01)  # give thread a chance to open the file

            LOG.debug("about to write line 1")
            with open(path + "/test.log", 'w') as f:
                f.write("line 1\n")

            eventlet.sleep(0.01)  # give thread a chance to read the line
            self.assertEqual(messages, [{"message": "line 1"}])

            LOG.debug("about to write line 2")
            with open(path + "/test.log", 'a') as f:
                f.write("line 2\n")

            eventlet.sleep(0.01)  # give thread a chance to read the line
            self.assertEqual(messages, [{"message": "line 1"},
                                        {"message": "line 2"}])

            tail.stop()
            eventlet.sleep(0.1)  # give thread a chance to close the line

        finally:
            shutil.rmtree(path)
