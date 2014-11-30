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


def _template_code(template):
    if (template in (True, False, None) or
            isinstance(template, six.integer_types) or
            isinstance(template, float)):
        return {}, repr(template)

    if isinstance(template, six.string_types):
        return _template_code_string(template)

    if isinstance(template, list):
        result = ["["]
        namespace = {}

        for item in template:
            ns, code = _template_code(item)
            result.append("%s," % code)
            namespace.update(ns)

        result.append("]")
        return namespace, "".join(result)

    if isinstance(template, dict):
        result = ["{"]
        namespace = {}

        for key, value in template.items():
            ns, value_code = _template_code(value)
            result.append("%r:%s," % (key, value_code))
            namespace.update(ns)

        result.append("}")
        return namespace, "".join(result)

    raise TypeError("Unsupported type for templating")


def _template_code_string(template):
    fmt = string.Formatter()

    namespace = {}
    result = []
    basic_index = 1

    for literal, field_name, format_spec, conversion in fmt.parse(template):

        # output the literal text
        if literal:
            result.append("%r" % literal)

        # if there's a field, output it
        if field_name is not None:
            if "[" in field_name or "." in field_name:
                namespace["fmt"] = fmt
                value_code = "fmt.get_field(%r, args, kwargs)[0]" % field_name
            elif field_name.isdigit():
                value_code = "args[%s]" % field_name
            elif not field_name:
                value_code = "args[%i]" % basic_index
                basic_index += 1
            else:
                value_code = "kwargs.get(%r, '')" % field_name

            if conversion:
                namespace["fmt"] = fmt
                value_code = "fmt.convert_field(%s, %r)" % (value_code,
                                                            conversion)

            if not format_spec:
                result.append("str(%s)" % value_code)
            elif '{' in format_spec:
                namespace["fmt"] = fmt
                result.append("format(%s, fmt.vformat(%r, args, kwargs))" %
                              (value_code, format_spec))
            else:
                result.append("format(%s, %r)\n" % (value_code, format_spec))

    if not result:
        return namespace, "\"\""
    if len(result) == 1:
        return namespace, result[0]

    return namespace, "\"\".join([%s])" % (", ".join(result))


def prepare_template(template):
    namespace, code = _template_code(template)

    result = ("def template(args, kwargs):\n"
              "  return %s" % code)

    six.exec_(result, namespace)

    fn = namespace["template"]
    fn.interpolate = lambda context: fn(context.backreferences,
                                        context.message)

    return fn


class Context():
    __slots__ = ['pipeline_manager', 'message', 'match', 'match_field',
                 'backreferences', 'matches']

    def __init__(self, message, pipeline_manager):
        self.pipeline_manager = pipeline_manager
        self.message = message
        self.match = None
        self.match_field = None
        self.matches = None
        self.backreferences = []

    def next_step(self):
        self.match = None
        self.match_field = None
        self.matches = None
        self.backreferences = []
