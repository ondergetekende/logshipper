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

import argparse
import logging

import eventlet
import pkg_resources
import yaml

import logshipper.pipeline

ARGS = None
LOG = None


def load_input_configuration(filenames, pipeline_manager):
    input_factories = dict(
        (entrypoint.name, entrypoint) for entrypoint in
        pkg_resources.iter_entry_points("logshipper.inputs")
    )

    input_handlers = []

    for input_config in filenames:
        for input_spec in yaml.load(input_config.read()):
            pipeline_name = input_spec.pop("pipeline", "default")
            pipeline = pipeline_manager.get(pipeline_name)
            if not pipeline:
                raise Exception("Pipeline %s not found" % pipeline_name)

            if len(input_spec) != 1:
                raise Exception("Need exactly one handler")

            handler_name, args = input_spec.items()[0]
            endpoint = input_factories[handler_name]
            input_handler = endpoint.load()(**args)
            input_handler.set_handler(
                lambda m: pipeline_manager.process_message(m, pipeline_name))

            input_handlers.append(input_handler)

    return input_handlers


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
    LOG = logging.getLogger(__name__)

    pipeline_manager = logshipper.pipeline.PipelineManager(
        ARGS.pipeline_path, reload_interval=ARGS.pipeline_reload)

    input_handlers = load_input_configuration(ARGS.input_config,
                                              pipeline_manager)

    if not input_handlers:
        raise Exception("No inputs. Nothing to do")

    for input_handler in input_handlers:
        input_handler.start()

    try:
        while True:
            eventlet.sleep(86400)
    finally:
        for input_handler in input_handlers:
            input_handler.stop()
