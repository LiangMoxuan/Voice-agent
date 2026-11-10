"""LLM 调用封装（B 维护）。DeepSeek 兼容 OpenAI 协议。"""
import os


def _client():
    """延迟创建，保证 load_dotenv() 已执行、且没有 openai 时也能 import 本模块。"""
    from openai import OpenAI

    return OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
    )


def chat(messages, tools=None, json_mode=False, temperature=0.3, timeout=20):
    kwargs = dict(
        model=os.getenv("LLM_MODEL", "deepseek-chat"),
        messages=messages,
        temperature=temperature,
        timeout=timeout,
    )
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = _client().chat.completions.create(**kwargs)
    return resp.choices[0].message
