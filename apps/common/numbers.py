"""숫자 표현 유틸.

결과 테이블은 수량/가격을 콤마 문자열("3,0.5,12")로 저장하고, 기존 NestJS 서버는 이를
JS Number#toString 형식으로 만들었다. 같은 형식을 유지하면서 부동소수점 오차(0.1 + 0.2 등)는 정리한다.
"""

# 부동소수점 누적 오차를 지우기 위한 반올림 자릿수
PRECISION = 9


def normalize(value):
    """부동소수점 오차를 정리하고, 정수값이면 int로 바꾼다 (3.0 -> 3)."""
    rounded = round(float(value), PRECISION)
    if rounded.is_integer():
        return int(rounded)
    return rounded


def format_number(value):
    """JS Number#toString과 같은 모양의 문자열 (3 -> "3", 0.5 -> "0.5")."""
    return str(normalize(value))


def join_numbers(values):
    return ",".join(format_number(value) for value in values)


def split_numbers(text):
    return [normalize(value) for value in split_csv(text)]


def split_csv(text):
    return text.split(",") if text else []
