#!/usr/bin/env python
# encoding: utf-8
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# python -m unittest tika.tests.test_from_file_service

import sys
import unittest
if sys.version_info >= (3, 3):
    from unittest import mock
else:
    import mock
import tika.parser


class CreateTest(unittest.TestCase):
    'test different services in from_file parsing: Content, Metadata or both in recursive mode'

    def test_default_service(self):
        'parse file using default service'
        result = tika.parser.from_file(
            'https://boe.es/boe/dias/2019/12/02/pdfs/BOE-A-2019-17288.pdf')
        self.assertEqual(result['metadata']['Content-Type'],'application/pdf')
        self.assertIn('AUTORIDADES Y PERSONAL',result['content'])
    @mock.patch('tika.parser._parse')
    @mock.patch('tika.parser.parse1')
    def test_remote_endpoint(self, tika_call_mock, _):
        result = tika.parser.from_file(
            'filename', 'http://tika:9998/tika')

        tika_call_mock.assert_called_with(
            'all', 'filename', 'http://tika:9998/tika', headers=None, config_path=None,
            requestOptions={})
    def test_default_service_explicit(self):
        'parse file using default service explicitly'
        result = tika.parser.from_file(
            'https://boe.es/boe/dias/2019/12/02/pdfs/BOE-A-2019-17288.pdf', service='all')
        self.assertEqual(result['metadata']['Content-Type'],'application/pdf')
        self.assertIn('AUTORIDADES Y PERSONAL',result['content'])
    def test_text_service(self):
        'parse file using the content only service'
        result = tika.parser.from_file(
            'https://boe.es/boe/dias/2019/12/02/pdfs/BOE-A-2019-17288.pdf', service='text')
        self.assertIsNone(result['metadata'])
        self.assertIn('AUTORIDADES Y PERSONAL',result['content'])
    def test_meta_service(self):
        'parse file using the content only service'
        result = tika.parser.from_file(
            'https://boe.es/boe/dias/2019/12/02/pdfs/BOE-A-2019-17288.pdf', service='meta')
        self.assertIsNone(result['content'])
        self.assertEqual(result['metadata']['Content-Type'],'application/pdf')
    def test_invalid_service(self):
        'parse file using an invalid service should perform the default parsing'
        result = tika.parser.from_file(
            'https://boe.es/boe/dias/2019/12/02/pdfs/BOE-A-2019-17288.pdf', service='bad')
        self.assertEqual(result['metadata']['Content-Type'],'application/pdf')
        self.assertIn('AUTORIDADES Y PERSONAL',result['content'])

if __name__ == '__main__':
    unittest.main()
