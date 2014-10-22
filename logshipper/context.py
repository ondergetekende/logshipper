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


import string

import six


def prepare_template(template):

    if not isinstance(template, six.string_types) or "{" not in template:
        result = lambda args, kwargs: template
        result.interpolate = lambda context: template
        return result

    fmt = string.Formatter()

    namespace = {}
    result = []
    for literal, field_name, format_spec, conversion in fmt.parse(template):

        # output the literal text
        if literal:
            result.append("%r" % literal)

        basic_index = 1
        highest_index = -1
        # if there's a field, output it
        if field_name is not None:
            if "[" in field_name or "." in field_name:
                namespace["fmt"] = fmt
                value_code = "fmt.get_field(%r, args, kwargs)"
            elif field_name.isdigit():
                idx = int(field_name)
                value_code = "args[%s]" % field_name
                highest_index = max(highest_index, idx)
            elif not field_name:
                value_code = "args[%i]" % basic_index
                highest_index = max(highest_index, basic_index)
                basic_index += 1
            else:
                value_code = "kwargs[%r]" % field_name

            if conversion:
                namespace["fmt"] = fmt
                value_code = "fmt.convert_field(%s, %r)" % (value_code,
                                                            conversion)

            if not format_spec:
                result.append("str(%s)" % value_code)
            elif '{' in format_spec:
                namespace["fmt"] = fmt
                result.append("format(%s, fmt.vformat(%r, args, kwargs))" %
                              (format_spec, value_code))
            else:
                result.append("format(%s, %r)\n" % (value_code, format_spec))

    result = ("def template(args, kwargs):\n"
              "  assert len(args) > %i, 'Insufficient backreferences'\n"
              "  return \"\".join([%s])" % (highest_index, ", ".join(result)))

    exec(result, namespace)
    fn = namespace["template"]
    fn.interpolate = lambda context: fn(context.backreferences,
                                        context.message)

    return fn


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
