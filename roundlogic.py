"""一轮听写的纯逻辑：决定下一步是继续、休息还是整轮结束。无 Streamlit 依赖，可单测。"""
from __future__ import annotations


def next_action(index: int, total: int, batch_size: int) -> tuple[str, int]:
    """
    index: 当前是第几个词（1-based）；total: 本轮总词数；batch_size: 每多少个歇一下。
    返回 (动作, 位置)：
      ("done", index) 整轮做完
      ("rest", index) 到休息点，先停一下
      ("go", index+1) 前进到下一个
    """
    if index >= total:
        return ("done", index)
    if batch_size and index % batch_size == 0:
        return ("rest", index)
    return ("go", index + 1)
