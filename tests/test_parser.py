# SPDX-License-Identifier: Apache-2.0

from http import HTTPStatus

from tika import parser


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
