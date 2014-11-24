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
import hashlib
import json

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


def md5_hash(data):
    md5 = hashlib.md5()
    md5.update(data)
    return md5.hexdigest()


def prepare_elasticsearch_http(parameters):
    """Sends documents to elasticsearch

    Parameters:

    ```index```
        The index to use. Defaults to ```logshipper-{timestamp:%Y.%m.%d}```
    ```id```
        The id for the document. Highly recomended if your log messages can be
        uniqely identified from some field. Defaults to an md5 hash of the
        document.
    ```doctype``
        The document type. Defaults to ```log```
    ```timestamp```
        In what field to store the timestamp. Defaults to ```@timestamp```
    ```document```
        The document to send. When not provided, the entire logmessage is sent.
    ```url```
        The URL of the elasticsearch instance. Defaults to
        ```http://localhost:9200/```.
    """

    index = parameters.get('index', 'logshipper-{timestamp:%Y.%m.%d}')
    index = logshipper.context.prepare_template(index)

    if 'id' in parameters:
        id_ = logshipper.context.prepare_template(parameters['id']).interpolate
    else:
        id_ = None

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
        document = document_template(context)
        if timestamp_field != 'timestamp':
            document[timestamp_field] = document.pop("timestamp")

        document = json.dumps(document, default=json_default,
                              sort_keys=sort_keys)

        url = "%s%s/%s/%s" % (base_url, index.interpolate(context), doctype,
                              id_(context) if id_ else md5_hash(document))

        result = session.put(url, data=document)
        result.raise_for_status()

    return handle_elasticsearch_http
