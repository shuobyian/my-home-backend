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
