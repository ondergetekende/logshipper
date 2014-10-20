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
import glob
import logging
import os

import eventlet
import pkg_resources
import pyinotify
import yaml

import logshipper.context
from logshipper import filters
import logshipper.pyinotify_eventlet_notifier

LOG = logging.getLogger(__name__)

FILTER_FACTORIES = dict(
    (entrypoint.name, entrypoint) for entrypoint in
    pkg_resources.iter_entry_points("logshipper.filters")
)
INPUT_FACTORIES = dict(
    (entrypoint.name, entrypoint) for entrypoint in
    pkg_resources.iter_entry_points("logshipper.inputs")
)

PIPELINE_POOL = eventlet.greenpool.GreenPool()


class Pipeline():
    def __init__(self, manager):
        self.manager = manager
        self.steps = []
        self.inputs = []

    def update(self, pipeline_yaml):
        pipeline = yaml.load(pipeline_yaml)
        self.stop()

        self.steps = [self.prepare_step(step)
                      for step in pipeline.get('steps', [])]

        input_config = pipeline.get('inputs', [])
        if isinstance(input_config, dict):
            input_config = input_config.items()
        else:
            input_config = sum((c.items() for c in input_config), [])
        self.inputs = [self.prepare_input(klass, params)
                       for klass, params in input_config]
        self.start()

    def start(self):
        for input_ in self.inputs:
            input_.start()

    def stop(self):
        for input_ in self.inputs:
            input_.stop()

    def prepare_input(self, klass, params):
        endpoint = INPUT_FACTORIES[klass]
        filter_factory = endpoint.load()
        input_ = filter_factory(**(params or {}))
        input_.set_handler(self.process)
        return input_

    def prepare_step(self, step_config):
        sequence = []
        sequence.extend(
            self.prepare_action(stepname, parameters)
            for (stepname, parameters) in step_config.items())

        sequence.sort(key=lambda action: getattr(action, "phase",
                                                 filters.PHASE_FORWARD))

        return sequence

    def prepare_action(self, name, parameters):
        endpoint = FILTER_FACTORIES[name]
        filter_factory = endpoint.load()
        return filter_factory(parameters)

    def process(self, message):
        message.setdefault('timestamp', datetime.datetime.now())
        PIPELINE_POOL.spawn_n(self.process_with_result, message)

    def process_with_result(self, message):
        context = logshipper.context.Context(message, self.manager)
        for step in self.steps:
            context.next_step()
            for action in step:
                result = action(message, context)
                if result == filters.DROP_MESSAGE:
                    return
                elif result == filters.SKIP_STEP:
                    break

        return message


class PipelineManager():
    def __init__(self, path):
        self.glob = os.path.join(path, "*.yml")
        self.pipelines = {}
        self.recursion_depth = 0

        self.watch_manager = pyinotify.WatchManager()
        flags = (pyinotify.IN_CLOSE_WRITE | pyinotify.IN_DELETE |
                 pyinotify.IN_DELETE_SELF)
        self.watch_manager.add_watch(path, flags, proc_fun=self._inotified)
        self.notifier = logshipper.pyinotify_eventlet_notifier.Notifier(
            self.watch_manager)
        self.thread = None

    def start(self):
        self.should_run = True
        if not self.thread:
            self.thread = eventlet.spawn(self._run)

    def stop(self):
        self.should_run = False
        thread = self.thread
        self.thread = None
        thread.kill()

    def _run(self):
        try:
            for path in glob.iglob(self.glob):
                self.load_pipeline(path)

            while self.should_run:
                self.notifier.loop(lambda _: not self.should_run)
        finally:
            pipelines = self.pipelines.values()
            self.pipelines = {}
            for pipeline in pipelines:
                pipeline.stop()

    def _inotified(self, event):
        name = os.path.basename(event.path).rsplit('.', 1)[0]
        if event.mask == pyinotify.IN_CLOSE_WRITE:
            self.load_pipeline(event.path)
        elif event.mask in (pyinotify.IN_DELETE, pyinotify.IN_DELETE_SELF):
            pipeline = self.pipelines.pop(name, None)
            if pipeline:
                pipeline.stop()

    def load_pipeline(self, path):
        name = os.path.basename(path).rsplit('.', 1)[0]
        try:
            pipeline = self.pipelines[name]
        except KeyError:
            pipeline = self.pipelines[name] = Pipeline(self)

        with open(path, 'r') as yaml_file:
            pipeline.update(yaml_file.read())

    def process_message(self, message, pipeline_name):
        if self.recursion_depth > 10:
            raise Exception("Recursion to deep")

        try:
            self.recursion_depth += 1
            self.pipelines[pipeline_name].process(message)
        finally:
            self.recursion_depth -= 1
