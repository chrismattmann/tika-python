# SPDX-License-Identifier: Apache-2.0

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import threading

import pytest

GITHUB_PAGES_REMOTE_FIXTURE_BASE_URL = (
    "https://chrismattmann.github.io/tika-python/_static/test-files"
)


@pytest.fixture
def test_file_path():
    return Path(__file__).parent / "files" / "rwservlet.pdf"


@pytest.fixture(scope="session")
def remote_fixture_base_url():
    configured_url = os.getenv("TIKA_REMOTE_TEST_BASE_URL")
    if configured_url:
        yield configured_url.rstrip("/")
        return

    if not os.getenv("CI"):
        yield GITHUB_PAGES_REMOTE_FIXTURE_BASE_URL
        return

    static_dir = Path(__file__).parents[1] / "docs" / "source" / "_static" / "test-files"
    handler = partial(SimpleHTTPRequestHandler, directory=static_dir)

    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as httpd:
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        yield f"http://127.0.0.1:{httpd.server_port}"
        httpd.shutdown()
