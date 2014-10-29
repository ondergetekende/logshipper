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
import fnmatch
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


def prepare_input(klass, params, processfn):
    entrypoint = INPUT_FACTORIES.get(klass)
    if not entrypoint:
        entrypoint = pkg_resources.EntryPoint.parse('X=' + klass)
    filter_factory = entrypoint.load(require=False)
    input_ = filter_factory(**(params or {}))
    input_.set_handler(processfn)
    return input_


def prepare_step(step_config):
    sequence = [prepare_action(stepname, parameters)
                for (stepname, parameters) in step_config.items()]

    sequence.sort(key=lambda action: getattr(action, "phase",
                                             filters.PHASE_FORWARD))

    return sequence


def prepare_action(name, parameters):
    entrypoint = FILTER_FACTORIES.get(name)
    if not entrypoint:
        entrypoint = pkg_resources.EntryPoint.parse('X=' + name)
    filter_factory = entrypoint.load(require=False)
    return filter_factory(parameters)


class Pipeline():
    def __init__(self, manager):
        self.manager = manager
        self.steps = []
        self.inputs = []

    def update(self, pipeline_yaml):
        pipeline = yaml.load(pipeline_yaml)
        self.stop()

        self.steps = [prepare_step(step) for step in pipeline.get('steps', [])]

        input_config = pipeline.get('inputs', [])
        if isinstance(input_config, dict):
            input_config = input_config.items()
        else:
            input_config = sum((c.items() for c in input_config), [])
        self.inputs = [prepare_input(klass, params, self.process_in_eventlet)
                       for klass, params in input_config]
        self.start()

    def start(self):
        for input_ in self.inputs:
            input_.start()

    def stop(self):
        for input_ in self.inputs:
            input_.stop()

    def process_in_eventlet(self, message):
        message.setdefault('timestamp', datetime.datetime.now())
        PIPELINE_POOL.spawn_n(self.process, message)

    def process(self, message):
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
    def __init__(self, globs):
        self.globs = globs
        self.pipelines = {}
        self.recursion_depth = 0

        self.watch_manager = pyinotify.WatchManager()
        flags = (pyinotify.IN_CLOSE_WRITE | pyinotify.IN_DELETE |
                 pyinotify.IN_DELETE_SELF | pyinotify.IN_MOVED_TO)

        for fileglob in self.globs:
            head, tail = os.path.split(fileglob)
            if ('?' in tail) or ('*' in tail):
                print head
                self.watch_manager.add_watch(head, flags,
                                             proc_fun=self._inotified)
            else:
                print fileglob
                self.watch_manager.add_watch(fileglob, flags,
                                             proc_fun=self._inotified)

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
            for fileglob in self.globs:
                for path in glob.iglob(fileglob):
                    self.load_pipeline(path)

            while self.should_run:
                self.notifier.loop(lambda _: not self.should_run)
        finally:
            pipelines = self.pipelines.values()
            self.pipelines = {}
            for pipeline in pipelines:
                pipeline.stop()

    def _inotified(self, event):
        if not any(fnmatch.fnmatch(event.pathname, pattern)
                   for pattern in self.globs):
            return

        name = os.path.splitext(os.path.basename(event.pathname))[0]

        if event.mask & (pyinotify.IN_CLOSE_WRITE | pyinotify.IN_MOVED_TO):
            self.load_pipeline(event.pathname)
        elif event.mask in (pyinotify.IN_DELETE, pyinotify.IN_DELETE_SELF):
            pipeline = self.pipelines.pop(name, None)
            if pipeline:
                LOG.info("Stopping pipeline %s", name)
                pipeline.stop()

    def load_pipeline(self, path):
        name = os.path.basename(path).rsplit('.', 1)[0]
        try:
            pipeline = self.pipelines[name]
            LOG.info("Reloading pipeline %s", name)
        except KeyError:
            pipeline = self.pipelines[name] = Pipeline(self)
            LOG.info("Loading pipeline %s", name)

        with open(path, 'r') as yaml_file:
            pipeline.update(yaml_file.read())

    def process_in_eventlet(self, message, pipeline_name):
        PIPELINE_POOL.spawn_n(self.process, message, pipeline_name)

    def process(self, message, pipeline_name):
        if self.recursion_depth > 10:
            raise Exception("Recursion to deep")

        try:
            self.recursion_depth += 1
            self.pipelines[pipeline_name].process(message)
        finally:
            self.recursion_depth -= 1
