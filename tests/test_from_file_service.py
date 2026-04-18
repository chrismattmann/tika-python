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

from unittest import mock

from tika import parser

TEST_PDF_URL = "https://boe.es/boe/dias/2019/12/02/pdfs/BOE-A-2019-17288.pdf"


def test_default_service():
    "parse file using default service"
    result = parser.from_file(TEST_PDF_URL)
    assert result["metadata"]["Content-Type"] == "application/pdf"
    assert "AUTORIDADES Y PERSONAL" in result["content"]


@mock.patch("tika.parser._parse")
@mock.patch("tika.parser.parse1")
def test_remote_endpoint(tika_call_mock, _):
    result = parser.from_file("filename", "http://tika:9998/tika")

    tika_call_mock.assert_called_with(
        "all",
        "filename",
        "http://tika:9998/tika",
        headers=None,
        config_path=None,
        requestOptions={},
    )


def test_default_service_explicit():
    "parse file using default service explicitly"
    result = parser.from_file(TEST_PDF_URL, service="all")
    assert result["metadata"]["Content-Type"] == "application/pdf"
    assert "AUTORIDADES Y PERSONAL" in result["content"]


def test_text_service():
    "parse file using the content only service"
    result = parser.from_file(TEST_PDF_URL, service="text")
    assert result["metadata"] is None
    assert "AUTORIDADES Y PERSONAL" in result["content"]


def test_meta_service():
    "parse file using the content only service"
    result = parser.from_file(TEST_PDF_URL, service="meta")
    assert result["content"] is None
    assert result["metadata"]["Content-Type"] == "application/pdf"


def test_invalid_service():
    "parse file using an invalid service should perform the default parsing"
    result = parser.from_file(TEST_PDF_URL, service="bad")
    assert result["metadata"]["Content-Type"] == "application/pdf"
    assert "AUTORIDADES Y PERSONAL" in result["content"]
