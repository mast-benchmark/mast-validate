#!/usr/bin/env python3
"""Performance check: 15 files x 50 records with realistic ~400 KB payloads (spec §7: < 30 s)."""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "src"))

from mast_validate.runner import validate_submission  # noqa: E402
from tests.conftest import make_zip, records_for, dumps_jsonl  # noqa: E402
from mast_validate.languages import TRACKS  # noqa: E402

PAYLOAD = "x" * 8000  # per tool_call output; ~40 steps -> ~320 KB per record


def main() -> None:
    with tempfile.TemporaryDirectory(dir=HERE.parent) as d:
        t0 = time.time()
        members = {}
        for lang in TRACKS["multilingual"]:
            recs = records_for("multilingual", lang)
            for r in recs:
                steps = []
                for i in range(20):
                    steps.append({"type": "reasoning", "tool_name": None, "arguments": None, "output": PAYLOAD[:500]})
                    steps.append({"type": "tool_call", "tool_name": "search", "arguments": "q", "output": PAYLOAD})
                steps.append(r["result"][-1])
                r["result"] = steps
                r["tool_call_counts"] = {"search": 20}
                r["retrieved_docids"] = [r["retrieved_docids"][0]] * 20
            members[f"{lang}.jsonl"] = dumps_jsonl(recs).encode("utf-8")
        z = make_zip(Path(d) / "bench.zip", members)
        size = sum(len(v) for v in members.values())
        print(f"generated {size / 1e6:.0f} MB of JSONL in {time.time() - t0:.1f}s; zip {z.stat().st_size / 1e6:.0f} MB")
        t1 = time.time()
        r = validate_submission(z, track="multilingual")
        dt = time.time() - t1
        print(f"validated {len(r.files)} files / {r.n_records} records in {dt:.1f}s -> status={r.status}")
        assert dt < 30, "slower than the 30 s target"


if __name__ == "__main__":
    main()
