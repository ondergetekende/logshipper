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

import six

import logshipper.context
from logshipper import filters


def prepare_rabbitmq(parameters):
    """Sends messages to RabbitMQ

    username
        RabbitMQ username, defaults to ``guest``
    password
        RabbitMQ password, defaults to ``guest``
    host
        RabbitMQ hostname, defaults to ``127.0.0.1``
    port
        RabbitMQ port, defaults to ``5672``
    exchange
        Defaults to ``logshipper``
    queue
        Defaults to ``logshipper``
    key
        The routing key. Defaults to ``logshipper``
    """
    import json  # noqa
    import pika  # noqa

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


def prepare_statsd(parameters):
    r"""Sends data to statsd

    Sends a value to statsd.

    host
        defaults to ``127.0.0.1``
    port
        defaults to ``8125``
    sample_rate
        defaults to ``1.0``
    type
        Accepted values are ``counter``, ``gauge`` and ``timer``, defaults to
        ``counter``
    value
        The value to send. Defaults to ``1.0``
    multiplier
        The amount to multiply the value by. Defaults to ``1.0``
    delta
        boolean, only used for gauge, whether to send differential values or
        absolute values. Defaults to ``False``
    prefix
        the prefix for the stat name backreferences not allowed
    name
        the name for the stat, backreferences allowed (required)


    Example:

    .. code:: yaml

        match: Duration: (\d+.\d+)s
        statsd:
            type: timer
            value: {1}
            prefix: appserver.request
            name: duration
        statsd:
            prefix: appserver.request
            name: count
    """

    import statsd  # noqa

    statsd_connection = statsd.Connection(
        host=parameters.get('host', '127.0.0.1'),
        port=int(parameters.get('port', 8125)),
        sample_rate=float(parameters.get('sample_rate', 1.0)),
    )

    meter_type = parameters.get('type', 'counter')
    name_template = logshipper.context.prepare_template(parameters['name'])
    val_template = logshipper.context.prepare_template(
        parameters.get('value', 1))
    multiplier = float(parameters.get('multiplier', 1.0))

    if meter_type == 'counter':
        statsd_client = statsd.Counter(parameters.get('prefix'),
                                       statsd_connection)
        delta = True
    elif meter_type == 'gauge':
        statsd_client = statsd.Gauge(parameters.get('prefix'),
                                     statsd_connection)
        delta_str = str(parameters.get("delta", False)).lower()
        delta = delta_str in filters.TRUTH_VALUES
    elif meter_type == 'timer':
        statsd_client = statsd.Timer(parameters.get('prefix'),
                                     statsd_connection)
        delta = False
    else:
        raise ValueError("Unknown meter type, should be one of counter, "
                         "gauge or timer")  # pragma: nocover

    def handle_statsd(message, context):
        name = name_template.interpolate(context)
        value = val_template.interpolate(context)

        if delta:
            statsd_client.increment(name, float(value) * multiplier)
        else:
            statsd_client.send(name, float(value) * multiplier)

    return handle_statsd


def prepare_stdout(parameters):
    """Sends messages to stdout

    Example:

    .. code:: yaml

        stdout: "{date}: {message}"
    """
    line_format = (parameters if isinstance(parameters, six.string_types)
                   else parameters.get("format", "{message}"))
    line_format = line_format.rstrip("\n\r") + "\n"
    format_template = logshipper.context.prepare_template(line_format)
    import sys

    def handle_stdout(message, context):
        message = format_template.interpolate(context)
        sys.stdout.write(message)

    return handle_stdout


def prepare_debug(parameters):  # pragma : nocover
    """Sends a detailed representation of messages to stdout

    Example:

    .. code:: yaml

        debug:
    """

    import sys  # noqa

    def handle_debug(message, context):
        sys.stdout.write(repr(message))
        sys.stdout.write("\n")

    return handle_debug


def prepare_jump(parameters):
    """Jumps to a different pipeline.

    Sends the message to a different pipeline. The remainder of this pipeline
    is not executed. Note that there is a hardcoded limit of 10 jumps per
    message (includes jumps made by ``call`` and ``jump``)

    Example:

    .. code:: yaml

        jump: my_pipeline
    """
    pipeline_name = (parameters if isinstance(parameters, six.string_types)
                     else parameters.get("pipeline"))
    if not pipeline_name:
        raise ValueError("parameter pipeline required")

    def handle_jump(message, context):
        context.pipeline_manager.process(message, pipeline_name)
        return filters.DROP_MESSAGE

    return handle_jump


def prepare_fork(parameters):
    """Dispatches messages to a different pipeline.

    Sends a copy of the message to a different pipeline. The remainder of this
    pipeline will also be executed. Note that there is a hardcoded limit of 10
    pipeline changes per message (includes jumps made by ``jump`` and ``call``)

    Example:

    .. code:: yaml

        fork: my_pipeline
    """
    pipeline_name = (parameters if isinstance(parameters, six.string_types)
                     else parameters.get("pipeline"))
    if not pipeline_name:
        raise ValueError("parameter pipeline required")

    def handle_fork(message, context):
        context.pipeline_manager.process_in_eventlet(dict(message),
                                                     pipeline_name)

    return handle_fork


def prepare_call(parameters):
    """Dispatches messages to a different pipeline.

    Sends the message through another pipeline. Any changes to the
    message will be visible in the remainder of this pipeline. Note that there
    is a hardcoded limit of 10 pipeline changes per message (includes jumps
    made by ``jump`` and ``fork``)

    Example:

    .. code:: yaml

        call: my_pipeline
    """
    pipeline_name = (parameters if isinstance(parameters, six.string_types)
                     else parameters.get("pipeline"))
    if not pipeline_name:
        raise ValueError("parameter pipeline required")

    def handle_call(message, context):
        context.pipeline_manager.process(message, pipeline_name)

    return handle_call
