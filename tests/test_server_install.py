# SPDX-License-Identifier: Apache-2.0
"""Unit tests for locating, downloading, verifying and extracting the Tika server.

These run without a Tika server, Java or network access.
"""

import hashlib
import os
import subprocess
import zipfile
from pathlib import Path
from unittest import mock

import pytest
import requests

import tika.tika
from tika.tika import TikaDownloadError, TikaException

DIST_URL = "https://dlcdn.apache.org/tika/9.9.9/tika-server-standard-9.9.9.zip"
ARCHIVE_URL = "https://archive.apache.org/dist/tika/9.9.9/tika-server-standard-9.9.9.zip"
SHA512 = hashlib.sha512(b"x").hexdigest()


def make_dist_zip(path, version="9.9.9", top_level_dir=None):
    prefix = f"{top_level_dir}/" if top_level_dir else ""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{prefix}tika-server-standard-{version}.jar", b"launcher")
        archive.writestr(f"{prefix}lib/tika-core-{version}.jar", b"core")
        archive.writestr(f"{prefix}plugins/tika-pipes-file-system/plugin.jar", b"plugin")
        archive.writestr(f"{prefix}LICENSE", b"Apache-2.0")
    return path


def sha512_of(path):
    return hashlib.sha512(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def install_env(tmp_path, monkeypatch):
    """Point the module-level cache config at a scratch directory."""
    monkeypatch.setattr(tika.tika, "TikaJarPath", str(tmp_path / "cache"))
    monkeypatch.setattr(tika.tika, "TikaJarHashAlgo", "sha512")
    return tmp_path


class FakeDownloader:
    """Stand-in for ``_urlretrieve`` serving an in-memory set of files by URL."""

    def __init__(self, files=None, missing=()):
        self.files = dict(files or {})
        self.missing = set(missing)
        self.requested = []

    def __call__(self, url, filename, **kwargs):
        self.requested.append(url)
        if url in self.missing or url not in self.files:
            raise TikaDownloadError(f"Failed to download {url}: 404", 404)
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        Path(filename).write_bytes(self.files[url])
        return filename


# --- pure helpers -----------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        SHA512,
        SHA512.upper(),
        SHA512 + "\n",
        f"{SHA512}  tika-server-standard-9.9.9.zip\n",
        "tika-server-standard-9.9.9.zip: "
        + " ".join(SHA512[i : i + 4].upper() for i in range(0, 64, 4))
        + "\n                                "
        + " ".join(SHA512[i : i + 4].upper() for i in range(64, 128, 4))
        + "\n",
    ],
)
def test_parse_checksum_file_accepts_common_layouts(text):
    assert tika.tika._parseChecksumFile(text, "sha512") == SHA512


@pytest.mark.parametrize("text", ["", "not a digest", SHA512[:-2], f"{SHA512}ab"])
def test_parse_checksum_file_rejects_garbage(text):
    with pytest.raises(TikaException):
        tika.tika._parseChecksumFile(text, "sha512")


def test_parse_checksum_file_honours_algorithm():
    md5 = hashlib.md5(b"x").hexdigest()
    assert tika.tika._parseChecksumFile(md5, "md5") == md5
    with pytest.raises(TikaException):
        tika.tika._parseChecksumFile(md5, "sha512")


@pytest.mark.parametrize(
    "url, expected",
    [
        (DIST_URL, ARCHIVE_URL),
        ("https://downloads.apache.org/tika/9.9.9/tika-server-standard-9.9.9.zip", ARCHIVE_URL),
        (ARCHIVE_URL, None),
        ("https://repo1.maven.org/maven2/org/apache/tika/x.jar", None),
        ("https://dlcdn.apache.org/solr/9.0.0/solr.tgz", None),
        ("/tmp/tika-server-standard-9.9.9.zip", None),
    ],
)
def test_fallback_distribution_url(url, expected):
    assert tika.tika._fallbackDistributionUrl(url) == expected


def test_local_path_from_url_or_path(tmp_path):
    target = tmp_path / "tika-server-standard-9.9.9.zip"
    assert tika.tika._localPathFromUrlOrPath(str(target)) == str(target)
    assert tika.tika._localPathFromUrlOrPath(target.as_uri()) == str(target)
    relative = tika.tika._localPathFromUrlOrPath("dist/x.zip")
    assert os.path.isabs(relative) and relative.endswith("x.zip")
    windows = tika.tika._localPathFromUrlOrPath(r"C:\tika\x.zip")
    assert windows is not None and windows.endswith("x.zip")
    assert tika.tika._localPathFromUrlOrPath(DIST_URL) is None
    assert tika.tika._localPathFromUrlOrPath("http://localhost:9998/x.zip") is None


