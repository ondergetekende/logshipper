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

SKIP_STEP = 1
DROP_MESSAGE = 2
TRUTH_VALUES = set(['1', 'true', 'yes', 'on'])

PHASE_MATCH = 10
PHASE_MANIPULATE = 20
PHASE_FORWARD = 30
PHASE_DROP = 40


def prepare_match(parameters):
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
            context.variables.update(m.groupdict())

        if len(matches) == 1:
            context.backreferences = [matches[0].group(0)]
            context.backreferences.extend(matches[0].groups())
            context.match_field = regexes[0][0]

    handle_match.phase = PHASE_MATCH
    return handle_match


def prepare_set(parameters):
    assert isinstance(parameters, dict)

    parameters = parameters.items()

    def handle_set(message, context):
        for fieldname, template in parameters:
            message[fieldname] = context.interpolate_template(template)

    handle_set.phase = PHASE_MANIPULATE
    return handle_set


def prepare_rabbitmq(parameters):
    import json

    import pika

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
    if isinstance(val_template, six.string_types) and '{' in val_template:
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
            name = context.interpolate_template(name_template)
        else:
            name = name_template

        if val_is_template:
            value = float(context.interpolate_template(val_template))
        else:
            value = val_template

        if delta:
            statsd_client.increment(name, float(value) * multiplier)
        else:
            statsd_client.send(name, float(value) * multiplier)

    return statsd


def prepare_drop(parameters):
    return lambda message, parameters: DROP_MESSAGE


def prepare_stdout(parameters):
    format = (parameters if isinstance(parameters, six.string_types)
              else parameters.get("format", "{message}"))
    format = format.rstrip("\n\r") + "\n"
    import sys

    def handle_stdout(message, context):
        message = context.interpolate_template(format)
        sys.stdout.write(message)

    return handle_stdout


def prepare_debug(parameters):
    import sys

    def handle_debug(message, context):
        sys.stdout.write(repr(message))
        sys.stdout.write("\n")

    return handle_debug


def prepare_jump(parameters):
    pipeline_name = (parameters if isinstance(parameters, six.string_types)
                     else parameters.get("parameters"))
    if not pipeline_name:
        raise Exception("parameter pipeline required")

    def handle_jump(message, context):
        context.pipeline_manager.process_message(message, pipeline_name)
        return DROP_MESSAGE

    return handle_jump


def prepare_call(parameters):
    pipeline_name = (parameters if isinstance(parameters, six.string_types)
                     else parameters.get("parameters"))
    if not pipeline_name:
        raise Exception("parameter pipeline required")

    def handle_call(message, context):
        context.pipeline_manager.process_message(message.clone(),
                                                 pipeline_name)

    return handle_call
