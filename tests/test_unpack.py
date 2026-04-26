# SPDX-License-Identifier: Apache-2.0

from tika import unpack

# Test data
TEXT_UTF8 = "Hello, world!! 😎 👽"
TEXT_ASCII = "Hello, world!!"


def test_utf8(tmp_path):
    """Test UTF-8 encoding"""
    test_file = tmp_path / "test_utf8.txt"
    test_file.write_bytes(TEXT_UTF8.encode("utf8"))
    parsed = unpack.from_file(str(test_file))
    assert parsed["content"].strip() == TEXT_UTF8


def test_ascii(tmp_path):
    """Test ASCII encoding"""
    test_file = tmp_path / "test_ascii.txt"
    test_file.write_text(TEXT_ASCII)
    parsed = unpack.from_file(str(test_file))
    assert parsed["content"].strip() == TEXT_ASCII


def test_from_buffer():
    parsed = unpack.from_buffer("what?")
    assert parsed is not None
    assert parsed["metadata"] is not None
    assert parsed["metadata"]["Content-Length"] == "5"


def test_from_buffer_with_headers():
    parsed = unpack.from_buffer("what?", headers={"Param": "whatever"})
    assert parsed is not None
    assert parsed["metadata"] is not None
    assert parsed["metadata"]["Content-Length"] == "5"
