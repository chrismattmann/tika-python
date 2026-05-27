# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""
Byte-frequency statistical MIME type detector.

This module implements content-based MIME detection using 256-bin byte
frequency histograms, beta companding (as used in the classic file type
identification literature), and simple but effective centroid models.

It is a cleaned, modernized Python 3.10+ evolution of ideas from the
NN-fileTypeDetection and ByteFrequency-ML repositories, and is designed
to complement (or run independently of) Apache Tika's TrainedModelDetector.

Key references / prior art:
- Govdocs1 + Tika studies (Mattmann, Totaro et al.)
- TREC-DD Polar dataset (large naturally-labeled web crawl data)
- TIKA-1582 / TrainedModelDetector in tika-core
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import math
import os
import sys
from pathlib import Path
from typing import BinaryIO, Iterable, Sequence, Union

# Optional numpy support (accelerates histogram + vector math)
try:
    import numpy as np  # type: ignore

    HAS_NUMPY = True
except ImportError:  # pragma: no cover
    HAS_NUMPY = False
    np = None  # type: ignore

logger = logging.getLogger(__name__)

__all__ = [
    "compute_histogram",
    "compand",
    "compute_fingerprint",
    "CentroidModel",
    "ByteFreqDetector",
    "generate_fingerprints_csv",
    "from_file",
    "from_buffer",
    "HAS_NUMPY",
]

# Public types
Source = Union[str, os.PathLike[str], bytes, bytearray, BinaryIO]
LabeledSource = tuple[str, Source]  # (mime_type, source)

# ---------------------------------------------------------------------------
# Low-level histogram / fingerprint primitives (fixed + modernized from
# NN-fileTypeDetection/preprocessors/preprocessors.py)
# ---------------------------------------------------------------------------


def _read_byte_table(source: Source, max_bytes: int = 1 << 20) -> list[int]:
    """
    Read up to max_bytes from source and return a 256-bin frequency table.

    Robust against Python 3 bytes (int values 0-255, no ord() needed).
    Streams in 1 MiB chunks to handle large files gracefully.
    """
    table: list[int] = [0] * 256
    bytes_read = 0

    if isinstance(source, (bytes, bytearray)):
        data = source[:max_bytes] if len(source) > max_bytes else source
        for b in data:
            table[b] += 1
        return table

    if isinstance(source, (str, os.PathLike)):
        path = os.fspath(source)
        with open(path, "rb") as f:
            while bytes_read < max_bytes:
                chunk = f.read(min(1 << 20, max_bytes - bytes_read))
                if not chunk:
                    break
                for b in chunk:
                    table[b] += 1
                bytes_read += len(chunk)
        return table

    # Assume file-like object (binary)
    if hasattr(source, "read"):
        # Support both real files and BytesIO etc.
        while bytes_read < max_bytes:
            chunk = source.read(min(1 << 20, max_bytes - bytes_read))
            if not chunk:
                break
            for b in chunk:
                table[b] += 1
            bytes_read += len(chunk)
        return table

    raise TypeError(
        f"Unsupported source type: {type(source)}. "
        "Expected path (str/Path), bytes, or binary file-like object."
    )


def compute_histogram(source: Source, max_bytes: int = 1 << 20) -> list[float]:
    """
    Compute a normalized byte frequency histogram (256 bins in [0.0, 1.0]).

    The highest frequency byte is scaled to 1.0; all others are relative.
    Empty input yields a zero vector.
    """
    table = _read_byte_table(source, max_bytes=max_bytes)
    total = sum(table)
    if total == 0:
        return [0.0] * 256

    if HAS_NUMPY:
        arr = np.asarray(table, dtype=np.float64)
        return (arr / arr.max()).tolist()

    max_val = max(table)
    if max_val == 0:
        return [0.0] * 256
    return [float(x) / max_val for x in table]


def compand(hist: Sequence[float], beta: float = 1.5) -> list[float]:
    """
    Apply beta companding to a normalized histogram.

    This non-linear transform (common in file type ID research) emphasizes
    rarer byte values. Default beta=1.5 matches the original NN-fileTypeDetection work.

    Formula:  (x ** (1/beta))  after normalization to [0,1].
    """
    if beta <= 0:
        raise ValueError("beta must be > 0")
    if HAS_NUMPY:
        arr = np.asarray(hist, dtype=np.float64)
        return np.power(arr, 1.0 / beta).tolist()
    return [float(x) ** (1.0 / beta) for x in hist]


