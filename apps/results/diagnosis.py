"""카탈로그(물품 레시피 + 시세) 진단 (DB와 무관한 순수 로직).

결과를 계산할 수 없게 만드는 차단 문제를 한 번에 모두 찾는다. 계산기는 첫 오류 하나에서 멈추므로 따로 둔다.
- UNKNOWN_SUB_PRODUCT: 하위 물품(basic=False)인데 같은 이름의 물품이 없다
- MISSING_PRICE: 기본 재료(basic=True)인데 같은 이름의 시세가 없다
- CIRCULAR_RECIPE: 하위 물품을 따라가면 자기 자신으로 돌아온다
- TOTAL_OVERFLOW: 합계가 결과 테이블 totalPrice(integer) 범위를 넘는다. 상위 물품으로 전파하지 않는다
- BLOCKED_BY_SUB_PRODUCT: 자기 레시피에는 문제가 없지만 직속 하위 물품을 계산할 수 없다

앞의 셋이 근본 원인이다. 계산할 수 없는 물품마다 그 이유(자기와 하위 트리의 근본 원인, 또는 자기 합계 초과)를
causes에 모은다. 쓰기 API는 쓰기 전후의 blocking_keys를 비교해 이번 쓰기가 새로 만든 문제만 거절한다
(apps.results.sync). 키는 물품 id 기준이라 이름을 바꿔도 같은 문제는 같은 키다.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from apps.common.fields import INT32_MAX
from apps.common.numbers import round_half_up
from apps.results.calculator import CostSheet, CraftingCalculator, Ingredient, RecipeError

UNKNOWN_SUB_PRODUCT = "UNKNOWN_SUB_PRODUCT"
MISSING_PRICE = "MISSING_PRICE"
CIRCULAR_RECIPE = "CIRCULAR_RECIPE"
TOTAL_OVERFLOW = "TOTAL_OVERFLOW"
BLOCKED_BY_SUB_PRODUCT = "BLOCKED_BY_SUB_PRODUCT"

# 차단 문제(error) 코드. 순서는 점검 응답(GET /catalog/check)의 정렬 순서다.
ERROR_CODES = (UNKNOWN_SUB_PRODUCT, MISSING_PRICE, CIRCULAR_RECIPE, TOTAL_OVERFLOW, BLOCKED_BY_SUB_PRODUCT)
# 근본 원인. 이 문제를 가진 물품과, 그 물품을 하위 물품으로 (몇 단계든) 쓰는 물품은 계산할 수 없다.
ROOT_CAUSE_CODES = frozenset({UNKNOWN_SUB_PRODUCT, MISSING_PRICE, CIRCULAR_RECIPE})

# 거절 메시지의 그룹 순서와 접두 문구. 앞의 넷은 기존 서버(계산기 RecipeError, 합계 초과)의 문구와 같다.
MESSAGE_PREFIXES = {
    UNKNOWN_SUB_PRODUCT: "하위 재료에 잘못된 물품명이 있습니다.",
    CIRCULAR_RECIPE: "재료 구성에 순환 참조가 있습니다.",
    MISSING_PRICE: "시세 정보가 없는 재료가 있습니다.",
    TOTAL_OVERFLOW: "합계 금액이 너무 커서 저장할 수 없습니다.",
    BLOCKED_BY_SUB_PRODUCT: "하위 물품에 문제가 있어 계산할 수 없습니다.",
}
# 거절 메시지 한 그룹에 적는 항목 수 상한. 넘으면 ' 외 N건'으로 줄인다.
MAX_MESSAGE_ITEMS = 10

HINT_PRODUCT_AS_BASIC = "같은 이름의 물품이 있습니다. '하위재료 O'로 바꾸세요."
HINT_NEW_MARKET = "새 재료라면 시세를 추가하고, 오타라면 레시피를 고치세요."
HINT_MARKET_AS_SUB = "같은 이름의 시세가 있습니다. '최하위재료'로 바꾸세요."
HINT_OVERFLOW = "재료 개수나 시세를 확인하세요."
HINT_BLOCKED = "먼저 하위 물품을 고치세요."


@dataclass(frozen=True, slots=True)
class ProductRef:
    id: int
    name: str


@dataclass(frozen=True, slots=True)
class Problem:
    """차단 문제 하나.

    product: 문제를 가진 물품. 재료 문제(UNKNOWN_SUB_PRODUCT, MISSING_PRICE)는 계산을 시작한 최상위 물품이 아니라
        그 재료 줄을 직접 가진 물품이고, 순환은 경로의 첫 물품이다.
    material: 문제가 된 재료 이름 (재료 문제만)
    path: 순환 경로. 첫 물품으로 다시 끝나는 닫힌 경로다 (순환만)
    related: 관련 물품 이름. BLOCKED_BY_SUB_PRODUCT는 계산할 수 없는 직속 하위 물품(레시피 순), 순환은 path의 이름이다.
    """

    code: str
    product: ProductRef
    material: str | None = None
    path: tuple[ProductRef, ...] = ()
    related: tuple[str, ...] = ()
    hint: str | None = None

    @property
    def message(self) -> str:
        return f"{MESSAGE_PREFIXES[self.code]} ({', '.join(self.message_items)})"

    @property
    def message_items(self) -> tuple[str, ...]:
        """메시지 괄호 안에 적을 항목. BLOCKED_BY_SUB_PRODUCT는 하위 물품마다 하나다."""
        if self.code == CIRCULAR_RECIPE:
            return (" → ".join(self.related),)
        if self.code == BLOCKED_BY_SUB_PRODUCT:
            return tuple(f"{self.product.name} ← {name}" for name in self.related)
        if self.material is not None:
            return (f"{self.product.name}: {self.material}",)
        return (self.product.name,)

    @property
    def owners(self) -> tuple[ProductRef, ...]:
        """문제를 가진 물품. 순환은 구성 물품 전부다."""
        if self.code == CIRCULAR_RECIPE:
            return tuple(dict.fromkeys(self.path))
        return (self.product,)

    @property
    def keys(self) -> tuple[tuple[str, int, str | None], ...]:
        """쓰기 전후를 비교하는 키 (code, 물품 id, 재료). 순환은 구성 물품마다 (code, id, None)을 하나씩 만든다."""
        if self.code == CIRCULAR_RECIPE:
            return tuple((self.code, owner.id, None) for owner in self.owners)
        return ((self.code, self.product.id, self.material),)


@dataclass(frozen=True)
class Diagnosis:
    """diagnose() 결과.

    problems: 차단 문제 5종. ERROR_CODES 순 → 물품 id 순 → 같은 물품 안에서는 레시피 순이다.
    sheets: 계산할 수 있고 저장할 수 있는(합계가 범위 안인) 물품의 비용. 물품 id 순이다.
    uncomputable: 계산할 수 없거나 합계가 범위를 넘어 저장할 수 없는 물품 이름
    causes: uncomputable 물품 → 그 이유. 자기와 하위 트리의 근본 원인(이미 있던 것 포함), 또는 자기 합계 초과다.
    blocking_keys: problems의 keys 전체
    """

    problems: tuple[Problem, ...]
    sheets: dict[str, CostSheet]
    uncomputable: frozenset[str]
    causes: dict[str, tuple[Problem, ...]]
    blocking_keys: frozenset[tuple[str, int, str | None]]


def diagnose(
    recipes: Mapping[str, Sequence[Ingredient]],
    product_ids: Mapping[str, int],
    prices: Mapping[str, float],
    *,
    focus: Iterable[str] = (),
) -> Diagnosis:
    """레시피(물품명 → 재료 목록)와 시세(재료명 → 가격)로 차단 문제를 모두 찾고, 계산할 수 있는 물품을 계산한다.

    focus: 이번에 쓴 물품 이름. 순환 경로를 이 물품부터 적는 데만 쓴다 (문제와 키는 focus와 관계없이 같다).
    """
    order = sorted(recipes, key=product_ids.__getitem__)
    refs = {name: ProductRef(product_ids[name], name) for name in order}
    # 하위 물품 간선(basic=False이고 있는 물품). subs는 레시피 순이고 중복이 없다.
    subs = {
        name: list(dict.fromkeys(item.name for item in recipes[name] if not item.basic and item.name in recipes))
        for name in order
    }
    users = {name: [] for name in order}
    for name in order:
        for sub in subs[name]:
            users[sub].append(name)

    # 1. 물품마다 자기 재료 줄만 본다.
    problems = []
    for name in order:
        own = (_material_problem(refs[name], item, recipes, prices) for item in recipes[name])
        problems.extend(dict.fromkeys(problem for problem in own if problem is not None))
    has_own_cause = {problem.product.name for problem in problems}

    # 2. 순환
    focus = list(focus)
    cycles = [_cycle_problem(_rotate_to_focus(path, focus), refs) for path in _find_cycle_paths(order, subs)]
    problems.extend(cycles)
    cycle_members = {name for problem in cycles for name in problem.related}

    # 3. 막힘: 근본 원인을 가진 물품에서 '하위 물품 → 그것을 쓰는 물품' 방향으로 닿는 물품
    blocked = _reachable(has_own_cause | cycle_members, users)

    # 4. 자기 근본 원인이 없는데 막힌 물품
    for name in order:
        if name in blocked and name not in has_own_cause and name not in cycle_members:
            related = tuple(sub for sub in subs[name] if sub in blocked)
            problems.append(Problem(BLOCKED_BY_SUB_PRODUCT, refs[name], related=related, hint=HINT_BLOCKED))
    problems.sort(key=_problem_order)

    # 5. 근본 원인마다 그 원인 때문에 계산할 수 없는 물품 전부에 원인을 더한다.
    causes = {}
    for problem in problems:
        if problem.code in ROOT_CAUSE_CODES:
            for name in _reachable({owner.name for owner in problem.owners}, users):
                causes.setdefault(name, []).append(problem)

    # 6. 막히지 않은 물품을 계산한다. 계산기 하나를 써서 하위 물품 펼친 결과를 공유한다.
    calculator = CraftingCalculator(recipes, prices)
    sheets, uncomputable = {}, set(blocked)
    for name in order:
        if name in blocked:
            continue
        try:
            sheet = calculator.calculate(name)
        except RecipeError:
            # 위에서 막힘으로 판정하지 못한 레시피 오류. 일어나지 않아야 하지만 계산 불가로 둔다.
            uncomputable.add(name)
            continue
        if not math.isfinite(sheet.total_price) or abs(round_half_up(sheet.total_price)) > INT32_MAX:
            # totalPrice 컬럼이 Postgres integer라서 저장할 수 없다 (미리 계산은 저장하지 않으므로 제한 없음).
            overflow = Problem(TOTAL_OVERFLOW, refs[name], hint=HINT_OVERFLOW)
            problems.append(overflow)
            causes[name] = [overflow]
            uncomputable.add(name)
            continue
        sheets[name] = sheet
    problems.sort(key=_problem_order)

    return Diagnosis(
        problems=tuple(problems),
        sheets=sheets,
        uncomputable=frozenset(uncomputable),
        causes={name: tuple(found) for name, found in causes.items()},
        blocking_keys=frozenset(key for problem in problems for key in problem.keys),
    )


def select_rejection(after: Diagnosis, new_keys: Iterable[tuple], focus: Iterable[str] = ()) -> list[Problem]:
    """쓰기를 거절할 때 메시지에 넣을 문제를 고른다.

    새 키(new_keys)를 가진 문제의 물품마다 그 근본 원인(이미 있던 것 포함)을 모으고, 새로 막힌 물품 중에서는
    이번에 쓴 물품(focus)의 BLOCKED_BY_SUB_PRODUCT만 더한다. 상위 물품이 줄줄이 막힌 것은 원인 하나로 알린다.
    """
    new_keys, focus = set(new_keys), set(focus)
    selected = [problem for problem in after.problems if not new_keys.isdisjoint(problem.keys)]
    chosen = set()
    for problem in selected:
        for owner in problem.owners:
            chosen.update(after.causes.get(owner.name, ()))
        if problem.code == BLOCKED_BY_SUB_PRODUCT and problem.product.name in focus:
            chosen.add(problem)
    # after.problems 순서(같은 물품 안에서는 레시피 순)를 지킨다.
    return [problem for problem in after.problems if problem in chosen] or selected


def rejection_message(problems: Iterable[Problem]) -> str:
    """문제를 MESSAGE_PREFIXES 순서의 그룹으로 묶어 메시지 하나로 만든다. 문제가 1건이면 그 문제의 message와 같다.

    그룹 안 항목은 물품 id 순이고 같은 물품 안에서는 받은 순서(레시피 순)다.
    """
    ordered = sorted(problems, key=lambda problem: problem.product.id)
    groups = []
    for code, prefix in MESSAGE_PREFIXES.items():
        items = [item for problem in ordered if problem.code == code for item in problem.message_items]
        if not items:
            continue
        listed = ", ".join(items[:MAX_MESSAGE_ITEMS])
        if len(items) > MAX_MESSAGE_ITEMS:
            listed += f" 외 {len(items) - MAX_MESSAGE_ITEMS}건"
        groups.append(f"{prefix} ({listed})")
    return " ".join(groups)


def _material_problem(product, item, recipes, prices):
    if item.basic:
        if item.name in prices:
            return None
        hint = HINT_PRODUCT_AS_BASIC if item.name in recipes else HINT_NEW_MARKET
        return Problem(MISSING_PRICE, product, item.name, hint=hint)
    if item.name in recipes:
        return None
    hint = HINT_MARKET_AS_SUB if item.name in prices else None
    return Problem(UNKNOWN_SUB_PRODUCT, product, item.name, hint=hint)


def _find_cycle_paths(order, subs):
    """반복형 DFS(색 표시)로 순환 경로를 찾는다. 같은 구성원 집합의 순환은 한 번만 돌려준다.

    시작점은 물품 id 순, 하위 물품은 레시피 순이다. focus와 관계없이 돌아서
    쓰기 전후에 같은 순환을 같은 구성원으로 찾는다 (구성원이 곧 키다).
    """
    white, gray, black = 0, 1, 2
    color = dict.fromkeys(order, white)
    paths, seen = [], set()
    for start in order:
        if color[start] != white:
            continue
        color[start] = gray
        stack, branches = [start], [iter(subs[start])]
        while stack:
            node = next(branches[-1], None)
            if node is None:
                color[stack.pop()] = black
                branches.pop()
            elif color[node] == white:
                color[node] = gray
                stack.append(node)
                branches.append(iter(subs[node]))
            elif color[node] == gray:
                path = [*stack[stack.index(node) :], node]
                members = frozenset(path)
                if members not in seen:
                    seen.add(members)
                    paths.append(path)
    return paths


def _rotate_to_focus(path, focus):
    """순환 경로에 focus 물품이 있으면 그 물품부터 시작하도록 돌린다 (같은 순환이다)."""
    cycle = path[:-1]
    for name in focus:
        if name in cycle:
            index = cycle.index(name)
            rotated = cycle[index:] + cycle[:index]
            return [*rotated, rotated[0]]
    return path


def _cycle_problem(path, refs):
    return Problem(CIRCULAR_RECIPE, refs[path[0]], path=tuple(refs[name] for name in path), related=tuple(path))


def _reachable(starts, users):
    """starts와, starts에서 '하위 물품 → 그것을 재료로 쓰는 물품' 방향으로 닿는 물품 전부 (BFS)."""
    found = set(starts)
    queue = deque(found)
    while queue:
        for user in users[queue.popleft()]:
            if user not in found:
                found.add(user)
                queue.append(user)
    return found


def _problem_order(problem):
    # 정렬이 안정적이라 같은 물품 안의 재료 문제는 만든 순서(레시피 순)를 지킨다.
    return ERROR_CODES.index(problem.code), problem.product.id
