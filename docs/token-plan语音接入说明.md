# Token Plan 语音接口接入说明（Day2 实测记录）

记录日期：2026-11-12　记录人：C（工程集成与 RSI）

## 一、结论先说

本次拿到的 Key 是 **阿里云百炼 Token Plan 套餐专属 Key**，前缀 `sk-sp-`。
它**不能**配普通地址 `dashscope.aliyuncs.com`，必须配专属网关：

```
https://token-plan.cn-beijing.maas.aliyuncs.com
```

用错地址会一直返回 `401 InvalidApiKey`，看起来像 Key 无效，实际是地址不匹配。

## 二、套餐内可用的语音模型

| 用途 | 模型名 | 说明 |
| --- | --- | --- |
| 语音识别 | `qwen-audio-3.0-asr-flash` | 非实时，单段音频 ≤ 5 分钟 |
| 语音合成 | `qwen-audio-3.0-tts-plus` | 音色示例 `longanhuan_v3.6`，支持 wav/mp3/pcm/opus |
| 实时对话 | `qwen-audio-3.0-realtime-plus` | Day3 做低延迟链路时再评估 |

已实测：`qwen-plus`、`paraformer-realtime-v2`、`cosyvoice-v2` **不在**套餐模型列表里，用它们会返回 `404 Model not exist`。

## 三、两个端点的调用方式

### 语音合成

```
POST https://token-plan.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer
Authorization: Bearer <sk-sp Key>
Content-Type: application/json

{"model":"qwen-audio-3.0-tts-plus",
 "input":{"text":"...","voice":"longanhuan_v3.6","format":"wav","sample_rate":16000}}
```

返回 `output.audio.url`，**音频 URL 有时效，必须立刻下载**；`usage.characters` 为计费字符数。

### 语音识别

```
POST https://token-plan.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
Authorization: Bearer <sk-sp Key>
Content-Type: application/json

{"model":"qwen-audio-3.0-asr-flash",
 "input":{"messages":[{"role":"user","content":[{"type":"input_audio",
   "input_audio":{"data":"data:audio/wav;base64,<音频 Base64>"}}]}]},
 "parameters":{"format":"wav","sample_rate":16000,"language_hints":["zh"]}}
```

返回 `output.text` 为识别文本，`usage.duration` 为音频秒数。音频走 Base64 内联，**不需要公网地址**。

## 四、实测结果

| 验证 | 结果 |
| --- | --- |
| 合成"您好，我是京东客服小智，请问您是张先生本人吗？" | 成功，耗时 1.7 秒，43 计费字符，产出 135 KB wav（16 kHz 单声道） |
| 把上一步的 wav 直接喂给识别接口 | 成功，音频时长 4 秒，识别为"您好，我是京东客服小智，请问您是张先生本人吗。" |
| 语音长度上限 | 单段 5 分钟，超出需切片 |

## 五、对项目的影响（Day3 前必须知道）

1. **指南第 7 章按 `paraformer` 实时流式写的**，套餐只有非实时识别。
   Day3 若要做"边说边出字"，需要向学姐确认套餐是否含 `qwen-audio-3.0-realtime-plus` 的实时能力，
   否则链路要改成"分段录音 + 非实时识别"，时延口径按第 7.5 节重算。
2. `tests/asr_demo.py`、`tests/tts_demo.py` 已按 Key 前缀**自动切换**两套接入方式，
   普通 `sk-` Key 到手后无需改代码。
3. Key 只写在 `.env`（已被 `.gitignore` 第 17 行挡住），仓库公开，**任何 Key 都不得提交**。

## 六、出问题时的排查顺序

1. `401 InvalidApiKey`：先核对地址是不是带 `token-plan.cn-beijing`；再核对 Key 有没有抄错字符（`l` 与 `I`、`0` 与 `O` 最容易错）。
2. `404 Model not exist`：模型名不在套餐里，见上表。
3. 合成成功但下载失败：音频 URL 过期，重新合成。
4. 识别结果为空：确认 `parameters.format` 与音频真实格式一致。
