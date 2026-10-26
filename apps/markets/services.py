from django.db import IntegrityError, transaction

from apps.common.exceptions import BadRequest
from apps.markets.models import Market
from apps.products.models import Material
from apps.results.sync import begin_catalog_change, finish_catalog_change

# PUT /market으로 바꿀 수 있는 필드. 분류(group)는 화면에서 묶어 보여 주는 데만 쓰여 결과에 영향이 없다.
EDITABLE_FIELDS = ("name", "price", "group")


def list_markets():
    return Market.objects.order_by("id")


@transaction.atomic
def update_markets(items):
    """시세를 저장(수정/추가)하고 모든 결과를 새 시세에 맞춘다.

    시세 이름을 바꾸면 그 이름을 쓰는 기본 재료(basic=True)의 이름도 함께 바꾼다. 새 시세로 계산할 수 있게 된
    물품의 결과도 만든다. 이미 있던 문제(레거시 레시피 등)로는 거절하지 않고, 새로 생긴 차단 문제(예: 합계 초과)가
    있으면 400이고 시세 저장도 함께 취소된다.
    """
    # 시세 전체를 잠가서(begin_catalog_change) 동시에 들어온 카탈로그 쓰기가 서로의 결과를 덮어쓰지 않게 한다.
    before = begin_catalog_change()
    existing = {market.pk: market for market in Market.objects.order_by("id")}
    unknown = list(dict.fromkeys(item["id"] for item in items if "id" in item and item["id"] not in existing))
    if unknown:
        # 다른 관리자가 지운 시세를 수정하려는 경우다. 새 행으로 만들면 같은 시세가 둘이 되므로 거절한다.
        raise BadRequest(f"존재하지 않는 시세입니다. (id: {', '.join(map(str, unknown))})")

    original = {pk: market.name for pk, market in existing.items()}
    saved, to_update, to_create = [], {}, []
    for item in items:
        market = existing.get(item.get("id"))
        if market is None:
            if "name" not in item or "price" not in item:
                raise BadRequest("새 시세에는 name과 price가 필요합니다.")
            # 분류를 보내지 않은 새 시세는 모델 기본값(기타)이다.
            market = Market()
            to_create.append(market)
        else:
            to_update[market.pk] = market
        for field in EDITABLE_FIELDS:
            if field in item:
                setattr(market, field, item[field])
        saved.append(market)

    try:
        with transaction.atomic():
            Market.objects.bulk_update(to_update.values(), EDITABLE_FIELDS)
            Market.objects.bulk_create(to_create)
    except IntegrityError:
        raise BadRequest("이미 존재하는 시세 이름입니다.") from None

    renames = {original[pk]: market.name for pk, market in to_update.items() if market.name != original[pk]}
    _rename_basic_materials(renames)
    finish_catalog_change(before)
    return saved


@transaction.atomic
def delete_markets(ids):
    """ids 중 찾아서 삭제한 시세 id를 오름차순으로 돌려준다.

    물품의 재료로 쓰이는 시세가 하나라도 있으면 아무것도 지우지 않고 400이다. 없는 id는 무시한다.
    """
    before = begin_catalog_change()
    targets = dict(Market.objects.filter(pk__in=ids).order_by("id").values_list("pk", "name"))
    references = list(
        Material.objects.filter(basic=True, name__in=targets.values())
        .order_by("product__name", "name")
        .values_list("product__name", "name")
        .distinct()
    )
    if references:
        # 지우면 그 재료를 쓰는 물품을 계산할 수 없게 된다.
        detail = ", ".join(f"{product}: {name}" for product, name in references)
        raise BadRequest(f"물품의 재료로 쓰이는 시세는 삭제할 수 없습니다. ({detail})")

    Market.objects.filter(pk__in=targets).delete()
    finish_catalog_change(before)
    return sorted(targets)


def _rename_basic_materials(renames):
    """시세 이름 변경(원래 이름 → 최종 이름)을 그 이름을 쓰는 기본 재료에 반영한다.

    레시피는 시세를 이름으로 가리키므로 함께 바꾸지 않으면 시세가 없는 재료가 된다. 요청 전 이름 기준의 매핑으로
    한 번에 바꾸므로, 같은 요청에서 A → B로 바꾸면서 새 시세 A를 추가해도 재료는 B를 따라간다.
    """
    if not renames:
        return
    materials = list(Material.objects.filter(basic=True, name__in=renames).only("id", "name"))
    for material in materials:
        material.name = renames[material.name]
    Material.objects.bulk_update(materials, ["name"], batch_size=500)
