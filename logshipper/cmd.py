import argparse
import logging

import eventlet
import pkg_resources
import yaml


from logshipper import pipeline

ARGS = None
LOG = None


def main():
    global LOG, ARGS
    parser = argparse.ArgumentParser(
        description="Detects resources related to a specific host or resource")

    parser.add_argument('--pipeline-path',
                        default="/etc/logshipper/pipelines/",
                        help='Where to find pipelines (*.yml files)')
    parser.add_argument('--pipeline-reload', type=float, default=60,
                        help='Number of seconds between two pipeline reloads')

    parser.add_argument('--input-config', nargs='+', default=[],
                        type=argparse.FileType('r'))

    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--debug', action='store_true')

    ARGS = parser.parse_args()

    if ARGS.debug:
        log_level = 'DEBUG'
    elif ARGS.verbose:
        log_level = 'INFO'
    else:
        log_level = 'WARNING'

    logging.basicConfig(level=log_level)
    LOG = logging.getLogger()

    pipeline_manager = pipeline.PipelineManager(
        ARGS.pipeline_path, reload_interval=ARGS.pipeline_reload)

    input_factories = dict(
        (entrypoint.name, entrypoint) for entrypoint in
        pkg_resources.iter_entry_points("logshipper.inputs")
    )

    input_handlers = []

    for input_config in ARGS.input_config:
        for input_spec in yaml.load(input_config.read()):
            pipeline_name = input_spec.pop("pipeline", "default")
            if len(input_spec) != 1:
                raise Exception("Need exactly one handler")

            handler_name, args = input_spec.items()[0]
            endpoint = input_factories[handler_name]
            input_handler = endpoint.load()(**args)
            input_handler.set_handler(
                lambda m: pipeline_manager.process_message(m, pipeline_name))

            input_handlers.append(input_handler)

    if not input_handlers:
        raise Exception("No inputs. Nothing to do")

    for input_handler in input_handlers:
        input_handler.start()

    try:
        while True:
            eventlet.sleep(1.0)
    finally:
        for input_handler in input_handlers:
            input_handler.stop()
