from apps.common.exceptions import BadRequest
from apps.markets.models import Market
from apps.products.models import Product
from apps.products.recipes import load_recipes
from apps.results.calculator import CraftingCalculator, RecipeError
from apps.results.models import Result


def list_results(name=None, tool=None, category=None):
    queryset = Result.objects.with_product().in_display_order()
    if name:
        queryset = queryset.filter(product__name__contains=name)
    if tool:
        queryset = queryset.filter(product__tool=tool)
    if category:
        queryset = queryset.filter(product__category=category)
    return queryset


def preview_results(prices):
    """입력한 시세로 전체 결과를 다시 계산한다 (저장하지 않음). (결과, CostSheet) 목록을 응답 순서대로 돌려준다."""
    missing = Product.objects.filter(result__isnull=True).order_by("id").first()
    if missing is not None:
        raise BadRequest(f"결과 정보가 없는 물품 ({missing.name}) 입니다.")

    calculator = _build_calculator(prices)
    return [
        (result, _calculate_or_400(calculator, result.product.name))
        for result in Result.objects.with_product().in_display_order()
    ]


def _build_calculator(prices=None):
    """load_recipes()로 읽은 레시피와 시세로 계산기를 만든다. prices가 None이면 DB 시세를 쓴다."""
    recipes = load_recipes()
    if prices is None:
        prices = dict(Market.objects.values_list("name", "price"))
    return CraftingCalculator(recipes, prices)


def _calculate_or_400(calculator, product_name):
    """계산기로 비용을 계산하고, RecipeError는 400(BadRequest)으로 바꾼다."""
    try:
        return calculator.calculate(product_name)
    except RecipeError as error:
        raise BadRequest(str(error)) from None
