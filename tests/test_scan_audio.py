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
