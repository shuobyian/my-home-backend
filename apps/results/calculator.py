"""물품 제작 비용 계산기 (DB와 무관한 순수 로직).

물품 레시피를 기본 재료(시세로 사는 재료)까지 펼쳐서 기본 재료별 총 수량과 가격을 구한다.

기존 NestJS 구현(makeResult)과의 차이
- 물품/시세를 이름 → 값 dict로 찾는다 (매 단계 전체 물품 목록을 선형 탐색하지 않음).
- 물품마다 펼친 결과를 한 번만 계산해 메모해 두고 재사용한다.
  하위 물품이 여러 물품에 쓰여도, 전체 물품을 한꺼번에 계산해도 각 물품은 한 번만 펼친다.
- 입력 데이터를 변경하지 않는다 (기존 구현은 재료 객체의 count를 직접 더해 다음 계산을 오염시켰다).
- 잘못된 하위 재료명이나 순환 참조는 무한 루프 대신 RecipeError로 알린다.

재료 순서는 기존 BFS 구현과 같다: 얕은 단계의 재료가 먼저 나오고, 같은 단계에서는 레시피 순서를 따른다.
이를 위해 물품마다 '단계(깊이)별 기본 재료 수량'을 메모한다.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

# 기본 재료 이름 → 수량. dict의 삽입 순서가 곧 재료가 처음 등장한 순서다.
Quantities = dict[str, float]


@dataclass(frozen=True, slots=True)
class Ingredient:
    name: str
    basic: bool
    count: float


@dataclass(frozen=True, slots=True)
class MaterialCost:
    name: str
    count: float
    price: float


@dataclass(frozen=True, slots=True)
class CostSheet:
    materials: tuple[MaterialCost, ...]
    total_price: float


class RecipeError(ValueError):
    """레시피를 계산할 수 없을 때 발생한다. 메시지는 사용자에게 그대로 보여준다."""


class UnknownMaterialError(RecipeError):
    pass


class MissingPriceError(RecipeError):
    pass


class CircularRecipeError(RecipeError):
    pass


class CraftingCalculator:
    """레시피와 시세를 받아 물품별 기본 재료 비용을 계산한다.

    recipes: 물품명 → 재료 목록, prices: 기본 재료명 → 개당 가격
    """

    def __init__(self, recipes: Mapping[str, Sequence[Ingredient]], prices: Mapping[str, float]):
        self._recipes = recipes
        self._prices = prices
        self._levels: dict[str, tuple[Quantities, ...]] = {}
        self._expanding: list[str] = []

    def calculate(self, product_name: str) -> CostSheet:
        totals: Quantities = {}
        for level in self._expand(product_name):
            _accumulate(totals, level)

        materials = tuple(
            MaterialCost(name, count, count * self._price(product_name, name)) for name, count in totals.items()
        )
        return CostSheet(materials, sum(material.price for material in materials))

    def _price(self, product_name: str, material_name: str) -> float:
        price = self._prices.get(material_name)
        if price is None:
            raise MissingPriceError(f"시세 정보가 없는 재료가 있습니다. ({product_name}: {material_name})")
        return price

    def _expand(self, product_name: str) -> tuple[Quantities, ...]:
        """물품을 기본 재료까지 펼친 결과를 단계별로 돌려준다. [0]은 레시피에 바로 적힌 기본 재료."""
        if product_name in self._levels:
            return self._levels[product_name]
        if product_name in self._expanding:
            path = " → ".join([*self._expanding[self._expanding.index(product_name) :], product_name])
            raise CircularRecipeError(f"재료 구성에 순환 참조가 있습니다. ({path})")

        recipe = self._recipes.get(product_name)
        if recipe is None:
            parent = self._expanding[-1] if self._expanding else product_name
            raise UnknownMaterialError(f"하위 재료에 잘못된 물품명이 있습니다. ({parent}: {product_name})")

        self._expanding.append(product_name)
        try:
            direct: Quantities = {}
            deeper: list[Quantities] = []
            for ingredient in recipe:
                if ingredient.basic:
                    _accumulate(direct, {ingredient.name: ingredient.count})
                    continue
                sub_levels = self._expand(ingredient.name)
                deeper.extend({} for _ in range(len(sub_levels) - len(deeper)))
                for target, level in zip(deeper, sub_levels, strict=False):
                    _accumulate(target, level, ingredient.count)
        finally:
            self._expanding.pop()

        levels = (direct, *deeper)
        self._levels[product_name] = levels
        return levels


def _accumulate(target: Quantities, source: Mapping[str, float], factor: float = 1) -> None:
    for name, count in source.items():
        target[name] = target.get(name, 0) + count * factor
