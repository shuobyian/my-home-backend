from rest_framework import serializers

from apps.common.dates import js_datetime
from apps.results.models import Result


class ResultSerializer(serializers.ModelSerializer):
    """POST /result 응답 (저장된 결과 행)."""

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
    price = serializers.FloatField()


class CalculatorInputSerializer(serializers.Serializer):
    markets = MarketPriceSerializer(many=True)
