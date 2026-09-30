# SPDX-License-Identifier: Apache-2.0

import io
import json
import zipfile

from tika import unpack

# Test data
TEXT_UTF8 = "Hello, world!! 😎 👽"
TEXT_ASCII = "Hello, world!!"


# --- zip response parsing, no server needed ---------------------------------------


def make_unpack_zip(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, json.dumps(data) if isinstance(data, dict) else data)
    return buffer.getvalue()


def test_parse_zip_splits_container_and_attachments():
    body = make_unpack_zip(
        {
            "0.pdf": b"%PDF-original",
            "0.pdf.metadata.json": {"tk:content": "hello", "Content-Type": "application/pdf"},
            "1.png": b"\x89PNG",
            "1.png.metadata.json": {"Content-Type": "image/png"},
            "2.docx": b"PK",
        }
    )
    parsed = unpack._parse((200, body))
    assert parsed["content"] == "hello"
    assert parsed["metadata"] == {"Content-Type": "application/pdf"}
    assert parsed["attachments"] == {"1.png": b"\x89PNG", "2.docx": b"PK"}


def test_parse_zip_accepts_stem_named_sidecar():
    body = make_unpack_zip({"0.txt": b"hi", "0.metadata.json": {"tk:content": "hi", "Content-Type": "text/plain"}})
    parsed = unpack._parse((200, body))
    assert parsed["content"] == "hi"
    assert parsed["metadata"]["Content-Type"] == "text/plain"
    assert parsed["attachments"] == {}


def test_parse_zip_without_sidecar():
    parsed = unpack._parse((200, make_unpack_zip({"0.txt": b"hi"})))
    assert parsed == {"content": "", "metadata": {}, "attachments": {}}


def test_parse_zip_empty_response():
    assert unpack._parse((204, b"")) == {}
    assert unpack._parse((200, None)) == {}
    assert unpack._parse(None) == {}


def test_utf8(tmp_path):
    """Test UTF-8 encoding"""
    test_file = tmp_path / "test_utf8.txt"
    test_file.write_bytes(TEXT_UTF8.encode("utf8"))
    parsed = unpack.from_file(str(test_file))
    assert parsed["content"].strip() == TEXT_UTF8
    assert parsed["attachments"] == {}


def test_ascii(tmp_path):
    """Test ASCII encoding"""
    test_file = tmp_path / "test_ascii.txt"
    test_file.write_text(TEXT_ASCII)
    parsed = unpack.from_file(str(test_file))
    assert parsed["content"].strip() == TEXT_ASCII
    assert parsed["metadata"]["Content-Type"].startswith("text/plain")
    assert parsed["attachments"] == {}


def test_embedded_documents_become_attachments(tmp_path):
    """A zip is a container: its members come back as attachments, its own text as content"""
    container = tmp_path / "container.zip"
    with zipfile.ZipFile(container, "w") as archive:
        archive.writestr("a.txt", "alpha text")
        archive.writestr("b.txt", "bravo text")
    parsed = unpack.from_file(str(container))
    assert parsed["metadata"]["Content-Type"] == "application/zip"
    assert "a.txt" in parsed["content"] and "b.txt" in parsed["content"]
    assert sorted(parsed["attachments"].values()) == [b"alpha text", b"bravo text"]
    assert all(name.startswith(("1.", "2.")) for name in parsed["attachments"]), parsed["attachments"].keys()


def test_from_buffer():
    parsed = unpack.from_buffer("what?")
    assert parsed is not None
    assert parsed["metadata"] is not None
    assert parsed["metadata"]["Content-Length"] == "5"
    assert parsed["content"].strip() == "what?"
    assert parsed["attachments"] == {}


def test_from_buffer_with_headers():
    parsed = unpack.from_buffer("what?", headers={"Param": "whatever"})
    assert parsed is not None
    assert parsed["metadata"] is not None
    assert parsed["metadata"]["Content-Length"] == "5"
