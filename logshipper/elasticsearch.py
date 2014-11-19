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

import datetime
import json
import random
import string

import requests

import logshipper.context
import logshipper.filters


def json_default(value):
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    else:
        return str(value)

TRUE_VALUES = set([True, 1, "yes", "true", "on"])


def to_bool(value):
    return (value in TRUE_VALUES or
            str(value).lower() in TRUE_VALUES)


def prepare_elasticsearch_http(parameters):
    index = parameters.get('index', 'logshipper-{timestamp:%Y.%m.%d}')
    index = logshipper.context.prepare_template(index)

    if 'id' in parameters:
        id_ = logshipper.context.prepare_template(parameters['id']).interpolate
    else:
        r = random.Random()
        characters = string.letters + string.digits
        # 21 random alphanumeric characters are equivalent to a version 4 uuid,
        # as 122 / log(36+36+10, 2) > 21
        id_ = lambda context: "".join(r.choice(characters) for _ in range(21))

    doctype = parameters.get('doctype', 'log')
    timestamp_field = parameters.get('timestamp', '@timestamp')

    if 'document' in parameters:
        document_template = logshipper.context.prepare_template(
            parameters['document']).interpolate
    else:
        document_template = lambda context: dict(context.message)

    sort_keys = to_bool(parameters.get('sort_keys', False))

    base_url = parameters.get('url', "http://localhost:9200/")
    if not base_url.endswith("/"):
        base_url += "/"

    session = requests.Session()

    def handle_elasticsearch_http(message, context):
        url = "%s%s/%s/%s" % (base_url, index.interpolate(context),
                              doctype, id_(context))
        document = document_template(context)
        if timestamp_field != 'timestamp':
            document[timestamp_field] = document.pop("timestamp")

        result = session.put(url, data=json.dumps(document,
                                                  default=json_default,
                                                  sort_keys=sort_keys))
        result.raise_for_status()

    return handle_elasticsearch_http
