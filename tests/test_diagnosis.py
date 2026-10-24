"""카탈로그 진단(apps.results.diagnosis) 테스트. 순수 함수라 DB를 쓰지 않는다."""

from apps.results.calculator import CraftingCalculator, Ingredient, RecipeError
from apps.results.diagnosis import (
    BLOCKED_BY_SUB_PRODUCT,
    CIRCULAR_RECIPE,
    HINT_BLOCKED,
    HINT_MARKET_AS_SUB,
    HINT_NEW_MARKET,
    HINT_OVERFLOW,
    HINT_PRODUCT_AS_BASIC,
    MISSING_PRICE,
    TOTAL_OVERFLOW,
    UNKNOWN_SUB_PRODUCT,
    Problem,
    ProductRef,
    diagnose,
    rejection_message,
    select_rejection,
)

PRICES = {"나무": 10, "못": 5, "천": 7}
# conftest의 catalog fixture와 같은 레시피 (판자 → 식탁, 의자)
BASE = {
    "판자": [("나무", True, 3)],
    "식탁": [("판자", False, 2), ("못", True, 4)],
    "의자": [("판자", False, 1), ("천", True, 2)],
}


def build(lines_by_product):
    """{물품명: [(재료, basic, 개수)]} → (recipes, product_ids). id는 넣은 순서다."""
    recipes = {name: [Ingredient(*line) for line in lines] for name, lines in lines_by_product.items()}
    return recipes, {name: index for index, name in enumerate(lines_by_product, start=1)}


def run(lines_by_product, prices=PRICES, focus=()):
    recipes, product_ids = build(lines_by_product)
    return diagnose(recipes, product_ids, prices, focus=focus)


def ref(diagnosis_input, name):
    return ProductRef(list(diagnosis_input).index(name) + 1, name)


def legacy_message(lines_by_product, name, prices=PRICES):
    """기존 서버가 쓰던 계산기 오류 문구."""
    recipes, _ = build(lines_by_product)
    try:
        CraftingCalculator(recipes, prices).calculate(name)
    except RecipeError as error:
        return str(error)
    raise AssertionError("계산기가 실패하지 않았다")


def test_base_catalog_has_no_problems():
    diagnosis = run(BASE)

    assert diagnosis.problems == ()
    assert diagnosis.blocking_keys == frozenset()
    assert diagnosis.uncomputable == frozenset()
    assert list(diagnosis.sheets) == ["판자", "식탁", "의자"]
    assert diagnosis.sheets["식탁"].total_price == 80


def test_missing_price_and_unknown_are_owned_by_direct_holder():
    catalog = {**BASE, "판자": [("나무오타", True, 3)], "뚜껑": [("없는물품", False, 1)], "상자": [("뚜껑", False, 1)]}

    diagnosis = run(catalog)

    missing = Problem(MISSING_PRICE, ref(catalog, "판자"), "나무오타", hint=HINT_NEW_MARKET)
    unknown = Problem(UNKNOWN_SUB_PRODUCT, ref(catalog, "뚜껑"), "없는물품")
    assert diagnosis.problems == (
        unknown,
        missing,
        Problem(BLOCKED_BY_SUB_PRODUCT, ref(catalog, "식탁"), related=("판자",), hint=HINT_BLOCKED),
        Problem(BLOCKED_BY_SUB_PRODUCT, ref(catalog, "의자"), related=("판자",), hint=HINT_BLOCKED),
        Problem(BLOCKED_BY_SUB_PRODUCT, ref(catalog, "상자"), related=("뚜껑",), hint=HINT_BLOCKED),
    )
    # 계산을 시작한 최상위 물품(식탁)이 아니라 그 재료 줄을 가진 물품(판자)으로 적는다.
    assert missing.message == "시세 정보가 없는 재료가 있습니다. (판자: 나무오타)"
    assert unknown.message == "하위 재료에 잘못된 물품명이 있습니다. (뚜껑: 없는물품)"
    assert diagnosis.problems[2].message == "하위 물품에 문제가 있어 계산할 수 없습니다. (식탁 ← 판자)"
    assert diagnosis.uncomputable == {"판자", "식탁", "의자", "뚜껑", "상자"}
    assert diagnosis.sheets == {}
    assert diagnosis.causes["식탁"] == (missing,)
    assert diagnosis.causes["상자"] == (unknown,)


def test_every_missing_material_in_recipe_is_reported():
    catalog = {**BASE, "새물품": [("은", True, 1), ("나무", True, 1), ("금", True, 2), ("은", True, 3)]}

    diagnosis = run(catalog)

    # 계산기는 첫 재료(은)에서 멈추지만 진단은 모두 찾는다. 같은 재료가 두 줄이어도 한 번만 적는다.
    assert [problem.material for problem in diagnosis.problems] == ["은", "금"]
    assert rejection_message(diagnosis.problems) == "시세 정보가 없는 재료가 있습니다. (새물품: 은, 새물품: 금)"
    assert set(diagnosis.sheets) == {"판자", "식탁", "의자"}


