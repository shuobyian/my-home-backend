from rest_framework import serializers

from apps.products.models import Category, Material, Product, Tool


def validate_csv_safe_name(value):
    # 결과 테이블이 재료 이름을 콤마로 이어 저장하므로 콤마가 들어가면 결과가 깨진다.
    if "," in value:
        raise serializers.ValidationError("이름에 콤마(,)를 넣을 수 없습니다.")
    return value


class MaterialInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, validators=[validate_csv_safe_name])
    basic = serializers.BooleanField()
    count = serializers.FloatField()

    def validate_count(self, value):
        if value <= 0:
            raise serializers.ValidationError("수량은 0보다 커야 합니다.")
        return value


class ProductInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, validators=[validate_csv_safe_name])
    level = serializers.IntegerField()
    craftingPrice = serializers.IntegerField(source="crafting_price")
    tool = serializers.ChoiceField(choices=Tool.choices)
    category = serializers.ChoiceField(choices=Category.choices, default=Category.NORMAL)
    materials = MaterialInputSerializer(many=True)


class ProductUpdateSerializer(serializers.Serializer):
    """PUT /product — 보낸 필드만 수정하고, 재료 목록은 통째로 교체한다."""

    id = serializers.IntegerField()
    name = serializers.CharField(max_length=255, validators=[validate_csv_safe_name], required=False)
    level = serializers.IntegerField(required=False)
    craftingPrice = serializers.IntegerField(source="crafting_price", required=False)
    tool = serializers.ChoiceField(choices=Tool.choices, required=False)
    category = serializers.ChoiceField(choices=Category.choices, required=False)
    materials = MaterialInputSerializer(many=True)


class ProductBulkCreateSerializer(serializers.Serializer):
    products = ProductInputSerializer(many=True)


class MaterialSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Material
        fields = ["id", "product_id", "name", "basic", "count"]


class ProductSerializer(serializers.ModelSerializer):
    craftingPrice = serializers.IntegerField(source="crafting_price")
    materials = MaterialSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "level", "craftingPrice", "tool", "category", "materials"]
