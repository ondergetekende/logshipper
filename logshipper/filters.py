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


import re

import six

import logshipper.context

SKIP_STEP = 1
DROP_MESSAGE = 2
TRUTH_VALUES = set(['1', 'true', 'yes', 'on'])

PHASE_MATCH = 10
PHASE_MANIPULATE = 20
PHASE_FORWARD = 30
PHASE_DROP = 40


def prepare_match(parameters):
    """Matches regexes against message fields

    The match action matches a regex to a specific field of a message. If the
    regex doesn't match, the step is skipped. By default the ``message`` field
    will be matched against the regex, but by providing a dictionary of regexes
    you can select a different field, or multiple fields. If you're matching
    against multiple fields, all regexes need to match for the step to be
    executed.

    Named groups in regular expressions get registered as additional fields
    on the message. When matching against a single field, unnamed groups get
    registered as backreferences, which can be used throughout the rest of the
    step.

    Example:


    .. code:: yaml

        match:
            message: (Time):\s+(?P<time>\d+)
        set:
            part: "{1} {time}"

        # In: {"message": "The Time: 1234"}
        # Out: {"message": "The Time: 1234",
        #       "part": "Time 1234",       -- from the set commend
        #       "time": "1234"}            -- from the named group in the regex

    A shorter syntax is available when there's a single match against the
    ``message`` field, the above example is equivalent to:

    .. code:: yaml

        match: (start_time):\s+(?P<time>\d+)
        set:
            part: "{1} {time}"
    """
    if isinstance(parameters, six.string_types):
        parameters = {"message": parameters}

    regexes = [(a, re.compile(b)) for (a, b) in parameters.items()]

    def handle_match(message, context):
        matches = []
        for field_name, regex in regexes:
            field_data = message.get(field_name)
            m = regex.search(field_data)
            if not m:
                return SKIP_STEP
            matches.append(m)

        for m in matches:
            message.update(m.groupdict())

        if len(matches) == 1:
            context.match = matches[0]
            context.backreferences = [matches[0].group(0)]
            context.backreferences.extend(matches[0].groups())
            context.match_field = regexes[0][0]

    handle_match.phase = PHASE_MATCH
    return handle_match


def prepare_replace(parameters):
    template = logshipper.context.prepare_template(parameters)

    def handle_replace(message, context):
        base = message[context.match_field]
        message[context.match_field] = "".join((
            base[:context.match.start()],
            template.interpolate(context),
            base[context.match.end():],
        ))

    handle_replace.phase = PHASE_MANIPULATE
    return handle_replace


def prepare_set(parameters):
    """Sets fields of messages

    The ``set`` action allows you to set fields of messages. You can use it to
    add conditional flags, or combine it with them match action to perform
    message feature extraction.

    .. code:: yaml

        match: Foo=(\d+)
        set:
            foo: "{1}s"
            has_foo: True

        # In: {"message": "Foo=1234"}
        # Out: {"message": "Foo=1234",
        #       "foo": "1234s",
        #       "has_foo": true}
    """
    assert isinstance(parameters, dict)

    parameters = [(key, logshipper.context.prepare_template(value))
                  for (key, value) in parameters.items()]

    def handle_set(message, context):
        for fieldname, template in parameters:
            message[fieldname] = template.interpolate(context)

    handle_set.phase = PHASE_MANIPULATE
    return handle_set


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
    """Sends data to statsd

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

    type = parameters.get('type', 'counter')
    name_template = logshipper.context.prepare_template(parameters['name'])
    val_template = logshipper.context.prepare_template(parameters['value'], 1)
    multiplier = float(parameters.get('multiplier', 1.0))

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
        name = name_template.interpolate(context)
        value = val_template.interpolate(context)

        if delta:
            statsd_client.increment(name, float(value) * multiplier)
        else:
            statsd_client.send(name, float(value) * multiplier)

    return statsd


def prepare_drop(parameters):
    """Drops messages

    Messages that encounter a drop action are dropped from the pipeline. If the
    message has been sent to other pipelines using the ``call`` action, the
    the message will not be dropped from those pipelines.

    Example:

    .. code:: yaml

        match: ^DEBUG
        drop:
    """
    return lambda message, parameters: DROP_MESSAGE


def prepare_stdout(parameters):
    """Sends messages to stdout

    Example:

    .. code:: yaml

        stdout: "{date}: {message}
    """
    format = (parameters if isinstance(parameters, six.string_types)
              else parameters.get("format", "{message}"))
    format = format.rstrip("\n\r") + "\n"
    format_template = logshipper.context.prepare_template(format)
    import sys

    def handle_stdout(message, context):
        message = format_template.interpolate(context)
        sys.stdout.write(message)

    return handle_stdout


def prepare_debug(parameters):
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
    message (includes jumps made by ``call``)

    Example:

    .. code:: yaml

        jump: my_pipeline

        # equivalent to
        call: my_pipeline
        drop:
    """
    pipeline_name = (parameters if isinstance(parameters, six.string_types)
                     else parameters.get("pipeline"))
    if not pipeline_name:
        raise Exception("parameter pipeline required")

    def handle_jump(message, context):
        context.pipeline_manager.process_message(message, pipeline_name)
        return DROP_MESSAGE

    return handle_jump


def prepare_call(parameters):
    """Dispatches messages to a different pipeline.

    Sends the message to a different pipeline. The remainder of this pipeline
    will also be executed. Note that there is a hardcoded limit of 10 pipe
    changes per message (includes jumps made by ``jump``)

    Example:

    .. code:: yaml

        call: my_pipeline
    """
    pipeline_name = (parameters if isinstance(parameters, six.string_types)
                     else parameters.get("pipeline"))
    if not pipeline_name:
        raise Exception("parameter pipeline required")

    def handle_call(message, context):
        context.pipeline_manager.process_message(message.clone(),
                                                 pipeline_name)

    return handle_call
