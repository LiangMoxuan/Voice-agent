"""时延统计工具测试（C 维护，Day4）。"""
import os
import tempfile
import uuid

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "lat.db"))

import pytest  # noqa: E402

from eval import latency  # noqa: E402
from server import db  # noqa: E402


@pytest.fixture()
def clean():
    db.init()
    return db


def add_case(sid, turn, e2e_ms, asr=300, llm=700, tts=1000, play=True):
    vad = 1000.0
    db.add_latency(sid, turn, {
        "vad_end": vad,
        "asr_final": vad + asr / 1000.0,
        "llm_first_token": vad + llm / 1000.0,
        "tts_first_audio": vad + tts / 1000.0,
        "browser_play_first": (vad + e2e_ms / 1000.0) if play else None,
    })


def test_percentiles_and_segments(clean):
    s = "S-lat-%s" % uuid.uuid4().hex[:6]
    for i, e in enumerate([1000, 1200, 1500, 1800, 1900], start=1):
        add_case(s, i, e)
    r = latency.compute(s)
    assert r["summary"]["turns"] == 5
    assert r["summary"]["p50_ms"] == 1500
    assert r["summary"]["mean_asr_ms"] == 300
    assert r["turns"][0]["tts_ms"] == 1000


def test_missing_play_marks_are_excluded(clean):
    s = "S-lat-%s" % uuid.uuid4().hex[:6]
    add_case(s, 1, 1400)
    add_case(s, 2, 0, play=False)  # 没打首播时点，不能当 0ms 计入
    r = latency.compute(s)
    assert r["summary"]["turns"] == 1
    assert r["summary"]["missing_marks"] == 1


def test_gate_passes_when_fast(clean):
    s = "S-lat-%s" % uuid.uuid4().hex[:6]
    for i, e in enumerate([1200, 1400, 1500, 1700, 1800, 1900], start=1):
        add_case(s, i, e)
    g = latency.gate(latency.compute(s)["summary"])
    assert g["passed"] is True


def test_gate_fails_when_slow(clean):
    s = "S-lat-%s" % uuid.uuid4().hex[:6]
    for i, e in enumerate([2000, 2100, 2400, 2800, 3200], start=1):
        add_case(s, i, e)
    g = latency.gate(latency.compute(s)["summary"])
    assert g["passed"] is False
    assert any("P95" in p for p in g["problems"])


def test_probe_data_is_flagged(clean):
    r = latency.compute("S-20261113-201530-check")
    if r["summary"]["turns"]:
        assert r["summary"]["probe_turns"] == r["summary"]["turns"]
    assert latency._is_probe("S-day3-probe") and latency._is_probe("S-test-abc")
    assert not latency._is_probe("S-20261114-001")
