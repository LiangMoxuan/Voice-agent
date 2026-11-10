# 消息协议 v0（已冻结）

> **状态：Day1 冻结。之后任何字段增删改，必须走 PR + A/B/C 三人签字。**
> 传输：控制消息走 WebSocket `/ws/control`；音频走 WebRTC 轨道（备选方案为 `/ws/audio` 二进制帧）。
> 所有 JSON 序列化必须 `ensure_ascii=False`（否则中文变 `\u4f60\u597d`）。

## 1. 通用字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | string | 消息类型，见下表 |
| `session_id` | string | 一通电话的唯一 ID，格式 `S-YYYYMMDD-xxxx` |
| `turn_id` | int | 第几轮对话，从 1 开始 |
| `seq` | int | 同一轮内第几个分片（流式用） |
| `ts` | float | Unix 时间戳（秒，带小数） |

## 2. 消息清单（8 种，缺一不可）

### A→B：ASR 最终文本
```json
{"type":"asr_final","session_id":"S-20261110-001","turn_id":3,"text":"嗯我是他本人","ts":1731206400.123}
```

### B→A：Agent 开始回复（流式文字增量）
```json
{"type":"agent_text_delta","session_id":"S-20261110-001","turn_id":3,"seq":1,"delta":"好的张先生，"}
```

### B→A：本句文字可直接合成（按句切，首句越短首字时延越好看）
```json
{"type":"tts_segment","session_id":"S-20261110-001","turn_id":3,"seq":1,"text":"好的张先生，已为您确认会员身份。","final":false}
```

### A→浏览器：TTS 音频块
二进制帧，**头 4 字节 = seq（小端 uint32）**，后面是 16k 单声道 PCM。

### A→B：用户开口打断
```json
{"type":"interrupt","session_id":"S-20261110-001","turn_id":3,"reason":"vad_speech_start","ts":1731206400.123}
```

### B→C：工具调用记录（C 落库）
```json
{"type":"tool_log","session_id":"S-20261110-001","turn_id":3,"tool":"get_order","args":{"customer_id":"C0001"},"result":{"order_id":"O-7788","status":"已发货"},"latency_ms":42,"tool_call_id":"tc-20261110-0003"}
```

### B→C：结果回写（幂等）
```json
{"type":"writeback","session_id":"S-20261110-001","payload":{"is_self":true,"need":"会员权益咨询","plan":"年卡续费9折","final_status":"已登记工单","ticket_id":"T-5566","turn_count":6},"tool_call_id":"tc-20261110-0007"}
```

### C→全员：状态变化（前端展示 + 评测用）
```json
{"type":"state_change","session_id":"S-20261110-001","from":"IDENTITY_CONFIRM","to":"REQUIREMENT"}
```

### A→C：时延打点（每个环节都发）
```json
{"type":"latency_mark","session_id":"S-20261110-001","turn_id":3,"marks":{"vad_end":1731206400.001,"asr_final":1731206400.210,"llm_first_token":1731206400.640,"tts_first_audio":1731206400.980,"browser_play_first":1731206401.050}}
```

## 3. 落库约定（C 统一写，A/B 不许自己 INSERT）

**回写不重复**：`results.tool_call_id` 建 UNIQUE 索引，用 `INSERT OR IGNORE`。

**工具失败**：Mock 接口 5 秒超时、重试 1 次；仍失败返回
```json
{"error":"tool_unavailable","fallback_hint":"转人工"}
```
Agent **必须**走兜底话术，**禁止**模型编造"已为您登记成功"。

## 4. 事件总线 topic 命名（与上面的 type 一一对应）

| topic | 发布方 | 订阅方 |
|---|---|---|
| `asr_final` | A | B |
| `agent_text_delta` | B | A |
| `tts_segment` | B | A |
| `interrupt` | A | A、B |
| `tts_flush` | A | 浏览器 |
| `tool_log` | B | C |
| `writeback` | B | C |
| `state_change` | B | 全员 |
| `latency_mark` | A | C |
| `turn_log` | A、B | C |

**topic 名必须与 `type` 完全一致，不许自创别名（`asr-final` ❌）。**

## 5. 首字时延口径（不许混用）

- 起点 `t0` = VAD 判定的 **speech_end**（用户最后一个有效音频帧）
- 终点 `t1` = 浏览器第一块 TTS 音频**真正开始播放**（`browser_play_first`）
- 首字时延 = `t1 - t0`，P50 = ≥20 通样本的中位数
- **禁止**把 ASR 尾包延迟、LLM 首 token 当成首字时延
