from collections import Counter

import pytest

from apps.results.calculator import (
    CircularRecipeError,
    CraftingCalculator,
    Ingredient,
    MissingPriceError,
    UnknownMaterialError,
)


def basic(name, count):
    return Ingredient(name, True, count)


def product(name, count):
    return Ingredient(name, False, count)


def as_rows(sheet):
    return [(material.name, material.count, material.price) for material in sheet.materials]


class CountingRecipes(dict):
    """레시피 조회 횟수를 센다 (메모이제이션 확인용)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lookups = Counter()

    def get(self, key, default=None):
        self.lookups[key] += 1
        return super().get(key, default)


def test_flat_recipe():
    calculator = CraftingCalculator({"의자": [basic("나무", 3), basic("못", 2)]}, {"나무": 10, "못": 5})

    sheet = calculator.calculate("의자")

    assert as_rows(sheet) == [("나무", 3, 30), ("못", 2, 10)]
    assert sheet.total_price == 40


def test_nested_recipe_multiplies_counts():
    recipes = {
        "식탁": [product("판자", 2), basic("못", 4)],
        "판자": [basic("나무", 3)],
    }
    calculator = CraftingCalculator(recipes, {"나무": 10, "못": 5})

    assert as_rows(calculator.calculate("식탁")) == [("못", 4, 20), ("나무", 6, 60)]


def test_order_matches_legacy_bfs():
    """얕은 단계 재료가 먼저, 같은 단계에서는 레시피 순서 (기존 makeResult BFS와 같은 순서)."""
    recipes = {
        "R": [basic("b1", 1), product("C", 1), basic("b2", 1), product("D", 1)],
        "C": [basic("c1", 1), product("E", 1)],
        "D": [basic("d1", 1)],
        "E": [basic("e1", 1)],
    }
    prices = dict.fromkeys(["b1", "b2", "c1", "d1", "e1"], 1)

    sheet = CraftingCalculator(recipes, prices).calculate("R")

    assert [material.name for material in sheet.materials] == ["b1", "b2", "c1", "d1", "e1"]


def test_same_basic_material_is_merged_at_first_position():
    recipes = {
        "R": [product("A", 2), basic("철", 1), product("B", 1)],
        "A": [basic("철", 3), basic("구리", 1)],
        "B": [product("A", 1)],
    }
    sheet = CraftingCalculator(recipes, {"철": 10, "구리": 1}).calculate("R")

    # 철: 1(직접) + 2*3(A) + 1*1*3(B→A) = 10, 구리: 2*1 + 1*1*1 = 3
    assert as_rows(sheet) == [("철", 10, 100), ("구리", 3, 3)]
    assert sheet.total_price == 103


def test_shared_sub_product_is_expanded_once():
    recipes = CountingRecipes(
        {
            "X": [product("부품", 1), product("Y", 1)],
            "Y": [product("부품", 2)],
            "부품": [basic("철", 1)],
        }
    )
    calculator = CraftingCalculator(recipes, {"철": 1})

    for name in ("X", "Y", "부품"):
        calculator.calculate(name)

    assert recipes.lookups == {"X": 1, "Y": 1, "부품": 1}


def test_does_not_mutate_input():
    """기존 구현은 재료 count를 직접 더해서 다음 물품 계산이 오염됐다."""
    recipes = {
        "A": [basic("철", 1), product("B", 1)],
        "B": [basic("철", 2)],
        "C": [product("A", 1)],
    }
    calculator = CraftingCalculator(recipes, {"철": 1})

    first = as_rows(calculator.calculate("A"))
    assert as_rows(calculator.calculate("C")) == first == [("철", 3, 3)]
    assert recipes["A"][0] == basic("철", 1)


def test_fractional_counts():
    recipes = {"R": [product("반쪽", 3)], "반쪽": [basic("천", 0.1)]}

    [(name, count, price)] = as_rows(CraftingCalculator(recipes, {"천": 7}).calculate("R"))

    assert name == "천"
    assert count == pytest.approx(0.3)
    assert price == pytest.approx(2.1)


def test_unknown_sub_product_raises_instead_of_infinite_loop():
    recipes = {"R": [product("A", 1)], "A": [product("없는물품", 1)]}

    with pytest.raises(UnknownMaterialError, match="하위 재료에 잘못된 물품명이 있습니다. \\(A: 없는물품\\)"):
        CraftingCalculator(recipes, {}).calculate("R")


def test_missing_price_raises():
    with pytest.raises(MissingPriceError, match="R: 금") as error:
        CraftingCalculator({"R": [basic("금", 1)]}, {}).calculate("R")

    # 계산기 미리보기가 DB 시세에 있는 재료인지 비교할 때 쓴다.
    assert error.value.material == "금"


@pytest.mark.parametrize(
    ("recipes", "path"),
    [
        ({"A": [product("A", 1)]}, "A → A"),
        ({"A": [product("B", 1)], "B": [product("C", 1)], "C": [product("A", 1)]}, "A → B → C → A"),
    ],
)
def test_circular_recipe_raises(recipes, path):
    with pytest.raises(CircularRecipeError, match=path):
        CraftingCalculator(recipes, {}).calculate("A")


def test_product_without_materials():
    sheet = CraftingCalculator({"빈물품": []}, {}).calculate("빈물품")

    assert sheet.materials == ()
    assert sheet.total_price == 0
