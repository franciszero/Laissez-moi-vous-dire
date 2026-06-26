import llm_lifecycle as lc


def test_should_idle_unload_truth_table():
    assert lc.should_idle_unload(False, last_active=0, now=10_000) is False                       # 未加载永不卸
    assert lc.should_idle_unload(True, last_active=100, now=100 + lc.IDLE_SECONDS - 1) is False    # 未到阈值
    assert lc.should_idle_unload(True, last_active=100, now=100 + lc.IDLE_SECONDS) is True         # 边界含等号
    assert lc.should_idle_unload(True, last_active=0, now=10_000) is True                          # 远超阈值


def test_idle_minutes_left_preserves_legacy_caption_formula():
    # 刚活动过：剩满阈值（沿用原 app.py 的 +1 取整公式，不改观感）
    assert lc.idle_minutes_left(last_active=1000, now=1000) == int(lc.IDLE_SECONDS / 60) + 1
    # 已超时：不显示负数
    assert lc.idle_minutes_left(last_active=0, now=10_000) == 0
