# SPDX-License-Identifier: Apache-2.0

"""
Tests for tika.bytefreq — byte frequency histogram + centroid MIME detector.
"""

import math
import tempfile
from pathlib import Path

from tika import bytefreq


def assert_approx(a, b, rel=1e-6, abs_tol=1e-9):
    """Tiny helper so tests don't require pytest at import time."""
    assert math.isclose(a, b, rel_tol=rel, abs_tol=abs_tol), f"{a} != {b}"


def test_histogram_on_real_pdf(test_file_path):
    h = bytefreq.compute_histogram(test_file_path)
    assert len(h) == 256
    assert all(0.0 <= x <= 1.0 for x in h)
    assert_approx(max(h), 1.0)


def test_fingerprint_companding():
    data = b"\x00\x01\x02" + b"\xff" * 100
    fp = bytefreq.compute_fingerprint(data, beta=1.5)
    assert len(fp) == 256
    # 0xff should dominate after normalization + companding
    assert fp[255] > 0.9


def test_centroid_model_basic():
    model = bytefreq.CentroidModel(beta=1.5)
    model.train(
        [
            ("text/plain", b"hello world " * 200),
            ("application/pdf", b"%PDF-1.4 " + b"\x00\x01\x02" * 50),
        ]
    )
    assert "text/plain" in model.centroids
    assert "application/pdf" in model.centroids

    # Predict on something very text-like
    res = model.predict(b"this is clearly plain text content " * 30, top_k=1)
    assert len(res) == 1
    assert res[0][0] == "text/plain"
    assert res[0][1] > 0.5


def test_detector_facade(test_file_path):
    model = bytefreq.CentroidModel()
    model.train(
        [
            ("application/pdf", test_file_path),
            ("text/plain", b"just some plain text for training"),
        ]
    )
    det = bytefreq.ByteFreqDetector(model)

    # Compatibility mode returns single string
    result = det.from_file(test_file_path)
    assert result == "application/pdf"

    # Synthetic buffer may or may not match strongly (centroid from one real PDF)
    # The important contract is that we return *some* string and don't crash.
    buf_result = det.from_buffer(b"%PDF-1.3 fake header here")
    assert isinstance(buf_result, str)
    assert buf_result  # non-empty


def test_module_level_from_functions_require_model():
    # Without a model we gracefully return octet-stream
    assert bytefreq.from_file("anything.bin") == "application/octet-stream"
    assert bytefreq.from_buffer(b"some bytes") == "application/octet-stream"


def test_generate_fingerprints_csv(tmp_path):
    # Create tiny labeled tree
    pdf_dir = tmp_path / "application" / "pdf"
    txt_dir = tmp_path / "text" / "plain"
    pdf_dir.mkdir(parents=True)
    txt_dir.mkdir(parents=True)

    (pdf_dir / "a.pdf").write_bytes(b"%PDF-1.4" + b"\x00" * 200)
    (txt_dir / "b.txt").write_text("hello plain text " * 40)

    csv_path = tmp_path / "fingerprints.csv"
    n = bytefreq.generate_fingerprints_csv(
        tmp_path, csv_path, beta=1.0, log_every=0
    )
    assert n == 2
    assert csv_path.exists()

    content = csv_path.read_text()
    assert "byte1,byte2" in content
    assert "application/pdf" in content or "text/plain" in content


def test_model_save_load_roundtrip(tmp_path):
    model = bytefreq.CentroidModel(beta=1.2)
    model.train([("text/plain", b"abc def ghi " * 100)])

    model_path = tmp_path / "m.json"
    model.save(model_path)

    loaded = bytefreq.CentroidModel.load(model_path)
    assert_approx(loaded.beta, 1.2)
    assert "text/plain" in loaded.centroids

    # Predictions should be identical
    orig = model.predict(b"more plain text here " * 20, top_k=1)
    after = loaded.predict(b"more plain text here " * 20, top_k=1)
    assert orig[0][0] == after[0][0]
    assert_approx(orig[0][1], after[0][1], abs_tol=1e-6)


def test_empty_and_small_inputs():
    h = bytefreq.compute_histogram(b"")
    assert h == [0.0] * 256

    fp = bytefreq.compute_fingerprint(b"\x00\x01", beta=2.0)
    assert len(fp) == 256
    assert sum(fp) > 0
