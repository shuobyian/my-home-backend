from rest_framework import serializers

from apps.common.dates import js_datetime
from apps.common.fields import FiniteFloatField
from apps.results.models import Result


class ResultSerializer(serializers.ModelSerializer):
    """POST /result 응답 (이번 동기화에서 새로 만든 결과 행)."""

    createdAt = serializers.SerializerMethodField()
    updatedAt = serializers.SerializerMethodField()
    product_id = serializers.IntegerField(read_only=True)
    totalPrice = serializers.IntegerField(source="total_price")

    class Meta:
        model = Result
        fields = ["id", "createdAt", "updatedAt", "product_id", "names", "counts", "prices", "totalPrice"]

    def get_createdAt(self, result):
        return js_datetime(result.created_at)

    def get_updatedAt(self, result):
        return js_datetime(result.updated_at)


class MarketPriceSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    # 프론트엔드 입력칸을 비우면 null이 오는데, 기존 서버는 이를 0원으로 계산했다.
    price = FiniteFloatField(min_value=0, allow_null=True)

    def validate_price(self, value):
        return 0 if value is None else value


class CalculatorInputSerializer(serializers.Serializer):
    markets = MarketPriceSerializer(many=True)

    def validate_markets(self, markets):
        names = [market["name"] for market in markets]
        duplicated = sorted({name for name in names if names.count(name) > 1})
        if duplicated:
            raise serializers.ValidationError(f"중복된 시세 이름이 있습니다. ({', '.join(duplicated)})")
        return markets
