"""물품 레시피를 DB에서 읽고, 끝까지 펼칠 수 있는지 확인한다."""

from apps.common.exceptions import BadRequest
from apps.products.models import Material, Product
from apps.results.calculator import CraftingCalculator, Ingredient, RecipeError


def load_recipes():
    """전체 레시피(쿼리 2번)를 물품명 → 재료 목록 dict로 읽는다.

    재료는 레시피 순서(id 순)다. 물품 응답의 재료 순서(apps.products.models.materials_prefetch)와 같은 기준이다.
    """
    recipes = {name: [] for name in Product.objects.values_list("name", flat=True)}
    materials = Material.objects.order_by("product_id", "id").values_list("product__name", "name", "basic", "count")
    for product_name, name, basic, count in materials:
        recipes[product_name].append(Ingredient(name, basic, count))
    return recipes


def check_recipes(product_names):
    """저장한 레시피를 끝까지 펼칠 수 있는지 확인한다. 실패하면 400 (트랜잭션 안에서 부르면 저장도 취소)."""
    calculator = CraftingCalculator(load_recipes(), prices={})
    for name in product_names:
        try:
            calculator.check(name)
        except RecipeError as error:
            raise BadRequest(str(error)) from None
