# SPDX-License-Identifier: Apache-2.0

from tika import language


def test_local_binary(test_file_path):
    with open(test_file_path, "rb") as file_obj:
        assert language.from_file(file_obj) == "en"


def test_local_path(test_file_path):
    assert language.from_file(str(test_file_path)) == "en"


def test_local_buffer():
    assert language.from_buffer("Good evening, David. How are you?") == "en"
