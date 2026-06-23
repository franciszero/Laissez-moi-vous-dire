"""按需启动 rapid-mlx，并用本地模型批改法语自由产出。"""
from __future__ import annotations

import atexit
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

BASE_URL = os.environ.get("DICTATION_LLM_URL", "http://127.0.0.1:8000/v1")
CONFIG = Path(os.environ.get("HERMES_CONFIG", "~/.hermes/config.yaml")).expanduser()
LOG = Path(os.environ.get("DICTATION_LLM_LOG", "/tmp/dictation-rapid-mlx.log"))
_process: subprocess.Popen | None = None


class LLMError(RuntimeError):
    pass


def configured_model() -> str:
    try:
        data = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
        model = str((data.get("model") or {}).get("default") or "").strip()
    except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
        raise LLMError(f"无法读取 Hermes 配置 {CONFIG}: {exc}") from exc
    if not model:
        raise LLMError(f"Hermes 配置 {CONFIG} 缺少 model.default")
    return model


def _session_model() -> str:
    """本会话用的模型：可用 env 覆盖以做 bakeoff，否则用 Hermes 默认。"""
    return os.environ.get("DICTATION_LLM_MODEL", "").strip() or configured_model()


def _thinking_enabled() -> bool:
    """thinking 是会话级实验配置（codex 评审 #4：不在每次调用间切换模型）。"""
    return os.environ.get("DICTATION_LLM_THINKING", "").strip().lower() in ("1", "true", "yes", "on")


def _request(path: str, payload: dict | None = None, timeout: float = 3):
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer no-key-required"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def is_loaded() -> bool:
    try:
        _request("/models", timeout=1)
        return True
    except (OSError, ValueError, urllib.error.URLError):
        return False


def load(timeout: float = 600) -> float:
    """启动当前 Hermes 模型并等到 API 就绪；返回加载秒数。"""
    global _process
    if _process and _process.poll() is None and is_loaded():
        return 0.0
    if is_loaded():
        raise LLMError("8000 端口已有非本模块启动的模型服务；请先关闭它再重试。")
    started = time.monotonic()
    serve_args = ["rapid-mlx", "serve", _session_model(), "--port", "8000",
                  "--served-model-name", "default"]
    if not _thinking_enabled():
        serve_args.append("--no-thinking")
    with LOG.open("w", encoding="utf-8") as log:
        _process = subprocess.Popen(
            serve_args, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
    while time.monotonic() - started < timeout:
        if _process.poll() is not None:
            break
        if is_loaded():
            return time.monotonic() - started
        time.sleep(1)
    unload()
    try:
        detail = LOG.read_text(encoding="utf-8", errors="replace")[-1200:].strip()
    except OSError:
        detail = ""
    raise LLMError("本地模型加载失败或超时。" + (f"\n\n{detail}" if detail else ""))


def unload() -> None:
    """只停止本模块拥有的 rapid-mlx 进程。"""
    global _process
    proc, _process = _process, None
    if not proc or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def chat(prompt: str, timeout: float = 180) -> str:
    """发一条 prompt 给本地模型，返回原始文本内容（prompt 构造与解析在 aigrade）。"""
    try:
        data = _request("/chat/completions", {
            "model": "default", "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1, "max_tokens": 1200,
            "response_format": {"type": "json_object"},
        }, timeout=timeout)
        return data["choices"][0]["message"]["content"]
    except (OSError, ValueError, KeyError, IndexError, urllib.error.URLError) as exc:
        raise LLMError(f"本地模型批改失败：{exc}") from exc


atexit.register(unload)
