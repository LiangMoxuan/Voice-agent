#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 3 天 L1：文字 -> 语音合成 -> 生成 wav（对应指南 7.2）

用法：
    python tests/tts_demo.py
    python tests/tts_demo.py "自定义要说的话"

生成文件：项目根目录 reply.wav
播放验证：afplay reply.wav
"""
import os
import sys

def die(msg, hint=""):
    print("\n[错误] " + msg)
    if hint:
        print("[怎么办] " + hint)
    sys.exit(1)

try:
    import dashscope
    from dashscope.audio.tts_v2 import SpeechSynthesizer
except ImportError:
    die("没装 dashscope",
        "先在项目根目录执行 source .venv/bin/activate 激活虚拟环境，"
        "再执行 pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple")

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(root, ".env"))
except ImportError:
    pass

api_key = (os.getenv("DASHSCOPE_API_KEY") or "").strip()
if not api_key or "在这里填" in api_key or not api_key.startswith("sk-"):
    die("DASHSCOPE_API_KEY 没有配置",
        "打开项目根目录的 .env 文件，把 DASHSCOPE_API_KEY= 后面换成组长给的真实 Key（sk- 开头）")

text = sys.argv[1] if len(sys.argv) > 1 else "您好，我是京东客服小智，请问您是张先生本人吗？"

dashscope.api_key = api_key
synth = SpeechSynthesizer(model="cosyvoice-v2", voice="longxiaochun")
audio = synth.call(text)

if not audio:
    die("合成返回为空",
        "依次检查：Key 是否有效、百炼控制台里 CosyVoice（cosyvoice-v2）是否已开通、"
        "音色 longxiaochun 是否可用、账户余额是否充足")

out = os.path.join(root, "reply.wav")
with open(out, "wb") as fp:
    fp.write(audio)

print("已生成 reply.wav")
print("完整路径:", out)
print("播放验证: afplay \"%s\"" % out)
