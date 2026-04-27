# SPDX-License-Identifier: Apache-2.0

import json

from http import HTTPStatus

import pytest

from tika import parser
from tika.parser import _parse


def test_remote_pdf():
    """parse remote PDF"""
    assert parser.from_file(
        "https://upload.wikimedia.org/wikipedia/commons/4/42/Article_feedback_flow_B_-_Thank_editors.pdf")


def test_remote_html():
    """parse remote HTML"""
    assert parser.from_file("http://nossl.sh")


def test_remote_mp3():
    """parse remote mp3"""
    assert parser.from_file(
        "https://archive.org/download/Ainst-Spaceshipdemo.mp3/Ainst-Spaceshipdemo.mp3")


def test_remote_jpg():
    """parse remote jpg"""
    assert parser.from_file(
        "https://upload.wikimedia.org/wikipedia/commons/b/b7/X_logo.jpg")


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


@pytest.mark.parametrize(
    "first,second,expected",
    [
        ("a", "b", ["a", "b"]),
        ("a", ["b", "c"], ["a", "b", "c"]),
        (["a", "b"], "c", ["a", "b", "c"]),
        (["a", "b"], ["c", "d"], ["a", "b", "c", "d"]),
    ],
    ids=["scalar+scalar", "scalar+list", "list+scalar", "list+list"],
)
def test_metadata_merge_across_embedded_objects(first, second, expected):
    """When the same metadata key appears in multiple embedded objects (nested
    PDFs, archives, ...), values must be merged into a single flat list rather
    than appended as nested lists."""
    rmeta = [
        {"X-TIKA:content": "first", "key": first},
        {"X-TIKA:content": "second", "key": second},
    ]
    result = _parse((HTTPStatus.OK, json.dumps(rmeta)))
    assert result["metadata"]["key"] == expected

