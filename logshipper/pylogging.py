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

import logging.config
import time

import logshipper.context


def prepare_logging(parameters):
    """Use python ``logging`` infrastructure.

    ``logging`` allows you to use regular python logging handlers. The
    congfiguration tries to mimick the python logging configuration as much as
    possible.

    Accepts the following parameters:

    ``handler``
        Construction details for the handler. The filters and formatter
        paramters will be filled automatically from the parameters defined
        below.
    ``formatter``
        Defines the formatter to be used.
    ``filters``
        Defines filters to be used. This is a list of filters, all of which
        are passed (in order) to the handler.
    ``name``
        The logging name to be used for messages. Defaults to ``logshipper``.
    ``level``
        The numeric logging level to be used for messages. See documentation of
        python's ``logging`` module to see which numbers map to what.
    ``pathname``
        Optional. The filename in which the log message was generated.
    ``lineno``
        Optional. The line number on which the log message was generated. If
        set needs to produce a numeric string.
    ``func``
        Optional. The name of the function in which the log message was
        generated.
    ``msg``
        The message format. Defaults to ``{message}``

    Example:

    .. code:: yaml

        - logging:
            handler:
              class: logging.StreamHandler
              stream: ext://sys.stdout
            formatter:
              (): logging.Formatter
              format: '%(asctime)s %(levelname)-8s %(name)-15s %(message)s'
              datefmt: '%Y-%m-%d %H:%M:%S'
            filters:
            - (): logging.Filter
              name: foo
            level: WARNING

    """

    assert isinstance(parameters, dict)

    name = logshipper.context.prepare_template(
        parameters.pop('name', 'logshipper'))

    level = logshipper.context.prepare_template(
        parameters.pop('level', logging.INFO))

    pathname = logshipper.context.prepare_template(
        parameters.pop('pathname', None))

    lineno = logshipper.context.prepare_template(
        parameters.pop('lineno', None))

    func = logshipper.context.prepare_template(parameters.pop('func', None))
    msg = logshipper.context.prepare_template(
        parameters.pop('msg', '{message}'))

    configurator = logging.config.DictConfigurator({})

    parameters = configurator.convert(parameters)

    filters = [configurator.configure_filter(f)
               for f in parameters.get('filters', [])]

    formatter = configurator.configure_formatter(
        parameters.get('formatter', {}))

    # Now mangle the parameters to match the dictformat
    parameters['handler']['formatter'] = "formatter"
    parameters['handler']['filters'] = [str(idx) for (idx, _)
                                        in enumerate(filters)]

    configurator.config['formatters'] = {
        "formatter": formatter,
    }
    configurator.config["filters"] = dict((str(idx), filter_)
                                          for (idx, filter_)
                                          in enumerate(filters))

    handler = configurator.configure_handler(parameters['handler'])

    def handle_logging(message, context):
        line = lineno.interpolate(context)
        line = int(line) if line else None

        record = logging.LogRecord(
            name=name.interpolate(context),
            level=int(level.interpolate(context)),
            pathname=pathname.interpolate(context),
            lineno=line,
            msg=msg.interpolate(context),
            args=context.backreferences[1:],
            exc_info=None,
            func=func)

        record.created = time.mktime(message.pop('timestamp').timetuple())

        for key, value in message.items():
            if not hasattr(record, key):
                setattr(record, key, value)

        handler.handle(record)

    return handle_logging
