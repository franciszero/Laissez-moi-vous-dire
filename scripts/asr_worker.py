#!/usr/bin/env python3
"""念法语 模式的后台转写 worker。
录麦克风 → 简单 VAD 攒一句话 → Qwen3-ASR 转法语 → 写最新转写到 /tmp/dictation_asr.json。
听写网页在「念法语」模式点「🛑念完了」时读这个文件。

在 VibeVoice 的 .venv-qwen 里跑（它有 qwen_asr + numpy）：
    cd ~/Documents/Georgian_College/GitHub/VibeVoice
    .venv-qwen/bin/pip install sounddevice          # 一次性（含 PortAudio）
    .venv-qwen/bin/python ~/Documents/法语/本地录屏课/听写/scripts/asr_worker.py
首次会下载 Qwen3-ASR-1.7B（几 GB）。需要麦克风权限。Ctrl+C 退出。

注意：本脚本无法在无麦克风/无模型环境测试，阈值（SILENCE_RMS 等）按你的麦克风现场调。
"""
import json
import os
import time

import numpy as np
import sounddevice as sd
from qwen_asr import Qwen3ASRModel

ASR_FILE = os.environ.get("DICTATION_ASR_FILE", "/tmp/dictation_asr.json")
SR = 16000              # Qwen3-ASR 期望 16kHz 单声道
SILENCE_RMS = 0.012     # 静音阈值（太灵敏就调大；收不到声就调小）
SILENCE_HOLD = 0.7      # 静音持续这么久算一句说完（秒）
MIN_SPEECH = 0.25       # 短于这个的忽略（秒）
BLOCK_SEC = 0.1


def write_latest(text: str) -> None:
    with open(ASR_FILE, "w", encoding="utf-8") as f:
        json.dump({"text": text, "ts": time.time(), "final": True}, f, ensure_ascii=False)


def main() -> None:
    print("加载 Qwen3-ASR-1.7B（首次会下载，几 GB）…")
    model = Qwen3ASRModel.from_pretrained("Qwen/Qwen3-ASR-1.7B")
    print(f"就绪，正在听麦克风。转写写到 {ASR_FILE}（Ctrl+C 退出）")

    block = int(SR * BLOCK_SEC)
    buf: list = []
    silence = 0.0
    speaking = False

    with sd.InputStream(samplerate=SR, channels=1, dtype="float32", blocksize=block) as stream:
        while True:
            data, _ = stream.read(block)
            chunk = data[:, 0]
            rms = float(np.sqrt(np.mean(chunk * chunk)) + 1e-9)

            if rms > SILENCE_RMS:
                speaking = True
                silence = 0.0
                buf.append(chunk)
            elif speaking:
                buf.append(chunk)
                silence += BLOCK_SEC
                if silence >= SILENCE_HOLD:
                    audio = np.concatenate(buf) if buf else np.zeros(0, np.float32)
                    buf, silence, speaking = [], 0.0, False
                    if len(audio) >= SR * MIN_SPEECH:
                        try:
                            res = model.transcribe((audio, SR), language="fr")
                            text = (res[0].text if res else "").strip()
                        except Exception as e:  # noqa: BLE001
                            print("转写出错:", e)
                            text = ""
                        if text:
                            print("→", text)
                            write_latest(text)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n退出。")
