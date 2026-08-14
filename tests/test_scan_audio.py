from __future__ import annotations

import ast
import pathlib
import subprocess

import pytest

import scanaudio


def _redirect(tmp_path, monkeypatch):
    monkeypatch.setattr(scanaudio, "AUDIO_DIR", tmp_path / "audio")


def test_cache_name_is_stable_and_distinct(tmp_path, monkeypatch):
    _redirect(tmp_path, monkeypatch)
    a = scanaudio.cache_name("la confiture", "Thomas")
    assert a == scanaudio.cache_name("la confiture", "Thomas")
    assert a != scanaudio.cache_name("la confiture", "Amelie")
    assert a != scanaudio.cache_name("s'installer", "Thomas")
    assert a.endswith(".m4a")
    assert "la-confiture" in a          # 前缀可读，出问题时人能在 Finder 里认出来


def test_cache_name_survives_hostile_lemmas(tmp_path, monkeypatch):
    _redirect(tmp_path, monkeypatch)
    for lemma in ("l'été", "中文", "a/b", "..", ""):
        name = scanaudio.cache_name(lemma, "Thomas")
        assert "/" not in name and not name.startswith(".")


def test_ensure_generates_then_hits_cache(tmp_path, monkeypatch):
    _redirect(tmp_path, monkeypatch)
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        out = pathlib.Path(cmd[cmd.index("-o") + 1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake-audio")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(scanaudio.subprocess, "run", fake_run)
    p1 = scanaudio.ensure("la confiture", "Thomas")
    assert p1.exists() and len(calls) == 1
    p2 = scanaudio.ensure("la confiture", "Thomas")
    assert p2 == p1 and len(calls) == 1          # 第二次不再调 say


def test_ensure_leaves_no_stub_on_failure(tmp_path, monkeypatch):
    """say 失败时不许留半个空文件——那会永久冒充缓存，再也生成不出来。"""
    _redirect(tmp_path, monkeypatch)

    def boom(cmd, **kw):
        out = pathlib.Path(cmd[cmd.index("-o") + 1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"")
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(scanaudio.subprocess, "run", boom)
    with pytest.raises(scanaudio.AudioUnavailable):
        scanaudio.ensure("la confiture", "Thomas")
    assert not scanaudio.cache_path("la confiture", "Thomas").exists()
    assert list((tmp_path / "audio").glob("*.part")) == []


def test_ensure_raises_when_say_is_missing(tmp_path, monkeypatch):
    _redirect(tmp_path, monkeypatch)

    def missing(cmd, **kw):
        raise FileNotFoundError("say")

    monkeypatch.setattr(scanaudio.subprocess, "run", missing)
    with pytest.raises(scanaudio.AudioUnavailable):
        scanaudio.ensure("x", "Thomas")


def test_warm_reports_progress_and_survives_failures(tmp_path, monkeypatch):
    _redirect(tmp_path, monkeypatch)
    seen = []

    def half_broken(cmd, **kw):
        lemma = cmd[3]
        seen.append(lemma)
        if lemma == "bad":
            raise subprocess.CalledProcessError(1, cmd)
        out = pathlib.Path(cmd[cmd.index("-o") + 1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(scanaudio.subprocess, "run", half_broken)
    status = scanaudio.warm(["a", "bad", "c", "a"], "Thomas")
    status["thread"].join(timeout=10)
    assert status["total"] == 3                  # 去重
    assert status["done"] == 3
    assert status["failed"] == 1
    assert status["running"] is False


def test_concurrent_ensure_of_the_same_lemma_does_not_explode(tmp_path, monkeypatch):
    """两条路同时生成同一个词（换课时新旧预热线程重叠、或多开一个标签），
    共用 ".part" 会让后完成那条 rename 时抛 FileNotFoundError。"""
    _redirect(tmp_path, monkeypatch)
    import threading

    gate = threading.Barrier(2, timeout=10)

    def slow_say(cmd, **kw):
        out = pathlib.Path(cmd[cmd.index("-o") + 1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake")
        gate.wait()          # 两条线程都写完 .part 之后再各自去 rename
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(scanaudio.subprocess, "run", slow_say)
    errors = []

    def worker():
        try:
            scanaudio.ensure("composer", "Thomas")
        except Exception as exc:      # noqa: BLE001 —— 就是要抓住任何异常
            errors.append(exc)

    ts = [threading.Thread(target=worker) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=15)
    assert errors == []
    assert scanaudio.cache_path("composer", "Thomas").exists()
    assert list((tmp_path / "audio").glob("*.part")) == []


def test_warm_survives_an_unexpected_exception(tmp_path, monkeypatch):
    """一个词出意外不许打死整条预热线程——线程一死 running 就永远是 True，
    页面会一直卡在「发音准备中」，剩下的词再也不生成。"""
    _redirect(tmp_path, monkeypatch)

    def boom_on_one(cmd, **kw):
        if cmd[3] == "boom":
            raise RuntimeError("非 AudioUnavailable 的意外")
        out = pathlib.Path(cmd[cmd.index("-o") + 1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(scanaudio.subprocess, "run", boom_on_one)
    status = scanaudio.warm(["a", "boom", "c"], "Thomas")
    status["thread"].join(timeout=10)
    assert status["running"] is False
    assert status["done"] == 3          # 没被中途打死
    assert status["failed"] == 1
    assert scanaudio.cache_path("c", "Thomas").exists()   # boom 之后的词照样生成


def test_static_url(tmp_path, monkeypatch):
    _redirect(tmp_path, monkeypatch)
    p = scanaudio.cache_path("la confiture", "Thomas")
    assert scanaudio.static_url(p) == f"/app/static/audio/{p.name}"


def test_module_is_pure():
    tree = ast.parse(pathlib.Path("scanaudio.py").read_text("utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert not (names & {"streamlit", "sqlite3", "app"})
