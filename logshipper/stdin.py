import sys

import eventlet.tpool


class Stdin:
    def set_handler(self, handler):
        self.handler = handler
        self.should_run = True
        self.thread = None

    def start(self):
        self.should_run = True
        if not self.thread:
            self.thread = eventlet.spawn(self._run)

    def _run(self):
        while self.should_run:
            line = eventlet.tpool.execute(sys.stdin.readline)
            self.handler({"message": line.rstrip()})

    def stop(self):
        self.should_run = True
        self.thread.kill()
        self.thread = None
