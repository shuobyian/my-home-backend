import math

from rest_framework import serializers

from apps.common.numbers import normalize

# Postgres integer 컬럼 범위
INT32_MIN = -(2**31)
INT32_MAX = 2**31 - 1


class Int32Field(serializers.IntegerField):
    """Postgres integer 범위를 넘는 값은 DB 에러(500) 대신 400으로 거절한다."""

    def __init__(self, **kwargs):
        kwargs.setdefault("min_value", INT32_MIN)
        kwargs.setdefault("max_value", INT32_MAX)
        super().__init__(**kwargs)


class FiniteFloatField(serializers.FloatField):
    """NaN/Infinity("nan", "inf", 1e999)를 거절한다. DRF FloatField는 float()로 그대로 받아들인다."""

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not math.isfinite(value):
            self.fail("invalid")
        return value


class NumberField(serializers.FloatField):
    """응답에서 3.0 대신 3처럼 JS와 같은 모양으로 숫자를 내보낸다."""

    def to_representation(self, value):
        return normalize(value)


def _validate_csv_safe_name(value):
    # 결과 테이블(result.names)이 재료 이름을 콤마로 이어 저장하므로 콤마가 들어가면 결과가 깨진다.
    if "," in value:
        raise serializers.ValidationError("이름에 콤마(,)를 넣을 수 없습니다.")
    return value


class CsvSafeNameField(serializers.CharField):
    """최대 255자(모델 CharField max_length와 같음), 콤마 금지.

    결과 테이블(result.names)이 이름을 콤마로 이어 저장하기 때문이다.
    validators를 넘겨도 콤마 검사는 항상 맨 앞에 붙는다. max_length는 255보다 크게 주지 않는다.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 255)
        # 넘긴 리스트를 바꾸지 않도록 새로 만든다. 콤마 에러가 길이 에러보다 먼저 나온다.
        kwargs["validators"] = [_validate_csv_safe_name, *kwargs.get("validators", ())]
        super().__init__(**kwargs)
