# SPDX-License-Identifier: Apache-2.0

from tika import detector


def test_local_binary(test_file_path):
    with open(test_file_path, "rb") as file_obj:
        assert detector.from_file(file_obj) == "application/pdf"


def test_local_path(test_file_path):
    assert detector.from_file(str(test_file_path)) == "application/pdf"


def test_local_buffer():
    assert detector.from_buffer("Good evening, David. How are you?") == "text/plain"
