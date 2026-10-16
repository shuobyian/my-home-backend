from django.db import IntegrityError, transaction

from apps.common.exceptions import BadRequest
from apps.markets.models import Market
from apps.results.services import recalculate_results


def list_markets():
    return Market.objects.order_by("id")


@transaction.atomic
def update_markets(items):
    """시세를 저장(수정/추가)하고 저장된 결과를 새 시세로 다시 계산한다.

    재계산에 실패하면 시세 저장도 함께 취소된다.
    """
    # 시세 전체를 잠가서 동시에 들어온 시세 수정이 서로의 재계산 결과를 덮어쓰지 않게 한다.
    existing = {market.pk: market for market in Market.objects.select_for_update().order_by("id")}
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

    recalculate_results()
    return saved
