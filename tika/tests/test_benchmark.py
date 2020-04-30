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
# pytest --benchmark-enable --benchmark-timer=time.process_time tika/tests/test_benchmark.py
# pytest --benchmark-enable --benchmark-timer=time.process_time tika/tests/test_benchmark.py
import os
import unittest
import zlib

import tika.parser
import tika.tika
from tika.tests.utils import HTTPStatusOk, gzip_compress


def test_local_binary(benchmark):
    """parse file binary"""
    file = os.path.join(os.path.dirname(__file__), 'files', 'rwservlet.pdf')
    response = benchmark(tika_from_binary, file)

    assert response['status'] == HTTPStatusOk


def test_parser_buffer(benchmark):
    """example how to send gzip file"""
    file = os.path.join(os.path.dirname(__file__), 'files', 'rwservlet.pdf')
    response = benchmark(tika_from_buffer, file)

    assert response['status'] == HTTPStatusOk


def test_parser_buffer_zlib_input(benchmark):
    """example how to send gzip file"""
    file = os.path.join(os.path.dirname(__file__), 'files', 'rwservlet.pdf')

    response = benchmark(tika_from_buffer_zlib, file)

    assert response['status'] == HTTPStatusOk


def test_parser_buffer_gzip_input(benchmark):
    """parse file binary"""
    file = os.path.join(os.path.dirname(__file__), 'files', 'rwservlet.pdf')
    response = benchmark(tika_from_buffer_gzip, file)

    assert response['status'] == HTTPStatusOk


def test_local_binary_with_gzip_output(benchmark):
    """parse file binary"""
    file = os.path.join(os.path.dirname(__file__), 'files', 'rwservlet.pdf')
    response = benchmark(tika_from_binary, file, headers={'Accept-Encoding': 'gzip, deflate'})

    assert response['status'] == HTTPStatusOk


def test_parser_buffer_with_gzip_output(benchmark):
    """example how to send gzip file"""
    file = os.path.join(os.path.dirname(__file__), 'files', 'rwservlet.pdf')
    response = benchmark(tika_from_buffer, file, headers={'Accept-Encoding': 'gzip, deflate'})

    assert response['status'] == HTTPStatusOk


def test_parser_buffer_zlib_input_and_gzip_output(benchmark):
    """example how to send gzip file"""
    file = os.path.join(os.path.dirname(__file__), 'files', 'rwservlet.pdf')

    response = benchmark(tika_from_buffer_zlib, file, headers={'Accept-Encoding': 'gzip, deflate'})

    assert response['status'] == HTTPStatusOk


def test_parser_buffer_gzip_input_and_gzip_output(benchmark):
    """parse file binary"""
    file = os.path.join(os.path.dirname(__file__), 'files', 'rwservlet.pdf')
    response = benchmark(tika_from_buffer_gzip, file, headers={'Accept-Encoding': 'gzip, deflate'})

    assert response['status'] == HTTPStatusOk


def tika_from_buffer_zlib(file, headers=None):
    with open(file, 'rb') as file_obj:
        return tika.parser.from_buffer(zlib.compress(file_obj.read()), headers=headers)


def tika_from_buffer_gzip(file, headers=None):
    with open(file, 'rb') as file_obj:
        return tika.parser.from_buffer(gzip_compress(file_obj.read()), headers=headers)


def tika_from_buffer(file, headers=None):
    with open(file, 'rb') as file_obj:
        return tika.parser.from_buffer(file_obj.read(), headers=headers)


def tika_from_binary(file, headers=None):
    with open(file, 'rb') as file_obj:
        return tika.parser.from_file(file_obj, headers=headers)


if __name__ == '__main__':
    unittest.main()
