# Byte Frequency MIME Detector (`tika.bytefreq`)

Statistical MIME type detection for tika-python using byte frequency histograms and beta companding.

This module provides a clean, modern Python 3.10+ implementation of content-based file type identification that does **not** rely on magic bytes, file extensions, or the Tika Server. It is designed to complement (or run completely independently of) the existing `tika.detector` module.

## Background & Prior Art

This work builds directly on several earlier efforts by the same research group:

- **NN-fileTypeDetection** – Multiple classifiers (Neural Nets, Random Forest, SVM, Decision Trees, etc.) trained on 256-bin byte histograms with beta companding.
- **ByteFrequency-ML** notebook – Early exploration of histogram + visualization techniques.
- **Tika-Govdocs-paper-2014** – Large-scale evaluation of Apache Tika against the GovDocs1 corpus.
- **TREC-DD Polar dataset** – 1.7 million naturally labeled records (158 GB) from polar science web crawls, with detailed per-MIME JSON aggregates. Excellent training resource for scientific and "long tail" formats (FITS, HDF, GRIB, etc.).
- **Apache Tika (TIKA-1582)** – The Java side has had `TrainedModelDetector` + `NNTrainedModel` support since Tika 1.9. This Python module is the spiritual sibling / training companion for that infrastructure.

The core technique (normalized 256-byte histogram → beta companding → centroid or ML classifier) is well-established in the digital forensics and file type identification literature.

## What Was Built

### 1. Clean `tika/bytefreq.py` Scaffold

A lightweight, dependency-minimal module with:

- **Histogram primitives**
  - `compute_histogram(source, max_bytes=1<<20)`
  - `compand(hist, beta=1.5)`
  - `compute_fingerprint(source, beta=1.5)` — the canonical feature vector

- **CentroidModel**
  - Simple but surprisingly effective mean-vector classifier per MIME type
  - Cosine similarity for scoring
  - `train()`, `predict(top_k=...)`, `save()`, `load()`
  - Persists as human-readable JSON

- **High-level detector API**
  - `ByteFreqDetector(model)`
  - `from_file()` and `from_buffer()` methods that deliberately mirror the signature style of `tika.detector`
  - Module-level convenience functions: `bytefreq.from_file(...)` and `bytefreq.from_buffer(...)`

- **Optional numpy acceleration**
  - Automatically used for histograms and vector math when `numpy` is installed. Pure Python fallback is always available.

### 2. Port + Fixes from NN-fileTypeDetection

The most valuable parts of the old preprocessor were extracted and modernized:

- Robust streaming byte table reader (correct Python 3 `bytes` handling — no more `ord()` bugs)
- Beta companding (default 1.5, matching the historical work)
- `generate_fingerprints_csv()` — walks a labeled directory tree and emits the classic CSV format expected by the old classifier training pipelines

All Python 2/3 compatibility bugs, undefined variables (`key`, `fileName`, `self.logger`, `output`, etc.), and broken file handling were eliminated.

### 3. Training Script / CLI

Fully functional command-line interface:

```bash
python -m tika.bytefreq --help
```

Subcommands:

- `generate-fingerprints <root-labeled-dir> <output.csv>`
- `train-centroid <labeled-root-dir> <model.json>`
- `detect <model.json> <path-or-dash>` (supports stdin with `-`)

This makes it easy to train on subsets of GovDocs1, the TREC-DD Polar data, or any custom labeled corpus using the classic subdirectory-as-label convention.

### 4. Tests

`tests/test_bytefreq.py` contains focused unit tests covering:

- Histogram and fingerprint computation on real files
- Companding behavior
- Model training and prediction
- Detector facade compatibility
- CSV generation
- Save/load roundtrips
- Edge cases (empty files, small inputs)

## Quick Usage

### Python API

```python
from tika import bytefreq

# 1. Train a model from a labeled directory tree
model = bytefreq.CentroidModel(beta=1.5)
model.train([
    ("application/pdf", "/data/pdfs/"),
    ("text/plain", "/data/text/"),
    ("image/jpeg", "/data/jpegs/"),
    # ... add as many classes as you have data for
])

model.save("my-bytefreq-model.json")

# 2. Use it
print(bytefreq.from_file("mystery.bin", model=model))

det = bytefreq.ByteFreqDetector(model)
print(det.from_buffer(b"\x89PNG\r\n\x1a\n..."))
print(det.predict("mystery.bin", top_k=3))
```

### Command Line

```bash
# Generate training fingerprints (for old ML pipelines or inspection)
python -m tika.bytefreq generate-fingerprints /data/labeled /tmp/fingerprints.csv

# Train a centroid model directly from a labeled directory
python -m tika.bytefreq train-centroid /data/labeled models/polar-v1.json --beta 1.5

# Detect with a trained model
python -m tika.bytefreq detect models/polar-v1.json mystery.bin --top-k 3

# Or from stdin
cat mystery.bin | python -m tika.bytefreq detect models/polar-v1.json -
```

## Directory Layout for Training

The `train-centroid` and `generate-fingerprints` commands expect this structure by default:

```
/data/labeled/
├── application/pdf/
│   ├── doc1.pdf
│   └── ...
├── text/plain/
│   ├── notes.txt
│   └── ...
├── image/jpeg/
│   └── photo.jpg
└── ...
```

Subdirectory names become the MIME type labels.

## Design Notes & Trade-offs

- **Centroid classifier first** — deliberately chose the simplest possible model (mean vectors + cosine) because it requires no heavy dependencies, is interpretable, and performs surprisingly well on byte frequency data.
- **No hard sklearn / PyTorch dependency** — keeps the core usable in minimal environments. More powerful models can be added later behind the same interface.
- **Beta companding preserved** — this non-linear scaling (emphasizing rarer bytes) has proven valuable in multiple published studies.
- **Designed for fallback / augmentation** — ideal for promoting `application/octet-stream` results or operating in air-gapped / sandboxed settings where you cannot run a full Tika Server.
- **Future Tika interoperability** — the JSON model format and fingerprint generation pipeline are intended to eventually feed models into (or be fed by) Tika's `TrainedModelDetector`.

## Next Steps / Roadmap (Ideas)

- Add a simple Polar manifest loader (consume the JSON aggregates from TREC-DD Polar directly)
- Expose `bytefreq` as a subcommand in the main `tika-python` CLI
- Ship a small set of pre-trained starter models for common broad categories
- Optional sklearn backends (RandomForest, etc.) while keeping the centroid path zero-dep
- Hierarchical detection (text vs binary first, then finer grained)
- Evaluation harness + scripts against held-out slices of GovDocs1 and TREC-DD Polar
- Bridge to produce `.nnmodel` files consumable by the Java `NNTrainedModel` in Tika

## References

- Apache Tika `TrainedModelDetector` (TIKA-1582)
- GovDocs1 corpus (digitalcorpora.org)
- TREC Dynamic Domain Polar dataset (trec-dd-polar)
- Previous internal repos: `NN-fileTypeDetection`, `ByteFrequency-ML`, `Tika-Govdocs-paper-2014`

---

**Status**: Experimental / research-quality scaffolding. The API is stable enough for experimentation and custom training, but the set of shipped models is currently empty (you must train your own).

Contributions, new training corpora, and model improvements are very welcome.