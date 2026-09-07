"""llm / retriever are read from the records."""
from mast_validate.runner import validate_file
from tests.conftest import records_for, write_jsonl


def test_meta_from_records(tmp_path):
    fr = validate_file(write_jsonl(tmp_path / "x.jsonl", records_for("indic", "hi")), track="indic")
    assert fr.llm == "test/llm-1" and fr.retriever == "Qwen/Qwen3-Embedding-8B" and fr.findings == []
    assert fr.to_dict()["llm"] == "test/llm-1"


def test_meta_inconsistent_is_error(tmp_path):
    recs = records_for("indic", "hi")
    for r in recs[:3]:
        r["llm"] = "other"
    recs[4]["retriever"] = " Qwen/Qwen3-Embedding-8B "   # whitespace-only difference is not a difference
    fr = validate_file(write_jsonl(tmp_path / "x.jsonl", recs), track="indic")
    assert fr.llm == "test/llm-1" and fr.retriever == "Qwen/Qwen3-Embedding-8B"
    f = [x for x in fr.findings if x.kind == "meta.inconsistent"]
    assert len(f) == 1 and f[0].details == {"field": "llm", "chosen": "test/llm-1"} and f[0].count == 2
    assert f[0].level.value == "error"
    recs[10]["retriever"] = "bm25"
    fr = validate_file(write_jsonl(tmp_path / "y.jsonl", recs), track="indic")
    assert sorted(x.details["field"] for x in fr.findings if x.kind == "meta.inconsistent") == ["llm", "retriever"]
