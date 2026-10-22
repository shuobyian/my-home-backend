from django.db import models


class MarketQuerySet(models.QuerySet):
    def lock_all(self):
        """시세 행 전체를 id 순서로 잠근다. 트랜잭션 안에서만 쓴다. 항상 같은 순서로 잠가 교착을 피한다."""
        return self.select_for_update().order_by("id")


class Market(models.Model):
    """기본 재료의 시세."""

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    price = models.IntegerField()

    objects = MarketQuerySet.as_manager()

    class Meta:
        db_table = "market"

    def __str__(self):
        return f"{self.name} ({self.price})"
