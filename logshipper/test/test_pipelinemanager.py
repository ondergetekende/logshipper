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
import json
import logging
import os
import shutil
import tempfile
import unittest

import eventlet

import logshipper.input
import logshipper.pipeline


LOG = logging.getLogger(__name__)


class TestInput(logshipper.input.BaseInput):
    testmessage = {'message': u'gen1', 'hostname': None,
                   "timestamp": datetime.datetime.now()}

    def run(self):
        LOG.debug("Emitting %r", self.testmessage)
        self.emit(dict(self.testmessage))

msg_history = []


def pipe_handler(params):
    global msg_history

    def handle(message, context):
        msg_history.append(message)
    return handle


class Tests(unittest.TestCase):
    def setUp(self):
        global msg_history
        msg_history = []
        self.path = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.path)

    def test_load(self):
        pipeline = {
            "inputs": {
                'test_pipelinemanager:TestInput': {}
            },
            "steps": [
                {'test_pipelinemanager:pipe_handler': {}}
            ]
        }
        with open(self.path + "/test1.yml", 'w') as f:
            json.dump(pipeline, f)

        mgr = logshipper.pipeline.PipelineManager([self.path + "/*.yml"])
        mgr.load_pipelines()

        eventlet.sleep()

        self.assertEqual(msg_history, [])
        mgr.process({'message': "Test"}, 'test1')
        self.assertEqual(msg_history, [{'message': "Test"}])

    def test_late_load(self):
        pipeline = {
            "inputs": {
                'test_pipelinemanager:TestInput': {}
            },
            "steps": [
                {'test_pipelinemanager:pipe_handler': {}}
            ]
        }

        mgr = logshipper.pipeline.PipelineManager([self.path + "/*.yml"])

        mgr.start()
        eventlet.sleep(0.1)
        with open(self.path + "/test1.yml", 'w') as f:
            json.dump(pipeline, f)
        LOG.debug("Just modified")
        eventlet.sleep(0.1)
        LOG.debug("Just modified (postsleep)")
        mgr.stop()

        self.assertEqual(msg_history, [TestInput.testmessage])

    def test_modify(self):
        pipeline = {
            "inputs": {
                'test_pipelinemanager:TestInput': {}
            },
            "steps": [
                {'test_pipelinemanager:pipe_handler': {}}
            ]
        }
        with open(self.path + "/test1.yml", 'w') as f:
            json.dump(pipeline, f)

        mgr = logshipper.pipeline.PipelineManager([self.path + "/*.yml"])

        mgr.start()
        eventlet.sleep(0.01)
        with open(self.path + "/test1.yml", 'w') as f:
            json.dump(pipeline, f)

        eventlet.sleep(0.01)
        mgr.stop()

        self.assertEqual(msg_history, [TestInput.testmessage,
                                       TestInput.testmessage])

    def test_delete(self):
        pipeline = {
            "inputs": {
                'test_pipelinemanager:TestInput': {}
            },
            "steps": [
                {'test_pipelinemanager:pipe_handler': {}}
            ]
        }
        with open(self.path + "/test1.yml", 'w') as f:
            json.dump(pipeline, f)

        mgr = logshipper.pipeline.PipelineManager([self.path + "/*.yml"])

        mgr.start()
        eventlet.sleep(0.01)
        os.unlink(self.path + "/test1.yml")
        eventlet.sleep(0.01)

        with self.assertRaises(Exception):  # noqa
            mgr.process({}, 'test1')

        mgr.stop()
