from pathlib import Path

from tika import language

TEST_FILE_PATH = Path(__file__).parent / "files" / "rwservlet.pdf"


def test_local_binary():
    with open(TEST_FILE_PATH, "rb") as file_obj:
        assert language.from_file(file_obj) == "en"


def test_local_path():
    assert language.from_file(str(TEST_FILE_PATH)) == "en"


def test_local_buffer():
    assert language.from_buffer("Good evening, David. How are you?") == "en"
