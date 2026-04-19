# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest


@pytest.fixture
def test_file_path():
    return Path(__file__).parent / "files" / "rwservlet.pdf"

