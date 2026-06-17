#!/usr/bin/env bash
# 一键启动「念法语」的后台转写 worker。
# 自动用 VibeVoice 的 .venv-qwen（那里有 qwen_asr），缺 sounddevice 就先补装。
# 用法：  ./scripts/run_asr_worker.sh
# 直接 `python3 scripts/asr_worker.py` 会报 ModuleNotFoundError: qwen_asr —— 那是系统 python，没装模型库。
set -e

VENV="${QWEN_VENV:-$HOME/Documents/Georgian_College/GitHub/VibeVoice/.venv-qwen}"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [ ! -x "$PY" ]; then
  echo "找不到 qwen venv：$PY"
  echo "改环境变量 QWEN_VENV 指向你的 venv，或编辑本脚本里的 VENV 路径。"
  exit 1
fi

if ! "$PY" -c "import sounddevice" 2>/dev/null; then
  echo "venv 里缺 sounddevice，正在补装（含 PortAudio）…"
  "$PIP" install sounddevice
fi

echo "用 $PY 启动 worker（首次会下载 Qwen3-ASR 模型，几 GB；Ctrl+C 退出）"
exec "$PY" "$HERE/asr_worker.py"
