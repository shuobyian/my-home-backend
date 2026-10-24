"""물품 레시피를 DB에서 읽고, 끝까지 펼칠 수 있는지 확인한다."""

from apps.common.exceptions import BadRequest
from apps.products.models import Material, Product
from apps.results.calculator import CraftingCalculator, Ingredient, RecipeError


def load_catalog():
    """전체 레시피와 물품 id를 쿼리 2번으로 읽는다. (recipes, product_ids)를 돌려준다.

    recipes는 물품명 → 재료 목록 dict이고 물품 id 순이다. product_ids는 물품명 → 물품 id다.
    재료는 레시피 순서(id 순)다. 물품 응답의 재료 순서(apps.products.models.materials_prefetch)와 같은 기준이다.
    """
    recipes, product_ids, recipes_by_id = {}, {}, {}
    for product_id, name in Product.objects.order_by("id").values_list("id", "name"):
        recipes[name] = recipes_by_id[product_id] = []
        product_ids[name] = product_id
    # order_by("product_id")로 쓰면 Django가 SELECT의 같은 열을 가리키는 'ORDER BY 1'로 바꾼다. 정렬 SQL을
    # 직접 확인하는 테스트(test_recipes_are_loaded_in_recipe_order)가 있어 FK 이름으로 정렬한다 (같은 열이다).
    materials = Material.objects.order_by("product", "id").values_list("product_id", "name", "basic", "count")
    for product_id, name, basic, count in materials:
        recipe = recipes_by_id.get(product_id)
        if recipe is not None:  # 잠그지 않고 읽으면 두 쿼리 사이에 추가된 물품의 재료가 섞일 수 있다.
            recipe.append(Ingredient(name, basic, count))
    return recipes, product_ids


def load_recipes():
    """전체 레시피(쿼리 2번)를 물품명 → 재료 목록 dict로 읽는다 (load_catalog의 recipes)."""
    return load_catalog()[0]


def check_recipes(product_names):
    """저장한 레시피를 끝까지 펼칠 수 있는지 확인한다. 실패하면 400 (트랜잭션 안에서 부르면 저장도 취소)."""
    calculator = CraftingCalculator(load_recipes(), prices={})
    for name in product_names:
        try:
            calculator.check(name)
        except RecipeError as error:
            raise BadRequest(str(error)) from None
