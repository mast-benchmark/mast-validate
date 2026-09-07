# mast-validate

Offline validator for **MAST @ FIRE 2026** run submissions. Run it on each
per-language `.jsonl` file before you upload it to the submission portal; the
portal runs exactly the same checks, so a clean run here is a clean upload there.

Nothing is downloaded at run time. The official query ids and the corpus docid
list ship inside the package.

## Install

```bash
pip install git+https://github.com/mast-benchmark/mast-validate.git
mast-validate --version
```

Python 3.9 or newer. The only dependency is `click`.

## Run

One file. The language is read from the records themselves (the `language`
field, which every record must carry), so the filename does not matter:

```bash
mast-validate runs/hi.jsonl --track indic
mast-validate runs/run7.jsonl.gz --track multilingual
mast-validate runs/hi.jsonl --track indic --language hi     # declare it; records must agree
```

A whole track at once, as a zip of one `.jsonl` file per language, named however
you like (a wrapper directory is fine):

```bash
mast-validate submission.zip --track multilingual --json report.json
```

The **portal accepts one per-language file per upload**, not a zip. The zip form
is a convenience for checking everything locally in one go.

| Flag | Effect |
|---|---|
| `--track {multilingual,indic}` | required |
| `--language LANG` | declare the language of a single file (code or name); default: read from the records |
| `--strict` | warnings become errors |
| `--json PATH` | machine-readable report (`-` for stdout) |
| `--max-examples N` | examples per finding, default 10 |
| `--quiet` | summary lines only |
| `--no-color` | plain output for CI |

Exit codes: `0` clean · `1` warnings only · `2` validation errors · `3` usage or I/O problem.

## Reading the output

```
MAST submission validator · track=multilingual

sw.jsonl    50 records   ✗ 2 errors, 3 warnings
    ERROR   coverage: 1 official query_id missing (found 49 of 50) (e.g. sw-337)
    ERROR   1 query_id duplicated within the file (e.g. sw-10 (lines 1, 50))
    WARN    2 distinct docids (28.6%) not in the corpus (e.g. '10986x', 'doc_88213')
    WARN    query_ids in 1 record carried no language prefix; reconstructed as 'sw-<id>' from the declared language
    WARN    1 record with no 'Exact Answer:' in the final output_text (e.g. line 4: 'The answer is probably X.')

2 errors, 3 warnings across 1 file, 50 records.  FAILED
```

Findings are grouped by kind with counts and a few examples, never one line per
record. **Errors** block an upload. **Warnings** do not, but read them: each
one describes something that will cost you score at evaluation time.

## The record format

One JSON object per line, one file per (track, language), 50 records covering
every official query id for that language. This is the format on the MAST
website; fields in full:

| Field | Type | Rule |
|---|---|---|
| `query_id` | string or int | `"zh-798"` as in the released dataset, or the bare number `798` / `"798"` as in the website example (see below) |
| `language` | string | code or name, e.g. `"zh"` or `"chinese"`; must be the file's language |
| `retriever` | string | non-empty |
| `llm` | string | non-empty |
| `tool_call_counts` | object | string → non-negative int; `"search"` is compared with the number of rounds |
| `retrieved_docids` | list of lists of strings | **one inner list per search round**, docids as strings |
| `result` | list of steps | non-empty; each step has `type` ∈ `reasoning` / `tool_call` / `output_text`, `tool_name` and `arguments` (string or null), `output` (string) |

The final `output_text` step's `output` must contain the substring
`Exact Answer:`; that is what the exact-match scorer parses.

**Language of a file.** Every record in a file must carry the same `language`
(any form: `hi`, `Hindi`, `hindi`). The validator reads it from the records;
a file whose records disagree, or that has no recognizable `language` field, is
rejected. Query-id prefixes, when present, must agree with it too.

**Query ids.** The released datasets use prefixed strings (`zh-798`), the
website example shows a bare integer (`11`). Both are accepted. A bare number
is combined with the file's language and produces one warning per file so
you know it happened. A *wrong* prefix (`zh-798` inside a Hindi file) is an
error, because it almost always means the wrong file was uploaded.

**Retrieved docids** must be nested by search round. A flat list of docids
(what the BrowseComp-Plus evaluation scripts consume) is rejected with a
message that says how to nest it.

**Unknown docids** are a warning, not an error: a docid outside the corpus
simply scores as a miss. If most of your docids are unknown, you indexed a
different corpus, and the message says so.

**Extra top-level keys** (`status`, `metadata`, …) are ignored, with one warning
listing them.

## Files

* `.jsonl` or gzipped `.jsonl.gz`; gzip is detected from the content, not the name.
* Caps: 200 MB on disk, 2 GB decompressed. A real file is a few MB.
* Filenames carry no meaning; the records decide the language. Pass `--language` to assert what you expect.

## Using it from Python

```python
from mast_validate.runner import single_file_report
report = single_file_report("runs/hi.jsonl", track="indic", lang=None)   # or lang="hi" to declare it
report.status, report.exit_code, report.kinds(), report.to_dict()
```

## Resources

`src/mast_validate/resources/` holds `queries.json` (the official qid list per
track and language), `docids.txt.gz` (100,195 corpus docids) and
`manifest.json` (dataset commits they were built from). Organizers rebuild them
with `scripts/build_resources.py` and check with `scripts/check_resources.py`.
Only the `qid` and `docid` columns are ever read; query text is never touched.

## Problems

If the validator rejects something you believe is correct, email
mast-organizers@googlegroups.com with the `--json` report attached.
