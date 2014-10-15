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

import logshipper.context
import logshipper.filters


class Tests(unittest.TestCase):
    def test_drop(self):
        handler = logshipper.filters.prepare_drop(None)

        self.assertEqual(handler({}, None),
                         logshipper.filters.DROP_MESSAGE)

    def test_match_1(self):
        handler = logshipper.filters.prepare_match("t(.st)")
        message = {"message": "This is a test."}
        context = logshipper.context.Context(None)
        result = handler(message, context)

        self.assertEqual(result, None)
        self.assertEqual(context.match_field, "message")
        self.assertEqual(context.backreferences, ['test', 'est'])

        message = {"message": "This is not a match."}
        context = logshipper.context.Context(None)
        result = handler(message, context)
        self.assertEqual(result, logshipper.filters.SKIP_STEP)
        self.assertEqual(context.match_field, None)
        self.assertEqual(context.backreferences, [])

    def test_match_n(self):
        handler = logshipper.filters.prepare_match({"message": "(t.st)",
                                                    "foo": "(?P<boo>b.r)"})
        message = {"message": "This is a test.", "foo": "barbar"}
        context = logshipper.context.Context(None)
        result = handler(message, context)

        self.assertEqual(result, None)
        self.assertEqual(context.match_field, None)
        self.assertEqual(context.backreferences, [])
        self.assertEqual(context.variables, {'boo': 'bar'})

    def test_set(self):
        handler = logshipper.filters.prepare_set({"foo": "l{1}{foo}r"})
        message = {}
        context = logshipper.context.Context(None)
        context.backreferences = ("", "og",)
        context.variables = {"foo": "shippe"}
        result = handler(message, context)
        self.assertEqual(result, None)
        self.assertEqual(message, {"foo": "logshipper"})
