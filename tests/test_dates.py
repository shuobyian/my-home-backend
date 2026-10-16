from datetime import datetime
from zoneinfo import ZoneInfo

from apps.common.dates import js_datetime


def test_js_datetime():
    value = datetime(2026, 1, 2, 3, 4, 5, 678901, tzinfo=ZoneInfo("Asia/Seoul"))

    assert js_datetime(value) == "2026-01-01T18:04:05.678Z"
    assert js_datetime(None) is None
