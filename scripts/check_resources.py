#!/usr/bin/env python3
"""Print a sanity table for the packaged resources. Run after every rebuild."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mast_validate import resources as R  # noqa: E402
from mast_validate.languages import TRACKS  # noqa: E402


def main() -> int:
    m = R.manifest()
    print(f"built_at: {m.get('built_at')}   numeric_set_identical: {m.get('numeric_set_identical')}")
    for track, info in m.get("query_repos", {}).items():
        print(f"  {track}: {info['repo']} @ {info['sha'][:10]}")
    ok = True
    print(f"\n{'track':12s} {'lang':4s} {'qids':>5s}  sample")
    for track, langs in TRACKS.items():
        for lang in langs:
            if not R.has_scope(track, lang):
                print(f"{track:12s} {lang:4s}  MISSING")
                ok = False
                continue
            q = R.qids_sorted(track, lang)
            flag = "" if len(q) == m.get("expected_per_scope", 50) else "   <-- unexpected count"
            print(f"{track:12s} {lang:4s} {len(q):5d}  {q[0]}, {q[1]}, ... {q[-1]}{flag}")
            ok = ok and not flag
    extra = [s for s in R.scopes() if s[1] not in TRACKS.get(s[0], ())]
    if extra:
        print(f"extra scopes not in TRACKS: {extra}")
        ok = False
    d = R.docids()
    exp = m.get("docid_count")
    print(f"\ndocids: {len(d):,} loaded (manifest says {exp:,})" if exp else f"\ndocids: {len(d):,}")
    ok = ok and (exp is None or exp == len(d))
    print("\nOK" if ok else "\nPROBLEMS FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
