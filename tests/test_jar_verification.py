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

"""The jar this package downloads gets executed, so it has to be the right one.

The bug these cover: the server jar was cached at a predictable path in the
shared temp directory, and verified against a checksum file sitting next to it
at an equally predictable path. The remote checksum was fetched only when that
local file was absent. So a local user who created both /tmp/tika-server.jar
and /tmp/tika-server.jar.md5 before another user's first parse had their jar
validated against their own checksum, and then executed as that user.

Nothing here touches the network.
"""

import hashlib
import os
import stat
import sys

import pytest

import tika.tika as tika_module


FORGED = b"PK\x03\x04 not the apache tika server jar"


def digest_of(data, algo="sha512"):
    h = hashlib.new(algo)
    h.update(data)
    return h.hexdigest()


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """A cache directory standing in for the shared temp directory."""
    d = tmp_path / "cache"
    d.mkdir()
    monkeypatch.setattr(tika_module, "TikaCacheDir", str(d))
    monkeypatch.setattr(tika_module, "TikaJarPath", str(d))
    monkeypatch.setattr(tika_module, "TikaFilesPath", str(d))
    monkeypatch.setattr(tika_module, "TikaServerLogFilePath", str(d))
    # Any network use at all is a failure of the premise.
    def no_network(*a, **k):
        raise AssertionError("the network was used")
    monkeypatch.setattr(tika_module, "_urlretrieve", no_network)
    monkeypatch.setattr(tika_module.requests, "get", no_network)
    return d


def plant(cache, data=FORGED, sidecars=("md5", "sha1", "sha256", "sha512")):
    """What the attacker does: a jar, and checksums that agree with it."""
    jar = cache / "tika-server.jar"
    jar.write_bytes(data)
    for algo in sidecars:
        (cache / ("tika-server.jar." + algo)).write_text(digest_of(data, algo))
    return jar


# ------------------------------------------------------- the reported bug ---

def test_a_planted_jar_with_a_matching_checksum_is_not_trusted(cache):
    """The attack, directly. The sidecar must not be what decides this."""
    jar = plant(cache)
    assert tika_module.checkJarSig(tika_module.DefaultTikaServerJar, str(jar)) is False


def test_the_hash_algorithm_was_never_the_problem(cache, monkeypatch):
    """Upgrading md5 to sha512 would not have fixed anything.

    The old code read the digest from a file in the same directory the jar came
    from, so an attacker who could write one could write the other. A stronger
    algorithm changes nothing about that.
    """
    monkeypatch.setenv("TIKA_JAR_HASH_ALGO", "sha512")
    jar = plant(cache, sidecars=("sha512",))
    assert tika_module.checkJarSig(tika_module.DefaultTikaServerJar, str(jar)) is False


def test_no_checksum_file_is_read_even_when_one_exists(cache):
    """A sidecar holding the *correct* pinned digest must not launder a forgery."""
    jar = cache / "tika-server.jar"
    jar.write_bytes(FORGED)
    pinned = tika_module.TikaServerJarDigests[tika_module.TikaVersion]
    (cache / "tika-server.jar.sha512").write_text(pinned)
    (cache / "tika-server.jar.md5").write_text(digest_of(FORGED, "md5"))
    assert tika_module.checkJarSig(tika_module.DefaultTikaServerJar, str(jar)) is False


def test_verification_failure_refuses_to_start_anything(cache, monkeypatch):
    """The old failure branch deleted the jar, redownloaded, and ran it anyway."""
    plant(cache)

    def download_something_else(url, filename, **kwargs):
        with open(filename, "wb") as f:
            f.write(b"also not the jar")
        return filename

    monkeypatch.setattr(tika_module, "_urlretrieve", download_something_else)
    with pytest.raises(RuntimeError, match="refusing to run it"):
        tika_module.cachedServerJar(tika_module.DefaultTikaServerJar)


