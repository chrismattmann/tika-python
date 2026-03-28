from tempfile import NamedTemporaryFile

from tika import unpack

# Test data
TEXT_UTF8 = "Hello, world!! 😎 👽"
TEXT_ASCII = "Hello, world!!"


def test_utf8():
    """Test UTF-8 encoding"""
    with NamedTemporaryFile("w+b", prefix="tika-python", suffix=".txt", dir="/tmp") as f:
        f.write(TEXT_UTF8.encode("utf8"))
        f.flush()
        f.seek(0)
        parsed = unpack.from_file(f.name)
        assert parsed["content"].strip() == TEXT_UTF8


def test_ascii():
    """Test ASCII encoding"""
    with NamedTemporaryFile("w+t", prefix="tika-python", suffix=".txt", dir="/tmp") as f:
        f.write(TEXT_ASCII)
        f.flush()
        f.seek(0)
        parsed = unpack.from_file(f.name)
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
