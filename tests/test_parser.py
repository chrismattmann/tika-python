from http import HTTPStatus

from tika import parser


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