@pytest.mark.parametrize(
    "output, expected",
    [
        ('openjdk version "17.0.2" 2022-01-18\nOpenJDK Runtime Environment', 17),
        ('java version "1.8.0_292"\nJava(TM) SE Runtime Environment', 8),
        ('openjdk version "25.0.4.1" 2026-08-18', 25),
        ('Picked up JAVA_TOOL_OPTIONS: -Dhttp.proxyHost=x\nopenjdk version "21" 2023-09-19', 21),
        ("gibberish", None),
    ],
)
def test_java_major_version(output, expected):
    completed = subprocess.CompletedProcess(["java", "-version"], 0, stdout="", stderr=output)
    with mock.patch("tika.tika.subprocess.run", return_value=completed):
        assert tika.tika._javaMajorVersion("java") == expected


def test_java_major_version_missing_binary():
    with mock.patch("tika.tika.subprocess.run", side_effect=FileNotFoundError):
        assert tika.tika._javaMajorVersion("/nonexistent/java") is None


def test_jar_needs_lib_dir(tmp_path):
    thin = tmp_path / "thin.jar"
    with zipfile.ZipFile(thin, "w") as jar:
        jar.writestr(
            "META-INF/MANIFEST.MF",
            "Manifest-Version: 1.0\r\nMain-Class: org.apache.tika.server.core.TikaServerCli\r\n"
            "Class-Path: lib/tika-server-core-9.9.9.jar lib/tika-core-9.9.9.jar lib/very-long-nam\r\n"
            " e-that-wraps.jar\r\n",
        )
    fat = tmp_path / "fat.jar"
    with zipfile.ZipFile(fat, "w") as jar:
        jar.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\r\nMain-Class: x.Main\r\n")
    assert tika.tika._jarNeedsLibDir(str(thin)) is True
    assert tika.tika._jarNeedsLibDir(str(fat)) is False
    assert tika.tika._jarNeedsLibDir(str(tmp_path / "missing.jar")) is False


# --- extraction --------------------------------------------------------------------


def test_extract_server_distribution(tmp_path):
    archive = make_dist_zip(tmp_path / "dist.zip")
    install_dir = tmp_path / "cache" / "tika-server-standard-9.9.9"

    tika.tika._extractServerDistribution(str(archive), str(install_dir))

    assert (install_dir / "tika-server-standard-9.9.9.jar").read_bytes() == b"launcher"
    assert (install_dir / "lib" / "tika-core-9.9.9.jar").is_file()
    assert (install_dir / "plugins" / "tika-pipes-file-system" / "plugin.jar").is_file()
    assert os.listdir(install_dir.parent) == ["tika-server-standard-9.9.9"], "no temp dirs left behind"
    assert tika.tika._findServerJar(str(install_dir)) == str(install_dir / "tika-server-standard-9.9.9.jar")


def test_extract_server_distribution_unwraps_single_top_level_dir(tmp_path):
    archive = make_dist_zip(tmp_path / "dist.zip", top_level_dir="tika-server-standard-9.9.9")
    install_dir = tmp_path / "tika-server-standard-9.9.9"
    tika.tika._extractServerDistribution(str(archive), str(install_dir))
    assert tika.tika._findServerJar(str(install_dir)) == str(install_dir / "tika-server-standard-9.9.9.jar")


def test_extract_server_distribution_keeps_existing_install(tmp_path):
    archive = make_dist_zip(tmp_path / "dist.zip")
    install_dir = tmp_path / "tika-server-standard-9.9.9"
    tika.tika._extractServerDistribution(str(archive), str(install_dir))
    (install_dir / "marker").write_text("first")
    tika.tika._extractServerDistribution(str(archive), str(install_dir))
    assert (install_dir / "marker").read_text() == "first"
    assert sorted(os.listdir(tmp_path)) == ["dist.zip", "tika-server-standard-9.9.9"], "no temp dirs left behind"


def test_extract_server_distribution_bad_zip_leaves_nothing(tmp_path):
    archive = tmp_path / "dist.zip"
    archive.write_bytes(b"not a zip")
    install_dir = tmp_path / "tika-server-standard-9.9.9"
    with pytest.raises(zipfile.BadZipFile):
        tika.tika._extractServerDistribution(str(archive), str(install_dir))
    assert not install_dir.exists()
    assert os.listdir(tmp_path) == ["dist.zip"]


