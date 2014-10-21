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
        context = logshipper.context.Context(message, None)
        result = handler(message, context)

        self.assertEqual(result, None)
        self.assertEqual(context.match_field, "message")
        self.assertEqual(context.backreferences, ['test', 'est'])

        message = {"message": "This is not a match."}
        context = logshipper.context.Context(message, None)
        result = handler(message, context)
        self.assertEqual(result, logshipper.filters.SKIP_STEP)
        self.assertEqual(context.match_field, None)
        self.assertEqual(context.backreferences, [])

    def test_match_n(self):
        handler = logshipper.filters.prepare_match({"message": "(t.st)",
                                                    "foo": "(?P<boo>b.r)"})
        message = {"message": "This is a test.", "foo": "barbar"}
        context = logshipper.context.Context(message, None)
        result = handler(message, context)

        self.assertEqual(result, None)
        self.assertEqual(context.match_field, None)
        self.assertEqual(context.backreferences, [])
        self.assertEqual(message['boo'], 'bar')

    def test_replace(self):
        match_handler = logshipper.filters.prepare_match("t(.st)")
        replace_handler = logshipper.filters.prepare_replace("T{1}")
        message = {"message": "This is a test."}
        context = logshipper.context.Context(message, None)
        match_handler(message, context)
        replace_handler(message, context)

        self.assertEqual(message['message'], 'This is a Test.')

    def test_set(self):
        handler = logshipper.filters.prepare_set({"baz": "l{1}{foo}r"})
        message = {"foo": "shippe"}
        context = logshipper.context.Context(message, None)
        context.backreferences = ("", "og",)
        result = handler(message, context)
        self.assertEqual(result, None)
        self.assertEqual(message['baz'], "logshipper")
