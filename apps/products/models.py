"""물품과 레시피(재료) 모델.

기존 TypeORM이 만든 테이블/컬럼명을 그대로 사용한다 (db_table, db_column).
"""

from django.db import models


class Tool(models.TextChoices):
    WOOD = "WOOD"
    FIRE_PIT = "FIRE_PIT"
    SEWING_MACHINE = "SEWING_MACHINE"
    LEATHER = "LEATHER"
    BRAZIER = "BRAZIER"
    POTTERY_WHEEL = "POTTERY_WHEEL"
    ALCHEMY_KETTLE = "ALCHEMY_KETTLE"


class Category(models.TextChoices):
    NORMAL = "NORMAL"
    EVENT = "EVENT"


class Product(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    level = models.IntegerField()
    crafting_price = models.IntegerField(db_column="craftingPrice")
    tool = models.CharField(max_length=255, choices=Tool.choices)
    category = models.CharField(max_length=255, choices=Category.choices)

    class Meta:
        db_table = "product"

    def __str__(self):
        return self.name


class Material(models.Model):
    """물품 하나를 만드는 데 필요한 재료.

    basic=True면 시세(market)로 사는 기본 재료, False면 다른 물품(product.name)을 뜻한다.
    """

    id = models.AutoField(primary_key=True)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="materials",
        db_column="product_id",
    )
    name = models.CharField(max_length=255)
    basic = models.BooleanField()
    count = models.FloatField()

    class Meta:
        db_table = "material"

    def __str__(self):
        return f"{self.name} x{self.count}"
