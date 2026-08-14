"""扫读的逐词发音缓存：macOS say → m4a，落在 static/audio/ 由 Streamlit 静态服务送出。

页面里用 <audio src="/app/static/audio/xxx.m4a">，点 ▶ 是纯浏览器行为，
不产生 rerun——这是速过能比逐词模式快两个数量级的前提之一。

无 Streamlit / sqlite3 依赖，可单测。
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import threading
from pathlib import Path

AUDIO_DIR = Path(__file__).resolve().parent / "static" / "audio"
STATIC_PREFIX = "/app/static/audio"
SAY_TIMEOUT = 30

_UNSAFE = re.compile(r"[^a-zA-Z0-9]+")


class AudioUnavailable(RuntimeError):
    """这个词的发音生成不出来（say 缺失、超时、或合成失败）。"""


def cache_name(lemma: str, voice: str) -> str:
    """文件名 = 可读前缀 + 内容哈希。

    哈希保证不同 lemma/voice 不撞车（重音、撇号、中文都安全）；
    前缀保证出问题时人能在 Finder 里一眼认出是哪个词。
    """
    slug = _UNSAFE.sub("-", lemma).strip("-").lower()[:24] or "x"
    digest = hashlib.sha1(f"{lemma}\x00{voice}".encode("utf-8")).hexdigest()[:10]
    return f"{slug}-{digest}.m4a"


def cache_path(lemma: str, voice: str) -> Path:
    return AUDIO_DIR / cache_name(lemma, voice)


def static_url(path: Path) -> str:
    return f"{STATIC_PREFIX}/{Path(path).name}"


def ensure(lemma: str, voice: str) -> Path:
    """缓存命中直接返回；否则用 say 生成。失败抛 AudioUnavailable。"""
    path = cache_path(lemma, voice)
    if path.exists() and path.stat().st_size > 0:
        return path
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    # 临时名必须按进程+线程唯一。同一个词可能被两条路同时生成（连着换两次课时
    # 新旧预热线程重叠、或者多开一个浏览器标签），共用 ".part" 会让先完成的那条
    # 把文件搬走，后完成的那条 rename 时找不到源文件而抛 FileNotFoundError。
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.part")
    try:
        subprocess.run(
            ["say", "-v", voice, lemma, "-o", str(tmp),
             "--file-format=m4af", "--data-format=aac"],
            check=True,
            capture_output=True,
            timeout=SAY_TIMEOUT,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        tmp.unlink(missing_ok=True)   # 半个空文件会永久冒充缓存，必须清掉
        raise AudioUnavailable(f"{lemma!r} 的发音生成失败：{exc}") from exc
    tmp.replace(path)                 # 原子改名：只有完整文件才配叫最终名
    return path


def warm(lemmas, voice: str) -> dict:
    """后台预热整课发音。返回一个 status dict，主线程每次 rerun 直接读：

        {"total": n, "done": 0, "failed": 0, "running": True, "thread": Thread}

    故意不回调、不碰 session_state——工作线程没有 Streamlit 的脚本上下文，
    往 session_state 写会炸。主线程轮询这个普通 dict 最省事也最稳。
    """
    items = list(dict.fromkeys(lemmas))   # 去重且保序
    status = {"total": len(items), "done": 0, "failed": 0, "running": True}

    def run() -> None:
        # catch 得宽是故意的：一个词出意外不能把整条预热线程打死。线程一死，
        # status["running"] 就永远停在 True，页面会一直显示「发音准备中」，
        # 而这一课剩下的词再也不会生成。宁可记一次 failed 继续往下走。
        try:
            for lemma in items:
                try:
                    ensure(lemma, voice)
                except Exception:
                    status["failed"] += 1
                status["done"] += 1
        finally:
            status["running"] = False

    thread = threading.Thread(target=run, daemon=True, name="scanaudio-warm")
    status["thread"] = thread
    thread.start()
    return status
