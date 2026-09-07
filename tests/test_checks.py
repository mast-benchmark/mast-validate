"""File-level behaviour through the streaming runner."""
import json

import pytest

from mast_validate import limits
from mast_validate.runner import validate_file
from tests.conftest import REAL_DOCIDS, dumps_jsonl, make_record, records_for, write_jsonl, write_text


def kinds(fr):
    return {f.kind for f in fr.findings}


def find(fr, kind):
    return next(f for f in fr.findings if f.kind == kind)


def test_valid_file_clean(tmp_path):
    p = write_jsonl(tmp_path / "hi.jsonl", records_for("indic", "hi"))
    fr = validate_file(p, track="indic", lang="hi")
    assert fr.records == 50 and fr.findings == []


def test_valid_gz_by_magic_not_extension(tmp_path):
    p = write_jsonl(tmp_path / "hi.jsonl", records_for("indic", "hi"), gz=True)
    fr = validate_file(p, track="indic", lang="hi")
    assert fr.records == 50 and fr.findings == []


def test_bom_and_crlf_tolerated(tmp_path):
    text = dumps_jsonl(records_for("indic", "hi")).replace("\n", "\r\n")
    (tmp_path / "hi.jsonl").write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8") + b"\r\n\r\n")
    fr = validate_file(tmp_path / "hi.jsonl", track="indic", lang="hi")
    assert fr.records == 50 and fr.findings == []


def test_mode_b_reconstruction_warns_once(tmp_path):
    recs = records_for("indic", "hi")
    for i, r in enumerate(recs):
        num = int(r["query_id"].split("-")[1])
        r["query_id"] = num if i % 2 else str(num)
    fr = validate_file(write_jsonl(tmp_path / "hi.jsonl", recs), track="indic", lang="hi")
    assert kinds(fr) == {"qid.reconstructed"}
    assert find(fr, "qid.reconstructed").count == 50


def test_duplicate_qid(tmp_path):
    recs = records_for("indic", "hi")
    recs.append(dict(recs[0]))
    fr = validate_file(write_jsonl(tmp_path / "hi.jsonl", recs), track="indic", lang="hi")
    assert kinds(fr) == {"qid.duplicate"}
    f = find(fr, "qid.duplicate")
    assert f.count == 1 and "lines 1, 51" in f.examples[0]


def test_unknown_qid_and_coverage(tmp_path):
    recs = records_for("indic", "hi")
    recs[3]["query_id"] = "hi-9999"
    fr = validate_file(write_jsonl(tmp_path / "hi.jsonl", recs), track="indic", lang="hi")
    assert kinds(fr) == {"qid.unknown", "coverage.missing"}
    assert find(fr, "coverage.missing").details == {"found": 49, "expected": 50}
    assert "hi-9999" in find(fr, "qid.unknown").examples[0]


def test_partial_coverage_examples_are_canonical(tmp_path):
    recs = records_for("indic", "hi", n=44)
    fr = validate_file(write_jsonl(tmp_path / "hi.jsonl", recs), track="indic", lang="hi")
    f = find(fr, "coverage.missing")
    assert f.count == 6 and len(f.examples) == 6 and all(e.startswith("hi-") for e in f.examples)


def test_wrong_language_prefix_is_error_not_reconstructed(tmp_path):
    recs = records_for("indic", "hi")
    recs[0]["query_id"] = "zh-" + recs[0]["query_id"].split("-")[1]
    fr = validate_file(write_jsonl(tmp_path / "hi.jsonl", recs), track="indic", lang="hi")
    assert kinds(fr) == {"qid.prefix_mismatch", "coverage.missing"}


def test_language_field_mismatch(tmp_path):
    recs = records_for("indic", "hi")
    recs[0]["language"] = "Chinese"
    fr = validate_file(write_jsonl(tmp_path / "hi.jsonl", recs), track="indic", lang="hi")
    assert kinds(fr) == {"lang.mismatch"}


def test_unknown_docids_minority(tmp_path):
    recs = records_for("indic", "hi")
    recs[0]["retrieved_docids"] = [["doc_88213", "10986x"], REAL_DOCIDS[:2]]
    fr = validate_file(write_jsonl(tmp_path / "hi.jsonl", recs), track="indic", lang="hi")
    assert kinds(fr) == {"docid.unknown"}
    f = find(fr, "docid.unknown")
    assert f.count == 2 and f.details["distinct_docids"] == 7


def test_unknown_docids_majority(tmp_path):
    recs = records_for("indic", "hi", retrieved_docids=[["x1", "x2"], ["x3"]])
    fr = validate_file(write_jsonl(tmp_path / "hi.jsonl", recs), track="indic", lang="hi")
    assert kinds(fr) == {"docid.unknown_majority"}
    assert find(fr, "docid.unknown_majority").details["pct"] == "100.0%"


