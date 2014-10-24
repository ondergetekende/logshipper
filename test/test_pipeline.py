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

import logshipper.pipeline
import logshipper.input


class Tests(unittest.TestCase):

    def test_prepare_input(self):
        handler = logshipper.pipeline.prepare_input('stdin', {}, None)

        self.assertIsInstance(handler, logshipper.input.Stdin)

    def test_prepare_filter(self):
        handler = logshipper.pipeline.prepare_step({'set': {'a': 'a'}})

        self.assertNotEquals(handler, None)
        self.assertEqual(len(handler), 1)
        message = {}
        handler[0](message, None)
        self.assertEqual(message['a'], 'a')
