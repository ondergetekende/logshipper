import re
import time
from gevent.server import StreamServer

SYSLOG_PRIORITIES = ['emergency', 'alert',  'critical',      'error',
                     'warning',   'notice', 'informational', 'debug']
SYSLOG_FACILITIES = ([
    'kern', 'user', 'mail', 'daemon',
    'auth', 'syslog', 'lpr', 'news',
    'uucp', 'cron', 'authpriv', 'ftp',
    'ntp', 'audit', 'alert', 'local', ]
    + ['local%i' % i for i in range(8)]
    + ['unknown%02i' % i for i in range(12)]
)

pri_matcher = re.compile(r'<(\d{1,3})>')  # <134>


def parse_syslog(message):

    priority = pri_matcher.match(message)
    if priority:
        prio = int(priority.group(1))

        return {
            'message': message[priority.end():],
            'time': time.time(),
            'source_transport': 'syslog',
            'facility': SYSLOG_FACILITIES[prio / 8],
            'severity': SYSLOG_PRIORITIES[prio % 8],
        }


class Syslog(StreamServer):
    def __init__(self, bind="127.0.0.1", port=514):
        StreamServer.__init__(self, (bind, port))

    def set_handler(self, handler):
        self.on_message = handler

    def handle(self, socket, address):
        fileobj = socket.makefile('r', 4096)

        for line in fileobj:
            line = line.rstrip('\r\n').decode('utf-8')
            message = parse_syslog(line)
            if message:
                self.on_message(message)
