# Day3 日志与落库说明（给 A、B 看的对接页）

> 状态：2026-11-13 完成并自检 8 项全过。
> 协议一个字没改（`docs/protocol-v0.md` 仍是冻结版），这里只说明**消息发过来之后落到哪张表**。

## 1. 一句话结论

A 和 B 只要按冻结协议往 `/ws/control` 发 JSON，轮次、时延、工具调用、回写结果就自动进 `data/app.db`，**不需要你们写任何 SQL**。请不要绕过 `server/db.py` 直接连库。

## 2. 消息类型 → 落库动作

| 协议消息 | 落库动作 | 落到哪张表 |
|---|---|---|
| `asr_final` | 记一条用户轮次（role=`user`） | `turns` |
| `agent_text_delta` | 先进内存缓冲，不落库 | — |
| `tts_segment`（`final:true`） | 把缓冲拼成一句，记一条 Agent 轮次（role=`agent`） | `turns` |
| `state_change` | 先把上一状态未收口的话入库（带旧状态），再切状态 | `turns` + 内存状态 |
| `interrupt` | 被打断的半句话也要留痕，立即收口入库 | `turns` |
| `latency_mark` | 五个打点键名映射成表列 | `latency_marks` |
| `tool_log` | 一条工具调用；同 `tool_call_id` 重复发不会重复写 | `tool_logs` |
| `writeback` | 幂等回写；首次插入时顺带把会话终态写上 | `results` + `sessions.final_status` |

**要点**：`agent_text_delta` 是流式的，逐条落库会把一句话拆成好几行，所以攒到 `final:true` 才写。如果中途打断，`interrupt` 会负责收口，不会丢话。

## 3. 怎么自己查

三个查询接口，浏览器直接打开：

```
http://127.0.0.1:8000/api/sessions          最近会话（含轮次数）
http://127.0.0.1:8000/api/turns/S-20261113-001   某通电话的完整轮次
http://127.0.0.1:8000/api/stats             六张表各有多少行
```

命令行核查（不用起服务，直接看库）：

```bash
sqlite3 data/app.db "select turn_id,role,state,substr(text,1,30) from turns order by turn_id desc limit 10;"
```

## 4. 日志在哪

- 控制台：`uvicorn` 窗口里直接看
- 结构化日志：`data/logs/app-YYYYMMDD.jsonl`，一行一条 JSON，字段 `ts / kind / rid / method / path / status / ms`
- `kind` 取值：`http`（正常请求）、`http_error`（请求抛异常）、`turn`（每轮落库）、`state`、`interrupt`、`latency`、`tool`、`writeback`、`record_error`（落库失败）
- 每个 HTTP 响应头带 `X-Request-Id`，报错时拿这个号去 jsonl 里 grep，能定位到具体那一次请求

`data/` 在 `.gitignore` 里，日志和库都不会进仓库。

## 5. 出问题怎么排

| 现象 | 先看哪 | 常见原因 |
|---|---|---|
| `/api/turns/xxx` 返回 0 条 | `data/logs` 里搜该 session | `session_id` 拼错；或消息缺 `session_id` |
| Agent 的话没进库 | 检查是否发了 `final:true` | 只发 delta、从不收口 |
| 轮次状态对不上 | 看 `turns.state` | 状态切换顺序反了（先切状态后收口） |
| 落库失败但信道没断 | jsonl 里 `kind:"record_error"` | 库被锁 / 磁盘满；错误原因就在该条日志 |

## 6. 自检脚本

```bash
bash scripts/verify_day3.sh          # 8 项，含真实 WebSocket 发 8 条消息
.venv/bin/python scripts/day3_probe.py ws://127.0.0.1:8000/ws/control S-测试号
```

`day3_probe.py` 不发语音，只伪造一轮完整对话，用来在 mic 和 Agent 还没接上时先验证落库链路。
