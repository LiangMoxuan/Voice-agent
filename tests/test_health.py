"""健康检查（C 维护）。"""
from server.main import health


def test_health_returns_ok():
    assert health() == {"status": "ok"}
