"""회원의 보유 재료."""

from django.conf import settings
from django.db import models

from apps.markets.models import Market


class InventoryItem(models.Model):
    """회원이 가진 기초 재료(시세가 있는 최하위 재료) 개수. 개수가 0이면 행을 두지 않는다.

    시세를 이름이 아니라 id로 가리켜서, 관리자가 시세 이름을 바꿔도 보유 개수가 따라간다.
    시세가 지워지면(물품 재료로 쓰이지 않는 시세만 지울 수 있다) 보유 개수도 함께 지워진다.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="inventory_items")
    # 운영 DB의 market 테이블은 TypeORM에서 넘겨받으며 id 기본키 제약이 빠져 있어 DB 외래 키를 걸 수 없다.
    # 그래서 DB 제약 없이 두고, 삭제 연쇄는 Django(on_delete)가, 없는 시세 검사는 services.update_inventory가 맡는다.
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name="+", db_constraint=False)
    count = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "market"], name="inventory_item_user_market_unique"),
        ]

    def __str__(self):
        return f"{self.user_id}: {self.market_id} × {self.count}"
