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
