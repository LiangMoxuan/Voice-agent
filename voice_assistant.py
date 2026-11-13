import pyaudio
import wave
from datetime import datetime

# 录音参数
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

# 时间戳命名，不会覆盖旧录音
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
WAVE_OUTPUT_FILENAME = f"recording_{timestamp}.wav"

input("🎤 按下回车键开始录音 >>>")

p = pyaudio.PyAudio()
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK)

print("✅ 录音进行中，想结束就按 Ctrl + C")
frames = []

try:
    while True:
        data = stream.read(CHUNK)
        frames.append(data)
except KeyboardInterrupt:
    print("\n🛑 收到停止指令")

stream.stop_stream()
stream.close()
p.terminate()

wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
wf.setnchannels(CHANNELS)
wf.setsampwidth(p.get_sample_size(FORMAT))
wf.setframerate(RATE)
wf.writeframes(b''.join(frames))
wf.close()
print(f"✅ 录音结束，保存为 {WAVE_OUTPUT_FILENAME}")