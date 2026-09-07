"""tar / tar.gz / tgz archives behave exactly like zips."""
import gzip
import io
import tarfile

import pytest

from mast_validate.runner import archive_kind, validate_submission
from tests.conftest import dumps_jsonl, records_for, track_members


def make_tar(path, members: dict, mode="w:gz", infos=()):
    with tarfile.open(path, mode) as tf:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        for info, data in infos:
            tf.addfile(info, io.BytesIO(data) if data is not None else None)
    return path


@pytest.mark.parametrize("mode,suffix", [("w:gz", ".tar.gz"), ("w:gz", ".tgz"), ("w", ".tar"), ("w:bz2", ".tar.bz2")])
def test_full_track_tar(tmp_path, mode, suffix):
    t = make_tar(tmp_path / f"indic{suffix}", track_members("indic", prefix="runs/"), mode)
    assert archive_kind(t) == "tar"
    r = validate_submission(t, track="indic")
    assert r.status == "ok" and len([f for f in r.files if f.present]) == 9


def test_single_gzipped_jsonl_is_not_a_tar(tmp_path):
    p = tmp_path / "hi.jsonl.gz"
    p.write_bytes(gzip.compress(dumps_jsonl(records_for("indic", "hi")).encode()))
    assert archive_kind(p) is None
    assert validate_submission(p, track="indic").status == "ok"


def test_tar_partial_and_noise(tmp_path):
    members = track_members("indic", langs=["hi", "gu"])
    members["README.md"] = b"x"
    members["__MACOSX/._hi.jsonl"] = b"junk"
    r = validate_submission(make_tar(tmp_path / "x.tgz", members), track="indic")
    assert r.kinds() == {"zip.member_ignored", "track.language_missing"} and r.exit_code == 1
    assert sum(1 for f in r.files if not f.present) == 7


def test_tar_unsafe_members(tmp_path):
    members = track_members("indic", langs=["gu"])
    link = tarfile.TarInfo("hi.jsonl"); link.type = tarfile.SYMTYPE; link.linkname = "/etc/passwd"
    hard = tarfile.TarInfo("bn.jsonl"); hard.type = tarfile.LNKTYPE; hard.linkname = "gu.jsonl"
    trav = tarfile.TarInfo("../evil.jsonl"); trav.size = 2
    absp = tarfile.TarInfo("/tmp/abs.jsonl"); absp.size = 2
    r = validate_submission(make_tar(tmp_path / "bad.tar", members, "w", infos=[(link, None), (hard, None), (trav, b"{}"), (absp, b"{}")]), track="indic")
    f = next(x for x in r.findings if x.kind == "zip.unsafe_member")
    assert f.count == 4 and r.exit_code == 2
    assert {e.split(" (")[1].rstrip(")") for e in f.examples} == {"symlink", "hard link", "path traversal", "absolute path"}
    assert [x.language for x in r.files if x.present] == ["gu"]


def test_tar_duplicate_language(tmp_path):
    members = track_members("indic", langs=["hi"])
    members["again.jsonl"] = members["hi.jsonl"]
    r = validate_submission(make_tar(tmp_path / "d.tgz", members), track="indic")
    assert "zip.duplicate_language" in r.kinds() and r.exit_code == 2
