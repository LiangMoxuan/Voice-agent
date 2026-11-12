#!/usr/bin/env python3
"""麦克风录音基础演示（A 同学 Day2 产出，C 代为移植到 main 基线）

功能：录制 3 秒麦克风音频，保存为 output.wav（16 kHz / 单声道 / 16 bit）
这两个参数与识别接口的要求一致，录完可直接用 tests/asr_demo.py 验证。

依赖安装（macOS 需先装 PortAudio）：
    brew install portaudio          # 没装 Homebrew 时先装 brew
    .venv/bin/pip install pyaudio

用法：
    .venv/bin/python tests/mic_record_demo.py
"""
import pyaudio
import wave

# 录音基础配置
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RECORD_SECONDS = 3
WAVE_OUTPUT_FILENAME = "output.wav"

p = pyaudio.PyAudio()

stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK)

print("开始录音，3秒后自动停止...")
frames = []

for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
    data = stream.read(CHUNK)
    frames.append(data)

print("录音结束！")

stream.stop_stream()
stream.close()
p.terminate()

wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
wf.setnchannels(CHANNELS)
wf.setsampwidth(p.get_sample_size(FORMAT))
wf.setframerate(RATE)
wf.writeframes(b''.join(frames))
wf.close()
print("音频保存成功：output.wav")