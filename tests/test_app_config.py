from __future__ import annotations

from pathlib import Path


def test_global_base_font_size_is_configured():
    """全局根字号收到 14px：写作资料区要在有限高度里多行阅读。"""
    cfg = Path(__file__).parents[1] / ".streamlit" / "config.toml"
    text = cfg.read_text(encoding="utf-8")
    assert "[theme]" in text, "缺少 [theme] 段"
    assert "baseFontSize = 14" in text, "未设置 theme.baseFontSize = 14"


def test_existing_client_config_preserved():
    """既有的 toolbarMode 配置不许被覆盖掉。"""
    cfg = Path(__file__).parents[1] / ".streamlit" / "config.toml"
    text = cfg.read_text(encoding="utf-8")
    assert "[client]" in text and 'toolbarMode = "viewer"' in text
