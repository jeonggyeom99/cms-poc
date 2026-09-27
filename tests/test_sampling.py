import pytest

from app.data_loader.sampling import sampling_metadata


@pytest.mark.parametrize("code,fs", [("5", 1280), ("6", 2560), ("9", 25600), ("10", 51200)])
@pytest.mark.parametrize("n,lines", [(1024, 400), (2048, 800), (4096, 1600)])
def test_sampling_rule(code, fs, n, lines):
    assert sampling_metadata(code, n, lines)["frequencyHz"] == fs


@pytest.mark.parametrize("code,n,lines", [("99", 2048, 800), ("9", 1000, 800), ("9", 0, 800), ("9", 2048, 0)])
def test_sampling_rejects_unknown_rule(code, n, lines):
    result = sampling_metadata(code, n, lines)
    assert not result["valid"]
    assert result["frequencyHz"] is None
    assert result["reason"]
