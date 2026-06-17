"""念法语模式的转写读写接口。
后台 ASR worker 一直把「最新转写」写到 ASR_FILE；听写网页读它。
这样 app 和 ASR 引擎解耦——app 启动/测试都不依赖真麦克风（用 stub 写文件即可）。
"""
from __future__ import annotations

import json
import os
import time

ASR_FILE = os.environ.get("DICTATION_ASR_FILE", "/tmp/dictation_asr.json")


def write_latest(text: str, final: bool = True, path: str | None = None) -> None:
    with open(path or ASR_FILE, "w", encoding="utf-8") as f:
        json.dump({"text": text, "ts": time.time(), "final": bool(final)}, f, ensure_ascii=False)


def read_latest(path: str | None = None):
    """返回 {text, ts, final} 或 None。"""
    try:
        with open(path or ASR_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def clear(path: str | None = None) -> None:
    try:
        os.remove(path or ASR_FILE)
    except OSError:
        pass