def test_hints_for_wrong_basic_flag():
    catalog = {
        **BASE,
        "상자": [("판자", True, 1), ("나무", False, 1), ("은", True, 1), ("없는물품", False, 1)],
    }

    hints = {(problem.code, problem.material): problem.hint for problem in run(catalog).problems}

    assert hints == {
        # 물품 이름을 기본 재료로 적었다 → '하위재료 O'로
        (MISSING_PRICE, "판자"): HINT_PRODUCT_AS_BASIC,
        # 시세 이름을 하위 물품으로 적었다 → '최하위재료'로
        (UNKNOWN_SUB_PRODUCT, "나무"): HINT_MARKET_AS_SUB,
        (MISSING_PRICE, "은"): HINT_NEW_MARKET,
        (UNKNOWN_SUB_PRODUCT, "없는물품"): None,
    }


def test_cycle_reported_once_with_path_from_focus():
    # test_rename_rolls_back_when_recipe_check_fails와 같은 상태: 판자(id 1)를 널빤지로 바꾸며 식탁을 재료로 넣었다.
    catalog = {
        "널빤지": [("식탁", False, 1)],
        "식탁": [("널빤지", False, 2), ("못", True, 4)],
        "의자": [("널빤지", False, 1), ("천", True, 2)],
    }

    from_plank = run(catalog, focus=["널빤지"])
    from_table = run(catalog, focus=["식탁"])

    cycles = [problem for problem in from_plank.problems if problem.code == CIRCULAR_RECIPE]
    assert len(cycles) == 1
    assert cycles[0].message == "재료 구성에 순환 참조가 있습니다. (널빤지 → 식탁 → 널빤지)"
    assert cycles[0].related == ("널빤지", "식탁", "널빤지")
    assert cycles[0].keys == ((CIRCULAR_RECIPE, 1, None), (CIRCULAR_RECIPE, 2, None))
    assert [problem.message for problem in from_table.problems if problem.code == CIRCULAR_RECIPE] == [
        "재료 구성에 순환 참조가 있습니다. (식탁 → 널빤지 → 식탁)"
    ]
    # focus는 경로를 적는 시작점만 바꾼다. 같은 상태면 키가 같아야 쓰기 전후 비교에서 새 문제로 보지 않는다.
    assert from_plank.blocking_keys == from_table.blocking_keys
    assert (BLOCKED_BY_SUB_PRODUCT, 3, None) in from_plank.blocking_keys


def test_cycle_found_even_after_unknown_sub_product():
    catalog = {"A": [("없는물품", False, 1), ("B", False, 1)], "B": [("A", False, 1)]}

    diagnosis = run(catalog)

    # 계산기는 '없는물품'에서 멈춰서 순환을 알리지 못한다.
    assert legacy_message(catalog, "A") == "하위 재료에 잘못된 물품명이 있습니다. (A: 없는물품)"
    assert [problem.message for problem in diagnosis.problems] == [
        "하위 재료에 잘못된 물품명이 있습니다. (A: 없는물품)",
        "재료 구성에 순환 참조가 있습니다. (A → B → A)",
    ]


def test_blocked_uses_reverse_reachability_and_terminates_on_cycles():
    catalog = {
        "A": [("B", False, 1)],
        "B": [("A", False, 1), ("C", False, 1)],
        "C": [("B", False, 1)],
        "D": [("A", False, 1), ("나무", True, 1)],  # 순환 밖에서 순환을 가리킨다
        "E": [("D", False, 1), ("D", False, 2)],
        "F": [("나무", True, 1)],
    }

    diagnosis = run(catalog)

    cycles = [problem for problem in diagnosis.problems if problem.code == CIRCULAR_RECIPE]
    assert [problem.related for problem in cycles] == [("A", "B", "A"), ("B", "C", "B")]
    blocked = {
        problem.product.name: problem.related
        for problem in diagnosis.problems
        if problem.code == BLOCKED_BY_SUB_PRODUCT
    }
    assert blocked == {"D": ("A",), "E": ("D",)}
    assert diagnosis.uncomputable == {"A", "B", "C", "D", "E"}
    assert list(diagnosis.sheets) == ["F"]
    assert diagnosis.causes["E"] == tuple(cycles)


def cycle_keys_by_name(diagnosis, lines_by_product):
    """CIRCULAR_RECIPE 키를 물품 이름 집합으로 바꾼다 (id 순서가 다른 입력끼리 비교하려고)."""
    names = {index: name for index, name in enumerate(lines_by_product, start=1)}
    return {names[product_id] for code, product_id, _ in diagnosis.blocking_keys if code == CIRCULAR_RECIPE}


