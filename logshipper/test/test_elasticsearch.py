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
import unittest

import mock
import requests

import logshipper.context
import logshipper.elasticsearch


class Tests(unittest.TestCase):

    def test_elasticsearch_http(self):
        class Foo(object):
            def __str__(self):
                return "1235"

        message = {
            "message": "This is a test.",
            "timestamp": datetime.datetime(2008, 10, 19, 14, 40, 0, 9),
            "set": Foo(),
        }
        context = logshipper.context.Context(message, None)

        with mock.patch.object(requests.Session, 'put') as mock_method:
            mock_method.return_value = mock.Mock()
            handler = logshipper.elasticsearch.prepare_elasticsearch_http(
                {'id': "1", 'sort_keys': 1})

            handler(message, context)

            mock_method.assert_called_once_with(
                'http://localhost:9200/logshipper-2008.10.19/log/1',
                data=(b'{"@timestamp": "2008-10-19T14:40:00.000009", '
                      b'"message": "This is a test.", '
                      b'"set": "1235"}'))

    def test_elasticsearch_autoid(self):
        message = {
            "message": "This is a test.",
            "timestamp": datetime.datetime(2008, 10, 19, 14, 40, 0, 9),
        }
        context = logshipper.context.Context(message, None)

        with mock.patch.object(requests.Session, 'put') as mock_method:
            mock_method.return_value = mock.Mock()
            handler = logshipper.elasticsearch.prepare_elasticsearch_http({
                'sort_keys': 1,
                'timestamp': "timestamp",
            })

            handler(message, context)

            mock_method.assert_called_once_with(
                ('http://localhost:9200/logshipper-2008.10.19/log/'
                 '184162c2c5d7e33406fcbb78ef1f968e'),
                data=(b'{"message": "This is a test.", '
                      b'"timestamp": "2008-10-19T14:40:00.000009"}'))

    def test_elasticsearch_doc(self):
        message = {
            "message": "This is a test.",
            "timestamp": datetime.datetime(2008, 10, 19, 14, 40, 0, 9),
            "the_id": 1
        }
        context = logshipper.context.Context(message, None)

        with mock.patch.object(requests.Session, 'put') as mock_method:
            mock_method.return_value = mock.Mock()
            handler = logshipper.elasticsearch.prepare_elasticsearch_http({
                'sort_keys': 1,
                "document": {"ma": "{message}"},
                "url": "http://somehost",
                "index": "foo-{timestamp:%Y-%m}",
                "doctype": "test",
                "id": "{the_id}"
            })

            handler(message, context)

            mock_method.assert_called_once_with(
                'http://somehost/foo-2008-10/test/1',
                data=(b'{"ma": "This is a test."}'))
