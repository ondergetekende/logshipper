import eventlet
import re
import time


SYSLOG_PRIORITIES = ['emergency', 'alert', 'critical', 'error', 'warning',
                     'notice', 'informational', 'debug']
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


class Syslog:
    def __init__(self, bind="127.0.0.1", port=514):
        self.bind = bind
        self.port = port
        self.server = None
        self.should_run = False

    def start(self):
        if not self.server:
            self.should_run = True
            self.server = eventlet.listen((bind, port))
            eventlet.spawn(eventlet.serve(self.server, self.handle))

    def stop(self):
        self.should_run = False
        self.server.close()
        self.server = None

    def accept_loop(self):

        while self.should_run:
            new_sock, address = self.server.accept()
            self.pool.spawn_n(handle, new_sock.makefile('r', 4096))

    def handle(self, socket, address):
        fileobj = socket.makefile('r', 4096)

        for line in fileobj:
            line = line.rstrip('\r\n').decode('utf-8')
            message = parse_syslog(line)
            if message:
                self.on_message(message)
