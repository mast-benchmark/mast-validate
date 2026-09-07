import json
import subprocess
import sys

from tests.conftest import make_zip, records_for, track_members, write_jsonl


def test_clean_file_exit_0(tmp_path, cli):
    p = write_jsonl(tmp_path / "hi.jsonl", records_for("indic", "hi"))
    r = cli(p, "--track", "indic", "--language", "hi")
    assert r.exit_code == 0, r.output
    assert "PASSED" in r.output and "50 records" in r.output


def test_language_inferred_from_filename(tmp_path, cli):
    p = write_jsonl(tmp_path / "hindi.jsonl", records_for("indic", "hi"))
    assert cli(p, "--track", "INDIC").exit_code == 0


def test_language_name_flag(tmp_path, cli):
    p = write_jsonl(tmp_path / "run1.jsonl", records_for("multilingual", "zh"))
    assert cli(p, "--track", "multilingual", "-l", "Chinese").exit_code == 0


def test_warnings_exit_1_strict_exit_2(tmp_path, cli):
    recs = records_for("indic", "hi")
    recs[0]["result"][-1]["output"] = "no exact answer"
    p = write_jsonl(tmp_path / "hi.jsonl", recs)
    assert cli(p, "--track", "indic").exit_code == 1
    r = cli(p, "--track", "indic", "--strict")
    assert r.exit_code == 2 and "--strict" in r.output


def test_errors_exit_2(tmp_path, cli):
    p = write_jsonl(tmp_path / "hi.jsonl", records_for("indic", "hi", n=10))
    r = cli(p, "--track", "indic")
    assert r.exit_code == 2 and "FAILED" in r.output and "coverage" in r.output


def test_usage_errors_exit_3(tmp_path, cli):
    p = write_jsonl(tmp_path / "hi.jsonl", records_for("indic", "hi"))
    assert cli(p, "--track", "indic", "--language", "yo").exit_code == 3       # unknown language
    assert cli(p, "--track", "multilingual", "--language", "gu").exit_code == 3  # not in track
    assert cli(tmp_path / "nope.jsonl", "--track", "indic").exit_code == 3     # missing file
    assert cli(p).exit_code == 3                                               # no --track
    assert cli(p, "--track", "indic", "--bogus").exit_code == 3                # bad flag
    q = write_jsonl(tmp_path / "submission.jsonl", records_for("indic", "hi"))
    assert cli(q, "--track", "indic").exit_code == 3                           # language not inferable


def test_json_output_file_and_stdout(tmp_path, cli):
    p = write_jsonl(tmp_path / "hi.jsonl", records_for("indic", "hi", n=49))
    out = tmp_path / "report.json"
    r = cli(p, "--track", "indic", "--json", out)
    assert r.exit_code == 2
    d = json.loads(out.read_text())
    assert d["status"] == "errors" and d["exit_code"] == 2 and d["summary"]["errors"] == 1
    assert d["files"][0]["findings"][0]["kind"] == "coverage.missing"
    assert d["validator"]["name"] == "mast-validate"
    r = cli(p, "--track", "indic", "--json", "-")
    assert r.exit_code == 2 and json.loads(r.output)["status"] == "errors"


def test_quiet_and_no_color(tmp_path, cli):
    p = write_jsonl(tmp_path / "hi.jsonl", records_for("indic", "hi", n=49))
    r = cli(p, "--track", "indic", "--quiet", "--no-color")
    assert r.exit_code == 2 and "coverage" not in r.output and "\033[" not in r.output


def test_zip_end_to_end(tmp_path, cli):
    members = track_members("multilingual", langs=[l for l in "ar bn cy de en es fi fr hi ru sw ta th ur".split()])
    z = make_zip(tmp_path / "sub.zip", members)
    r = cli(z, "--track", "multilingual")
    assert r.exit_code == 1 and "zh.jsonl" in r.output and "found 14" in r.output


def test_console_entrypoint_runs():
    out = subprocess.run([sys.executable, "-m", "mast_validate.cli", "--version"], capture_output=True, text=True)
    assert out.returncode == 0 and "mast-validate" in out.stdout
