"""测试用：模拟后台 ASR worker，把一句转写写进 ASR_FILE。
用法：python3 scripts/asr_stub.py "réfrigérateur"
然后在听写「念法语」模式点「🛑 念完了」，就会读到这句。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import asr  # noqa: E402

text = " ".join(sys.argv[1:]) or "bonjour"
asr.write_latest(text, final=True)
print(f"已写入转写：{text!r} -> {asr.ASR_FILE}")
