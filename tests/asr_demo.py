#!/usr/bin/env python3
"""Day2 验收项：语音识别演示（把一段中文录音转成文字）

用法：
    python tests/asr_demo.py reply.wav
    python tests/asr_demo.py ~/Desktop/我的录音.wav

支持两种 Key（脚本自动判断）：
  1. sk-sp- 开头 → 阿里云百炼 Token Plan 套餐专属 Key
     接口：/api/v1/services/aigc/multimodal-generation/generation
     模型：qwen-audio-3.0-asr-flash（非实时，单段 ≤5 分钟）
     音频以 Base64 Data URI 上传，无需公网地址
  2. sk- 开头（普通百炼按量付费 Key）→ dashscope SDK + paraformer-realtime-v2
"""
import os
import sys
import json
import base64
import pathlib

from dotenv import load_dotenv
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

TOKEN_PLAN_URL = "https://token-plan.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

MIME = {
    "wav": "audio/wav", "mp3": "audio/mpeg", "m4a": "audio/mp4",
    "ogg": "audio/ogg", "opus": "audio/opus", "flac": "audio/flac",
}


def die(msg, tips):
    print(f"\n[错误] {msg}")
    for t in tips:
        print(f"[怎么办] {t}")
    sys.exit(1)


def check_audio(path):
    if not path.exists():
        die(f"找不到音频文件：{path}", ["确认路径拼写", "可以先用 python tests/tts_demo.py 生成一段 reply.wav 来测试"])
    if path.stat().st_size < 1024:
        die("音频文件过小，可能是空文件", ["换一段真实录音"])
    return path.suffix.lstrip(".").lower() or "wav"


def asr_token_plan(key, path, fmt):
    b64 = base64.b64encode(path.read_bytes()).decode()
    payload = {
        "model": os.getenv("ASR_MODEL", "qwen-audio-3.0-asr-flash"),
        "input": {
            "messages": [{
                "role": "user",
                "content": [{"type": "input_audio", "input_audio": {"data": f"data:{MIME.get(fmt, 'audio/' + fmt)};base64,{b64}"}}],
            }]
        },
        "parameters": {"format": fmt, "sample_rate": 16000, "language_hints": ["zh"]},
    }
    r = requests.post(
        TOKEN_PLAN_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=300,
    )
    if r.status_code != 200:
        die(f"识别接口返回 {r.status_code}", [str(r.text)[:300], "确认套餐 Key 有效、音频不超过 5 分钟"])
    data = r.json()
    text = data.get("output", {}).get("text")
    if not text:
        text = data.get("output", {}).get("sentence", {}).get("text", "")
    return text, data.get("usage", {})


def asr_dashscope(key, path):
    import dashscope
    from dashscope.audio.asr import Recognition

    dashscope.api_key = key
    import wave
    with wave.open(str(path), "rb") as w:
        ch, rate = w.getnchannels(), w.getframerate()
    if ch != 1 or rate != 16000:
        die(f"音频须为 16kHz 单声道，当前 {rate}Hz / {ch} 声道",
            [f"先转换：afconvert -f WAVE -d LEI16@16000 -c 1 '{path}' reply16k.wav", "再用本脚本识别 reply16k.wav"])
    model = os.getenv("ASR_MODEL", "paraformer-realtime-v2")
    rec = Recognition(model=model, format="pcm", sample_rate=16000, callback=None)
    result = rec.call(str(path))
    return (result.get_sentence() or {}).get("text", "") if isinstance(result, dict) else str(result)


def main():
    if len(sys.argv) < 2:
        die("缺少音频路径参数", ["用法：python tests/asr_demo.py reply.wav"])
    path = pathlib.Path(sys.argv[1]).expanduser().resolve()
    fmt = check_audio(path)

    key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not key or "在这里填" in key:
        die("DASHSCOPE_API_KEY 没有配置", ["打开项目根目录 .env，填入真实 Key"])

    print(f"[1/3] 音频：{path.name}（{path.stat().st_size/1024:.0f} KB，格式 {fmt}）")
    if key.startswith("sk-sp-"):
        text, usage = asr_token_plan(key, path, fmt)
        print(f"[2/3] 套餐模式识别完成，音频时长 {usage.get('duration', '—')} 秒")
    else:
        text = asr_dashscope(key, path)
        print("[2/3] 按量模式识别完成")
    print(f"[3/3] 识别结果：{text}")
    print("\n成功标志：上面打出来的是一句通顺的中文，和录音内容一致。")


if __name__ == "__main__":
    main()
