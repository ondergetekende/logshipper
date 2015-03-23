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


class Tests(unittest.TestCase):
    def test_str(self):
        r = logshipper.context.prepare_template("{1}{foo!s:>4}")
        value = r(["f", "F"], {"foo": '123'})
        self.assertEqual(value, "F 123")

    def test_str_arrayindex(self):
        r = logshipper.context.prepare_template("{foo[0]}")
        value = r([], {"foo": ['123']})
        self.assertEqual(value, "123")

    def test_str_dictindex(self):
        r = logshipper.context.prepare_template("{foo[m]}")
        value = r([], {"foo": {"m": '123'}})
        self.assertEqual(value, "123")

    def test_str_selfref(self):
        r = logshipper.context.prepare_template("{0:>{1}}")
        value = r(["r", "4"], {})
        self.assertEqual(value, "   r")

    def test_empty(self):
        r = logshipper.context.prepare_template("")
        value = r([], {})
        self.assertEqual(value, "")

    def test_dict(self):
        r = logshipper.context.prepare_template({"foo": "{1}{foo!s:>4}"})
        value = r(["f", "F"], {"foo": '123'})
        self.assertEqual(value, {"foo": "F 123"})

    def test_list(self):
        r = logshipper.context.prepare_template([1, "{1}{foo!s:>4}"])
        value = r(["f", "F"], {"foo": '123'})
        self.assertEqual(value, [1, "F 123"])

    def test_unknowntype(self):
        class Foo(object):
            pass

        with self.assertRaises(TypeError):
            logshipper.context.prepare_template(Foo())
