"""LLM 资源生命周期 policy —— 与 llm.py（mechanism）分开。

不变量（单一的家）：本模块只决定「何时 load / unload」，委托 llm.load()/llm.unload()
管理 rapid-mlx 子进程；**绝不读写 Hermes 配置 ~/.hermes/config.yaml**
（配置仅由 llm.configured_model() 只读取用）。rapid-mlx benchmark 曾覆盖过它一次，故立此规。
"""
from __future__ import annotations

IDLE_SECONDS = 5 * 60  # 模型闲置多久后自动卸载（兜底，最大泄漏 = 此阈值）


def should_idle_unload(loaded: bool, last_active: float, now: float,
                       idle_seconds: int = IDLE_SECONDS) -> bool:
    """已加载且闲置 ≥ 阈值 → 该卸载。"""
    return loaded and (now - last_active) >= idle_seconds


def idle_minutes_left(last_active: float, now: float,
                      idle_seconds: int = IDLE_SECONDS) -> int:
    """距自动卸载还剩几分钟（给 UI caption；保持原 app.py 公式不变）。"""
    idle = now - last_active
    return max(0, int((idle_seconds - idle) / 60) + 1)
