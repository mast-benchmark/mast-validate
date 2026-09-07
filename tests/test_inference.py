"""Language inference from records (no filename involved)."""
from mast_validate.runner import infer_language, validate_file
from tests.conftest import records_for, write_jsonl


def kinds(fr):
    return {f.kind for f in fr.findings}


def test_infer_majority_and_tie_order():
    assert infer_language([{"language": "hi"}, {"language": "Hindi"}, {"language": "zh"}]) == "hi"
    assert infer_language([{"language": "zh"}, {"language": "hi"}]) == "zh"      # tie: first seen
    assert infer_language([{"language": "yo"}, {"nolang": 1}, "junk", None]) is None


def test_inferred_clean(tmp_path):
    fr = validate_file(write_jsonl(tmp_path / "x.jsonl", records_for("indic", "hi")), track="indic")
    assert fr.language == "hi" and fr.inferred and fr.findings == []


def test_declared_overrides_and_checks(tmp_path):
    p = write_jsonl(tmp_path / "x.jsonl", records_for("indic", "hi"))
    fr = validate_file(p, track="indic", lang="gu")
    assert fr.language == "gu" and not fr.inferred
    assert {"lang.mismatch", "qid.prefix_mismatch", "coverage.missing"} <= kinds(fr)


def test_integer_ids_use_language_field(tmp_path):
    recs = records_for("indic", "hi")
    for r in recs:
        r["query_id"] = int(r["query_id"].split("-")[1]); r["language"] = "Hindi"
    fr = validate_file(write_jsonl(tmp_path / "x.jsonl", recs), track="indic")
    assert fr.language == "hi" and kinds(fr) == {"qid.reconstructed"}


def test_odd_first_record_does_not_flip_language(tmp_path):
    recs = records_for("indic", "hi")
    recs[0]["language"] = "chinese"
    fr = validate_file(write_jsonl(tmp_path / "x.jsonl", recs), track="indic")
    assert fr.language == "hi" and kinds(fr) == {"lang.mismatch"}
    assert next(f for f in fr.findings if f.kind == "lang.mismatch").count == 1


def test_mixed_languages_late_in_file(tmp_path):
    recs = records_for("indic", "hi")
    for r in recs[40:]:
        r["language"] = "gu"
    fr = validate_file(write_jsonl(tmp_path / "x.jsonl", recs), track="indic")
    assert fr.language == "hi" and kinds(fr) == {"lang.mismatch"}


def test_qid_prefix_must_agree_with_language_field(tmp_path):
    recs = records_for("indic", "hi")
    recs[3]["query_id"] = "gu-" + recs[3]["query_id"].split("-")[1]
    fr = validate_file(write_jsonl(tmp_path / "x.jsonl", recs), track="indic")
    assert fr.language == "hi" and kinds(fr) == {"qid.prefix_mismatch", "coverage.missing"}


def test_undetermined_language(tmp_path):
    recs = records_for("indic", "hi")
    for r in recs:
        del r["language"]
    fr = validate_file(write_jsonl(tmp_path / "x.jsonl", recs), track="indic")
    assert fr.language is None and kinds(fr) == {"lang.undetermined"} and fr.records == 50


def test_not_in_track(tmp_path):
    fr = validate_file(write_jsonl(tmp_path / "x.jsonl", records_for("indic", "gu")), track="multilingual")
    assert fr.language == "gu" and kinds(fr) == {"lang.not_in_track"}


def test_small_file_decides_at_eof(tmp_path):
    fr = validate_file(write_jsonl(tmp_path / "x.jsonl", records_for("indic", "hi", n=3)), track="indic")
    assert fr.language == "hi" and kinds(fr) == {"coverage.missing"} and fr.records == 3


def test_bad_json_before_decision_is_kept(tmp_path):
    from tests.conftest import dumps_jsonl, write_text
    text = "{not json\n" + dumps_jsonl(records_for("indic", "hi"))
    fr = validate_file(write_text(tmp_path / "x.jsonl", text), track="indic")
    assert fr.language == "hi" and kinds(fr) == {"json.invalid_line"}
