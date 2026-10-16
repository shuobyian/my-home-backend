"""레거시 NestJS 계산 결과(골든 데이터)와 새 계산기/응답 모양이 같은지 확인한다.

tests/fixtures/legacy_golden.json 은 레거시 src/result/util/makeResult.ts, parseResults.ts 원본을
트랜스파일해서 시드 고정 난수 레시피(물품 3~40개, 깊이 1~6, 하위 물품 공유, 정수/소수 수량)로 실행한 결과다.
레거시는 물품마다 입력을 깊은 복사해서 돌렸다 (재료 객체를 공유할 때 생기는 변경 오염 버그는 정답에서 제외).
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.results.calculator import CraftingCalculator, Ingredient
from apps.results.models import Result
from apps.results.presenters import present_result

GOLDEN = json.loads((Path(__file__).parent / "fixtures" / "legacy_golden.json").read_text(encoding="utf-8"))
SCENARIOS = GOLDEN["scenarios"]
PRESENTED = [(scenario, item) for scenario in SCENARIOS for item in scenario.get("presented", [])]

# 계산 순서(곱셈/덧셈 순서)가 달라 생기는 부동소수점 차이만 허용한다.
REL = 1e-9
# 응답 숫자는 유효숫자 12자리로 정리(normalize)하므로, 0에 가까운 값을 위해 작은 절대 오차도 허용한다.
PRESENT_ABS = 1e-9


def numbers(text):
    return [float(value) for value in text.split(",")] if text else []


def build_calculator(scenario):
    recipes = {
        name: [Ingredient(material, basic, count) for material, basic, count in materials]
        for name, materials in scenario["recipes"].items()
    }
    return CraftingCalculator(recipes, scenario["markets"])


def as_rows(sheet):
    return [(material.name, material.count, material.price) for material in sheet.materials], sheet.total_price


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[scenario["id"] for scenario in SCENARIOS])
def test_calculator_matches_legacy(scenario):
    calculator = build_calculator(scenario)

    for name, expected in scenario["expected"].items():
        sheet = calculator.calculate(name)

        assert [material.name for material in sheet.materials] == expected["names"].split(","), name
        assert [material.count for material in sheet.materials] == pytest.approx(numbers(expected["counts"]), rel=REL)
        assert [material.price for material in sheet.materials] == pytest.approx(numbers(expected["prices"]), rel=REL)
        assert sheet.total_price == pytest.approx(expected["totalPrice"], rel=REL), name


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[scenario["id"] for scenario in SCENARIOS])
def test_calculation_order_does_not_change_results(scenario):
    """메모이제이션 때문에 계산 순서나 계산기 재사용 여부에 따라 결과가 달라지면 안 된다."""
    names = list(scenario["expected"])
    shared = build_calculator(scenario)
    forward = {name: as_rows(shared.calculate(name)) for name in names}

    reversed_calculator = build_calculator(scenario)
    for name in reversed(names):
        assert as_rows(reversed_calculator.calculate(name)) == forward[name], name
        assert as_rows(build_calculator(scenario).calculate(name)) == forward[name], name


def fake_result(scenario, name):
    meta = scenario["meta"][name]
    materials = [
        SimpleNamespace(name=material, basic=basic, count=count) for material, basic, count in scenario["recipes"][name]
    ]
    product = SimpleNamespace(
        id=meta["id"],
        name=name,
        level=meta["level"],
        crafting_price=meta["craftingPrice"],
        tool=meta["tool"],
        category=meta["category"],
        materials=SimpleNamespace(all=lambda: materials),
    )
    return SimpleNamespace(id=1, created_at=None, updated_at=None, product=product)


@pytest.mark.parametrize(
    ("scenario", "item"),
    PRESENTED,
    ids=[f"{scenario['id']}-{item['product']}-x{item['count']}" for scenario, item in PRESENTED],
)
def test_present_result_matches_legacy_parse_result(scenario, item):
    name, count = item["product"], item["count"]
    legacy_row = scenario["expected"][name]
    result = fake_result(scenario, name)
    stored = Result(
        names=legacy_row["names"],
        counts=legacy_row["counts"],
        prices=legacy_row["prices"],
        total_price=legacy_row["totalPrice"],
    )
    sheets = {
        # GET /result: 레거시가 저장한 결과 행을 새 서버가 읽어서 응답
        "stored": stored.cost_sheet(),
        # POST /result/calculator: 계산 결과를 저장 없이 바로 응답
        "calculated": build_calculator(scenario).calculate(name),
    }

    meta = scenario["meta"][name]
    for label, sheet in sheets.items():
        body = present_result(result, sheet, count=count)

        assert (body["name"], body["level"], body["tool"]) == (name, meta["level"], meta["tool"])
        assert body["product"]["craftingPrice"] == meta["craftingPrice"]
        assert body["craftingPrice"] == item["craftingPrice"], label
        assert body["totalPrice"] == pytest.approx(item["totalPrice"], rel=REL, abs=PRESENT_ABS), label
        assert [material["name"] for material in body["materials"]] == legacy_row["names"].split(","), label
        assert [value for material in body["materials"] for value in (material["price"], material["count"])] == (
            pytest.approx([value for pair in item["materials"] for value in pair], rel=REL, abs=PRESENT_ABS)
        ), label
        assert [material["count"] for material in body["product"]["materials"]] == pytest.approx(
            item["productMaterialCounts"], rel=REL, abs=PRESENT_ABS
        ), label
