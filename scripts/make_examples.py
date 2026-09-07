#!/usr/bin/env python3
"""Write example submissions, one per validator outcome, for docs and manual testing.

    python scripts/make_examples.py OUT_DIR

Every file is built from the real official query ids and real corpus docids, with
tiny placeholder traces. Indic/Hindi is used for errors and warnings, Multilingual
for the second valid example. EXPECTED.md in OUT_DIR lists what each file triggers.
"""
from __future__ import annotations

import gzip
import json
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "src"))

from mast_validate.languages import TRACKS  # noqa: E402
from tests.conftest import REAL_DOCIDS, dumps_jsonl, records_for, write_jsonl  # noqa: E402

CASES: list[tuple[str, str, str]] = []  # (relative path, expected kinds, note)


def emit(rel: str, records, note: str, kinds: str, raw: str | None = None) -> None:
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        p.write_text(raw, encoding="utf-8")
    else:
        write_jsonl(p, records)
    CASES.append((rel, kinds, note))


def hi(**kw):
    return records_for("indic", "hi", **kw)


def main(out: Path) -> None:
    global OUT
    OUT = out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # ---- valid
    emit("valid/hi.jsonl", hi(), "all 50 official ids, prefixed form", "none (exit 0)")
    zh = records_for("multilingual", "zh")
    for r in zh:
        r["query_id"] = int(r["query_id"].split("-")[1]); r["language"] = "chinese"
    emit("valid/zh_website_form.jsonl", zh, "integer ids and 'chinese', exactly as the website example", "qid.reconstructed (warning, exit 1)")
    gzp = out / "valid" / "hi.jsonl.gz"
    gzp.write_bytes(gzip.compress(dumps_jsonl(hi()).encode()))
    CASES.append(("valid/hi.jsonl.gz", "none (exit 0)", "same as hi.jsonl, gzipped"))

    # ---- errors
    emit("errors/bad_json_line.jsonl", None, "line 51 is not JSON", "json.invalid_line",
         raw=dumps_jsonl(hi()) + '{"query_id": "hi-10", "language": hi}\n')
    emit("errors/not_an_object.jsonl", None, "line 51 is a JSON array", "json.not_object",
         raw=dumps_jsonl(hi()) + '["hi-10"]\n')
    recs = hi(); [r.pop("llm") for r in recs[:5]]
    emit("errors/missing_field.jsonl", recs, "5 records without 'llm'", "schema.missing_field")
    recs = hi(); recs[0]["tool_call_counts"] = "2"; recs[1]["retriever"] = ""
    emit("errors/wrong_type.jsonl", recs, "tool_call_counts is a string; retriever empty", "schema.wrong_type")
    recs = hi()
    for r in recs:
        r["retrieved_docids"] = REAL_DOCIDS[:5]
    emit("errors/flat_retrieved_docids.jsonl", recs, "flat docid list (BrowseComp-Plus shape) instead of rounds", "schema.wrong_type")
    recs = hi(); recs[0]["result"] = []
    emit("errors/result_empty.jsonl", recs, "one record with result = []", "schema.result_empty")
    recs = hi(); recs[0]["result"][0]["type"] = "thought"
    emit("errors/unknown_step_type.jsonl", recs, "step type 'thought'", "schema.step_unknown_type")
    recs = hi(); recs[0]["language"] = "chinese"
    emit("errors/language_mismatch.jsonl", recs, "'language': 'chinese' inside the Hindi file", "lang.mismatch")
    recs = hi(); recs[0]["query_id"] = "zh-" + recs[0]["query_id"].split("-")[1]
    emit("errors/qid_prefix_mismatch.jsonl", recs, "zh-798 inside the Hindi file (never reconstructed)", "qid.prefix_mismatch + coverage.missing")
    recs = hi(); recs[0]["query_id"] = "hi-9999"
    emit("errors/qid_unknown.jsonl", recs, "hi-9999 is not an official id", "qid.unknown + coverage.missing")
    recs = hi(); recs.append(dict(recs[0]))
    emit("errors/qid_duplicate.jsonl", recs, "first record repeated at line 51", "qid.duplicate")
    recs = hi(); recs[0]["query_id"] = "hi_" + recs[0]["query_id"].split("-")[1]
    emit("errors/qid_malformed.jsonl", recs, "'hi_798' (underscore) cannot be parsed", "qid.malformed + coverage.missing")
    emit("errors/coverage_missing.jsonl", hi(n=49), "49 of the 50 official ids", "coverage.missing")
    recs = hi(); recs[0]["retrieved_docids"] = [[81120, ""], REAL_DOCIDS[:2]]
    emit("errors/bad_docid_entry.jsonl", recs, "integer and empty docids", "docid.bad_entry")
    emit("errors/empty.jsonl", None, "zero records, so no language can be read", "lang.undetermined", raw="")

    # ---- warnings
    recs = hi(); recs[0]["retrieved_docids"] = [["doc_88213", "10986x"], REAL_DOCIDS[:2]]
    emit("warnings/unknown_docids.jsonl", recs, "two docids not in the corpus", "docid.unknown")
    recs = hi()
    for r in recs:
        r["retrieved_docids"] = [["x1", "x2"], ["x3"]]
    emit("warnings/unknown_docids_majority.jsonl", recs, "every docid unknown: wrong corpus indexed", "docid.unknown_majority")
    recs = hi(); recs[0]["result"][-1]["output"] = "The answer is 42."
    emit("warnings/no_exact_answer.jsonl", recs, "final output_text lacks 'Exact Answer:'", "answer.no_exact_answer")
    recs = hi(); recs[0]["result"] = recs[0]["result"][:-1]
    emit("warnings/no_output_text.jsonl", recs, "no output_text step at all", "answer.no_output_text")
    recs = hi(); recs[0]["tool_call_counts"] = {"search": 7}
    emit("warnings/rounds_count_mismatch.jsonl", recs, "2 rounds but tool_call_counts.search = 7", "rounds.count_mismatch")
    recs = hi(); recs[0]["retrieved_docids"] = [REAL_DOCIDS[:2], []]
    emit("warnings/empty_round.jsonl", recs, "a search round with no docids", "rounds.empty")
    recs = hi(); recs[0]["status"] = "completed"; recs[1]["token_stats"] = []
    emit("warnings/unknown_keys.jsonl", recs, "extra top-level keys status, token_stats", "keys.unknown")
    recs = hi()
    for r in recs:
        r["query_id"] = int(r["query_id"].split("-")[1])
    emit("warnings/integer_ids.jsonl", recs, "bare integer ids, reconstructed as hi-<id>", "qid.reconstructed")

    # ---- zips (CLI only)
    zdir = out / "zips"; zdir.mkdir()
    with zipfile.ZipFile(zdir / "indic_complete.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        for lang in TRACKS["indic"]:
            zf.writestr(f"runs/{lang}.jsonl", dumps_jsonl(records_for("indic", lang)))
    CASES.append(("zips/indic_complete.zip", "none (exit 0)", "all 9 Indic languages under a wrapper directory"))
    with zipfile.ZipFile(zdir / "indic_partial.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        for lang in TRACKS["indic"][:-1]:
            zf.writestr(f"{lang}.jsonl", dumps_jsonl(records_for("indic", lang)))
        zf.writestr("README.txt", "notes")
    CASES.append(("zips/indic_partial.zip", "track.language_missing + archive.member_ignored (warnings)", "8 of 9 languages plus a stray file"))
    with zipfile.ZipFile(zdir / "unsafe.zip", "w") as zf:
        zf.writestr("../escape.jsonl", "{}")
        zf.writestr("hi.jsonl", dumps_jsonl(hi()))
    CASES.append(("zips/unsafe.zip", "archive.unsafe_member (error)", "path traversal member is rejected; hi.jsonl still validated; other languages missing (warning)"))

    lines = ["# Example submissions", "", "Built by `scripts/make_examples.py` from the real query ids and corpus docids.",
             "Validate any of them with, e.g.", "", "```", "mast-validate valid/hi.jsonl --track indic",
             "mast-validate zips/indic_partial.zip --track indic", "```", "",
             "| File | Triggers | What is wrong |", "|---|---|---|"]
    lines += [f"| `{rel}` | `{kinds}` | {note} |" for rel, kinds, note in CASES]
    (out / "EXPECTED.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(CASES)} examples to {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "examples")
