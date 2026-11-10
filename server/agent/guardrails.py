"""合规护栏（B 主写，C 复核词表）。规则层永远不能只靠 Prompt。"""
import os
import re

FALLBACK_TEXT = "不好意思，这个问题我帮您转接人工客服，请稍等。"
YAML_PATH = os.path.join(os.path.dirname(__file__), "guardrails.yaml")

_BANNED = ["绝对保证", "100%", "肯定赚钱", "不买就亏了", "最后一次机会", "包您满意"]
_MUST = {
    "GREETING": r"(京东)?客服.*(身份|小智)",
    "SOLUTION": r"9折.*12个月|到期(前)?提醒",
    "COMPLETED": r"再见|感谢",
}
_PRIVACY = r"1[3-9]\d{9}"


def load_rules(path=YAML_PATH):
    """词表放 yaml，官方资料包到手后只换数据、不动代码。"""
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


RULES = load_rules()
if RULES:
    _BANNED = RULES.get("banned") or _BANNED
    _MUST = RULES.get("must_say") or _MUST
    _PRIVACY = RULES.get("privacy_pattern") or _PRIVACY
    FALLBACK_TEXT = RULES.get("fallback_text") or FALLBACK_TEXT


def check(state, reply, had_tool=False):
    """返回 {'ok': bool, 'problems': [...], 'reply': 下发文本}。命中即换成兜底话术。"""
    problems = []
    if re.search(_PRIVACY, reply or ""):
        problems.append("隐私泄露")
    hits = [w for w in _BANNED if w in (reply or "")]
    if hits:
        problems.append("禁语:" + ",".join(hits))
    pat = _MUST.get(state)
    if pat and not re.search(pat, reply or ""):
        problems.append("缺必说话术")
    if problems:
        return {"ok": False, "problems": problems, "reply": FALLBACK_TEXT}
    return {"ok": True, "problems": [], "reply": reply}
