from roundlogic import next_action


def test_next_action():
    assert next_action(5, 144, 10) == ("go", 6)        # 普通前进
    assert next_action(10, 144, 10) == ("rest", 10)    # 到批次边界 -> 休息
    assert next_action(20, 144, 10) == ("rest", 20)
    assert next_action(144, 144, 10) == ("done", 144)  # 到末尾 -> 结束
    assert next_action(140, 140, 10) == ("done", 140)  # 末尾即使是边界也算结束，不休息
    assert next_action(1, 5, 10) == ("go", 2)          # 每批比总数还大 -> 不休息
