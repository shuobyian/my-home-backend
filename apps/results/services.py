from apps.common.exceptions import BadRequest
from apps.markets.models import Market
from apps.products.recipes import load_recipes
from apps.results.calculator import CraftingCalculator, MissingPriceError, RecipeError
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
    """입력한 시세로 전체 결과를 다시 계산한다 (저장하지 않음). (결과, CostSheet) 목록을 응답 순서대로 돌려준다.

    결과가 없는 물품과, 서버 데이터 문제(시세 없는 재료, 없는 하위 물품, 순환)로 계산할 수 없는 물품은 건너뛴다.
    그런 물품 하나 때문에 모든 사용자의 계산기가 막히지 않게 하기 위해서다 (관리자는 데이터 점검에서 본다).
    사용자가 입력에서 DB에 있는 시세를 뺀 경우만 400이다.
    """
    calculator = CraftingCalculator(load_recipes(), prices)
    db_markets = set(Market.objects.values_list("name", flat=True))
    rows = []
    for result in Result.objects.with_product().in_display_order():
        try:
            sheet = calculator.calculate(result.product.name)
        except MissingPriceError as error:
            if error.material in db_markets:
                raise BadRequest(str(error)) from None  # 사용자가 입력에서 뺀 시세
            continue  # 서버에도 없는 시세 (데이터 점검에 보인다)
        except RecipeError:
            continue
        rows.append((result, sheet))
    return rows
