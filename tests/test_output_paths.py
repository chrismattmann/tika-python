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

"""Where parseAndSave writes, and what it refuses to write through.

The output name is derived from the input name, so it is predictable, which
makes a symlink planted at it a way to have tika write through to somewhere
else as whoever is running it. Unlike the cache, the directory itself is the
caller's choice and may legitimately be shared, so ownership is not
second-guessed here -- only the link is refused.
"""

import os
import stat
import sys

import pytest

import tika.tika as tika_module


@pytest.fixture
def no_server(monkeypatch):
    """parse1 without a Tika server behind it."""
    monkeypatch.setattr(
        tika_module, "parse1",
        lambda option, path, *a, **k: (200, '{"Content-Type": "text/plain"}'))


def test_metadata_is_written_to_the_output_directory(tmp_path, no_server):
    source = tmp_path / "a.txt"
    source.write_text("hello")
    out = tmp_path / "out"
    out.mkdir()

    written = tika_module.parseAndSave("meta", [str(source)], outDir=str(out))

    assert written == [str(out / "a.txt_meta.json")]
    assert os.path.isfile(written[0])
    assert "Content-Type" in open(written[0]).read()


def test_with_no_output_directory_it_actually_saves(tmp_path, no_server):
    """It used to return a filename it had not written.

    The write sat inside the `else` for the outDir case, so parseAndSave with
    no outDir computed a path, saved nothing, and handed back the name of a
    file that did not exist -- in a function called parseAndSave, whose
    docstring says it writes the metadata.
    """
    source = tmp_path / "b.txt"
    source.write_text("hello")

    written = tika_module.parseAndSave("meta", [str(source)])

    assert written == [str(source) + "_meta.json"]
    assert os.path.isfile(written[0]), "parseAndSave returned a path it never wrote"
    assert "Content-Type" in open(written[0]).read()


def test_every_input_gets_its_own_output(tmp_path, no_server):
    out = tmp_path / "out"
    out.mkdir()
    sources = []
    for name in ("one.txt", "two.txt", "three.txt"):
        f = tmp_path / name
        f.write_text(name)
        sources.append(str(f))

    written = tika_module.parseAndSave("meta", sources, outDir=str(out))

    assert len(written) == 3
    assert all(os.path.isfile(p) for p in written)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
def test_a_symlink_at_the_output_name_is_not_written_through(tmp_path, no_server):
    source = tmp_path / "c.txt"
    source.write_text("hello")
    out = tmp_path / "out"
    out.mkdir()

    victim = tmp_path / "victim.conf"
    victim.write_text("the victim's configuration\n")
    (out / "c.txt_meta.json").symlink_to(victim)

    with pytest.raises(OSError):
        tika_module.parseAndSave("meta", [str(source)], outDir=str(out))

    assert victim.read_text() == "the victim's configuration\n", \
        "the metadata was written through the symlink"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_a_shared_output_directory_is_still_allowed(tmp_path, no_server):
    """The caller chose it. Refusing it would break ordinary use."""
    source = tmp_path / "d.txt"
    source.write_text("hello")
    out = tmp_path / "shared-out"
    out.mkdir()
    os.chmod(str(out), 0o777)

    written = tika_module.parseAndSave("meta", [str(source)], outDir=str(out))
    assert os.path.isfile(written[0])


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_the_umask_still_decides_the_output_permissions(tmp_path, no_server):
    """Not forced to 0600: these are outputs somebody asked for, and the plain
    open() this replaced let the umask decide."""
    source = tmp_path / "e.txt"
    source.write_text("hello")
    out = tmp_path / "out"
    out.mkdir()

    previous = os.umask(0o022)
    try:
        written = tika_module.parseAndSave("meta", [str(source)], outDir=str(out))
    finally:
        os.umask(previous)

    assert stat.S_IMODE(os.stat(written[0]).st_mode) == 0o644


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_an_existing_output_file_is_overwritten_not_appended(tmp_path, no_server):
    source = tmp_path / "f.txt"
    source.write_text("hello")
    out = tmp_path / "out"
    out.mkdir()
    stale = out / "f.txt_meta.json"
    stale.write_text("x" * 5000)

    tika_module.parseAndSave("meta", [str(source)], outDir=str(out))
    assert stale.read_text().count("Content-Type") == 1
    assert "xxxx" not in stale.read_text()


# ------------------------------------------- the opener's two callers differ ---

def test_a_cache_file_is_private_and_an_output_file_is_not(tmp_path):
    cache_file = tmp_path / "cache.bin"
    with tika_module._openPrivate(str(cache_file), 'wb') as f:
        f.write(b"x")
    output_file = tmp_path / "output.json"
    with tika_module._openPrivate(str(output_file), 'w', checkOwner=False,
                                  encoding='utf-8', perm=0o666) as f:
        f.write("x")
    if sys.platform != "win32":
        assert stat.S_IMODE(os.stat(str(cache_file)).st_mode) == 0o600


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX ownership")
def test_ownership_is_checked_for_a_cache_file_and_not_for_an_output(
        tmp_path, monkeypatch):
    target = tmp_path / "g.json"
    target.write_text("")
    monkeypatch.setattr(os, "geteuid", lambda: os.stat(str(target)).st_uid + 1)

    with pytest.raises(RuntimeError, match="owned by uid"):
        tika_module._openPrivate(str(target), 'wb')

    # Same file, as an output the caller named: allowed.
    with tika_module._openPrivate(str(target), 'w', checkOwner=False,
                                  encoding='utf-8', perm=0o666) as f:
        f.write("ok")
    assert target.read_text() == "ok"


def test_text_mode_writes_utf8(tmp_path):
    target = tmp_path / "h.json"
    with tika_module._openPrivate(str(target), 'w', checkOwner=False,
                                  encoding='utf-8', perm=0o666) as f:
        f.write(u"café")
    assert target.read_bytes() == u"café".encode("utf-8")
