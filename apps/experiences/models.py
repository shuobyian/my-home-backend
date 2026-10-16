from django.db import models


class Experience(models.Model):
    """레벨별 필요 경험치."""

    id = models.AutoField(primary_key=True)
    level = models.IntegerField()
    amount = models.IntegerField()

    class Meta:
        db_table = "experience"

    def __str__(self):
        return f"Lv.{self.level} ({self.amount})"
