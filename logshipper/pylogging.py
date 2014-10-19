import logging.config


def prepare_logging(parameters):
    assert isinstance(parameters, dict)

    configurator = logging.config.DictConfigurator({})

    parameters = configurator.convert(parameters)

    filters = [configurator.configure_filter(f)
               for f in parameters.get('filters', [])]

    formatter = configurator.configure_formatter(
        parameters.get('formatter', {}))

    # Now mangle the parameters to match the dictformat
    parameters['formatter'] = "formatter"
    parameters['filters'] = [str(i) for (i, f) in enumerate(filters)]

    configurator.config['formatters'] = {
        "formatter": formatter,
    }
    configurator.config["filters"] = dict((str(i), f)
                                          for (i, f) in enumerate(filters))

    handler = configurator.configure_handler(parameters)

    name_template = parameters.get('name', 'logshipper')
    level_template = parameters.get('level', 'INFO')
    pathname_template = parameters.get('pathname')
    lineno_template = parameters.get('lineno')
    func_template = parameters.get('func')
    msg_template = parameters.get('msg', '{message}')

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
        handler.handle(record)

    return handle_logging
