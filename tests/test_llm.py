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


def test_chat_returns_content_and_requests_json(monkeypatch):
    response = {"choices": [{"message": {"content": '{"总判定":"部分"}'}}]}
    payloads = []
    def urlopen(req, **_kwargs):
        payloads.append(json.loads(req.data))
        return _Response(json.dumps(response).encode())
    monkeypatch.setattr(llm.urllib.request, "urlopen", urlopen)
    assert llm.chat("批改这句") == '{"总判定":"部分"}'
    assert payloads[0]["response_format"] == {"type": "json_object"}
    assert payloads[0]["messages"][0]["content"] == "批改这句"


def test_session_model_and_thinking_are_env_configurable(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text("model:\n  default: hermes-default\n", encoding="utf-8")
    monkeypatch.setattr(llm, "CONFIG", config)
    monkeypatch.delenv("DICTATION_LLM_MODEL", raising=False)
    assert llm._session_model() == "hermes-default"          # 默认用 Hermes
    monkeypatch.setenv("DICTATION_LLM_MODEL", "bakeoff-27b")
    assert llm._session_model() == "bakeoff-27b"             # env 覆盖以做 bakeoff
    monkeypatch.delenv("DICTATION_LLM_THINKING", raising=False)
    assert llm._thinking_enabled() is False
    monkeypatch.setenv("DICTATION_LLM_THINKING", "true")
    assert llm._thinking_enabled() is True


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


def test_unload_never_writes_hermes_config(tmp_path, monkeypatch):
    """生命周期不变量：卸载只停进程，绝不改 Hermes 配置（曾被 benchmark 覆盖过）。"""
    config = tmp_path / "config.yaml"
    config.write_text("model:\n  default: keep-me\n", encoding="utf-8")
    before = config.read_text(encoding="utf-8")
    monkeypatch.setattr(llm, "CONFIG", config)

    # 无进程分支：unload 空转，配置不变
    llm._process = None
    llm.unload()
    assert config.read_text(encoding="utf-8") == before

    # 有进程分支：走真实 terminate/wait 卸载路径，仍绝不碰配置
    class _FakeProc:
        def poll(self): return None          # 活着 → 进入 terminate 分支
        def terminate(self): self.killed = True
        def wait(self, timeout=None): return 0
    llm._process = _FakeProc()
    llm.unload()
    assert config.read_text(encoding="utf-8") == before
    assert llm._process is None              # 卸载后进程句柄清空
