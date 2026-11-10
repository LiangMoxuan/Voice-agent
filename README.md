# voice-agent · 「智语外呼」

第二届北京市大学生"人工智能+"创新大赛参赛项目。

一句话：浏览器里模拟打电话，AI 客服自报身份 → 确认身份 → 追问需求 → 沟通方案 → 确认结果 → 结构化回写数据库。全链路流式，首字时延 P50 ≤ 2 秒。

## 三步复现（评委）

1. 安装 Docker
2. `cp .env.example .env` 并填入你的 API Key
3. `docker compose -f docker/docker-compose.yml up -d --build`
4. 浏览器打开 http://localhost:8000

## 不用 Docker 的兜底方式

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # 填入 Key
python -m server.db init  # 建表
./start.sh
```

## 目录与分工

| 目录 / 文件 | 内容 | 负责人 |
|---|---|---|
| `frontend/` | 浏览器页面、WebRTC、音频采集与播放 | A |
| `server/audio/` | VAD、ASR、TTS、WebRTC 服务端 | A |
| `server/agent/` | 状态机、Prompt、意图槽位、合规护栏 | B |
| `server/tools/` | Mock 业务接口、结构化回写（幂等） | B |
| `server/main.py` `db.py` `bus.py` `logging_mw.py` | 入口、数据库、事件总线、日志中间件 | C |
| `eval/` | 评测集、评分、归因、RSI 版本管理 | C |
| `docker/` | Dockerfile、compose、一键启动 | C |
| `docs/` | 协议文档、协作规范、设计稿、材料 | C |
| `tests/` | 各模块 pytest | 各自 |

## 当前进度（Day1 骨架）

- [x] 目录骨架 + `.gitignore`（`.env` / `data/` / `.venv` 已挡）
- [x] `/health`、`/ws/control`（回声）、静态页（前端可打开）
- [x] SQLite 6 张表 + `results.tool_call_id` UNIQUE（幂等）
- [x] 事件总线 `bus.py`、日志中间件 `logging_mw.py`
- [x] 消息协议 v0（已冻结，改动需三人签字）
- [x] Mock 4 个业务接口 + `write_back` 幂等回写
- [x] 状态机 / 槽位 / Prompt v1 / 合规护栏 骨架
- [ ] 实时语音链路（A，Day3–4）
- [ ] Agent 主循环联调（B，Day5–9）
- [ ] 评测与 RSI（C，Day10–12）

## 关键文档

- 消息协议：[`docs/protocol-v0.md`](docs/protocol-v0.md)
- 协作规范（分支、PR、每日同步）：[`docs/协作规范.md`](docs/协作规范.md)
- 评测与 RSI 设计：[`eval/README.md`](eval/README.md)

## 三条铁律（赛题官方要求，违反出局）

1. 不得对真实电话外呼（只用脱敏/合成数据 + 官方 Mock 接口）
2. 不得用成品商业外呼机器人当核心（开源框架可用，须注明许可证）
3. 不得硬编码测试答案、不得针对已知用例特判
