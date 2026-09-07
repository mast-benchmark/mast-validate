"""Shared fixture helpers: deterministic records built from the real resources."""
from __future__ import annotations

import gzip
import json
import zipfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from mast_validate import resources as R
from mast_validate.cli import main as cli_main
from mast_validate.languages import TRACKS

# A handful of real corpus docids (numerically smallest, for readable fixtures).
REAL_DOCIDS = sorted(R.docids(), key=lambda d: (len(d), d))[:20]

EXACT = "Explanation: because the documents say so. Exact Answer: compassionate pugilist"


def make_record(lang: str, qid, **overrides):
    rec = {
        "query_id": qid,
        "language": lang,
        "retriever": "Qwen/Qwen3-Embedding-8B",
        "llm": "test/llm-1",
        "tool_call_counts": {"search": 2},
        "retrieved_docids": [REAL_DOCIDS[:3], REAL_DOCIDS[3:5]],
        "result": [
            {"type": "reasoning", "tool_name": None, "arguments": None, "output": "Let me search."},
            {"type": "tool_call", "tool_name": "search", "arguments": "query: something",
             "output": json.dumps([{"docid": REAL_DOCIDS[0], "score": 1.0, "snippet": "..."}])},
            {"type": "tool_call", "tool_name": "search", "arguments": "query: more", "output": "[]"},
            {"type": "output_text", "tool_name": None, "arguments": None, "output": EXACT},
        ],
    }
    rec.update(overrides)
    return rec


def records_for(track: str, lang: str, n: int | None = None, **overrides):
    qids = R.qids_sorted(track, lang)
    if n is not None:
        qids = qids[:n]
    return [make_record(lang, q, **overrides) for q in qids]


def dumps_jsonl(records) -> str:
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)


def write_jsonl(path: Path, records, gz: bool = False) -> Path:
    data = dumps_jsonl(records).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(data) if gz else data)
    return path


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_zip(path: Path, members: dict[str, bytes], infos: list[tuple[zipfile.ZipInfo, bytes]] = ()) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
        for info, data in infos:
            zf.writestr(info, data)
    return path


def track_members(track: str, langs=None, prefix: str = "") -> dict[str, bytes]:
    langs = TRACKS[track] if langs is None else langs
    return {f"{prefix}{lang}.jsonl": dumps_jsonl(records_for(track, lang)).encode("utf-8") for lang in langs}


@pytest.fixture
def cli():
    runner = CliRunner()

    def run(*args: str):
        return runner.invoke(cli_main, [str(a) for a in args])

    return run
