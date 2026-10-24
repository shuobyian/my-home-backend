from django.db import IntegrityError, transaction

from apps.common.exceptions import BadRequest
from apps.markets.models import Market
from apps.results.sync import begin_catalog_change, finish_catalog_change


def list_markets():
    return Market.objects.order_by("id")


@transaction.atomic
def update_markets(items):
    """시세를 저장(수정/추가)하고 모든 결과를 새 시세에 맞춘다.

    새 시세로 계산할 수 있게 된 물품의 결과도 만든다. 이미 있던 문제(레거시 레시피 등)로는 거절하지 않고,
    새로 생긴 차단 문제(예: 합계 초과)가 있으면 400이고 시세 저장도 함께 취소된다.
    """
    # 시세 전체를 잠가서(begin_catalog_change) 동시에 들어온 카탈로그 쓰기가 서로의 결과를 덮어쓰지 않게 한다.
    before = begin_catalog_change()
    existing = {market.pk: market for market in Market.objects.order_by("id")}
    saved, to_update, to_create = [], {}, []
    for item in items:
        market = existing.get(item.get("id"))
        if market is None:
            if "name" not in item or "price" not in item:
                raise BadRequest("새 시세에는 name과 price가 필요합니다.")
            market = Market(name=item["name"], price=item["price"])
            to_create.append(market)
        else:
            for field in ("name", "price"):
                if field in item:
                    setattr(market, field, item[field])
            to_update[market.pk] = market
        saved.append(market)

    try:
        with transaction.atomic():
            Market.objects.bulk_update(to_update.values(), ["name", "price"])
            Market.objects.bulk_create(to_create)
    except IntegrityError:
        raise BadRequest("이미 존재하는 시세 이름입니다.") from None

    finish_catalog_change(before)
    return saved
