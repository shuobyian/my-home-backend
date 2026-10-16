"""물품과 레시피(재료) 모델.

기존 TypeORM이 만든 테이블/컬럼명을 그대로 사용한다 (db_table, db_column).
"""

from django.db import models


# 값과 이름은 프론트엔드(my-home-frontend src/apis/type)의 목록과 같아야 한다.
class Tool(models.TextChoices):
    WOOD = "WOOD", "원목 작업대"
    FIRE_PIT = "FIRE_PIT", "요리용 화덕"
    SEWING_MACHINE = "SEWING_MACHINE", "재봉틀"
    LEATHER = "LEATHER", "가죽 작업대"
    BRAZIER = "BRAZIER", "금속용 화로"
    POTTERY_WHEEL = "POTTERY_WHEEL", "도자기 물레"
    ALCHEMY_KETTLE = "ALCHEMY_KETTLE", "별님 연금솥"
    MIMI = "MIMI", "미미 화덕"


class Category(models.TextChoices):
    NORMAL = "NORMAL", "일반"
    EVENT = "EVENT", "이벤트"


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


def materials_prefetch(lookup="materials"):
    """재료는 항상 id 순(= 레시피 순서)으로 읽는다. 응답의 재료 순서가 이 정렬에 달려 있다.

    Prefetch는 중첩 prefix를 붙일 때 객체가 바뀌므로 모듈 상수로 두지 않고 호출할 때마다 새로 만든다.
    """
    return models.Prefetch(lookup, queryset=Material.objects.order_by("id"))
