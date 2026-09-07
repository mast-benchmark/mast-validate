from mast_validate import resources as R
from mast_validate.languages import TRACKS


def test_all_scopes_present_with_50_qids():
    for track, langs in TRACKS.items():
        for lang in langs:
            q = R.qids(track, lang)
            assert len(q) == 50, (track, lang)
            assert all(x.startswith(f"{lang}-") and x[len(lang) + 1:].isdigit() for x in q)
    assert len(R.scopes()) == 24


def test_numeric_identity_recorded_and_true():
    assert R.manifest()["numeric_set_identical"] is True
    nums = {tuple(sorted(int(q.rsplit("-", 1)[1]) for q in R.qids(t, l))) for t, l in R.scopes()}
    assert len(nums) == 1


def test_qids_sorted_numeric():
    q = R.qids_sorted("indic", "hi")
    assert [int(x.split("-")[1]) for x in q] == sorted(int(x.split("-")[1]) for x in q)


def test_docids():
    d = R.docids()
    assert len(d) == 100_195 == R.manifest()["docid_count"]
    assert all(x.isdigit() and 1 <= len(x) <= 6 for x in list(d)[:1000])
    assert "5412" in d and "82002" in d


def test_missing_scope_raises():
    import pytest
    with pytest.raises(R.ResourceError):
        R.qids("multilingual", "yo")