def test_a_rejected_download_leaves_nothing_behind(cache, monkeypatch):
    def download_something_else(url, filename, **kwargs):
        with open(filename, "wb") as f:
            f.write(b"also not the jar")
        return filename

    monkeypatch.setattr(tika_module, "_urlretrieve", download_something_else)
    with pytest.raises(RuntimeError):
        tika_module.cachedServerJar(tika_module.DefaultTikaServerJar)
    leftovers = sorted(p.name for p in cache.iterdir())
    assert leftovers == [], "a jar that failed verification was left at %s" % leftovers


# ------------------------------------------------------ the happy path ---

def test_a_jar_matching_the_expected_digest_is_accepted(cache, monkeypatch):
    payload = b"pretend this is tika-server"
    monkeypatch.setattr(tika_module, "TikaServerJarSha512", digest_of(payload))

    def download(url, filename, **kwargs):
        with open(filename, "wb") as f:
            f.write(payload)
        return filename

    monkeypatch.setattr(tika_module, "_urlretrieve", download)
    path = tika_module.cachedServerJar("https://example.invalid/tika-server.jar")
    assert os.path.isfile(path)
    assert open(path, "rb").read() == payload


def test_a_verified_jar_is_not_accompanied_by_a_checksum_file(cache, monkeypatch):
    """Writing the digest to disk is what created the attack surface."""
    payload = b"pretend this is tika-server"
    monkeypatch.setattr(tika_module, "TikaServerJarSha512", digest_of(payload))
    monkeypatch.setattr(
        tika_module, "_urlretrieve",
        lambda url, filename, **k: (open(filename, "wb").write(payload), filename)[1])
    tika_module.cachedServerJar("https://example.invalid/tika-server.jar")
    assert sorted(p.name for p in cache.iterdir()) == ["tika-server.jar"]


def test_a_cached_jar_is_reused_without_downloading_again(cache, monkeypatch):
    payload = b"pretend this is tika-server"
    monkeypatch.setattr(tika_module, "TikaServerJarSha512", digest_of(payload))
    jar = cache / "tika-server.jar"
    jar.write_bytes(payload)
    # _urlretrieve is the network stub that raises, so reaching it fails the test.
    assert tika_module.cachedServerJar(
        "https://example.invalid/tika-server.jar") == str(jar)


# --------------------------------------------------- where it downloads from ---

def test_the_default_jar_url_is_https(cache):
    """It was http://search.maven.org, so the jar and its checksum both
    travelled in plaintext and needed no local account to substitute."""
    assert tika_module.DefaultTikaServerJar.startswith("https://")


def test_the_default_jar_url_is_the_canonical_repository(cache):
    assert "repo1.maven.org/maven2/" in tika_module.DefaultTikaServerJar
    assert "search.maven.org" not in tika_module.DefaultTikaServerJar


def test_a_published_digest_is_not_trusted_over_plaintext(cache):
    """Over http, a published digest proves nothing: the same attacker who
    rewrites the jar in flight rewrites the digest in flight."""
    assert tika_module.publishedJarDigest(
        "http://example.invalid/tika-server.jar") == (None, None)


def test_this_release_pins_a_digest_for_the_version_it_ships(cache):
    """Bumping TIKA_VERSION without pinning its digest must not be silent."""
    assert tika_module.TikaVersion in tika_module.TikaServerJarDigests
    pinned = tika_module.TikaServerJarDigests[tika_module.TikaVersion]
    assert len(pinned) == 128 and all(c in "0123456789abcdef" for c in pinned)


def test_the_pinned_digest_is_what_is_checked(cache):
    algo, expected, source = tika_module.expectedJarDigest(
        tika_module.DefaultTikaServerJar)
    assert algo == "sha512"
    assert expected == tika_module.TikaServerJarDigests[tika_module.TikaVersion]
    assert "pinned" in source


def test_an_operator_can_override_the_expected_digest(cache, monkeypatch):
    monkeypatch.setattr(tika_module, "TikaServerJarSha512", "ab" * 64)
    algo, expected, source = tika_module.expectedJarDigest("https://x.invalid/j.jar")
    assert (algo, expected) == ("sha512", "ab" * 64)
    assert "TIKA_SERVER_JAR_SHA512" in source


# ----------------------------------------------------- the shared directory ---

