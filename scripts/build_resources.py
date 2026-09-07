#!/usr/bin/env python3
"""Build the packaged validation resources from the released MAST datasets.

Organizer-only. Reads the ``qid`` column of every query subset (never the
obfuscated ``query`` text) and the ``docid`` column of the corpus Parquet
shards via HTTP column projection (the 1.76 GB corpus is never downloaded).

    python scripts/build_resources.py            # writes src/mast_validate/resources/
    python scripts/build_resources.py --out DIR  # elsewhere

Requires: huggingface_hub, pyarrow.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from mast_validate.languages import TRACKS  # noqa: E402

QUERY_REPOS = {
    "multilingual": "mast-benchmark/multilingual-queries-2026",
    "indic": "mast-benchmark/indic-queries-2026",
}
CORPUS_REPO = "mast-benchmark/100k-corpus-2026"
EXPECTED_PER_SCOPE = 50
EXPECTED_DOCIDS = 100_195


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def build_qids(api) -> tuple[dict[str, list[str]], dict[str, str], bool]:
    from huggingface_hub import hf_hub_download

    out: dict[str, list[str]] = {}
    shas: dict[str, str] = {}
    numeric_sets: dict[str, frozenset[str]] = {}
    for track, repo in QUERY_REPOS.items():
        shas[track] = api.dataset_info(repo).sha
        expected_langs = TRACKS[track]
        for lang in expected_langs:
            path = hf_hub_download(repo, f"data/{lang}/queries.jsonl", repo_type="dataset", revision=shas[track])
            qids: list[str] = []
            with open(path, encoding="utf-8") as fh:
                for line_no, line in enumerate(fh, 1):
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    qid = row["qid"]  # only the id; never touch row["query"]
                    if not isinstance(qid, str) or not qid.startswith(f"{lang}-") or not qid[len(lang) + 1:].isdigit():
                        raise SystemExit(f"{track}/{lang} line {line_no}: unexpected qid {qid!r}")
                    qids.append(qid)
            if len(qids) != EXPECTED_PER_SCOPE or len(set(qids)) != EXPECTED_PER_SCOPE:
                raise SystemExit(f"{track}/{lang}: expected {EXPECTED_PER_SCOPE} unique qids, got {len(qids)} ({len(set(qids))} unique)")
            key = f"{track}/{lang}"
            out[key] = sorted(qids, key=lambda q: int(q.rsplit("-", 1)[1]))
            numeric_sets[key] = frozenset(q.rsplit("-", 1)[1] for q in qids)
            log(f"  {key:20s} {len(qids)} qids  e.g. {qids[0]}")
        if len([k for k in out if k.startswith(track + '/')]) != len(expected_langs):
            raise SystemExit(f"{track}: scope count mismatch")

    ref_key = "multilingual/ar"
    ref = numeric_sets[ref_key]
    differing = {k: (sorted(v - ref), sorted(ref - v)) for k, v in numeric_sets.items() if v != ref}
    identical = not differing
    if identical:
        log(f"numeric-set identity: HOLDS across all {len(numeric_sets)} scopes ({len(ref)} ids)")
    else:
        log("numeric-set identity: DOES NOT HOLD. Organizers should look at this before eval day:")
        for k, (extra, missing) in differing.items():
            log(f"  {k}: +{extra} -{missing}")
    return out, shas, identical


def build_docids(api) -> tuple[list[str], str]:
    import pyarrow.parquet as pq
    from huggingface_hub import HfFileSystem

    sha = api.dataset_info(CORPUS_REPO).sha
    fs = HfFileSystem()
    shards = sorted(
        p for p in fs.ls(f"datasets/{CORPUS_REPO}@{sha}/data", detail=False) if p.endswith(".parquet")
    )
    if not shards:
        raise SystemExit("no parquet shards found in corpus")
    seen: set[str] = set()
    total_rows = 0
    for shard in shards:
        t0 = time.time()
        with fs.open(shard, "rb") as fh:
            pf = pq.ParquetFile(fh)
            if "docid" not in pf.schema_arrow.names:
                raise SystemExit(f"{shard}: no docid column ({pf.schema_arrow.names})")
            col = pf.read(columns=["docid"]).column("docid").to_pylist()
        total_rows += len(col)
        for d in col:
            if not isinstance(d, str) or not d:
                raise SystemExit(f"{shard}: bad docid {d!r}")
            seen.add(d)
        log(f"  {shard.rsplit('/', 1)[-1]}: {len(col):,} rows in {time.time() - t0:.1f}s")
    if total_rows != len(seen):
        log(f"WARNING: {total_rows - len(seen)} duplicate docids across shards")
    if len(seen) != EXPECTED_DOCIDS:
        raise SystemExit(f"expected {EXPECTED_DOCIDS:,} unique docids, got {len(seen):,}")
    return sorted(seen, key=lambda d: (len(d), d)), sha


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=HERE.parent / "src" / "mast_validate" / "resources")
    ap.add_argument("--skip-docids", action="store_true", help="only rebuild queries.json")
    args = ap.parse_args()
    from huggingface_hub import HfApi

    api = HfApi()
    args.out.mkdir(parents=True, exist_ok=True)

    log("query ids:")
    qids, q_shas, identical = build_qids(api)
    (args.out / "queries.json").write_text(json.dumps(qids, indent=0, sort_keys=True) + "\n", encoding="utf-8")

    manifest = {
        "built_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "query_repos": {t: {"repo": r, "sha": q_shas[t]} for t, r in QUERY_REPOS.items()},
        "scopes": {k: len(v) for k, v in qids.items()},
        "expected_per_scope": EXPECTED_PER_SCOPE,
        "numeric_set_identical": identical,
    }
    if not args.skip_docids:
        log("docids:")
        docids, c_sha = build_docids(api)
        with gzip.open(args.out / "docids.txt.gz", "wt", encoding="utf-8", compresslevel=9) as fh:
            fh.write("\n".join(docids) + "\n")
        manifest["corpus_repo"] = {"repo": CORPUS_REPO, "sha": c_sha}
        manifest["docid_count"] = len(docids)
    else:
        try:
            old = json.loads((args.out / "manifest.json").read_text())
            manifest["corpus_repo"] = old.get("corpus_repo")
            manifest["docid_count"] = old.get("docid_count")
        except FileNotFoundError:
            pass
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    log(f"wrote {args.out}")


if __name__ == "__main__":
    main()