def test_cycle_members_are_strongly_connected_regardless_of_traversal_order():
    # A → B → C → A와 A → D → B. D도 순환 A → D → B → C → A 위에 있다. 순환 밖의 P가 D를 쓴다.
    cycle = {
        "A": [("B", False, 1), ("D", False, 1)],
        "B": [("C", False, 1)],
        "C": [("A", False, 1)],
        "D": [("B", False, 1)],
    }
    variants = [
        {"P": [("D", False, 1)], **cycle},  # 순회가 P → D로 순환에 들어간다
        {"P": [("나무", True, 1)], **cycle},  # P가 순환을 쓰지 않는다
        {**cycle, "A": [("D", False, 1), ("B", False, 1)]},  # A의 재료 순서만 다르다
        dict(reversed(list(cycle.items()))),  # 물품 id 순서가 다르다
    ]

    for lines_by_product in variants:
        diagnosis = run(lines_by_product)

        assert cycle_keys_by_name(diagnosis, lines_by_product) == {"A", "B", "C", "D"}
        blocked = {problem.product.name for problem in diagnosis.problems if problem.code == BLOCKED_BY_SUB_PRODUCT}
        assert blocked <= {"P"}
        # 순환 구성원은 모두 어떤 순환 경로엔가 나온다 (점검 화면에서 이유가 보인다).
        cycles = [problem for problem in diagnosis.problems if problem.code == CIRCULAR_RECIPE]
        assert {name for problem in cycles for name in problem.related} == {"A", "B", "C", "D"}


def test_chord_cycle_member_is_reported_as_cycle_and_keeps_keys_when_entry_changes():
    # 순환 A ↔ B에 현(A → C → B)이 있다. C도 순환 A → C → B → A 위에 있다. 순환 밖의 D가 A를 쓴다.
    before_lines = {
        "D": [("나무", True, 1), ("A", False, 1)],
        "A": [("B", False, 1), ("C", False, 1)],
        "B": [("A", False, 1)],
        "C": [("B", False, 1)],
    }
    after_lines = {**before_lines, "D": [("나무", True, 1), ("C", False, 1)]}

    before = run(before_lines)
    after = run(after_lines, focus=["D"])

    assert [problem.related for problem in before.problems if problem.code == CIRCULAR_RECIPE] == [
        ("A", "B", "A"),
        ("C", "B", "A", "C"),
    ]
    blocked = {
        problem.product.name: problem.related for problem in before.problems if problem.code == BLOCKED_BY_SUB_PRODUCT
    }
    assert blocked == {"D": ("A",)}
    # 순환 밖의 D가 순환에 들어가는 물품만 바꿨으므로 새 문제가 없다.
    assert after.blocking_keys == before.blocking_keys


def test_new_cycle_through_product_blocked_by_cycle_is_a_new_key():
    before_lines = {"A": [("B", False, 1)], "B": [("A", False, 1)], "C": [("B", False, 1)]}
    after_lines = {**before_lines, "A": [("B", False, 1), ("C", False, 1)]}

    before = run(before_lines)
    after = run(after_lines, focus=["A"])

    assert after.blocking_keys - before.blocking_keys == {(CIRCULAR_RECIPE, 3, None)}
    selected = select_rejection(after, after.blocking_keys - before.blocking_keys, focus=["A"])
    assert rejection_message(selected) == "재료 구성에 순환 참조가 있습니다. (A → B → A, A → C → B → A)"


def test_overflow_removed_from_sheets_not_propagated():
    catalog = {**BASE, "조각": [("판자", False, 0.0001)]}

    diagnosis = run(catalog, prices={**PRICES, "나무": 2**31 - 1})

    overflows = [problem for problem in diagnosis.problems if problem.code == TOTAL_OVERFLOW]
    assert [problem.product.name for problem in overflows] == ["판자", "식탁", "의자"]
    assert all(problem.hint == HINT_OVERFLOW for problem in overflows)
    # 판자를 아주 조금 쓰는 조각은 저장할 수 있다. 합계 초과는 상위 물품을 막지 않는다.
    assert {problem.code for problem in diagnosis.problems} == {TOTAL_OVERFLOW}
    assert list(diagnosis.sheets) == ["조각"]
    assert diagnosis.uncomputable == {"판자", "식탁", "의자"}
    assert diagnosis.causes["판자"] == (overflows[0],)
    assert (TOTAL_OVERFLOW, 1, None) in diagnosis.blocking_keys


