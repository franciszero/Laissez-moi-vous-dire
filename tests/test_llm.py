import json
from io import BytesIO

import pytest

import llm


class _Response(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def test_configured_model_reads_hermes_default(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text("model:\n  default: current-bakeoff-winner\n", encoding="utf-8")
    monkeypatch.setattr(llm, "CONFIG", config)
    assert llm.configured_model() == "current-bakeoff-winner"


def test_grade_returns_structured_result(monkeypatch):
    result = {"判定": "部分", "错在哪": "配合", "改进建议": "改词尾", "更好的版本": "Je l'ai vue."}
    response = {"choices": [{"message": {"content": json.dumps(result, ensure_ascii=False)}}]}
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda *_a, **_k: _Response(json.dumps(response).encode()))
    assert llm.grade("我看见了她", "Je l'ai vu.", "检查直接宾语提前配合") == result


def test_grade_preserves_raw_text_when_json_is_invalid(monkeypatch):
    response = {"choices": [{"message": {"content": "模型没有按 JSON 输出"}}]}
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda *_a, **_k: _Response(json.dumps(response, ensure_ascii=False).encode()))
    assert llm.grade("提示", "答案", "要点") == {"raw": "模型没有按 JSON 输出", "parse_error": True}


def test_load_failure_is_clear_and_stops_process(tmp_path, monkeypatch):
    class DeadProcess:
        def poll(self): return 2
        def terminate(self): pass

    monkeypatch.setattr(llm, "LOG", tmp_path / "llm.log")
    monkeypatch.setattr(llm, "is_loaded", lambda: False)
    monkeypatch.setattr(llm, "configured_model", lambda: "configured-model")
    monkeypatch.setattr(llm.subprocess, "Popen", lambda *_a, **_k: DeadProcess())
    with pytest.raises(llm.LLMError, match="加载失败"):
        llm.load(timeout=0.01)