def test_non_string_docid_is_error(tmp_path):
    recs = records_for("indic", "hi")
    recs[0]["retrieved_docids"] = [[123, ""], REAL_DOCIDS[:1]]
    fr = validate_file(write_jsonl(tmp_path / "hi.jsonl", recs), track="indic", lang="hi")
    assert kinds(fr) == {"docid.bad_entry"}


def test_missing_exact_answer_warns(tmp_path):
    recs = records_for("indic", "hi")
    recs[0]["result"][-1]["output"] = "I think the answer is 42"
    recs[1]["result"][-1]["output"] = "no idea"
    fr = validate_file(write_jsonl(tmp_path / "hi.jsonl", recs), track="indic", lang="hi")
    assert kinds(fr) == {"answer.no_exact_answer"} and find(fr, "answer.no_exact_answer").count == 2


def test_bad_json_line(tmp_path):
    text = dumps_jsonl(records_for("indic", "hi")) + "{not json\n"
    fr = validate_file(write_text(tmp_path / "hi.jsonl", text), track="indic", lang="hi")
    assert kinds(fr) == {"json.invalid_line"}
    assert find(fr, "json.invalid_line").lines == [51]


def test_non_object_line(tmp_path):
    text = dumps_jsonl(records_for("indic", "hi")) + "[1, 2]\n"
    fr = validate_file(write_text(tmp_path / "hi.jsonl", text), track="indic", lang="hi")
    assert kinds(fr) == {"json.not_object"}


def test_invalid_utf8_line(tmp_path):
    data = dumps_jsonl(records_for("indic", "hi")).encode() + b'{"query_id": "\xff"}\n'
    (tmp_path / "hi.jsonl").write_bytes(data)
    fr = validate_file(tmp_path / "hi.jsonl", track="indic", lang="hi")
    assert kinds(fr) == {"json.invalid_line"}


def test_missing_field_and_wrong_type_grouped(tmp_path):
    recs = records_for("indic", "hi")
    for r in recs[:7]:
        del r["llm"]
    for r in recs[7:10]:
        r["tool_call_counts"] = "2"
    fr = validate_file(write_jsonl(tmp_path / "hi.jsonl", recs), track="indic", lang="hi")
    assert kinds(fr) == {"schema.missing_field", "schema.wrong_type"}
    assert find(fr, "schema.missing_field").count == 7
    assert find(fr, "schema.wrong_type").count == 3
    assert len(fr.findings) == 2  # grouped, never one finding per record


def test_unknown_keys_once_per_file(tmp_path):
    recs = records_for("indic", "hi", status="completed", token_stats=[])
    fr = validate_file(write_jsonl(tmp_path / "hi.jsonl", recs), track="indic", lang="hi")
    assert kinds(fr) == {"keys.unknown"}
    assert find(fr, "keys.unknown").details["keys"] == ["status", "token_stats"]


def test_empty_file(tmp_path):
    fr = validate_file(write_text(tmp_path / "hi.jsonl", ""), track="indic", lang="hi")
    assert fr.records == 0 and kinds(fr) == {"coverage.missing"}
    assert find(fr, "coverage.missing").details["found"] == 0


def test_zip_given_as_file_is_rejected(tmp_path):
    (tmp_path / "hi.jsonl").write_bytes(b"PK\x03\x04garbage")
    fr = validate_file(tmp_path / "hi.jsonl", track="indic", lang="hi")
    assert kinds(fr) == {"io.not_jsonl"}


def test_decompressed_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(limits, "MAX_DECOMPRESSED_BYTES", 2000)
    p = write_jsonl(tmp_path / "hi.jsonl", records_for("indic", "hi"), gz=True)
    fr = validate_file(p, track="indic", lang="hi")
    assert "io.oversize" in kinds(fr) and "coverage.missing" not in kinds(fr)


def test_compressed_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(limits, "MAX_COMPRESSED_BYTES", 100)
    p = write_jsonl(tmp_path / "hi.jsonl", records_for("indic", "hi"))
    fr = validate_file(p, track="indic", lang="hi")
    assert kinds(fr) == {"io.oversize"}


def test_max_examples_respected(tmp_path):
    recs = records_for("indic", "hi", n=10)
    fr = validate_file(write_jsonl(tmp_path / "hi.jsonl", recs), track="indic", lang="hi", max_examples=3)
    f = find(fr, "coverage.missing")
    assert f.count == 40 and len(f.examples) == 3


def test_report_json_roundtrip(tmp_path):
    recs = records_for("indic", "hi", n=49)
    fr = validate_file(write_jsonl(tmp_path / "hi.jsonl", recs), track="indic", lang="hi")
    d = json.loads(json.dumps(fr.to_dict()))
    assert d["records"] == 49 and d["errors"] == 1 and d["findings"][0]["kind"] == "coverage.missing"
