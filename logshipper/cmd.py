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
import bz2
import gzip
import logging
import os
import sys
import time

import eventlet
eventlet.monkey_patch()

import logshipper.pipeline

ARGS = None
LOG = None


def main():
    global LOG, ARGS
    parser = argparse.ArgumentParser(
        description="Processes log messages and sends them elsewhere")

    parser.add_argument('pipeline', nargs='+',
                        help='Where to find pipelines (*.yml files)')

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
        [os.path.abspath(p) for p in ARGS.pipeline])

    pipeline_manager.start()

    try:
        while True:
            eventlet.sleep(86400)
    finally:
        pipeline_manager.stop()


def ship_file():
    global LOG, ARGS
    parser = argparse.ArgumentParser(
        description="Processes log messages and sends them elsewhere")

    parser.add_argument('--pipeline', required=True)

    parser.add_argument('--pipeline-path', action='append',
                        help='Where to find pipelines (*.yml files)')

    parser.add_argument('file', nargs='+', help='File to ship')

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
        [os.path.abspath(p) for p in ARGS.pipeline_path])

    pipeline_manager.load_pipelines()

    for file in ARGS.file:
        # Peek to detect gzip
        with open(file, 'rb') as f:
            header = f.read(16)

        if header[0:2] == b"\037\213":
            print("Processing gzipped file %s" % file)
            f = gzip.open(file)
        elif header[0:3] == b"\x42\x5A\x68":
            print("Processing bz2'ed file %s" % file)
            f = bz2.BZ2File(file)
        else:
            print("Processing uncompressed file %s" % file)
            f = open(file)

        with f:
            lines = 0
            t0 = time.time()
            treport = 0
            for line in f:
                lines += 1
                line = line.rstrip("\r\n")
                try:
                    pipeline_manager.process({'message': line},
                                             ARGS.pipeline)
                except KeyboardInterrupt:
                    break
                except Exception:
                    print("\n")
                    LOG.exception("Error processing %r", line)
                    continue

                if (time.time() - treport) > 1:
                    rate = lines / (time.time() - t0)
                    sys.stdout.write(
                        "Processing %i lines, %4.1f/s\r" % (lines, rate))
                    treport = time.time()
                sys.stdout.flush()

            print("Processed ")
