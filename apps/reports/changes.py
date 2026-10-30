"""제보의 바꿀 값: 대상마다 현재 값을 읽는 방법과 바꿀 수 있는 값(필드)·검증.

필드 이름과 값의 모양은 각 API 응답(GET /experience, /market, /product)과 같다.
대상이나 필드를 더하면 프론트엔드(my-home-frontend src/domain/report.ts)의 목록도 함께 고친다.
"""

from functools import partial

from rest_framework import serializers

from apps.common.fields import CsvSafeNameField, FiniteFloatField, Int32Field
from apps.common.numbers import normalize
from apps.experiences.models import Experience
from apps.markets.models import Market, MarketGroup
from apps.products.models import Category, Material, Product, Tool
from apps.products.serializers import MAX_MATERIAL_COUNT
from apps.reports.models import ChangeTarget


def _positive(value):
    if value <= 0:
        raise serializers.ValidationError("0보다 커야 합니다.")
    return value


def _experience(pk):
    row = Experience.objects.filter(pk=pk).first()
    if row is None:
        return None
    return f"{row.level}레벨", {"amount": row.amount}


def _market(pk):
    row = Market.objects.filter(pk=pk).first()
    if row is None:
        return None
    return row.name, {"name": row.name, "price": row.price, "group": row.group}


def _product(pk):
    row = Product.objects.filter(pk=pk).first()
    if row is None:
        return None
    current = {
        "name": row.name,
        "level": row.level,
        "craftingPrice": row.crafting_price,
        "tool": row.tool,
        "category": row.category,
    }
    return row.name, current


def _material(pk):
    # 재료 id는 GET /product 응답의 materials[].id다. 물품을 수정하면 재료 행을 새로 만들어 id가 바뀐다.
    row = Material.objects.select_related("product").filter(pk=pk).first()
    if row is None:
        return None
    return f"{row.product.name} · {row.name}", {"name": row.name, "count": normalize(row.count)}


# 대상 → (현재 값 읽기, {필드: 검증 필드 만들기}). 읽기는 (이름, {필드: 현재 값}) 또는 없으면 None을 돌려준다.
# 검증 필드는 요청마다 새로 만든다 (DRF 필드는 상태를 가진다).
TARGETS = {
    ChangeTarget.EXPERIENCE: (_experience, {"amount": partial(Int32Field, min_value=0)}),
    ChangeTarget.MARKET: (
        _market,
        {
            "name": CsvSafeNameField,
            "price": partial(Int32Field, min_value=0),
            "group": partial(serializers.ChoiceField, choices=MarketGroup.choices),
        },
    ),
    ChangeTarget.PRODUCT: (
        _product,
        {
            "name": CsvSafeNameField,
            "level": partial(Int32Field, min_value=1),
            "craftingPrice": partial(Int32Field, min_value=0),
            "tool": partial(serializers.ChoiceField, choices=Tool.choices),
            "category": partial(serializers.ChoiceField, choices=Category.choices),
        },
    ),
    ChangeTarget.MATERIAL: (
        _material,
        {
            "name": CsvSafeNameField,
            "count": partial(FiniteFloatField, max_value=MAX_MATERIAL_COUNT, validators=[_positive]),
        },
    ),
}


def resolve_change(target, target_id, field, value):
    """바꿀 값 한 줄을 검증하고 현재 값과 이름을 읽어 ReportChange 필드로 돌려준다. 잘못되면 ValidationError."""
    load, fields = TARGETS[target]
    make_field = fields.get(field)
    if make_field is None:
        raise serializers.ValidationError({"field": f"바꿀 수 없는 값입니다. ({', '.join(fields)})"})
    try:
        after = make_field().run_validation(value)
    except serializers.ValidationError as error:
        raise serializers.ValidationError({"value": error.detail}) from None
    found = load(target_id)
    if found is None:
        raise serializers.ValidationError({"targetId": "존재하지 않는 대상입니다."})
    label, current = found
    before = current[field]
    if isinstance(after, float):
        after = normalize(after)
    if after == before:
        raise serializers.ValidationError({"value": "현재 값과 같습니다."})
    return {"target": target, "target_id": target_id, "label": label, "field": field, "before": before, "after": after}
