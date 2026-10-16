"""숫자 표현 유틸.

결과 테이블은 수량/가격을 콤마 문자열("3,0.5,12")로 저장하고, 기존 NestJS 서버는 이를
JS Number#toString 형식으로 만들었다. 저장은 정밀도를 잃지 않도록 그대로 하고,
응답에 내보낼 때만 부동소수점 오차(0.1 + 0.2 등)를 유효숫자 기준으로 정리한다.
"""

import math
import re
from decimal import Decimal

# 응답 숫자의 유효숫자. float 오차(16~17번째 자리)는 지우고 2**53 이하 정수는 그대로 둔다.
# (0.30000000000000004 -> 0.3, 0.9999999999999999 -> 1)
SIGNIFICANT_DIGITS = 15


def normalize(value):
    """부동소수점 오차를 정리하고, 정수값이면 int로 바꾼다 (3.0 -> 3)."""
    value = float(value)
    if value == 0 or not math.isfinite(value):
        return 0
    rounded = float(f"{value:.{SIGNIFICANT_DIGITS}g}")
    return int(rounded) if rounded.is_integer() else rounded


def round_half_up(value):
    """JS Math.round처럼 .5를 올림한다 (Python round는 은행가 반올림이라 2.5 -> 2)."""
    return math.floor(normalize(value) + 0.5)


def format_number(value):
    """JS Number#toString과 같은 모양의 문자열 (3 -> "3", 0.5 -> "0.5", 0.000025 -> "0.000025", 1e-7 -> "1e-7")."""
    value = float(value)
    if value.is_integer():
        return str(int(value))
    text = repr(value)  # 다시 읽으면 같은 값이 되는 가장 짧은 표기 (JS와 같은 규칙)
    if "e" not in text:
        return text
    # Python은 1e-4 미만을, JS는 1e-6 미만을 지수로 쓴다. 지수부도 JS처럼 0을 채우지 않는다 (1e-08 -> 1e-8).
    if abs(value) >= 1e-6:
        return format(Decimal(text), "f")
    return re.sub(r"e([+-])0*(\d)", r"e\1\2", text)


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
