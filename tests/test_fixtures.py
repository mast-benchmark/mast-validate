"""The committed fixtures must keep validating the same way (guards resource drift)."""
from pathlib import Path

from mast_validate.runner import validate_submission

FIX = Path(__file__).parent / "fixtures"


def test_valid_fixture():
    r = validate_submission(FIX / "valid" / "hi.jsonl", track="indic")
    assert r.status == "ok"


def test_broken_fixture_kinds():
    r = validate_submission(FIX / "broken" / "sw.jsonl", track="multilingual")
    assert r.kinds() == {"coverage.missing", "qid.duplicate", "qid.reconstructed", "docid.unknown",
                         "answer.no_exact_answer", "keys.unknown"}
    assert r.exit_code == 2
