from datetime import UTC


def js_datetime(value):
    """JS Date#toJSON 형식 (UTC, 밀리초, Z) — 기존 NestJS 응답과 같은 모양."""
    if value is None:
        return None
    value = value.astimezone(UTC)
    return value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond // 1000:03d}Z"
