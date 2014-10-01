import gevent
import gevent.wsgi
import logging
import argparse

from logshipper.pipeline import PipelineManager
import logshipper.syslog

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
    parser.add_argument('--syslog-port', type=int, default=None,
                        help='The port number to listen to for syslog (TCP)')
    parser.add_argument('--syslog-bind', default='127.0.0.1',
                        help='The IP to bind for syslog (TCP)')

    parser.add_argument('--syslog-pipeline', default='default',
                        help='Name of the pipeline to use for syslog')

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

    pipeline_manager = PipelineManager(ARGS.pipeline_path)

    services = []

    if ARGS.syslog_port:
        syslog = logshipper.syslog.SyslogServer(
            ('127.0.0.1', 3514),  # TODO: configurize this
            lambda m: pipeline_manager.process_message(m, ARGS.syslog_pipeline)
        )
        syslog.start()
        services.append(syslog)

    stop_event = gevent.event.Event()

    try:
        stop_event.wait()
    finally:
        # The wait failed, usually indicating an interruption, e.g. ctrl-c
        stop_event.set()
        for service in services:
            service.stop()
