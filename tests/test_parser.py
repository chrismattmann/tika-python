# SPDX-License-Identifier: Apache-2.0

import json
from http import HTTPStatus

from tika import parser


# --- response parsing, no server needed -------------------------------------------


def test_parse_concatenates_content_and_merges_metadata():
    body = json.dumps(
        [
            {parser._CONTENT_KEY: "outer ", "Content-Type": "application/pdf", "dc:title": "t"},
            {parser._CONTENT_KEY: "inner", "Content-Type": "image/png"},
        ]
    )
    parsed = parser._parse((200, body))
    assert parsed["status"] == 200
    assert parsed["content"] == "outer inner"
    assert parsed["metadata"]["Content-Type"] == ["application/pdf", "image/png"]
    assert parsed["metadata"]["dc:title"] == "t"
    assert parser._CONTENT_KEY not in parsed["metadata"]


def test_parse_without_content_yields_none():
    parsed = parser._parse((200, json.dumps([{"Content-Type": "image/png"}])))
    assert parsed["content"] is None
    assert parsed["metadata"] == {"Content-Type": "image/png"}


def test_parse_meta_service():
    parsed = parser._parse((200, json.dumps({"Content-Type": "application/pdf"})), service="meta")
    assert parsed == {"metadata": {"Content-Type": "application/pdf"}, "content": None, "status": 200}


def test_parse_text_service_returns_body_verbatim():
    parsed = parser._parse((200, "plain text"), service="text")
    assert parsed == {"metadata": None, "content": "plain text", "status": 200}


def test_parse_empty_body():
    assert parser._parse((204, "")) == {"metadata": None, "content": None, "status": 204}
    assert parser._parse(None) == {"metadata": None, "content": None}


def test_parse_does_not_decode_error_bodies():
    parsed = parser._parse((503, json.dumps({"status": "TIMEOUT", "message": "worker timed out"})))
    assert parsed == {"metadata": None, "content": None, "status": 503}
    parsed = parser._parse((422, "Unprocessable Entity"), service="meta")
    assert parsed == {"metadata": None, "content": None, "status": 422}


# --- integration, against the live server -----------------------------------------


def test_remote_pdf(remote_fixture_base_url):
    """parse remote PDF"""
    assert parser.from_file(f"{remote_fixture_base_url}/remote.pdf")


def test_remote_html(remote_fixture_base_url):
    """parse remote HTML"""
    assert parser.from_file(f"{remote_fixture_base_url}/remote.html")


def test_remote_mp3(remote_fixture_base_url):
    """parse remote mp3"""
    assert parser.from_file(f"{remote_fixture_base_url}/remote.mp3")


def test_remote_jpg(remote_fixture_base_url):
    """parse remote jpg"""
    assert parser.from_file(f"{remote_fixture_base_url}/remote.jpg")


def test_local_binary(test_file_path):
    """parse file binary"""
    with open(test_file_path, "rb") as file_obj:
        assert parser.from_file(file_obj)


def test_local_buffer():
    response = parser.from_buffer("Good evening, Dave")
    assert response["status"] == HTTPStatus.OK


def test_local_path(test_file_path):
    """parse file path"""
    assert parser.from_file(str(test_file_path))
