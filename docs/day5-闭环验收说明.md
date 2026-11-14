# Day5 文本闭环验收说明（C 维护）

> 对应指南第 10 章 Day5：C 任务"必说/禁语词表（通用版）"，验收"文本闭环走通到 COMPLETED"。
> 产出：`server/agent/guardrails.yaml`（v1.1）+ `docs/guardrails-词表-v1.md` + `scripts/day5_close_loop.py` + `scripts/verify_day5.sh`。

## 1. 结论

| 验收项 | 结果 |
|---|---|
| 词表可加载 | 禁语 31 条、必说 8 个状态、隐私 3 种格式 |
| 禁语命中 | 整句替换为兜底话术，原文不下发 |
| 隐私命中 | 手机号、身份证号均被拦 |
| 合规话术 | 正常放行，不误伤 |
| 缺必说话术 | 被拦并替换 |
| 自动测试 | 21 passed |
| 文本闭环 | 7 轮走完 INIT → COMPLETED，41 条协议消息全部落库 |
| 验货脚本 | `bash scripts/verify_day5.sh` 8/8 |

## 2. 怎么跑

```bash
cd ~/Desktop/voice-agent
bash scripts/verify_day5.sh
```

只想单独看闭环：

```bash
.venv/bin/python -m uvicorn server.main:app --port 8010 &
.venv/bin/python scripts/day5_close_loop.py
```

## 3. 闭环发了什么

脚本扮演"整条链路"，把 8 种协议消息按真实顺序发进 `/ws/control`。7 轮对话：

| 轮 | 用户说 | 状态迁移 | Agent 要点 |
|---|---|---|---|
| 1 | （Agent 主动开口） | INIT → GREETING | 报身份：京东客服小智 |
| 2 | 是我本人 | GREETING → IDENTITY_CONFIRM | 确认本人，提示会员下月到期 |
| 3 | 到期了怎么办 | IDENTITY_CONFIRM → REQUIREMENT | 追问续费还是放着 |
| 4 | 续一下怎么算 | REQUIREMENT → SOLUTION | 9折 + 12个月 + 到期短信提醒 |
| 5 | 就按这个办 | SOLUTION → CONFIRM | 再确认一次"可以吗" |
| 6 | 办吧 | CONFIRM → WRITEBACK | 已登记 + 回写业务系统 |
| 7 | （Agent 收尾） | WRITEBACK → COMPLETED | 感谢、再见 |

每轮固定五件事：用户开口（`asr_final`）→ Agent 流式出字（`agent_text_delta`）→ 本句合成（`tts_segment` final）→ 切状态（`state_change`）→ 时延打点（`latency_mark`）。第 6 轮额外发 `tool_log` 与 `writeback`。

一共 41 条消息。

## 4. 落库侧还原出了什么

| 检查 | 实际 | 判定 |
|---|---|---|
| 轮次落库 | 用户 5 条 / Agent 7 条 / 合计 12 条 | 通过 |
| results 表 | 1 行，`ticket_id = T-20261114-01`，五个必需槽位齐全 | 通过 |
| 时延打点 | 7 条，每轮一条 | 通过 |
| 工具记录 | 1 条（write_back） | 通过 |

这就是"一通完整电话"在数据库里的样子：谁说了什么、走到哪一步、每段多慢、调了什么接口、最终结果是什么。

## 5. 这个脚本证明了什么、没证明什么

**证明了三件事：**

1. 协议 8 种消息都能被 `turns.py` 正确识别并落入对应表，没有 silently 丢消息
2. `state_change` 时"先收口再切状态"的顺序是对的——12 条轮次里 Agent 的话没有串到下一个状态上
3. `results` 的幂等与校验链是通的：`write_back` 校验五个必需字段 + 状态白名单，才写入

**没证明两件事（必须说清）：**

1. **没有真实语音**。这里所有文字都是脚本造的，A 的 `vad / asr_client / tts_client / webrtc` 还是 TODO，所以麦克风 → 文字 → 回音这条链路没被验证。
2. **没有真实决策**。B 的 `fsm.step()` 仍抛 `NotImplementedError`，状态是我在脚本里手动"推"过去的，不是 Agent 自己判断的。真正的"文本闭环"要等 `step()` 实现。

所以准确说法是：**落库侧闭环已通，整条业务闭环待 A、B 接上。** 指南 Day5 的验收项写的是"文本闭环走通到 COMPLETED"，从 C 侧能控的部分看，这一项已经做完并留了可复跑的脚本。

## 6. 探针标记

脚本默认会话号形如 `S-20261114-probe-d5`，带 `probe` 字样。

`eval/latency.py` 里 `_is_probe()` 会把这类会话识别为探针数据，**不计入比赛验收样本**。所以这个脚本造出来的时延数字不会被误当成真实成绩——这一点是特意设计的，不能省。

## 7. 下一步（Day6 之前要补的）

1. 官方词表到手后整份替换 `guardrails.yaml`，跑 `verify_day5.sh` 复验
2. 等 B 的 `fsm.step()` 落地后，本脚本可以改成"只发用户话，由 Agent 真实决策"，那时才是完整闭环
3. 等 A 的音频链路通了，加一条真人录音的端到端测试
