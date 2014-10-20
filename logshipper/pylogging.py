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


def prepare_logging(parameters):
    """ Use python ``logging`` infrastructure.

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
        The logging level to be used for messages. Chose from ``DEBUG``,
        ``INFO``, ``WARNING``, ``ERROR``, ``CRITICAL`` and ``NOTSET``. Defaults
        to ``INFO``. Most handlers also accept other values.
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

    name_template = parameters.pop('name', 'logshipper')
    level_template = parameters.pop('level', 'INFO')
    pathname_template = parameters.pop('pathname', None)
    lineno_template = parameters.pop('lineno', None)
    func_template = parameters.pop('func', None)
    msg_template = parameters.pop('msg', '{message}')

    configurator = logging.config.DictConfigurator({})

    parameters = configurator.convert(parameters)

    filters = [configurator.configure_filter(f)
               for f in parameters.get('filters', [])]

    formatter = configurator.configure_formatter(
        parameters.get('formatter', {}))

    # Now mangle the parameters to match the dictformat
    parameters['handler']['formatter'] = "formatter"
    parameters['handler']['filters'] = [str(i) for (i, f)
                                        in enumerate(filters)]

    configurator.config['formatters'] = {
        "formatter": formatter,
    }
    configurator.config["filters"] = dict((str(i), f)
                                          for (i, f) in enumerate(filters))

    handler = configurator.configure_handler(parameters['handler'])

    def handle_logging(message, context):
        name = context.interpolate_template(name_template)
        level = context.interpolate_template(level_template)
        pathname = context.interpolate_template(pathname_template)
        func = context.interpolate_template(func_template)
        lineno = context.interpolate_template(lineno_template)
        lineno = int(lineno) if lineno else None

        msg = context.interpolate_template(msg_template)

        record = logging.LogRecord(name, level, pathname, lineno, msg,
                                   context.backreferences[1:],
                                   None, func)

        for key, value in message.items():
            if not hasattr(record, key):
                setattr(record, name, value)

        handler.handle(record)

    return handle_logging