def test_find_server_jar_requires_lib_dir(tmp_path):
    (tmp_path / "tika-server-standard-9.9.9.jar").write_bytes(b"x")
    assert tika.tika._findServerJar(str(tmp_path)) is None
    (tmp_path / "lib").mkdir()
    assert tika.tika._findServerJar(str(tmp_path)) == str(tmp_path / "tika-server-standard-9.9.9.jar")
    assert tika.tika._findServerJar(str(tmp_path / "missing")) is None


def test_find_server_jar_accepts_single_unnamed_jar(tmp_path):
    (tmp_path / "lib").mkdir()
    (tmp_path / "custom-build.jar").write_bytes(b"x")
    assert tika.tika._findServerJar(str(tmp_path)) == str(tmp_path / "custom-build.jar")
    (tmp_path / "another.jar").write_bytes(b"x")
    assert tika.tika._findServerJar(str(tmp_path)) is None


# --- download layer ----------------------------------------------------------------


def test_urlretrieve_reports_http_status(tmp_path):
    response = mock.Mock()
    response.raise_for_status.side_effect = requests.HTTPError(response=mock.Mock(status_code=404))
    target = tmp_path / "x.zip"
    with mock.patch("tika.tika.requests.get", return_value=response):
        with pytest.raises(TikaDownloadError) as excinfo:
            tika.tika._urlretrieve("https://example.org/x.zip", str(target))
    assert excinfo.value.status_code == 404
    assert not target.exists()


def test_urlretrieve_connection_error_has_no_status(tmp_path):
    with mock.patch("tika.tika.requests.get", side_effect=requests.ConnectionError("refused")):
        with pytest.raises(TikaDownloadError) as excinfo:
            tika.tika._urlretrieve("https://example.org/x.zip", str(tmp_path / "x.zip"))
    assert excinfo.value.status_code is None


def test_download_with_fallback_retries_on_archive(tmp_path, monkeypatch):
    downloader = FakeDownloader({ARCHIVE_URL: b"zip"}, missing={DIST_URL})
    monkeypatch.setattr(tika.tika, "_urlretrieve", downloader)
    target = tmp_path / "x.zip"
    tika.tika._downloadWithFallback(DIST_URL, str(target))
    assert downloader.requested == [DIST_URL, ARCHIVE_URL]
    assert target.read_bytes() == b"zip"


def test_download_with_fallback_does_not_retry_other_urls(tmp_path, monkeypatch):
    url = "https://repo1.maven.org/maven2/org/apache/tika/x.jar"
    downloader = FakeDownloader(missing={url})
    monkeypatch.setattr(tika.tika, "_urlretrieve", downloader)
    with pytest.raises(TikaDownloadError):
        tika.tika._downloadWithFallback(url, str(tmp_path / "x.jar"))
    assert downloader.requested == [url]


# --- ensureTikaServerJar -----------------------------------------------------------


@pytest.fixture
def remote_dist(install_env, tmp_path, monkeypatch):
    """A fake remote hosting a valid zip and its sha512 sidecar under DIST_URL."""
    archive = make_dist_zip(tmp_path / "upstream.zip")
    downloader = FakeDownloader(
        {DIST_URL: archive.read_bytes(), DIST_URL + ".sha512": (sha512_of(archive) + "\n").encode()}
    )
    monkeypatch.setattr(tika.tika, "_urlretrieve", downloader)
    return downloader


def test_ensure_downloads_verifies_and_extracts(install_env, remote_dist):
    cache = install_env / "cache"

    jar = tika.tika.ensureTikaServerJar(DIST_URL)

    assert jar == str(cache / "tika-server-standard-9.9.9" / "tika-server-standard-9.9.9.jar")
    assert (cache / "tika-server-standard-9.9.9" / "lib").is_dir()
    assert (cache / "tika-server-standard-9.9.9.zip").is_file(), "archive kept for later re-extraction"
    assert (cache / "tika-server-standard-9.9.9.zip.sha512").is_file()
    assert remote_dist.requested == [DIST_URL, DIST_URL + ".sha512"]


def test_ensure_reuses_extracted_distribution(install_env, remote_dist):
    first = tika.tika.ensureTikaServerJar(DIST_URL)
    remote_dist.requested.clear()
    with mock.patch("tika.tika._fileDigest", side_effect=AssertionError("must not hash again")):
        assert tika.tika.ensureTikaServerJar(DIST_URL) == first
    assert remote_dist.requested == []