def test_the_cache_does_not_default_to_the_shared_temp_directory(monkeypatch):
    import tempfile
    assert tika_module._defaultCacheDir() != tempfile.gettempdir()
    assert not tika_module._defaultCacheDir().startswith(
        tempfile.gettempdir() + os.sep + "tika-server")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
def test_a_symlink_where_the_jar_should_be_is_refused(cache, tmp_path):
    victim = tmp_path / "victim-secret"
    victim.write_bytes(b"not for the attacker")
    (cache / "tika-server.jar").symlink_to(victim)
    with pytest.raises(OSError):
        tika_module.fileDigest(str(cache / "tika-server.jar"))


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
def test_a_symlinked_log_is_not_written_through(cache, tmp_path, capsys):
    victim = tmp_path / "dot-profile"
    victim.write_text("# the victim's shell profile\n")
    link = cache / "tika.log"
    link.symlink_to(victim)
    assert tika_module._safeFileHandler(str(link)) is None
    assert victim.read_text() == "# the victim's shell profile\n"
    assert "not logging to" in capsys.readouterr().err


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX ownership")
def test_a_file_owned_by_another_user_is_refused(cache, monkeypatch):
    jar = cache / "tika-server.jar"
    jar.write_bytes(FORGED)
    # Stand in for a file UID 1002 created before we got here.
    monkeypatch.setattr(os, "geteuid", lambda: os.stat(str(jar)).st_uid + 1)
    with pytest.raises(RuntimeError, match="owned by uid"):
        tika_module.fileDigest(str(jar))


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_a_world_writable_jar_is_refused(cache):
    jar = cache / "tika-server.jar"
    jar.write_bytes(FORGED)
    os.chmod(str(jar), 0o666)
    with pytest.raises(RuntimeError, match="writable by other users"):
        tika_module.fileDigest(str(jar))


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_the_default_cache_directory_is_private(tmp_path, monkeypatch):
    d = tmp_path / "mine"
    d.mkdir(mode=0o755)
    monkeypatch.setattr(tika_module, "TikaCacheDir", str(d))
    tika_module._prepareCacheDir(str(d), ours=True)
    assert stat.S_IMODE(os.stat(str(d)).st_mode) == 0o700


# ----------------------------------------------- where the cache goes ---

class Response:
    """Just enough of requests' response for publishedJarDigest."""

    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


