import zipfile

import pytest

from mast_validate.archive import unsafe_reason
from mast_validate.runner import UsageProblem, validate_submission
from tests.conftest import dumps_jsonl, make_zip, records_for, track_members


def kinds(report):
    return report.kinds()


def _info(name, mode=None):
    info = zipfile.ZipInfo(name)
    if mode is not None:
        info.external_attr = mode << 16
    return info


@pytest.mark.parametrize("name,mode,reason", [
    ("hi.jsonl", None, None),
    ("sub/dir/hi.jsonl", 0o100644, None),
    ("/abs/hi.jsonl", None, "absolute path"),
    ("C:\\hi.jsonl", None, "absolute path"),
    ("../hi.jsonl", None, "path traversal"),
    ("a/../../hi.jsonl", None, "path traversal"),
    ("hi.jsonl", 0o120777, "symlink"),
    ("hi.jsonl", 0o020644, "not a regular file"),
    ("hi\x00.jsonl", None, "NUL in name"),
])
def test_unsafe_reason(name, mode, reason):
    info = _info("placeholder")
    info.filename = name
    if mode is not None:
        info.external_attr = mode << 16
    assert unsafe_reason(info) == reason


def test_full_track_zip_ok(tmp_path):
    z = make_zip(tmp_path / "indic.zip", track_members("indic"))
    r = validate_submission(z, track="indic")
    assert r.status == "ok" and r.exit_code == 0
    assert [f.language for f in r.files] == sorted(f.language for f in r.files) and len(r.files) == 9
    assert all(f.records == 50 for f in r.files)


def test_wrapper_directory_and_noise_ignored(tmp_path):
    members = track_members("indic", prefix="my-submission/runs/")
    members["__MACOSX/my-submission/runs/._hi.jsonl"] = b"junk"
    members["my-submission/.DS_Store"] = b"junk"
    z = make_zip(tmp_path / "indic.zip", members)
    r = validate_submission(z, track="indic")
    assert r.status == "ok" and kinds(r) == set()


def test_partial_track_is_warning(tmp_path):
    langs = [l for l in "bn gu hi kn ml or pa ta".split()]
    z = make_zip(tmp_path / "indic.zip", track_members("indic", langs))
    r = validate_submission(z, track="indic")
    assert r.status == "warnings" and r.exit_code == 1
    missing = [f for f in r.files if not f.present]
    assert [f.language for f in missing] == ["te"]
    assert missing[0].findings[0].kind == "track.language_missing"
    assert missing[0].findings[0].details == {"expected": 9, "found": 8}
    assert all(f.inferred for f in r.files if f.present)


def test_empty_zip(tmp_path):
    z = make_zip(tmp_path / "empty.zip", {})
    r = validate_submission(z, track="indic")
    assert r.exit_code == 1 and sum(1 for f in r.files if not f.present) == 9


def test_non_jsonl_member_warns_and_other_track_language_is_error(tmp_path):
    members = track_members("multilingual")
    members["README.txt"] = b"hello"
    members["extra.jsonl"] = dumps_jsonl(records_for("indic", "gu")).encode()
    z = make_zip(tmp_path / "ml.zip", members)
    r = validate_submission(z, track="multilingual")
    assert kinds(r) == {"archive.member_ignored", "lang.not_in_track"} and r.exit_code == 2
    gu = next(f for f in r.files if f.name == "extra.jsonl")
    assert gu.language == "gu" and gu.inferred and gu.kinds() == {"lang.not_in_track"}


def test_member_names_do_not_matter(tmp_path):
    members = {"run-A.jsonl": dumps_jsonl(records_for("indic", "hi")).encode(),
               "zh.jsonl.gz": __import__("gzip").compress(dumps_jsonl(records_for("indic", "gu")).encode())}
    z = make_zip(tmp_path / "indic.zip", members)
    r = validate_submission(z, track="indic")
    present = {f.language: f for f in r.files if f.present}
    assert set(present) == {"hi", "gu"} and all(f.findings == [] and f.inferred for f in present.values())
    assert present["gu"].name == "zh.jsonl.gz"


def test_duplicate_language_is_error(tmp_path):
    members = track_members("indic")
    members["hindi.jsonl"] = members["hi.jsonl"]
    z = make_zip(tmp_path / "indic.zip", members)
    r = validate_submission(z, track="indic")
    assert "archive.duplicate_language" in kinds(r) and r.exit_code == 2
    copies = [f for f in r.files if f.language == "hi" and f.present]
    assert len(copies) == 2 and all("archive.duplicate_language" in f.kinds() for f in copies)


def test_unsafe_members_rejected_not_read(tmp_path):
    members = track_members("indic")
    infos = [(_info("../evil.jsonl"), b"{}"), (_info("hi.jsonl", 0o120777), b"/etc/passwd")]
    del members["hi.jsonl"]
    z = make_zip(tmp_path / "indic.zip", members, infos)
    r = validate_submission(z, track="indic")
    assert "archive.unsafe_member" in kinds(r) and r.exit_code == 2
    f = next(x for x in r.findings if x.kind == "archive.unsafe_member")
    assert f.count == 2 and any("symlink" in e for e in f.examples) and any("traversal" in e for e in f.examples)


def test_bad_zip_is_usage_error(tmp_path):
    p = tmp_path / "x.zip"
    p.write_bytes(b"PK\x03\x04" + b"\x00" * 50)
    with pytest.raises(UsageProblem):
        validate_submission(p, track="indic")


def test_zip_with_language_flag_is_usage_error(tmp_path):
    z = make_zip(tmp_path / "indic.zip", track_members("indic"))
    with pytest.raises(UsageProblem):
        validate_submission(z, track="indic", language="hi")


def test_per_file_findings_inside_zip(tmp_path):
    members = track_members("indic")
    members["te.jsonl"] = dumps_jsonl(records_for("indic", "te", n=45)).encode()
    z = make_zip(tmp_path / "indic.zip", members)
    r = validate_submission(z, track="indic")
    te = next(f for f in r.files if f.language == "te")
    assert te.kinds() == {"coverage.missing"} and r.exit_code == 2
