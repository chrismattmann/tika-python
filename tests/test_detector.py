from pathlib import Path

from tika import detector


TEST_FILE_PATH = Path(__file__).parent / "files" / "rwservlet.pdf"


def test_local_binary():
    with open(TEST_FILE_PATH, "rb") as file_obj:
        assert detector.from_file(file_obj) == "application/pdf"


def test_local_path():
    assert detector.from_file(str(TEST_FILE_PATH)) == "application/pdf"


def test_local_buffer():
    assert detector.from_buffer("Good evening, David. How are you?") == "text/plain"
