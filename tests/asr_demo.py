#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 3 天 L1：录音 -> 识别 -> 在终端打印文字（对应指南 7.2）

用法：
    python tests/asr_demo.py 你的录音.wav

录音要求：16kHz、单声道、PCM 的 wav。
macOS 转换方法（有 m4a/mp3 时）：
    afconvert -f WAVE -d LEI16@16000 -c 1 输入.m4a tests/sample.wav
    （afconvert 是 macOS 自带，不需要装 ffmpeg）
"""
import os
import sys
import wave

def die(msg, hint=""):
    print("\n[错误] " + msg)
    if hint:
        print("[怎么办] " + hint)
    sys.exit(1)

# ---------- 1. 依赖 ----------
try:
    import dashscope
    from dashscope.audio.asr import Recognition, RecognitionCallback
except ImportError:
    die("没装 dashscope",
        "先在项目根目录执行 source .venv/bin/activate 激活虚拟环境，"
        "再执行 pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple")

# ---------- 2. 读 .env ----------
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except ImportError:
    pass

api_key = (os.getenv("DASHSCOPE_API_KEY") or "").strip()
if not api_key or "在这里填" in api_key or not api_key.startswith("sk-"):
    die("DASHSCOPE_API_KEY 没有配置",
        "打开项目根目录的 .env 文件，把 DASHSCOPE_API_KEY= 后面换成组长给的真实 Key（sk- 开头）")

# ---------- 3. 参数与音频检查 ----------
if len(sys.argv) < 2:
    die("缺少录音文件参数", "用法：python tests/asr_demo.py 你的录音.wav")

wav_path = sys.argv[1]
if not os.path.exists(wav_path):
    die("找不到文件：" + wav_path, "确认路径写对了，文件名带空格时要加引号")

f = wave.open(wav_path, "rb")
rate = f.getframerate()
channels = f.getnchannels()
if rate != 16000:
    die("采样率是 %d Hz，需要 16000 Hz" % rate,
        "转换命令：afconvert -f WAVE -d LEI16@16000 -c 1 \"%s\" tests/sample.wav" % wav_path)
if channels != 1:
    die("声道数是 %d，需要单声道" % channels,
        "转换命令：afconvert -f WAVE -d LEI16@16000 -c 1 \"%s\" tests/sample.wav" % wav_path)

class CB(RecognitionCallback):
    def on_event(self, result):  # noqa: N802
        sent = result.get_sentence()
        if sent and sent.get("text"):
            print("识别:", sent["text"])

dashscope.api_key = api_key
rec = Recognition(model="paraformer-realtime-v2", format="pcm", sample_rate=16000, callback=CB())
rec.start()
while True:
    chunk = f.readframes(3200)  # 每块 200ms
    if not chunk:
        break
    rec.send_audio_frame(chunk)
rec.stop()

print("\n[完成] 以上是识别结果。如果中间出现报错，先确认：Key 是否有效、"
      "百炼控制台里“paraformer-realtime-v2”是否已开通、余额是否充足。")
