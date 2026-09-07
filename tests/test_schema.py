import pytest

from mast_validate.schema import EXACT_ANSWER, FLAT_LIST_HINT, parse_qid, validate_record
from tests.conftest import REAL_DOCIDS, make_record


@pytest.mark.parametrize("value,lang,qid,kind,recon", [
    ("hi-798", "hi", "hi-798", None, False),
    ("HI-798", "hi", "hi-798", None, False),
    ("hindi-798", "hi", "hi-798", None, False),
    (" hi-798 ", "hi", "hi-798", None, False),
    (798, "hi", "hi-798", None, True),
    ("798", "hi", "hi-798", None, True),
    ("0798", "hi", "hi-798", None, True),
    ("zh-798", "hi", None, "qid.prefix_mismatch", False),
    ("chinese-798", "hi", None, "qid.prefix_mismatch", False),
    ("798a", "hi", None, "qid.malformed", False),
    ("hi_798", "hi", None, "qid.malformed", False),
    ("q-798", "hi", None, "qid.malformed", False),
    ("hi-79x", "hi", None, "qid.malformed", False),
    ("", "hi", None, "qid.malformed", False),
    (None, "hi", None, "qid.malformed", False),
    (True, "hi", None, "qid.malformed", False),
    (-1, "hi", None, "qid.malformed", False),
    (798.0, "hi", None, "qid.malformed", False),
    (["hi-798"], "hi", None, "qid.malformed", False),
])
def test_parse_qid(value, lang, qid, kind, recon):
    got_qid, issue, got_recon = parse_qid(value, lang)
    assert got_qid == qid
    assert (issue.kind if issue else None) == kind
    assert got_recon is recon


def test_valid_record():
    rr = validate_record(make_record("hi", "hi-798"), "indic", "hi")
    assert rr.issues == []
    assert rr.qid == "hi-798" and not rr.reconstructed
    assert rr.rounds == [REAL_DOCIDS[:3], REAL_DOCIDS[3:5]] and rr.search_count == 2
    assert rr.has_output_text and EXACT_ANSWER in rr.final_output
    assert rr.unknown_keys == frozenset()


def test_language_name_forms_accepted():
    for form in ("Hindi", "hindi", "HI", "hin"):
        assert validate_record(make_record("hi", "hi-798", language=form), "indic", "hi").issues == []


def test_not_object():
    assert validate_record(["hi-798"], "indic", "hi").kinds() == {"json.not_object"}


def test_missing_fields():
    rec = make_record("hi", "hi-798")
    del rec["llm"], rec["retriever"]
    rr = validate_record(rec, "indic", "hi")
    assert rr.kinds() == {"schema.missing_field"}
    assert "'llm'" in rr.issues[0].example and "'retriever'" in rr.issues[0].example


@pytest.mark.parametrize("field,value", [
    ("language", 11), ("retriever", ""), ("llm", "   "), ("llm", None),
    ("tool_call_counts", ["search"]), ("tool_call_counts", {"search": -1}), ("tool_call_counts", {"search": "2"}),
    ("tool_call_counts", {"search": True}), ("retrieved_docids", "81120"), ("retrieved_docids", [["1"], "2"]),
    ("result", "text"), ("result", [{"type": "output_text", "output": None}]),
    ("result", [{"type": "reasoning", "tool_name": 5, "output": "x"}, {"type": "output_text", "output": "Exact Answer: y"}]),
    ("result", ["not a step"]),
])
def test_wrong_types(field, value):
    rr = validate_record(make_record("hi", "hi-798", **{field: value}), "indic", "hi")
    assert "schema.wrong_type" in rr.kinds(), rr.issues


def test_flat_docid_list_is_error_with_hint():
    rr = validate_record(make_record("hi", "hi-798", retrieved_docids=REAL_DOCIDS[:5]), "indic", "hi")
    assert rr.kinds() == {"schema.wrong_type"}
    assert FLAT_LIST_HINT in rr.issues[0].example
    assert rr.rounds is None


def test_docid_entries():
    rr = validate_record(make_record("hi", "hi-798", retrieved_docids=[["1", 2, ""], [" "]]), "indic", "hi")
    assert rr.kinds() == {"docid.bad_entry"}
    assert rr.rounds == [["1"], []]


def test_empty_round_warns():
    rr = validate_record(make_record("hi", "hi-798", retrieved_docids=[REAL_DOCIDS[:2], []]), "indic", "hi")
    assert rr.kinds() == {"rounds.empty"}


def test_round_count_mismatch():
    rr = validate_record(make_record("hi", "hi-798", tool_call_counts={"search": 5}), "indic", "hi")
    assert rr.kinds() == {"rounds.count_mismatch"}
    rr = validate_record(make_record("hi", "hi-798", tool_call_counts={"fetch": 5}), "indic", "hi")
    assert rr.kinds() == set()  # no search count declared: nothing to compare


def test_result_checks():
    assert validate_record(make_record("hi", "hi-798", result=[]), "indic", "hi").kinds() == {"schema.result_empty"}
    rr = validate_record(make_record("hi", "hi-798", result=[{"type": "thought", "output": "x"}]), "indic", "hi")
    assert rr.kinds() == {"schema.step_unknown_type", "answer.no_output_text"}
    rr = validate_record(make_record("hi", "hi-798", result=[{"type": "reasoning", "output": None}]), "indic", "hi")
    assert rr.kinds() == {"answer.no_output_text"}
    rr = validate_record(make_record("hi", "hi-798", result=[{"type": "output_text", "output": "no answer here"}]), "indic", "hi")
    assert rr.kinds() == {"answer.no_exact_answer"}
    # only the LAST output_text counts
    steps = [{"type": "output_text", "output": "Exact Answer: early"}, {"type": "output_text", "output": "final without it"}]
    assert validate_record(make_record("hi", "hi-798", result=steps), "indic", "hi").kinds() == {"answer.no_exact_answer"}


def test_language_mismatch():
    rr = validate_record(make_record("hi", "hi-798", language="chinese"), "indic", "hi")
    assert rr.kinds() == {"lang.mismatch"}
    rr = validate_record(make_record("hi", "hi-798", language="yoruba"), "indic", "hi")
    assert rr.kinds() == {"lang.mismatch"} and "unrecognized" in rr.issues[0].example


def test_unknown_keys_collected_not_flagged_per_record():
    rr = validate_record(make_record("hi", "hi-798", status="completed", metadata={}), "indic", "hi")
    assert rr.issues == []
    assert rr.unknown_keys == {"status", "metadata"}
