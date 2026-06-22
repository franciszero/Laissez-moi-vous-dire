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
    with LOG.open("w", encoding="utf-8") as log:
        _process = subprocess.Popen(
            ["rapid-mlx", "serve", configured_model(), "--port", "8000",
             "--served-model-name", "default", "--no-thinking"],
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
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


def _parse_json(text: str) -> dict:
    clean = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        value = json.loads(clean)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    return {"raw": text, "parse_error": True}


def grade(chinese_prompt: str, french_answer: str, rubric: str) -> dict:
    prompt = f"""你是严格但简洁的法语老师。只输出一个 JSON 对象，不要 Markdown。
字段必须是：判定（对/部分/错）、错在哪、改进建议、更好的版本。
中文提示：{chinese_prompt}
学生法语：{french_answer}
评分要点：{rubric}
若答案正确也要给自然度更高的版本；不要因可接受的表达差异误判。"""
    try:
        data = _request("/chat/completions", {
            "model": "default", "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1, "max_tokens": 600,
        }, timeout=180)
        text = data["choices"][0]["message"]["content"]
        return _parse_json(text)
    except (OSError, ValueError, KeyError, IndexError, urllib.error.URLError) as exc:
        raise LLMError(f"本地模型批改失败：{exc}") from exc


atexit.register(unload)
