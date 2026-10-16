from rest_framework import serializers

from apps.common.fields import FiniteFloatField, Int32Field, NumberField
from apps.products.models import Category, Material, Product, Tool


def validate_csv_safe_name(value):
    # 결과 테이블이 재료 이름을 콤마로 이어 저장하므로 콤마가 들어가면 결과가 깨진다.
    if "," in value:
        raise serializers.ValidationError("이름에 콤마(,)를 넣을 수 없습니다.")
    return value


# 재료 수량 상한. 하위 물품을 거치며 곱해져도 합계가 정수 컬럼 범위 안에 들도록 넉넉한 현실값으로 제한한다.
MAX_MATERIAL_COUNT = 1_000_000


class MaterialInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, validators=[validate_csv_safe_name])
    basic = serializers.BooleanField()
    count = FiniteFloatField(max_value=MAX_MATERIAL_COUNT)

    def validate_count(self, value):
        if value <= 0:
            raise serializers.ValidationError("수량은 0보다 커야 합니다.")
        return value


class ProductInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, validators=[validate_csv_safe_name])
    level = Int32Field()
    craftingPrice = Int32Field(source="crafting_price")
    tool = serializers.ChoiceField(choices=Tool.choices)
    category = serializers.ChoiceField(choices=Category.choices, default=Category.NORMAL)
    materials = MaterialInputSerializer(many=True)


class ProductUpdateSerializer(serializers.Serializer):
    """PUT /product — 보낸 필드만 수정하고, 재료 목록은 통째로 교체한다."""

    id = Int32Field()
    name = serializers.CharField(max_length=255, validators=[validate_csv_safe_name], required=False)
    level = Int32Field(required=False)
    craftingPrice = Int32Field(source="crafting_price", required=False)
    tool = serializers.ChoiceField(choices=Tool.choices, required=False)
    category = serializers.ChoiceField(choices=Category.choices, required=False)
    materials = MaterialInputSerializer(many=True)


class ProductBulkCreateSerializer(serializers.Serializer):
    products = ProductInputSerializer(many=True)


class ProductIdsSerializer(serializers.Serializer):
    """DELETE /product 본문. 프론트엔드는 {"ids": [...]}를, 기존 API 문서는 [...]를 보낸다."""

    ids = serializers.ListField(child=Int32Field())

    def to_internal_value(self, data):
        if isinstance(data, list):
            data = {"ids": data}
        return super().to_internal_value(data)


class MaterialSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(read_only=True)
    count = NumberField()

    class Meta:
        model = Material
        fields = ["id", "product_id", "name", "basic", "count"]


class ProductSerializer(serializers.ModelSerializer):
    craftingPrice = serializers.IntegerField(source="crafting_price")
    materials = MaterialSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "level", "craftingPrice", "tool", "category", "materials"]