def compute_fingerprint(
    source: Source, *, beta: float = 1.5, max_bytes: int = 1 << 20
) -> list[float]:
    """
    Convenience: compute normalized histogram then apply beta companding.
    This is the canonical "fingerprint" vector used for training and detection.
    """
    hist = compute_histogram(source, max_bytes=max_bytes)
    return compand(hist, beta=beta)


# ---------------------------------------------------------------------------
# Vector similarity (pure Python + optional numpy)
# ---------------------------------------------------------------------------


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity on two equal-length vectors. Returns 0.0 on zero vectors."""
    if len(a) != len(b):
        raise ValueError("Vectors must have identical length")

    if HAS_NUMPY:
        va = np.asarray(a, dtype=np.float64)
        vb = np.asarray(b, dtype=np.float64)
        dot = float(np.dot(va, vb))
        na = float(np.linalg.norm(va))
        nb = float(np.linalg.norm(vb))
    else:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))

    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# Centroid model (simple, effective, no heavy dependencies)
# ---------------------------------------------------------------------------


class CentroidModel:
    """
    Centroid-based classifier over companded byte-frequency fingerprints.

    Each MIME type is represented by the mean vector of its training fingerprints.
    Prediction uses cosine similarity against the stored centroids.

    This is intentionally lightweight and interpretable. For more power you can
    later plug in sklearn RandomForest, a small neural net, etc. while keeping
    the same fingerprint generation pipeline.
    """

    def __init__(self, beta: float = 1.5):
        self.beta = beta
        self.centroids: dict[str, list[float]] = {}
        # Pre-computed L2 norms for faster prediction
        self._norms: dict[str, float] = {}

    def train(self, labeled: Iterable[LabeledSource]) -> None:
        """
        Train (or incrementally extend) the model.

        labeled: iterable of (mime_type: str, source) pairs.
                 Sources can be paths, bytes, or file-like objects.
        """
        sums: dict[str, list[float]] = {}
        counts: dict[str, int] = {}

        for mime, src in labeled:
            if not mime:
                continue
            fp = compute_fingerprint(src, beta=self.beta)
            if mime not in sums:
                sums[mime] = fp[:]
                counts[mime] = 1
            else:
                for i in range(256):
                    sums[mime][i] += fp[i]
                counts[mime] += 1

        # Compute means and norms
        for mime, total in sums.items():
            n = counts[mime]
            mean_vec = [v / n for v in total]
            self.centroids[mime] = mean_vec
            if HAS_NUMPY:
                self._norms[mime] = float(np.linalg.norm(mean_vec))
            else:
                self._norms[mime] = math.sqrt(sum(v * v for v in mean_vec))

    def predict(self, source: Source, top_k: int = 1) -> list[tuple[str, float]]:
        """
        Predict the most likely MIME type(s) for a source.

        Returns list of (mime_type, cosine_similarity) sorted descending.
        Empty model or zero-vector input returns [].
        """
        if not self.centroids:
            return []

        fp = compute_fingerprint(source, beta=self.beta)
        if sum(fp) == 0.0:
            return []

        scores: list[tuple[str, float]] = []
        for mime, centroid in self.centroids.items():
            sim = _cosine_similarity(fp, centroid)
            scores.append((mime, sim))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[: max(1, top_k)]

    def save(self, path: str | os.PathLike[str]) -> None:
        """Persist the model as human-readable JSON."""
        data = {
            "version": 1,
            "beta": self.beta,
            "centroids": self.centroids,
        }
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> CentroidModel:
        """Load a previously saved CentroidModel."""
        with Path(path).open("r", encoding="utf-8") as f:
            data = json.load(f)

        model = cls(beta=data.get("beta", 1.5))
        model.centroids = data["centroids"]
        # Recompute norms
        for mime, vec in model.centroids.items():
            if HAS_NUMPY:
                model._norms[mime] = float(np.linalg.norm(vec))
            else:
                model._norms[mime] = math.sqrt(sum(v * v for v in vec))
        return model


# ---------------------------------------------------------------------------
# High-level detector API (style-compatible with tika.detector)
# ---------------------------------------------------------------------------


class ByteFreqDetector:
    """
    High-level detector with the same ergonomic surface as tika.detector.

    Example:
        from tika import bytefreq
        det = bytefreq.ByteFreqDetector(model)
        print(det.from_file("mystery.bin"))
        print(det.from_buffer(b"\\x89PNG..."))
    """

    def __init__(self, model: CentroidModel | None = None):
        self.model = model or CentroidModel()

    def from_file(
        self,
        filename: Source,
        config_path: str | None = None,  # signature compatibility with tika.detector
        requestOptions: dict | None = None,  # signature compatibility
    ) -> str:
        """
        Detect MIME type from a file path or file-like object.

        Returns best MIME string for compatibility with tika.detector.
        Use .predict(source, top_k=N) for scores + alternatives.
        """
        if not self.model or not self.model.centroids:
            return "application/octet-stream"
        results = self.model.predict(filename, top_k=1)
        return results[0][0] if results else "application/octet-stream"

    def from_buffer(
        self,
        string: bytes | str | BinaryIO,
        config_path: str | None = None,
        requestOptions: dict | None = None,
    ) -> str:
        """Detect MIME type from an in-memory buffer."""
        if isinstance(string, str):
            data: bytes | BinaryIO = string.encode("utf-8", errors="replace")
        else:
            data = string
        if not self.model or not self.model.centroids:
            return "application/octet-stream"
        results = self.model.predict(data, top_k=1)
        return results[0][0] if results else "application/octet-stream"

    def predict(
        self, source: Source, top_k: int = 3
    ) -> list[tuple[str, float]]:
        """Return top-k (mime, score) tuples with full confidence information."""
        return self.model.predict(source, top_k=top_k) if self.model else []


# ---------------------------------------------------------------------------
# Training data generation (ported + heavily fixed from NN-fileTypeDetection)
# ---------------------------------------------------------------------------


def generate_fingerprints_csv(
    root_dir: str | os.PathLike[str],
    output_csv: str | os.PathLike[str],
    *,
    beta: float = 1.5,
    max_bytes: int = 1 << 20,
    label_from: str = "subdir",  # "subdir" | "filename"
    recursive: bool = True,
    log_every: int = 100,
) -> int:
    """
    Walk a directory of labeled files and emit a CSV suitable for training
    classical ML models (the format expected by the old NN-fileTypeDetection
    classifiers and similar pipelines).

    Directory layout convention (label_from="subdir"):
        root/
            text/plain/
                file1.txt
                ...
            application/pdf/
                doc1.pdf
                ...

    Output CSV columns:
        byte1,byte2,...,byte256,output,label
        (values are the companded fingerprint; output is 1 for the target
         label when doing one-vs-rest, but here we write the actual label)

    Returns number of files processed.
    """
    root = Path(root_dir)
    out_path = Path(output_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not root.exists():
        raise FileNotFoundError(f"Root directory does not exist: {root}")

    files: list[tuple[str, Path]] = []
    if label_from == "subdir":
        for dirpath, dirnames, filenames in os.walk(root):
            if not recursive and dirpath != str(root):
                continue
            rel = Path(dirpath).relative_to(root)
            if rel == Path("."):
                continue
            # Use the immediate subdirectory as the label (full relative path also works)
            label = str(rel).replace(os.sep, "/")
            for name in filenames:
                if name.startswith("."):
                    continue
                files.append((label, Path(dirpath) / name))
    else:
        # Simple fallback: use filename suffix or whole name as crude label
        for p in root.rglob("*") if recursive else root.iterdir():
            if p.is_file() and not p.name.startswith("."):
                label = p.suffix.lstrip(".") or "unknown"
                files.append((label, p))

    header = [f"byte{i+1}" for i in range(256)] + ["output", "label"]

    count = 0
    with out_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)

        for i, (label, path) in enumerate(files):
            try:
                fp = compute_fingerprint(path, beta=beta, max_bytes=max_bytes)
                # For compatibility with old one-vs-rest pipelines we still emit
                # an "output" column. Here we put 1.0 as a placeholder (real
                # multi-class training usually ignores it or uses the label col).
                row = fp + [1.0, label]
                writer.writerow(row)
                count += 1
                if log_every and (i + 1) % log_every == 0:
                    logger.info("Processed %d files...", i + 1)
            except Exception as e:
                logger.warning("Skipping %s: %s", path, e)

    logger.info("Wrote %d fingerprints to %s", count, out_path)
    return count


# ---------------------------------------------------------------------------
# Convenience top-level detector (stateless, requires model)
# ---------------------------------------------------------------------------


def from_file(
    filename: Source,
    model: CentroidModel | None = None,
    **kwargs,
) -> str:
    """
    Stateless convenience function (mirrors tika.detector.from_file).

    You must supply a trained CentroidModel (or any future model type) for
    meaningful results. Without one, "application/octet-stream" is returned.
    """
    if model is None:
        return "application/octet-stream"
    return ByteFreqDetector(model).from_file(filename, **kwargs)  # type: ignore[arg-type]


def from_buffer(
    data: bytes | str | BinaryIO,
    model: CentroidModel | None = None,
    **kwargs,
) -> str:
    """Stateless convenience function (mirrors tika.detector.from_buffer)."""
    if model is None:
        return "application/octet-stream"
    return ByteFreqDetector(model).from_buffer(data, **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Training script / CLI support
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m tika.bytefreq",
        description="Byte-frequency MIME detector training and utilities",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # generate-fingerprints
    g = sub.add_parser(
        "generate-fingerprints",
        help="Walk labeled directory tree and emit training CSV (companded fingerprints)",
    )
    g.add_argument("root_dir", help="Root of labeled files (subdirs = MIME labels)")
    g.add_argument("output_csv", help="Path to write CSV")
    g.add_argument("--beta", type=float, default=1.5, help="Companding beta (default 1.5)")
    g.add_argument("--max-bytes", type=int, default=1 << 20)
    g.add_argument("--label-from", choices=["subdir", "filename"], default="subdir")
    g.add_argument("--no-recursive", action="store_true")

    # train-centroid
    t = sub.add_parser(
        "train-centroid",
        help="Train a CentroidModel from a labeled directory (or existing CSV)",
    )
    t.add_argument("input", help="Labeled root directory (subdirectories become MIME labels)")
    t.add_argument("model_out", help="Where to write the .json model")
    t.add_argument("--beta", type=float, default=1.5)

    # detect
    d = sub.add_parser("detect", help="Detect using a trained model")
    d.add_argument("model", help="Path to trained .json model")
    d.add_argument("path_or_dash", help="File path or '-' for stdin")
    d.add_argument("--top-k", type=int, default=3)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.cmd == "generate-fingerprints":
        n = generate_fingerprints_csv(
            args.root_dir,
            args.output_csv,
            beta=args.beta,
            max_bytes=args.max_bytes,
            label_from=args.label_from,
            recursive=not args.no_recursive,
        )
        print(f"Generated fingerprints for {n} files -> {args.output_csv}")
        return 0

    elif args.cmd == "train-centroid":
        model = CentroidModel(beta=args.beta)
        root = Path(args.input)

        def _walk() -> Iterable[LabeledSource]:
            for dirpath, _, filenames in os.walk(root):
                rel = Path(dirpath).relative_to(root)
                if str(rel) == ".":
                    continue
                label = str(rel).replace(os.sep, "/")
                for name in filenames:
                    if name.startswith("."):
                        continue
                    yield (label, Path(dirpath) / name)

        model.train(_walk())
        model.save(args.model_out)
        print(f"Saved CentroidModel ({len(model.centroids)} classes) -> {args.model_out}")
        return 0

    elif args.cmd == "detect":
        model = CentroidModel.load(args.model)
        det = ByteFreqDetector(model)

        if args.path_or_dash == "-":
            data = sys.stdin.buffer.read()
            results = det.predict(data, top_k=args.top_k)
        else:
            results = det.predict(args.path_or_dash, top_k=args.top_k)

        for mime, score in results:
            print(f"{score:.4f}\t{mime}")
        return 0

    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
