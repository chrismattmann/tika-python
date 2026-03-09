#!/usr/bin/env python
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

from pathlib import Path
from http import HTTPStatus

import tika.parser
import tika.tika


TEST_FILE_PATH = Path(__file__).parent / "files" / "rwservlet.pdf"


def test_remote_pdf():
    """parse remote PDF"""
    assert tika.parser.from_file(
        "https://upload.wikimedia.org/wikipedia/commons/4/42/Article_feedback_flow_B_-_Thank_editors.pdf")


def test_remote_html():
    """parse remote HTML"""
    assert tika.parser.from_file("http://nossl.sh")


def test_remote_mp3():
    """parse remote mp3"""
    assert tika.parser.from_file(
        "https://archive.org/download/Ainst-Spaceshipdemo.mp3/Ainst-Spaceshipdemo.mp3")


def test_remote_jpg():
    """parse remote jpg"""
    assert tika.parser.from_file(
        "https://upload.wikimedia.org/wikipedia/commons/b/b7/X_logo.jpg")


def test_local_binary():
    """parse file binary"""
    with open(TEST_FILE_PATH, "rb") as file_obj:
        assert tika.parser.from_file(file_obj)


def test_local_buffer():
    response = tika.parser.from_buffer("Good evening, Dave")
    assert response["status"] == HTTPStatus.OK


def test_local_path():
    """parse file path"""
    assert tika.parser.from_file(str(TEST_FILE_PATH))


def test_kill_server():
    """parse some file then kills server"""
    with open(TEST_FILE_PATH, "rb") as file_obj:
        tika.parser.from_file(file_obj)
    assert tika.tika.killServer() is None
