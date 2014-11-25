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
import unittest

import pytz

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

    def test_extract1(self):
        handler = logshipper.filters.prepare_extract({"message": "(t.st)",
                                                      "foo": "(?P<boo>b.r)"})
        message = {"message": "This is a test.", "foo": "barbar"}
        context = logshipper.context.Context(message, None)
        result = handler(message, context)

        self.assertEqual(result, None)
        self.assertEqual(context.match_field, None)
        self.assertEqual(context.backreferences, [])
        self.assertEqual(message['boo'], 'bar')
        self.assertEqual(message['foo'], 'bar')
        self.assertEqual(message['message'], 'This is a .')

    def test_extract2(self):
        handler = logshipper.filters.prepare_extract({"message": "(t.st)"})
        message = {"message": "This is a fail."}
        context = logshipper.context.Context(message, None)
        result = handler(message, context)

        self.assertEqual(result, logshipper.filters.SKIP_STEP)

    def test_edge1(self):
        h = logshipper.filters.prepare_edge("{foo}")
        handler = lambda m: h(m, logshipper.context.Context(m, None))

        result = handler({"foo": "1"})
        self.assertNotEqual(result, logshipper.filters.SKIP_STEP)
        result = handler({"foo": "1"})
        self.assertEqual(result, logshipper.filters.SKIP_STEP)
        result = handler({"foo": "2"})
        self.assertNotEqual(result, logshipper.filters.SKIP_STEP)
        result = handler({"foo": "1"})
        self.assertNotEqual(result, logshipper.filters.SKIP_STEP)

    def test_edge2(self):
        h = logshipper.filters.prepare_edge({"trigger": "{foo}",
                                             "backlog": 2})
        handler = lambda m: h(m, logshipper.context.Context(m, None))
        result = handler({"foo": "1"})
        self.assertNotEqual(result, logshipper.filters.SKIP_STEP)
        result = handler({"foo": "2"})
        self.assertNotEqual(result, logshipper.filters.SKIP_STEP)
        result = handler({"foo": "1"})
        self.assertEqual(result, logshipper.filters.SKIP_STEP)
        result = handler({"foo": "2"})
        self.assertEqual(result, logshipper.filters.SKIP_STEP)
        result = handler({"foo": "3"})
        self.assertNotEqual(result, logshipper.filters.SKIP_STEP)
        result = handler({"foo": "1"})
        self.assertNotEqual(result, logshipper.filters.SKIP_STEP)

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

    def test_unset(self):
        handler = logshipper.filters.prepare_unset("foo, bar")
        message = {"foo": "shippe", "baz": "yeah"}
        context = logshipper.context.Context(message, None)
        context.backreferences = ("", "og",)
        result = handler(message, context)
        self.assertEqual(result, None)
        self.assertEqual(message, {"baz": "yeah"})

    def test_python(self):
        handler = logshipper.filters.prepare_python("message['a'] = 4")
        message = {}
        context = logshipper.context.Context(message, None)
        result = handler(message, context)
        self.assertEqual(result, None)
        self.assertEqual(message, {"a": 4})

    def test_strptime1(self):
        handler = logshipper.filters.prepare_strptime({
            "field": "foo",
        })

        message = {"foo": "Nov 13 01:22:22 CEST"}
        context = logshipper.context.Context(message, None)
        result = handler(message, context)
        self.assertEqual(result, None)
        date = datetime.datetime(2014, 11, 13, 1, 22, 22, 0)
        self.assertEqual(message['foo'].replace(tzinfo=None), date)

    def test_strptime2(self):
        handler = logshipper.filters.prepare_strptime({
            "format": "%Y %b %d %H:%M:%S",
            "field": "foo",
            "timezone": "Europe/Amsterdam"
        })

        message = {"foo": "2014 Nov 13 01:22:22"}
        context = logshipper.context.Context(message, None)
        result = handler(message, context)
        self.assertEqual(result, None)
        date = datetime.datetime(2014, 11, 13, 1, 22, 22, 0,
                                 tzinfo=pytz.timezone("Europe/Amsterdam"))
        self.assertEqual(
            message,
            {"foo": date})

    def test_timewindow1(self):
        handler = logshipper.filters.prepare_timewindow("1m")

        cest = pytz.timezone("Europe/Amsterdam")
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)

        message = {"timestamp": now}
        context = logshipper.context.Context(message, None)
        result = handler(message, context)
        self.assertEqual(result, None)

        message["timestamp"] = (now.astimezone(cest))
        result = handler(message, context)
        self.assertEqual(result, None)

        message["timestamp"] = (now.astimezone(cest) -
                                datetime.timedelta(minutes=2))
        result = handler(message, context)
        self.assertEqual(result, logshipper.filters.SKIP_STEP)

        message["timestamp"] = (now.astimezone(cest) +
                                datetime.timedelta(minutes=2))
        result = handler(message, context)
        self.assertEqual(result, logshipper.filters.SKIP_STEP)

    def test_timewindow2(self):
        handler = logshipper.filters.prepare_timewindow("1m-3m")

        cest = pytz.timezone("Europe/Amsterdam")
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)

        message = {"timestamp": now}
        context = logshipper.context.Context(message, None)
        result = handler(message, context)
        self.assertEqual(result, None)

        message["timestamp"] = (now.astimezone(cest))
        result = handler(message, context)
        self.assertEqual(result, None)

        message["timestamp"] = (now.astimezone(cest) -
                                datetime.timedelta(minutes=2))
        result = handler(message, context)
        self.assertEqual(result, logshipper.filters.SKIP_STEP)

        message["timestamp"] = (now.astimezone(cest) +
                                datetime.timedelta(minutes=2))
        result = handler(message, context)
        self.assertEqual(result, None)
