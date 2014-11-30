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

import eventlet

import logshipper.input
import logshipper.pipeline


class TestInput(logshipper.input.BaseInput):
    testmessage = {"generated": 1, 'message': u'gen1', 'hostname': None,
                   "timestamp": datetime.datetime.now()}

    def run(self):
        self.emit(dict(self.testmessage))


def prepare_handler1(params):
    c = []

    def h_counter(message, context):
        c.append(dict(message))
        message['handler1'] = True
        message['history'] = list(c)

    h_counter.phase = logshipper.filters.PHASE_MANIPULATE
    return h_counter


def prepare_handler2(params):
    l = lambda message, context: message.update({'handler2': True})
    l.phase = logshipper.filters.PHASE_MANIPULATE + 1
    return l


def prepare_skip(params):
    x = lambda m, c: logshipper.filters.SKIP_STEP
    x.phase = logshipper.filters.PHASE_MATCH
    return x


def prepare_drop(params):
    x = lambda m, c: logshipper.filters.DROP_MESSAGE
    x.phase = logshipper.filters.PHASE_DROP
    return x


class Tests(unittest.TestCase):

    def test_prepare_input(self):
        result = []

        def handler(message):
            self.assertEqual(message, TestInput.testmessage)
            result.append(1)

        input_ = logshipper.pipeline.prepare_input(__name__ + ":TestInput", {},
                                                   handler)
        self.assertIsInstance(input_, TestInput)

        self.assertEqual(result, [])
        input_.start()
        eventlet.sleep(.01)
        self.assertEqual(result, [1])
        input_.stop()

    def test_prepare_filter(self):
        handler = logshipper.pipeline.prepare_step({
            __name__ + ":prepare_handler1": {},
            __name__ + ":prepare_handler2": {},
        })

        self.assertNotEqual(handler, None)
        self.assertEqual(len(handler), 2)
        message = {}
        handler[0](message, None)
        self.assertTrue(message['handler1'])
        handler[1](message, None)
        self.assertTrue(message['handler2'])

    def test_pipeline(self):
        pipeline = logshipper.pipeline.Pipeline(None)

        pipeline.update(
            "inputs:\n"
            "  'test_pipeline:TestInput': {}\n"
            "steps:\n"
            "- 'test_pipeline:prepare_handler1': None\n"
            "- 'test_pipeline:prepare_handler2': None\n"
        )

        self.assertEqual(len(pipeline.inputs), 1)
        self.assertEqual(len(pipeline.steps), 2)

        pipeline.start()
        eventlet.sleep(.03)

        m = pipeline.process({'timestamp': None, 'hostname': None,
                              'message': u''})

        pipeline.stop()

        self.assertEqual(len(m['history']), 2)
        self.assertIn('generated', m['history'][0])
        self.assertNotIn('generated', m['history'][1])

    def test_pipeline_drop(self):
        pipeline = logshipper.pipeline.Pipeline(None)

        pipeline.update(
            "inputs:\n"
            "  'test_pipeline:TestInput': {}\n"
            "steps:\n"
            "- 'test_pipeline:prepare_drop': None\n"
            "- 'test_pipeline:prepare_handler1': None\n"
        )

        self.assertEqual(len(pipeline.inputs), 1)
        self.assertEqual(len(pipeline.steps), 2)

        pipeline.start()
        eventlet.sleep(.03)

        m = pipeline.process({'timestamp': None, 'hostname': None,
                              'message': u''})

        pipeline.stop()

        self.assertIsNone(m)

    def test_pipeline_skip(self):
        pipeline = logshipper.pipeline.Pipeline(None)

        pipeline.update(
            "inputs:\n"
            "  'test_pipeline:TestInput': {}\n"
            "steps:\n"
            "- 'test_pipeline:prepare_skip': None\n"
            "  'test_pipeline:prepare_handler1': None\n"
            "- 'test_pipeline:prepare_handler2': None\n"
        )

        self.assertEqual(len(pipeline.inputs), 1)
        self.assertEqual(len(pipeline.steps), 2)
        self.assertEqual(pipeline.steps[0][0].phase,
                         logshipper.filters.PHASE_MATCH)
        self.assertEqual(pipeline.steps[0][1].phase,
                         logshipper.filters.PHASE_MANIPULATE)

        pipeline.start()
        eventlet.sleep(.03)

        m = pipeline.process({'timestamp': None, 'hostname': None,
                              'message': u''})

        pipeline.stop()

        self.assertNotIn('handler1', m)
        self.assertIn('handler2', m)
