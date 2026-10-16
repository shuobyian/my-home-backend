from rest_framework import serializers

from apps.markets.models import Market
from apps.products.serializers import validate_csv_safe_name


class MarketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Market
        fields = ["id", "name", "price"]


class MarketUpdateSerializer(serializers.Serializer):
    """PUT /market 항목. id가 있으면 보낸 필드만 수정하고, 없으면 새로 추가한다."""

    id = serializers.IntegerField(required=False)
    name = serializers.CharField(max_length=255, validators=[validate_csv_safe_name], required=False)
    price = serializers.IntegerField(required=False)
