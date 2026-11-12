"""WebRTC 可用性验证（C 维护，Day4）。

指南第 7.4 节要求把音频搬到 WebRTC 轨道上，第 13 章风险表又写明：
"aiortc 装不上 / 握手折腾超过 2 天 → Day4 下午即决策，启用 WS 等效方案"。
所以这个脚本就是那道决策关：本机能不能真跑通 WebRTC，跑通了记录实测时延，
跑不通就立刻切备选，不拖到 Day5 之后。

用法：
    .venv/bin/python scripts/verify_aiortc.py
    .venv/bin/python scripts/verify_aiortc.py --frames 200 --json

做的事：
1. 本机开两个 PeerConnection，交换 offer / answer，走本地回环，不依赖外网；
2. 一边发 16 kHz 单声道正弦波音频帧（和项目里 TTS 输出同一格式）；
3. 另一边收帧，统计收到了多少帧、端到端走了多少毫秒；
4. 给出结论：WebRTC 可用 / 不可用（不可用则明确写"转 WS 备选"）。
"""
import argparse
import asyncio
import fractions
import json
import sys
import time

import numpy as np

try:
    import aiortc
    from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
    from av import AudioFrame
except ImportError:
    sys.exit("aiortc 或 av 未安装：.venv/bin/pip install -r requirements.txt")

SAMPLE_RATE = 16000
SAMPLES_PER_FRAME = 320  # 20 ms / 帧，与协议 100ms 分片前的底层帧同量级


class SineTrack(MediaStreamTrack):
    """发送端：一直产出 16 kHz 单声道正弦波，写上正确的 pts。"""

    kind = "audio"

    def __init__(self, total_frames):
        super().__init__()
        self.total = total_frames
        self.count = 0
        self.t_start = None
        self.sent_at = []  # 每帧的发车时间，用来算传输延迟

    async def recv(self):
        if self.count >= self.total:
            raise asyncio.CancelledError  # 发完就停，让对端可能收到 end
        if self.t_start is None:
            self.t_start = time.time()
        n = self.count
        t = (np.arange(SAMPLES_PER_FRAME, dtype=np.float32) + n * SAMPLES_PER_FRAME) / SAMPLE_RATE
        pcm = (np.sin(2 * np.pi * 440 * t) * 8000).astype(np.int16)

        frame = AudioFrame(format="s16", layout="mono", samples=SAMPLES_PER_FRAME)
        frame.sample_rate = SAMPLE_RATE
        frame.planes[0].update(pcm.tobytes())
        frame.pts = n * SAMPLES_PER_FRAME
        frame.time_base = fractions.Fraction(1, SAMPLE_RATE)
        self.count += 1
        self.sent_at.append(time.time())
        await asyncio.sleep(SAMPLES_PER_FRAME / SAMPLE_RATE)
        return frame


async def wait_ice(pc, timeout=3.0):
    t0 = time.time()
    while pc.iceGatheringState != "complete" and time.time() - t0 < timeout:
        await asyncio.sleep(0.05)


async def run(frames):
    result = {"ok": False, "received": 0, "sent": 0, "connect_ms": None,
              "one_way_ms": None, "conclusion": ""}
    pc_send = RTCPeerConnection()
    pc_recv = RTCPeerConnection()
    received = []

    @pc_recv.on("track")
    def on_track(track):
        async def pump():
            while True:
                try:
                    frame = await track.recv()
                except Exception:
                    break  # 发送端发完就停，这里随之退出，属正常结束
                received.append(time.time())
        asyncio.ensure_future(pump())

    track = SineTrack(frames)
    pc_send.addTrack(track)
    pc_recv.addTransceiver("audio", direction="recvonly")

    t0 = time.time()
    offer = await pc_send.createOffer()
    await pc_send.setLocalDescription(offer)
    await wait_ice(pc_send)
    await pc_recv.setRemoteDescription(RTCSessionDescription(
        sdp=pc_send.localDescription.sdp, type="offer"))
    answer = await pc_recv.createAnswer()
    await pc_recv.setLocalDescription(answer)
    await wait_ice(pc_recv)
    await pc_send.setRemoteDescription(RTCSessionDescription(
        sdp=pc_recv.localDescription.sdp, type="answer"))
    result["connect_ms"] = int((time.time() - t0) * 1000)
    result["sent"] = frames

    # 收帧数不再变化即视为传输结束，不必死等最后一帧
    last = -1
    stable_since = time.time()
    deadline = time.time() + 10
    while time.time() < deadline:
        if len(received) != last:
            last = len(received)
            stable_since = time.time()
        elif time.time() - stable_since > 0.4:
            break
        await asyncio.sleep(0.05)

    result["received"] = len(received)
    result["recv_ratio"] = round(len(received) / float(frames), 3)
    # 回环通了就算可用：允许首尾各丢几帧（发送端停发时的正常收尾）
    result["ok"] = len(received) >= max(5, int(frames * 0.8))
    if received and track.sent_at:
        n = min(len(received), len(track.sent_at))
        gaps = [(received[i] - track.sent_at[i]) * 1000 for i in range(1, n)]
        if gaps:
            result["one_way_ms"] = round(float(np.median(gaps)), 1)

    await pc_send.close()
    await pc_recv.close()
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=50)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    print("aiortc %s / 平台 %s" % (aiortc.__version__, sys.platform))
    r = asyncio.run(run(a.frames))

    if r["ok"]:
        r["conclusion"] = "WebRTC 本机回环可用，可按指南第 7.4 节上 aiortc"
    else:
        r["conclusion"] = "WebRTC 回环不通，按第 13 章风险对策转 WS 等效方案"

    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print("连接建立耗时：%s ms" % r["connect_ms"])
        print("发送/接收帧数：%s / %s（收帧率 %s）" % (r["sent"], r["received"], r.get("recv_ratio")))
        print("帧到帧单程延迟中位数：%s ms" % r["one_way_ms"])
        print("结论：%s" % r["conclusion"])

    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()
