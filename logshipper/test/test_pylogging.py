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
import tempfile
import unittest

import logshipper.context
import logshipper.pylogging


class Tests(unittest.TestCase):
    def setUp(self):
        global records
        records = []

    def test_pylogging(self):
        message = {
            "message": "This is a test.",
            "timestamp": datetime.datetime(2008, 10, 19, 14, 40, 0, 9),
        }
        context = logshipper.context.Context(message, None)

        with tempfile.NamedTemporaryFile() as f:
            handler = logshipper.pylogging.prepare_logging({
                "handler": {
                    'class': 'logging.FileHandler',
                    'filename': f.name,
                },
                'formatter': {
                    '()': 'logging.Formatter',
                    'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S',
                }
            })

            handler(message, context)

            logfile = f.read()

            self.assertEqual(
                logfile,
                b"2008-10-19 14:40:00 INFO logshipper This is a test.\n")
