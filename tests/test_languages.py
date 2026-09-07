import pytest

from mast_validate import languages as L


def test_track_sizes():
    assert len(L.langs_for("multilingual")) == 15
    assert len(L.langs_for("indic")) == 9
    assert set(L.TRACKS["multilingual"]) & set(L.TRACKS["indic"]) == {"bn", "hi", "ta"}


@pytest.mark.parametrize("code", sorted(L.ALL_CODES))
def test_codes_round_trip(code):
    assert L.normalize(code) == code
    assert L.normalize(code.upper()) == code
    assert L.normalize(f"  {code} ") == code


@pytest.mark.parametrize("code,alias", [(c, a) for c, al in L.ALIASES.items() for a in sorted(al)])
def test_aliases_round_trip(code, alias):
    assert L.normalize(alias) == code
    assert L.normalize(alias.upper()) == code
    assert L.normalize(alias.title()) == code


@pytest.mark.parametrize("value,expected", [
    ("Chinese", "zh"), ("zh_CN", "zh"), ("ZH-cn", "zh"), ("Mandarin", "zh"),
    ("Bangla", "bn"), ("Kiswahili", "sw"), ("Cymraeg", "cy"), ("Oriya", "or"), ("Panjabi", "pa"),
    ("yo", None), ("mi", None), ("yoruba", None), ("maori", None), ("xx", None),
    ("", None), ("   ", None), (None, None), (11, None), (["hi"], None),
])
def test_normalize_edge_cases(value, expected):
    assert L.normalize(value) == expected


@pytest.mark.parametrize("value,expected", [
    ("multilingual", "multilingual"), ("Indic", "indic"),
    ("MAST Multilingual (16 diverse languages: Chinese, German, Yoruba, ...)", "multilingual"),
    ("Mast Indic (10 Indian languages: Hindi, Kannada, Bengali, Punjabi, ....)", "indic"),
    ("mast-indic", "indic"), ("track 1", None), ("", None), (None, None),
])
def test_normalize_track(value, expected):
    assert L.normalize_track(value) == expected


def test_in_track():
    assert L.in_track("multilingual", "cy")
    assert not L.in_track("indic", "cy")
    assert L.in_track("indic", "hi") and L.in_track("multilingual", "hi")
    assert not L.in_track("nope", "hi")
