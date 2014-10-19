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


class Context():
    __slots__ = ['pipeline_manager', 'message', 'match', 'match_field',
                 'backreferences']

    def __init__(self, message, pipeline_manager):
        self.pipeline_manager = pipeline_manager
        self.message = message
        self.match = None
        self.match_field = None
        self.backreferences = []

    def interpolate_template(self, template):
        if not template:
            return template

        return template.format(*self.backreferences, **self.message)

    def next_step(self):
        self.match = None
        self.match_field = None
        self.backreferences = []
