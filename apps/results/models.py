from django.db import models
from django.db.models.functions import Now

from apps.common.numbers import join_numbers, round_half_up, split_csv, split_numbers
from apps.products.models import Product, materials_prefetch
from apps.results.calculator import CostSheet, MaterialCost


class ResultQuerySet(models.QuerySet):
    def with_product(self):
        """물품과 물품 재료(id 순)를 함께 읽는다 (present_result가 쓰는 데이터)."""
        return self.select_related("product").prefetch_related(materials_prefetch("product__materials"))

    def in_display_order(self):
        """레벨, 이름 순. GET /result와 계산기(POST /result/calculator) 응답이 같은 순서여야 한다."""
        return self.order_by("product__level", "product__name", "id")


class Result(models.Model):
    """물품별 계산 결과 캐시.

    기본 재료 이름/수량/가격을 같은 순서의 콤마 문자열로 저장한다 (기존 스키마 유지).
    totalPrice 컬럼은 정수라서 반올림해 저장하고, 응답의 합계는 재료 가격의 합으로 계산한다.
    """

    id = models.AutoField(primary_key=True)
    created_at = models.DateTimeField(db_column="createdAt", db_default=Now())
    updated_at = models.DateTimeField(db_column="updatedAt", null=True, db_default=Now())
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="result",
        db_column="product_id",
    )
    names = models.CharField(max_length=None)
    counts = models.CharField(max_length=None)
    prices = models.CharField(max_length=None)
    total_price = models.IntegerField(db_column="totalPrice")

    objects = ResultQuerySet.as_manager()

    class Meta:
        db_table = "result"

    def __str__(self):
        return f"Result({self.product_id})"

    def cost_sheet(self) -> CostSheet:
        """저장된 콤마 문자열을 CostSheet로 되돌린다."""
        names = split_csv(self.names)
        # 기존 서버가 시세 없는 재료의 가격을 빠뜨려 저장한 데이터도 있으므로 모자란 값은 0으로 채운다.
        counts = _pad(split_numbers(self.counts), len(names))
        prices = _pad(split_numbers(self.prices), len(names))
        materials = tuple(map(MaterialCost, names, counts, prices))
        return CostSheet(materials, sum(material.price for material in materials))

    @staticmethod
    def cost_fields_of(sheet: CostSheet) -> tuple[str, str, str, int]:
        """CostSheet를 저장할 컬럼 값 (names, counts, prices, total_price)으로 바꾼다."""
        return (
            ",".join(material.name for material in sheet.materials),
            join_numbers(material.count for material in sheet.materials),
            join_numbers(material.price for material in sheet.materials),
            round_half_up(sheet.total_price),
        )

    def apply_cost_sheet(self, sheet: CostSheet) -> None:
        self.names, self.counts, self.prices, self.total_price = self.cost_fields_of(sheet)

    def matches(self, sheet: CostSheet) -> bool:
        """저장된 4개 컬럼이 sheet로 저장할 값과 같은지 본다. 다르면 결과가 낡은 것이다."""
        return (self.names, self.counts, self.prices, self.total_price) == self.cost_fields_of(sheet)


def _pad(values, length):
    return values + [0] * (length - len(values))
