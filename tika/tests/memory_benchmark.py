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
# To run:
# python tika/tests/memory_benchmark.py
import os
import zlib


import tika.parser
import tika.tika
from memory_profiler import profile

from tika.tests.utils import gzip_compress


@profile
def test_parser_binary():
    """parse file binary"""
    file = os.path.join(os.path.dirname(__file__), 'files', 'rwservlet.pdf')

    with open(file, 'rb') as file_obj:
        response = tika.parser.from_file(file_obj, headers={'Accept-Encoding': 'gzip, deflate'})


@profile
def test_parser_buffer():
    """parse buffer"""
    file = os.path.join(os.path.dirname(__file__), 'files', 'rwservlet.pdf')

    with open(file, 'rb') as file_obj:
        response = tika.parser.from_buffer(file_obj.read(), headers={'Accept-Encoding': 'gzip, deflate'})


@profile
def test_parser_zlib():
    """parse buffer zlib"""

    file = os.path.join(os.path.dirname(__file__), 'files', 'rwservlet.pdf')

    with open(file, 'rb') as file_obj:
        response = tika.parser.from_buffer(zlib.compress(file_obj.read()), headers={'Accept-Encoding': 'gzip, deflate'})


@profile
def test_parser_gzip():
    """parse buffer gzip"""
    file = os.path.join(os.path.dirname(__file__), 'files', 'rwservlet.pdf')

    with open(file, 'rb') as file_obj:
        response = tika.parser.from_buffer(gzip_compress(file_obj.read()), headers={'Accept-Encoding': 'gzip, deflate'})

if __name__ == '__main__':
    test_parser_buffer()
    test_parser_binary()
    test_parser_zlib()
    test_parser_gzip()
