from rest_framework import serializers

from apps.common.fields import Int32Field
from apps.inventories.models import InventoryItem


class InventoryItemSerializer(serializers.ModelSerializer):
    marketId = serializers.IntegerField(source="market_id")
    name = serializers.CharField(source="market.name")

    class Meta:
        model = InventoryItem
        fields = ["marketId", "name", "count"]


class InventoryUpdateSerializer(serializers.Serializer):
    """PUT /inventory 항목. count를 0으로 보내면 보유 목록에서 뺀다."""

    marketId = Int32Field(source="market_id")
    count = Int32Field(min_value=0)
