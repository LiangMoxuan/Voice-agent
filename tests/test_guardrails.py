"""合规护栏冒烟测试（B 主写，C 复核）。"""
from server.agent.guardrails import check


def test_banned_word_blocked():
    r = check("SOLUTION", "绝对保证能省钱，年卡续费享9折，有效期12个月")
    assert r["ok"] is False
    assert "禁语" in " ".join(r["problems"])


def test_privacy_blocked():
    r = check("REQUIREMENT", "您的号码是 13812345678 对吧")
    assert r["ok"] is False


def test_must_say_missing():
    r = check("GREETING", "你好呀")
    assert r["ok"] is False


def test_clean_reply_pass():
    r = check("SOLUTION", "年卡续费享9折，有效期12个月")
    assert r["ok"] is True
