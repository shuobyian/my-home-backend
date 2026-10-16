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