def test_blocking_keys_are_id_based_and_survive_rename():
    before = run({**BASE, "판자": [("은", True, 3)]})
    renamed = run(
        {
            "널빤지": [("은", True, 3)],
            "식탁": [("널빤지", False, 2), ("못", True, 4)],
            "의자": [("널빤지", False, 1), ("천", True, 2)],
        }
    )

    expected = {(MISSING_PRICE, 1, "은"), (BLOCKED_BY_SUB_PRODUCT, 2, None), (BLOCKED_BY_SUB_PRODUCT, 3, None)}
    assert before.blocking_keys == expected
    assert renamed.blocking_keys == expected


def test_rejection_message_single_problem_equals_legacy_text():
    unknown = {"C": [("없음", False, 1)]}
    cycle = {"A": [("B", False, 1)], "B": [("A", False, 1)]}
    missing = {"D": [("은", True, 1)]}
    cases = [
        (run(unknown).problems, legacy_message(unknown, "C")),
        (run(cycle).problems, legacy_message(cycle, "A")),
        (run(missing).problems, legacy_message(missing, "D")),
        # 기존 서버의 결과 저장 오류 문구
        (
            run(BASE, prices={**PRICES, "나무": 2**31 - 1}).problems[:1],
            "합계 금액이 너무 커서 저장할 수 없습니다. (판자)",
        ),
    ]

    for problems, legacy in cases:
        assert len(problems) == 1
        assert rejection_message(problems) == problems[0].message == legacy


def test_rejection_message_group_order_and_truncation():
    plank, table = ProductRef(1, "판자"), ProductRef(2, "식탁")
    problems = [
        Problem(BLOCKED_BY_SUB_PRODUCT, table, related=("판자",)),
        Problem(TOTAL_OVERFLOW, ProductRef(3, "의자")),
        Problem(MISSING_PRICE, table, "은"),
        Problem(MISSING_PRICE, plank, "금"),
        Problem(CIRCULAR_RECIPE, plank, path=(plank, table, plank), related=("판자", "식탁", "판자")),
        Problem(UNKNOWN_SUB_PRODUCT, table, "없음"),
    ]

    assert rejection_message(problems) == (
        "하위 재료에 잘못된 물품명이 있습니다. (식탁: 없음) "
        "재료 구성에 순환 참조가 있습니다. (판자 → 식탁 → 판자) "
        "시세 정보가 없는 재료가 있습니다. (판자: 금, 식탁: 은) "
        "합계 금액이 너무 커서 저장할 수 없습니다. (의자) "
        "하위 물품에 문제가 있어 계산할 수 없습니다. (식탁 ← 판자)"
    )

    many = [Problem(MISSING_PRICE, plank, f"재료{index:02d}") for index in range(11)]
    assert rejection_message(many) == (
        "시세 정보가 없는 재료가 있습니다. (" + ", ".join(f"판자: 재료{index:02d}" for index in range(10)) + " 외 1건)"
    )
    assert rejection_message(many[:10]).endswith("판자: 재료09)")


def test_select_rejection_includes_preexisting_causes_and_focus_blocked_only():
    # 판자 레시피를 고장 내면 식탁·의자도 새로 막히지만, 메시지에는 근본 원인만 적는다.
    before = run(BASE)
    after = run({**BASE, "판자": [("은", True, 3)]}, focus=["판자"])
    new_keys = after.blocking_keys - before.blocking_keys

    assert len(new_keys) == 3
    selected = select_rejection(after, new_keys, focus=["판자"])
    assert rejection_message(selected) == "시세 정보가 없는 재료가 있습니다. (판자: 은)"

    # 이미 고장 난 판자를 새물품이 쓰면, 이미 있던 원인과 이번에 쓴 물품의 막힘을 함께 적는다.
    # 이미 막혀 있던 식탁·의자는 적지 않는다.
    legacy = {**BASE, "판자": [("은", True, 3)]}
    before = run(legacy)
    after = run({**legacy, "새물품": [("판자", False, 1)]}, focus=["새물품"])

    selected = select_rejection(after, after.blocking_keys - before.blocking_keys, focus=["새물품"])

    assert rejection_message(selected) == (
        "시세 정보가 없는 재료가 있습니다. (판자: 은) 하위 물품에 문제가 있어 계산할 수 없습니다. (새물품 ← 판자)"
    )


def test_select_rejection_lists_new_problems_of_several_products_in_id_order():
    before = run(BASE)
    after = run(
        {**BASE, "C": [("없음", False, 1)], "D": [("은", True, 1)]},
        focus=["C", "D"],
    )

    selected = select_rejection(after, after.blocking_keys - before.blocking_keys, focus=["C", "D"])

    assert rejection_message(selected) == (
        "하위 재료에 잘못된 물품명이 있습니다. (C: 없음) 시세 정보가 없는 재료가 있습니다. (D: 은)"
    )
