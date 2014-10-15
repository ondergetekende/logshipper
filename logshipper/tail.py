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


import glob

import eventlet
import eventlet.green.os as os
import six


class Tail:
    def __init__(self, filename):
        if isinstance(filename, six.string_types):
            filename = [filename]

        self.tails = {}
        self.globs = filename
        self.updater_thread = None

    def start(self):
        if not self.updater_thread:
            self.should_run = True
            self.update_tails(self.globs, do_read_all=False)

    def _updater_loop(self):
        while True:
            eventlet.sleep(60)
            self.update_tails(self.globs, do_read_all=True)

    def update_tails(self, globs, do_read_all):
        inodes = set()
        for file in globs:
            for filename in glob.iglob(file):
                stat = os.lstat(filename)
                inodes.add(stat.st_inode)
                if stat.st_inode not in self.tails:
                    thread = eventlet.spawn_n(self.tail, filename, do_read_all)
                    self.tails[stat.st_inode] = thread

        for vanished in (set(self.tails) - inodes):
            tail = self.tails.pop(vanished)
            tail.kill()

    def stop(self):
        self.should_run = False
        self.update_tails([], do_read_all=False)

    def _tail(self, filename, do_read_all):
        fd = os.open(filename, os.O_RDONLY)
        if not do_read_all:
            os.lseek(fd, 0, os.SEEK_END)

        while True:
            buff = os.read(fd, 1024)
            print(buff)
