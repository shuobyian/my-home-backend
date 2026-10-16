from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.utils import timezone

from apps.common.exceptions import BadRequest
from apps.common.fields import INT32_MAX
from apps.markets.models import Market
from apps.products.models import Material, Product
from apps.results.calculator import CraftingCalculator, Ingredient, RecipeError
from apps.results.models import Result
from apps.results.presenters import present_result


def results_with_products():
    return Result.objects.select_related("product").prefetch_related(
        Prefetch("product__materials", queryset=Material.objects.order_by("id"))
    )


def build_calculator(prices=None):
    """전체 레시피(쿼리 2번)와 시세로 계산기를 만든다. prices가 없으면 DB 시세를 쓴다."""
    recipes = {name: [] for name in Product.objects.values_list("name", flat=True)}
    materials = Material.objects.order_by("product_id", "id").values_list("product__name", "name", "basic", "count")
    for product_name, name, basic, count in materials:
        recipes[product_name].append(Ingredient(name, basic, count))

    if prices is None:
        prices = dict(Market.objects.values_list("name", "price"))
    return CraftingCalculator(recipes, prices)


def calculate(calculator, product_name):
    try:
        sheet = calculator.calculate(product_name)
    except RecipeError as error:
        raise BadRequest(str(error)) from None
    if abs(sheet.total_price) > INT32_MAX:
        raise BadRequest(f"합계 금액이 너무 큽니다. ({product_name})")
    return sheet


def check_recipes(product_names):
    """저장한 레시피를 끝까지 펼칠 수 있는지 확인한다. 실패하면 400 (트랜잭션 안에서 부르면 저장도 취소)."""
    calculator = build_calculator(prices={})
    for name in product_names:
        try:
            calculator.check(name)
        except RecipeError as error:
            raise BadRequest(str(error)) from None


def list_results(name=None, tool=None, category=None):
    queryset = results_with_products().order_by("product__level", "product__name", "id")
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
    products = list(Product.objects.filter(result__isnull=True).order_by("id"))
    if not products:
        raise BadRequest("추가할 결과가 없습니다.")

    calculator = build_calculator()
    results = []
    for product in products:
        result = Result(product=product)
        result.apply_cost_sheet(calculate(calculator, product.name))
        results.append(result)
    try:
        with transaction.atomic():
            return Result.objects.bulk_create(results)
    except IntegrityError:
        # 같은 요청이 동시에 들어와 다른 요청이 먼저 결과를 만든 경우
        raise BadRequest("추가할 결과가 없습니다.") from None


def preview_results(prices):
    """입력한 시세로 전체 결과를 다시 계산해 보여준다 (저장하지 않음)."""
    missing = Product.objects.filter(result__isnull=True).order_by("id").first()
    if missing is not None:
        raise BadRequest(f"결과 정보가 없는 물품 ({missing.name}) 입니다.")

    calculator = build_calculator(prices)
    return [
        present_result(result, calculate(calculator, result.product.name))
        for result in results_with_products().order_by("product__level", "product__name", "id")
    ]


def recalculate_results():
    """저장된 모든 결과를 현재 DB 시세로 다시 계산해 저장한다 (시세 수정 시 호출)."""
    calculator = build_calculator()
    results = list(Result.objects.select_related("product"))
    now = timezone.now()
    for result in results:
        result.apply_cost_sheet(calculate(calculator, result.product.name))
        result.updated_at = now
    Result.objects.bulk_update(results, ["names", "counts", "prices", "total_price", "updated_at"], batch_size=500)
