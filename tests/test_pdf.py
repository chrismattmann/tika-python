from pathlib import Path

from tika import pdf

TEST_FILE_PATH = Path(__file__).parent / "files" / "rwservlet.pdf"


def test_local_path():
    text_pages = pdf.text_from_pdf_pages(str(TEST_FILE_PATH))
    assert isinstance(text_pages, list)