def test_ensure_redownloads_once_on_checksum_mismatch(install_env, remote_dist):
    remote_dist.files[DIST_URL + ".sha512"] = (SHA512 + "\n").encode()  # wrong digest
    with pytest.raises(TikaException, match="Checksum mismatch"):
        tika.tika.ensureTikaServerJar(DIST_URL)
    assert remote_dist.requested == [DIST_URL, DIST_URL + ".sha512", DIST_URL, DIST_URL + ".sha512"]
    assert not (install_env / "cache" / "tika-server-standard-9.9.9").exists()


def test_ensure_falls_back_to_archive(install_env, remote_dist):
    remote_dist.files[ARCHIVE_URL] = remote_dist.files.pop(DIST_URL)
    remote_dist.files[ARCHIVE_URL + ".sha512"] = remote_dist.files.pop(DIST_URL + ".sha512")

    jar = tika.tika.ensureTikaServerJar(DIST_URL)

    assert jar.endswith("tika-server-standard-9.9.9.jar")
    assert remote_dist.requested == [DIST_URL, ARCHIVE_URL, DIST_URL + ".sha512", ARCHIVE_URL + ".sha512"]


def test_ensure_local_zip_via_file_url(install_env, tmp_path, monkeypatch):
    archive = make_dist_zip(tmp_path / "offline" / "tika-server-standard-9.9.9.zip")
    (tmp_path / "offline" / "tika-server-standard-9.9.9.zip.sha512").write_text(sha512_of(archive))
    monkeypatch.setattr(tika.tika, "_urlretrieve", mock.Mock(side_effect=AssertionError("no network")))

    jar = tika.tika.ensureTikaServerJar(archive.as_uri())

    assert jar == str(install_env / "cache" / "tika-server-standard-9.9.9" / "tika-server-standard-9.9.9.jar")
    assert archive.is_file(), "the user's archive is left in place"
    assert not (install_env / "cache" / "tika-server-standard-9.9.9.zip").exists(), "not copied"


def test_ensure_local_zip_plain_path_without_sidecar_warns(install_env, tmp_path, monkeypatch, caplog):
    archive = make_dist_zip(tmp_path / "offline" / "tika-server-standard-9.9.9.zip")
    monkeypatch.setattr(tika.tika, "_urlretrieve", mock.Mock(side_effect=AssertionError("no network")))

    with caplog.at_level("WARNING", logger="tika.tika"):
        jar = tika.tika.ensureTikaServerJar(str(archive))

    assert jar.endswith("tika-server-standard-9.9.9.jar")
    assert "skipping verification" in caplog.text


def test_ensure_local_zip_with_bad_sidecar_fails_without_deleting(install_env, tmp_path):
    archive = make_dist_zip(tmp_path / "offline" / "tika-server-standard-9.9.9.zip")
    (tmp_path / "offline" / "tika-server-standard-9.9.9.zip.sha512").write_text(SHA512)

    with pytest.raises(TikaException, match="Checksum mismatch"):
        tika.tika.ensureTikaServerJar(str(archive))

    assert archive.is_file()
    assert not (install_env / "cache" / "tika-server-standard-9.9.9").exists()


def test_ensure_local_jar_override_is_used_as_is(install_env, tmp_path):
    unpacked = tmp_path / "unpacked"
    (unpacked / "lib").mkdir(parents=True)
    jar = unpacked / "tika-server-standard-9.9.9.jar"
    jar.write_bytes(b"launcher")

    assert tika.tika.ensureTikaServerJar(str(jar)) == str(jar)
    assert tika.tika.ensureTikaServerJar(jar.as_uri()) == str(jar)
    with pytest.raises(TikaException, match="does not exist"):
        tika.tika.ensureTikaServerJar(str(tmp_path / "missing.jar"))


def test_ensure_remote_jar_override_is_downloaded_and_verified(install_env, monkeypatch):
    url = "https://repo1.maven.org/maven2/org/apache/tika/tika-server-standard/3.3.2/tika-server-standard-3.3.2.jar"
    downloader = FakeDownloader({url: b"fat jar", url + ".sha512": hashlib.sha512(b"fat jar").hexdigest().encode()})
    monkeypatch.setattr(tika.tika, "_urlretrieve", downloader)

    jar = tika.tika.ensureTikaServerJar(url)

    assert jar == str(install_env / "cache" / "tika-server-standard-3.3.2.jar")
    assert Path(jar).read_bytes() == b"fat jar"
    assert downloader.requested == [url, url + ".sha512"]
    downloader.requested.clear()
    assert tika.tika.ensureTikaServerJar(url) == jar
    assert downloader.requested == [], "cached jar is reused"


def test_ensure_rejects_url_without_file_name(install_env):
    with pytest.raises(TikaException, match="file name"):
        tika.tika.ensureTikaServerJar("https://dlcdn.apache.org/tika/")
