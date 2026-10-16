"""숫자 표현 유틸.

결과 테이블은 수량/가격을 콤마 문자열("3,0.5,12")로 저장하고, 기존 NestJS 서버는 이를
JS Number#toString 형식으로 만들었다. 같은 형식을 유지하면서 부동소수점 오차(0.1 + 0.2 등)는 정리한다.
오차 정리는 소수 자릿수가 아니라 유효숫자 기준이라 아주 작은 값도 정밀도를 잃지 않는다.
"""

import math
from decimal import Decimal

# 응답에 내보낼 때의 유효숫자 (0.30000000000000004 -> 0.3, 0.9999999999999999 -> 1)
RESPONSE_DIGITS = 12
# 저장할 때의 유효숫자. 응답보다 넉넉하게 두어 저장 후 다시 곱해도 오차가 쌓이지 않게 한다.
STORAGE_DIGITS = 15


def normalize(value, digits=RESPONSE_DIGITS):
    """부동소수점 오차를 유효숫자 기준으로 정리하고, 정수값이면 int로 바꾼다 (3.0 -> 3)."""
    value = float(value)
    if value == 0 or not math.isfinite(value):
        return 0
    rounded = float(f"{value:.{digits}g}")
    return int(rounded) if rounded.is_integer() else rounded


def round_half_up(value):
    """JS Math.round처럼 .5를 올림한다 (Python round는 은행가 반올림이라 2.5 -> 2)."""
    return math.floor(normalize(value, STORAGE_DIGITS) + 0.5)


def format_number(value):
    """JS Number#toString과 같은 모양의 문자열 (3 -> "3", 0.5 -> "0.5", 0.000025 -> "0.000025")."""
    number = normalize(value, STORAGE_DIGITS)
    if isinstance(number, int):
        return str(number)
    text = repr(number)
    # Python은 1e-4 미만을 지수로 쓰지만 JS는 1e-7 미만부터 지수로 쓴다.
    if "e" in text and abs(number) >= 1e-7:
        text = format(Decimal(text), "f")
    return text


def join_numbers(values):
    return ",".join(format_number(value) for value in values)


def split_numbers(text):
    return [_parse_number(value) for value in split_csv(text)]


def split_csv(text):
    return text.split(",") if text else []


def _parse_number(text):
    # 기존 서버가 남긴 잘못된 값("NaN", "" 등)은 0으로 읽는다.
    try:
        value = float(text)
    except ValueError:
        return 0.0
    return value if math.isfinite(value) else 0.0
