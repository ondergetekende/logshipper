import logging
import re
import time
import yaml
import yaml.constructor
import os

TRUTH_VALUES = set(['1', 'true', 'yes', 'on'])
SKIP_STEP = 1
DROP_MESSAGE = 2
LOG = logging.getLogger(__name__)


try:
    # included in standard lib from Python 2.7
    from collections import OrderedDict
except ImportError:
    # try importing the backported drop-in replacement
    # it's available on PyPI
    from ordereddict import OrderedDict


def interpolate_template(template, context):
    return template.format(*context.get('pargs', []),
                           **context.get('variables', {}))


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
    def __init__(self, pipeline_yaml):
        pipeline = yaml.load()

        self.steps = [self.prepare_step(step) for step in pipeline]

    def prepare_step(self, step_config):
        sequence = []
        for stepname in ['match']:
            parameters = step_config.pop(stepname, None)
            prepare_func = getattr(self, 'prepare_' + stepname)
            sequence.add(prepare_func(parameters))

        for stepname, parameters in step_config.items():
            prepare_func = getattr(self, 'prepare_' + stepname)
            sequence.add(prepare_func(parameters))

        return sequence

    def prepare_match(self, parameters):
        if isinstance(parameters, basestring):
            parameters = {"msg": parameters}

        regexes = [(a, re.compile(b)) for (a, b) in parameters.items()]

        def handle_match(message, context):
            matches = []
            for field_name, regex in regexes:
                field_data = message.get(field_name)
                m = regex.search(field_data)
                if not m:
                    return SKIP_STEP
                matches.append()

            for m in matches:
                context['variables'].update(m.groupdict())

            if len(matches) == 1:
                context['pargs'] = matches[0].groups()
                context['match_field'] = regexes[0][0]

        return handle_match

    def prepare_set(self, parameters):
        assert isinstance(parameters, dict)

        parameters = parameters.items()

        def handle_set(message, context):
            for fieldname, template in parameters:
                message[fieldname] = interpolate_template(template, context)

        return handle_set

    def prepare_rabbitmq(self, parameters):
        import pika
        import json

        conn_parameters = pika.connection.ConnectionParameters(
            credentials=pika.PlainCredentials(
                parameters.get('username', 'guest'),
                parameters.get('password', 'guest')),
            host=parameters.get('host', '127.0.0.1'),
            port=int(parameters.get('port', 5672))
        )

        connection = pika.adapters.BlockingConnection(conn_parameters)
        channel = connection.channel()

        exchange = parameters.get('exchange', "logshipper")
        queue = parameters.get('queue', "logshipper")
        key = parameters.get('key', "logshipper")

        channel.queue_declare(queue=queue, durable=False,
                              arguments={'x-ha-policy': 'all'})

        channel.exchange_declare(exchange=exchange, durable=False)
        channel.queue_bind(exchange=exchange, queue=queue, routing_key=key)

        def handle_rabbitmq(message, context):
            channel.basic_publish(exchange=exchange, routing_key=key,
                                  body=json.dumps(message),
                                  properties=pika.BasicProperties(
                                      content_type='text/json',
                                      delivery_mode=1
                                  ))
        return handle_rabbitmq

    def prepare_statsd(self, parameters):
        import statsd

        statsd_connection = statsd.Connection(
            host=parameters.get('host', '127.0.0.1'),
            port=int(parameters.get('port', 8125)),
            sample_rate=float(parameters.get('sample_rate', 1.0)),
        )

        type = parameters.get('type', 'counter')
        name_template = parameters['name']
        name_is_template = '{' in name_template
        multiplier = float(parameters.get('multiplier', 1.0))
        val_template = parameters.get('value', "1")
        if isinstance(val_template, basestring) and '{' in val_template:
            val_is_template = True
        else:
            val_is_template = False
            val_template = float(val_template)

        if type == 'counter':
            statsd_client = statsd.Counter(parameters.get('prefix'),
                                           statsd_connection)
            delta = True
        elif type == 'gauge':
            statsd_client = statsd.Gauge(parameters.get('prefix'),
                                         statsd_connection)
            delta = str(parameters.get("delta", False)).lower() in TRUTH_VALUES
        elif type == 'timer':
            statsd_client = statsd.Timer(parameters.get('prefix'),
                                         statsd_connection)
            delta = False
        else:
            raise Exception()

        def handle_statsd(message, context):
            if name_is_template:
                name = interpolate_template(name_template, context)
            else:
                name = name_template

            if val_is_template:
                value = float(interpolate_template(val_template, context))
            else:
                value = val_template

            if delta:
                statsd_client.increment(name, float(value) * multiplier)
            else:
                statsd_client.send(name, float(value) * multiplier)

        return statsd

    def prepare_drop(self, parameters):
        if str(parameters).lower() in TRUTH_VALUES:
            return lambda message, parameters: DROP_MESSAGE

    def process(self, message):
        variables = {}
        for step in self.steps:
            context = {'variables': variables}
            for substep in step:
                if substep:
                    result = substep(message, context)
                    if result == DROP_MESSAGE:
                        return None
                    elif result == SKIP_STEP:
                        break

        return message


class PipelineManager():
    def __init__(self, path, reload_interval=60):
        self.path = path
        self.pipelines = {}
        self.reload_interval = reload_interval

    def get(self, name="default"):
        try:
            pipeline = self.pipelines[name]
        except IndexError:
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
                    pipeline['pipeline'] = Pipeline(yaml_file.read())
                pipeline['mtime'] = s.st_mtime

            pipeline['reload_time'] = time.time() + self.reload_interval

        return pipeline['pipeline']

    def process_message(self, message, pipeline_name):
        pipeline = self.get(pipeline_name)
        pipeline.process(message)

