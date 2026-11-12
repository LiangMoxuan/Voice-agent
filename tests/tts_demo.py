#!/usr/bin/env python3
"""Day2 验收项：语音合成演示（生成 reply.wav 并能播放出声）

用法：
    python tests/tts_demo.py                 # 用默认文本
    python tests/tts_demo.py "要合成的话"     # 指定文本

支持两种 Key（脚本自动判断）：
  1. sk-sp- 开头 → 阿里云百炼 Token Plan 套餐专属 Key
     接口：/api/v1/services/audio/tts/SpeechSynthesizer
     模型：qwen-audio-3.0-tts-plus，音色 longanhuan_v3.6
  2. sk- 开头（普通百炼按量付费 Key）→ dashscope SDK + cosyvoice-v2

输出文件固定为项目根目录 reply.wav（16kHz / 单声道，可直接喂给 asr_demo.py）
"""
import os
import sys
import json
import pathlib
import subprocess

from dotenv import load_dotenv
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

OUT = ROOT / "reply.wav"
TEXT = sys.argv[1] if len(sys.argv) > 1 else "您好，我是京东客服小智，请问您是张先生本人吗？"

TOKEN_PLAN_URL = "https://token-plan.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer"


def die(msg, tips):
    print(f"\n[错误] {msg}")
    for t in tips:
        print(f"[怎么办] {t}")
    sys.exit(1)


def fetch_key():
    key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not key or "在这里填" in key:
        die("DASHSCOPE_API_KEY 没有配置", ["打开项目根目录 .env，把 DASHSCOPE_API_KEY= 后面换成真实 Key（sk- 开头）"])
    return key


def synth_token_plan(key):
    model = os.getenv("TTS_MODEL", "qwen-audio-3.0-tts-plus")
    voice = os.getenv("TTS_VOICE", "longanhuan_v3.6")
    payload = {
        "model": model,
        "input": {"text": TEXT, "voice": voice, "format": "wav", "sample_rate": 16000},
    }
    r = requests.post(
        TOKEN_PLAN_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    if r.status_code != 200:
        die(f"合成接口返回 {r.status_code}", [str(r.text)[:300], "确认 Key 是 Token Plan 套餐 Key、且套餐未过期"])
    data = r.json()
    url = data.get("output", {}).get("audio", {}).get("url")
    if not url:
        die("返回里没有音频地址", [json.dumps(data, ensure_ascii=False)[:300]])
    audio = requests.get(url, timeout=120)
    OUT.write_bytes(audio.content)
    return model, data.get("usage", {})


def synth_dashscope(key):
    import dashscope
    from dashscope.audio.tts_v2 import SpeechSynthesizer

    dashscope.api_key = key
    model = os.getenv("TTS_MODEL", "cosyvoice-v2")
    voice = os.getenv("TTS_VOICE", "longxiaochun")
    s = SpeechSynthesizer(model=model, voice=voice)
    audio = s.call(TEXT)
    if not audio:
        die("合成返回空音频", ["确认该 Key 已开通 CosyVoice 语音合成", "确认 voice 名与模型匹配（cosyvoice-v2 配 longxiaochun）"])
    OUT.write_bytes(audio)
    return model, {}


def main():
    key = fetch_key()
    print(f"[1/3] 文本：{TEXT}")
    if key.startswith("sk-sp-"):
        model, usage = synth_token_plan(key)
        print(f"[2/3] 套餐模式合成完成，模型 {model}，计费字符 {usage.get('characters', '—')}")
    else:
        model, usage = synth_dashscope(key)
        print(f"[2/3] 按量模式合成完成，模型 {model}")
    size = OUT.stat().st_size
    print(f"[3/3] 已生成：{OUT}（{size/1024:.0f} KB）")
    print("\n播放命令：")
    print(f"  afplay {OUT}")
    try:
        subprocess.run(["afplay", str(OUT)], check=False, timeout=60)
    except Exception:
        pass
    print("\n成功标志：听到一句中文客服开场白，文件 reply.wav 存在且大于 100 KB。")


if __name__ == "__main__":
    main()
