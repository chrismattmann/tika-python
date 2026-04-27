# SPDX-License-Identifier: Apache-2.0

from tika import pdf


def test_local_path(test_file_path):
    text_pages = pdf.text_from_pdf_pages(str(test_file_path))
    assert isinstance(text_pages, list)
