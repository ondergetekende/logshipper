import logging
import os
import pkg_resources
import time
import yaml

from logshipper import filters
from logshipper.context import Context

LOG = logging.getLogger(__name__)


class Pipeline():
    def __init__(self, pipeline_yaml, manager):
        self.manager = manager
        pipeline = yaml.load(pipeline_yaml)
        self.filter_factories = dict(
            (entrypoint.name, entrypoint) for entrypoint in
            pkg_resources.iter_entry_points("logshipper.filters")
        )

        self.steps = [self.prepare_step(step) for step in pipeline]

    def prepare_step(self, step_config):
        sequence = []
        sequence.extend(
            self.prepare_action(stepname, parameters)
            for (stepname, parameters) in step_config.items())

        sequence.sort(key=lambda action: getattr(action, "phase",
                                                 filters.PHASE_FORWARD))

        return sequence

    def prepare_action(self, name, parameters):
        endpoint = self.filter_factories[name]
        filter_factory = endpoint.load()
        return filter_factory(parameters)

    def process(self, message):
        context = Context(self.manager)
        for step in self.steps:
            context.next_step()
            for substep in step:
                result = substep(message, context)
                if result == filters.DROP_MESSAGE:
                    return None
                elif result == filters.SKIP_STEP:
                    break

        return message


class PipelineManager():
    def __init__(self, path, reload_interval=60):
        self.path = path
        self.pipelines = {}
        self.reload_interval = reload_interval
        self.recursion_depth = 0

    def get(self, name="default"):
        try:
            pipeline = self.pipelines[name]
        except KeyError:
            pipeline = self.pipelines[name] = {
                "path": os.path.join(self.path, name + ".yml"),
                "reload_time": 0,
                "mtime": 0,
                "pipeline": None,
            }

        if pipeline['reload_time'] < time.time():
            try:
                s = os.stat(pipeline['path'])
            except OSError:
                # Does not exist
                LOG.warning("Requested pipeline %s does not exist",
                            pipeline['path'])
                return None

            if s.st_mtime > pipeline['mtime']:
                with open(pipeline['path'], 'r') as yaml_file:
                    pipeline['pipeline'] = Pipeline(yaml_file.read(), self)
                pipeline['mtime'] = s.st_mtime

            pipeline['reload_time'] = time.time() + self.reload_interval

        return pipeline['pipeline']

    def process_message(self, message, pipeline_name):
        if self.recursion_depth > 10:
            raise Exception("Recursion to deep")

        try:
            self.recursion_depth += 1
            pipeline = self.get(pipeline_name)
            pipeline.process(message)
        finally:
            self.recursion_depth -= 1
