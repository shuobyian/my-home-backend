from collections import Counter

from django.db import transaction

from apps.common.exceptions import BadRequest
from apps.inventories.models import InventoryItem
from apps.markets.models import Market


def list_inventory(user):
    return InventoryItem.objects.filter(user=user).select_related("market").order_by("market_id")


@transaction.atomic
def update_inventory(user, items):
    """보낸 시세의 보유 개수만 바꾸고(0이면 지운다) 바뀐 뒤의 전체 보유 목록을 돌려준다. 보내지 않은 시세는 그대로 둔다.

    ponytail: 검사한 뒤 커밋하기 전에 관리자가 그 시세를 지우면 외래 키 오류(500)가 난다. 시세 삭제는 드물고
    재료로 쓰이지 않는 시세만 지울 수 있어서 잠그지 않는다. 문제가 되면 시세 행을 잠그고 검사한다.
    """
    duplicated = sorted(pk for pk, n in Counter(item["market_id"] for item in items).items() if n > 1)
    if duplicated:
        # 같은 시세가 두 번 있으면 어느 개수로 저장할지 알 수 없다.
        raise BadRequest(f"중복된 시세가 있습니다. (id: {', '.join(map(str, duplicated))})")

    counts = {item["market_id"]: item["count"] for item in items}
    known = set(Market.objects.filter(pk__in=counts).values_list("pk", flat=True))
    unknown = sorted(pk for pk in counts if pk not in known)
    if unknown:
        raise BadRequest(f"존재하지 않는 시세입니다. (id: {', '.join(map(str, unknown))})")

    InventoryItem.objects.filter(user=user, market_id__in=[pk for pk, count in counts.items() if count == 0]).delete()
    InventoryItem.objects.bulk_create(
        [InventoryItem(user=user, market_id=pk, count=count) for pk, count in counts.items() if count > 0],
        update_conflicts=True,
        unique_fields=["user", "market"],
        update_fields=["count"],
    )
    return list_inventory(user)
