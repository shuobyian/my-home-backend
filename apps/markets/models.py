from django.db import models


class Market(models.Model):
    """기본 재료의 시세."""

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    price = models.IntegerField()

    class Meta:
        db_table = "market"

    def __str__(self):
        return f"{self.name} ({self.price})"
