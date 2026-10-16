from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.common.exceptions import BadRequest
from apps.common.fields import INT32_MAX
from apps.common.numbers import round_half_up
from apps.markets.models import Market
from apps.products.models import Product
from apps.products.recipes import load_recipes
from apps.results.calculator import CraftingCalculator, RecipeError
from apps.results.models import Result


def build_calculator(prices=None):
    """load_recipes()로 읽은 레시피와 시세로 계산기를 만든다. prices가 None이면 DB 시세를 쓴다."""
    recipes = load_recipes()
    if prices is None:
        prices = dict(Market.objects.values_list("name", "price"))
    return CraftingCalculator(recipes, prices)


def calculate(calculator, product_name):
    try:
        return calculator.calculate(product_name)
    except RecipeError as error:
        raise BadRequest(str(error)) from None


def _apply_calculation(result, calculator):
    sheet = calculate(calculator, result.product.name)
    if abs(round_half_up(sheet.total_price)) > INT32_MAX:
        # totalPrice 컬럼이 Postgres integer라서 저장할 수 없다 (미리 계산은 저장하지 않으므로 제한 없음).
        raise BadRequest(f"합계 금액이 너무 커서 저장할 수 없습니다. ({result.product.name})")
    result.apply_cost_sheet(sheet)


def _lock_prices():
    """시세 행 전체를 잠근다. 결과를 저장하는 작업끼리, 그리고 시세 수정과 순서대로 실행되게 한다."""
    list(Market.objects.lock_all().values_list("id", flat=True))


def list_results(name=None, tool=None, category=None):
    queryset = Result.objects.with_product().in_display_order()
    if name:
        queryset = queryset.filter(product__name__contains=name)
    if tool:
        queryset = queryset.filter(product__tool=tool)
    if category:
        queryset = queryset.filter(product__category=category)
    return queryset


@transaction.atomic
def create_missing_results():
    """결과가 없는 물품의 결과를 현재 시세로 계산해 저장한다."""
    _lock_prices()
    products = list(Product.objects.filter(result__isnull=True).order_by("id"))
    if not products:
        raise BadRequest("추가할 결과가 없습니다.")

    calculator = build_calculator()
    results = []
    for product in products:
        result = Result(product=product)
        _apply_calculation(result, calculator)
        results.append(result)
    try:
        with transaction.atomic():
            return Result.objects.bulk_create(results)
    except IntegrityError:
        # 같은 요청이 동시에 들어와 다른 요청이 먼저 결과를 만든 경우
        raise BadRequest("추가할 결과가 없습니다.") from None


def preview_results(prices):
    """입력한 시세로 전체 결과를 다시 계산한다 (저장하지 않음). (결과, CostSheet) 목록을 응답 순서대로 돌려준다."""
    missing = Product.objects.filter(result__isnull=True).order_by("id").first()
    if missing is not None:
        raise BadRequest(f"결과 정보가 없는 물품 ({missing.name}) 입니다.")

    calculator = build_calculator(prices)
    return [
        (result, calculate(calculator, result.product.name))
        for result in Result.objects.with_product().in_display_order()
    ]


@transaction.atomic
def recalculate_results():
    """저장된 모든 결과를 현재 DB 시세로 다시 계산해 저장한다 (시세 수정 시 호출)."""
    _lock_prices()
    calculator = build_calculator()
    results = list(Result.objects.select_related("product"))
    now = timezone.now()
    for result in results:
        _apply_calculation(result, calculator)
        result.updated_at = now
    Result.objects.bulk_update(results, ["names", "counts", "prices", "total_price", "updated_at"], batch_size=500)
