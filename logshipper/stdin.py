import gevent.monkey
gevent.monkey.patch_sys(stdin=True, stdout=False, stderr=False)
import sys


class Stdin(gevent.Greenlet):
    def set_handler(self, handler):
        self.handler = handler

    def _run(self):
        for line in sys.stdin:
            self.handler({"message": line.rstrip()})

    def stop(self):
        pass
