import asr


def test_asr_roundtrip(tmp_path):
    p = str(tmp_path / "a.json")
    assert asr.read_latest(p) is None
    asr.write_latest("bonjour", final=True, path=p)
    d = asr.read_latest(p)
    assert d["text"] == "bonjour" and d["final"] is True and d["ts"] > 0
    asr.clear(p)
    assert asr.read_latest(p) is None
