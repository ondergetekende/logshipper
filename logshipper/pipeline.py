import logging
import os
import pkg_resources
import time
import yaml
import yaml.constructor

from logshipper import filters
from logshipper.context import Context

LOG = logging.getLogger(__name__)

try:
    # included in standard lib from Python 2.7
    from collections import OrderedDict
except ImportError:
    # try importing the backported drop-in replacement
    # it's available on PyPI
    from ordereddict import OrderedDict


class OrderedDictYAMLLoader(yaml.Loader):
    """
    A YAML loader that loads mappings into ordered dictionaries.
    """

    def __init__(self, *args, **kwargs):
        yaml.Loader.__init__(self, *args, **kwargs)

        self.add_constructor(u'tag:yaml.org,2002:map',
                             type(self).construct_yaml_map)
        self.add_constructor(u'tag:yaml.org,2002:omap',
                             type(self).construct_yaml_map)

    def construct_yaml_map(self, node):
        data = OrderedDict()
        yield data
        value = self.construct_mapping(node)
        data.update(value)

    def construct_mapping(self, node, deep=False):
        if isinstance(node, yaml.MappingNode):
            self.flatten_mapping(node)
        else:
            raise yaml.constructor.ConstructorError(
                None, None,
                'expected a mapping node, but found %s' % node.id,
                node.start_mark)

        mapping = OrderedDict()
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                hash(key)
            except TypeError, exc:
                raise yaml.constructor.ConstructorError(
                    'while constructing a mapping',
                    node.start_mark, 'found unacceptable key (%s)' % exc,
                    key_node.start_mark)
            value = self.construct_object(value_node, deep=deep)
            mapping[key] = value
        return mapping


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
        for stepname in ['match']:
            if stepname in step_config:
                parameters = step_config.pop(stepname, None)
                sequence.append(self.prepare_action(stepname, parameters))

        sequence.extend(
            self.prepare_action(stepname, parameters)
            for (stepname, parameters) in step_config.items())

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
