from rest_framework import serializers

from apps.common.fields import CsvSafeNameField, Int32Field
from apps.markets.models import Market


class MarketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Market
        fields = ["id", "name", "price"]


class MarketUpdateSerializer(serializers.Serializer):
    """PUT /market 항목. id가 있으면 보낸 필드만 수정하고, 없으면 새로 추가한다."""

    id = Int32Field(required=False)
    name = CsvSafeNameField(required=False)
    price = Int32Field(required=False)


class MarketIdsSerializer(serializers.Serializer):
    """DELETE /market 본문. DELETE /product(ProductIdsSerializer)처럼 {"ids": [...]}와 [...]를 둘 다 받는다."""

    ids = serializers.ListField(child=Int32Field())

    def to_internal_value(self, data):
        if isinstance(data, list):
            data = {"ids": data}
        return super().to_internal_value(data)
