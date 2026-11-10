"""意图/槽位解析辅助（B 维护）。"""
import json
import re


def parse_json_reply(raw):
    """剥掉模型可能加的 ```json 包裹，再解析。"""
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            return json.loads(m.group(0))
        raise