def test_each_platform_gets_a_directory_under_its_own_conventions(monkeypatch):
    # An absolute path in this platform's own syntax: the assertion is that
    # LOCALAPPDATA is what gets consulted on Windows, and a C:\... literal is
    # not absolute when these tests run on POSIX.
    local_app_data = os.path.join(os.sep, "Users", "x", "AppData", "Local")
    monkeypatch.setattr(tika_module, "Windows", True)
    monkeypatch.setenv("LOCALAPPDATA", local_app_data)
    assert tika_module._defaultCacheDir() == os.path.join(local_app_data, "tika")

    monkeypatch.setattr(tika_module, "Windows", False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CACHE_HOME", os.path.join(os.sep, "xdg"))
    assert tika_module._defaultCacheDir() == os.path.join(os.sep, "xdg", "tika")

    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr(os.path, "expanduser", lambda p: os.path.join(os.sep, "home", "x"))
    assert tika_module._defaultCacheDir() == os.path.join(
        os.sep, "home", "x", ".cache", "tika")


def test_with_no_home_directory_it_still_does_not_use_the_shared_one(monkeypatch):
    """Falling back to the shared directory itself is what caused this bug."""
    import tempfile as _tempfile
    monkeypatch.setattr(tika_module, "Windows", False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr(os.path, "expanduser", lambda p: "~")
    chosen = tika_module._defaultCacheDir()
    assert chosen != _tempfile.gettempdir()
    assert os.path.basename(os.path.dirname(chosen)).startswith("tika-")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
def test_a_symlinked_cache_directory_is_refused(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(RuntimeError, match="symlink"):
        tika_module._prepareCacheDir(str(link), ours=True)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX ownership")
def test_a_cache_directory_owned_by_someone_else_is_refused(tmp_path, monkeypatch):
    d = tmp_path / "theirs"
    d.mkdir()
    monkeypatch.setattr(os, "geteuid", lambda: os.stat(str(d)).st_uid + 1)
    with pytest.raises(RuntimeError, match="owned by uid"):
        tika_module._prepareCacheDir(str(d), ours=True)


def test_an_undirectoryable_cache_path_is_reported_clearly(tmp_path):
    blocker = tmp_path / "a-file-not-a-directory"
    blocker.write_text("")
    with pytest.raises(RuntimeError, match="unable to create the tika directory"):
        tika_module._prepareCacheDir(str(blocker / "cache"), ours=True)


def test_a_caller_chosen_directory_is_not_second_guessed(tmp_path):
    """TIKA_PATH is the operator's business; per-file checks cover safety.

    On macOS /tmp is itself a symlink, so refusing symlinked directories here
    would break ordinary setups.
    """
    d = tmp_path / "chosen"
    d.mkdir(mode=0o755)
    assert tika_module._prepareCacheDir(str(d), ours=False) == str(d)


# ------------------------------------------- the published digest, in memory ---

def test_the_strongest_published_digest_is_preferred(cache, monkeypatch):
    payload = b"x"
    served = {
        "https://e.invalid/j.jar.sha512": Response(200, digest_of(payload, "sha512")),
        "https://e.invalid/j.jar.sha256": Response(200, digest_of(payload, "sha256")),
    }
    monkeypatch.setattr(tika_module.requests, "get",
                        lambda url, **k: served.get(url, Response(404, "")))
    assert tika_module.publishedJarDigest("https://e.invalid/j.jar") == (
        "sha512", digest_of(payload, "sha512"))


def test_a_weaker_digest_is_used_when_that_is_all_there_is(cache, monkeypatch):
    """Maven Central publishes sha1 and md5 for this artifact, not sha512."""
    payload = b"x"
    served = {"https://e.invalid/j.jar.sha1": Response(200, digest_of(payload, "sha1"))}
    monkeypatch.setattr(tika_module.requests, "get",
                        lambda url, **k: served.get(url, Response(404, "")))
    assert tika_module.publishedJarDigest("https://e.invalid/j.jar") == (
        "sha1", digest_of(payload, "sha1"))


def test_an_html_error_page_is_not_mistaken_for_a_digest(cache, monkeypatch):
    """getRemoteJar used to write whatever came back into the checksum file."""
    monkeypatch.setattr(tika_module.requests, "get",
                        lambda url, **k: Response(200, "<html>404 Not Found</html>"))
    assert tika_module.publishedJarDigest("https://e.invalid/j.jar") == (None, None)


def test_an_empty_body_is_not_a_digest(cache, monkeypatch):
    monkeypatch.setattr(tika_module.requests, "get",
                        lambda url, **k: Response(200, "   \n"))
    assert tika_module.publishedJarDigest("https://e.invalid/j.jar") == (None, None)


def test_a_digest_of_the_wrong_length_is_rejected(cache, monkeypatch):
    monkeypatch.setattr(tika_module.requests, "get",
                        lambda url, **k: Response(200, "abc123"))
    assert tika_module.publishedJarDigest("https://e.invalid/j.jar") == (None, None)


def test_a_network_failure_is_not_a_digest(cache, monkeypatch):
    def boom(url, **k):
        raise tika_module.requests.RequestException("no route to host")
    monkeypatch.setattr(tika_module.requests, "get", boom)
    assert tika_module.publishedJarDigest("https://e.invalid/j.jar") == (None, None)


def test_a_published_digest_is_used_when_nothing_is_pinned(cache, monkeypatch):
    payload = b"x"
    monkeypatch.setattr(tika_module.requests, "get",
                        lambda url, **k: Response(200, digest_of(payload))
                        if url.endswith(".sha512") else Response(404, ""))
    algo, expected, source = tika_module.expectedJarDigest("https://e.invalid/j.jar")
    assert (algo, expected) == ("sha512", digest_of(payload))
    assert "published at" in source


def test_an_unpinned_version_says_so_rather_than_failing_quietly(cache, monkeypatch, caplog):
    """Bumping TIKA_VERSION without pinning a digest must be loud."""
    monkeypatch.setattr(tika_module, "TikaVersion", "99.99.99")
    monkeypatch.setattr(tika_module, "DefaultTikaServerJar", "https://e.invalid/j.jar")
    monkeypatch.setattr(tika_module.requests, "get", lambda url, **k: Response(404, ""))
    with caplog.at_level("WARNING"):
        assert tika_module.expectedJarDigest("https://e.invalid/j.jar") == (
            None, None, None)
    assert "no pinned digest" in caplog.text


def test_an_unverifiable_jar_is_allowed_but_announced(cache, monkeypatch, caplog):
    """A private build the operator points at is theirs, but say so out loud."""
    jar = cache / "tika-server.jar"
    jar.write_bytes(FORGED)
    monkeypatch.setattr(tika_module, "expectedJarDigest",
                        lambda url: (None, None, None))
    with caplog.at_level("WARNING"):
        assert tika_module.checkJarSig("https://e.invalid/j.jar", str(jar)) is True
    assert "cannot verify" in caplog.text


# ---------------------------------------------------- a jar given by path ---

def test_a_local_jar_is_checked_where_it_lies_and_not_copied(cache, tmp_path, monkeypatch):
    payload = b"somebody's own build of tika-server"
    own = tmp_path / "my-tika-server.jar"
    own.write_bytes(payload)
    monkeypatch.setattr(tika_module, "TikaServerJarSha512", digest_of(payload))
    assert tika_module.cachedServerJar(str(own)) == str(own)
    assert not (cache / "tika-server.jar").exists()


def test_a_local_jar_that_fails_verification_is_refused(cache, tmp_path, monkeypatch):
    own = tmp_path / "my-tika-server.jar"
    own.write_bytes(b"not what the operator said it would be")
    monkeypatch.setattr(tika_module, "TikaServerJarSha512", "ab" * 64)
    with pytest.raises(RuntimeError, match="refusing to run it"):
        tika_module.cachedServerJar(str(own))


# ------------------------------------------------------ the old location ---

def test_a_leftover_jar_in_the_shared_directory_is_mentioned_once(
        cache, tmp_path, monkeypatch, caplog):
    """Mentioned, not deleted: on a shared host it may not be ours to delete."""
    shared = tmp_path / "shared-tmp"
    shared.mkdir()
    (shared / "tika-server.jar").write_bytes(b"left over from an older release")
    monkeypatch.setattr(tika_module.tempfile, "gettempdir", lambda: str(shared))
    monkeypatch.setattr(tika_module, "_legacyCacheWarned", False)
    with caplog.at_level("WARNING"):
        tika_module._warnAboutLegacyCache()
    assert "no longer used" in caplog.text
    assert (shared / "tika-server.jar").exists(), "it should not be deleted"

    caplog.clear()
    with caplog.at_level("WARNING"):
        tika_module._warnAboutLegacyCache()
    assert caplog.text == "", "it should be said once, not on every parse"


def test_a_stale_part_file_does_not_block_a_later_download(cache, monkeypatch):
    payload = b"pretend this is tika-server"
    monkeypatch.setattr(tika_module, "TikaServerJarSha512", digest_of(payload))
    stale = cache / ("tika-server.jar.%d.part" % os.getpid())
    stale.write_bytes(b"interrupted earlier")

    def download(url, filename, **kwargs):
        with open(filename, "wb") as f:
            f.write(payload)
        return filename

    monkeypatch.setattr(tika_module, "_urlretrieve", download)
    path = tika_module.cachedServerJar("https://e.invalid/tika-server.jar")
    assert open(path, "rb").read() == payload
    assert sorted(p.name for p in cache.iterdir()) == ["tika-server.jar"]


def test_a_download_that_raises_leaves_nothing_behind(cache, monkeypatch):
    def fails(url, filename, **kwargs):
        with open(filename, "wb") as f:
            f.write(b"partial")
        raise tika_module.requests.RequestException("connection reset")

    monkeypatch.setattr(tika_module, "_urlretrieve", fails)
    with pytest.raises(tika_module.requests.RequestException):
        tika_module.cachedServerJar("https://e.invalid/tika-server.jar")
    assert sorted(p.name for p in cache.iterdir()) == []
