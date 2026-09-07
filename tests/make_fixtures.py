#!/usr/bin/env python3
"""Regenerate the committed example fixtures under tests/fixtures/.

    python tests/make_fixtures.py

``valid/hi.jsonl`` validates clean for ``--track indic``. ``broken/sw.jsonl``
(multilingual) contains one of each common mistake and is what the README shows.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "src"))

from tests.conftest import records_for, write_jsonl  # noqa: E402


def main() -> None:
    write_jsonl(HERE / "fixtures" / "valid" / "hi.jsonl", records_for("indic", "hi"))
    recs = records_for("multilingual", "sw")
    recs.pop(10)                                                # coverage: one missing
    recs.append(dict(recs[0]))                                  # duplicate
    recs[1]["query_id"] = int(recs[1]["query_id"].split("-")[1])  # integer id (website form)
    recs[2]["retrieved_docids"] = [["doc_88213", "10986x"], recs[2]["retrieved_docids"][1]]  # unknown docids
    recs[3]["result"][-1]["output"] = "The answer is probably X."  # no Exact Answer:
    recs[4]["language"] = "Kiswahili"                           # accepted alias, no finding
    recs[5]["status"] = "completed"                             # unknown key
    write_jsonl(HERE / "fixtures" / "broken" / "sw.jsonl", recs)
    print("fixtures written")


if __name__ == "__main__":
    main()
