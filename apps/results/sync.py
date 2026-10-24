"""시세·물품·결과를 잇는 곳: 카탈로그 쓰기의 전역 잠금, 쓰기 전후 진단, 결과 동기화.

모든 카탈로그 쓰기 서비스(물품 추가·수정·삭제, 시세 수정)는 자기 트랜잭션 안에서 같은 흐름을 따른다.
    before = begin_catalog_change()              # 잠금 → 레시피·시세 읽기 → 진단 → 이미 있던 문제의 키
    ... 시세/물품/재료 쓰기 ...
    finish_catalog_change(before, focus=[...])   # 다시 진단 → 새 차단 문제면 400(전부 롤백) → 결과 동기화

그래서 쓰기 API가 성공하면 계산할 수 있는 모든 물품의 결과가 현재 레시피·시세와 같다. 이미 있던 문제(레거시 데이터,
DB 직접 수정)는 다른 쓰기를 막지 않고, 그런 물품의 저장된 결과는 지우지 않고 마지막 값으로 둔다.
결과는 지우고 다시 만들지 않고 제자리에서 갱신한다 (id·createdAt 보존, 값이 바뀐 행만 updatedAt 갱신).
남은 문제는 check_catalog(GET /catalog/check)가 저장하지 않고 모두 보여 준다.

이 모듈은 products.services, markets.services를 import하지 않는다 (그쪽이 이 모듈을 부른다).
"""

from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.transaction import TransactionManagementError
from django.utils import timezone

from apps.common.exceptions import BadRequest
from apps.experiences.services import AMPLE_PRODUCT_NAME
from apps.markets.models import Market
from apps.products.recipes import load_catalog
from apps.results.diagnosis import (
    BLOCKED_BY_SUB_PRODUCT,
    ERROR_CODES,
    diagnose,
    rejection_message,
    select_rejection,
)
from apps.results.models import Result

SAVE_CONFLICT_MESSAGE = "결과를 저장하지 못했습니다. 잠시 후 다시 시도해 주세요."

# 점검(GET /catalog/check)의 경고·정보 문제. 차단 문제(error)는 apps.results.diagnosis가 찾는다.
MISSING_RESULT = "MISSING_RESULT"
STALE_RESULT = "STALE_RESULT"
NAME_CONFLICT = "NAME_CONFLICT"
REQUIRED_PRODUCT_MISSING = "REQUIRED_PRODUCT_MISSING"
UNUSED_MARKET = "UNUSED_MARKET"
HINT_SYNC_RESULTS = "'결과 다시 맞추기'를 누르세요."
# code → (severity, 메시지 접두 문구, hint). 메시지는 '{접두 문구} ({이름})'이다.
NOTICES = {
    MISSING_RESULT: ("warning", "결과가 없습니다.", HINT_SYNC_RESULTS),
    STALE_RESULT: ("warning", "저장된 결과가 현재 레시피·시세와 다릅니다.", HINT_SYNC_RESULTS),
    NAME_CONFLICT: (
        "warning",
        "같은 이름의 물품과 시세가 있습니다.",
        "'최하위재료'로 쓰면 시세 가격, '하위재료 O'로 쓰면 물품 레시피로 계산됩니다.",
    ),
    REQUIRED_PRODUCT_MISSING: ("warning", "호두작 계산에 쓰는 물품의 결과가 없습니다.", None),
    UNUSED_MARKET: ("info", "어떤 물품도 쓰지 않는 시세입니다.", "필요 없으면 삭제하세요."),
}
# 점검 문제의 정렬 순서: 수준 → 코드 → 물품 id(없으면 뒤) → (같은 물품 안에서는 레시피 순) → 시세 id
SEVERITIES = ("error", "warning", "info")
CHECK_CODES = (*ERROR_CODES, *NOTICES)


@dataclass(frozen=True)
class SyncReport:
    """결과 동기화 결과. created는 새로 만든 결과(물품 id 순), recalculated는 동기화 전에 저장돼 있던 결과 수다."""

    created: list[Result]
    updated: int
    unchanged: int
    recalculated: int


@dataclass(frozen=True)
class ProductCheck:
    """점검한 물품 하나. status: ok | missing(결과 없음) | stale(결과 낡음) | error(계산할 수 없음)"""

    id: int
    name: str
    status: str
    result_id: int | None


@dataclass(frozen=True)
class MarketUsage:
    """시세 하나와, 그 이름을 기본 재료(basic=True)로 직접 쓰는 물품 이름(물품 id 순)."""

    id: int
    name: str
    price: int
    used_by: tuple[str, ...]


@dataclass(frozen=True)
class CheckProblem:
    """점검 문제 하나. 해당 없는 필드는 None이나 ()다."""

    code: str
    severity: str
    message: str
    product_id: int | None = None
    product_name: str | None = None
    material: str | None = None
    market_id: int | None = None
    related: tuple[str, ...] = ()
    hint: str | None = None


@dataclass(frozen=True)
class CatalogCheck:
    """check_catalog() 결과. products는 물품 id 순, markets는 시세 id 순, problems는 CHECK_CODES 기준 정렬이다."""

    products: list[ProductCheck]
    markets: list[MarketUsage]
    problems: list[CheckProblem]
    results: int  # 저장된 결과 수


def lock_catalog():
    """카탈로그 쓰기의 전역 잠금. 시세 행 전체를 id 순서로 잠근다 (Market.lock_all).

    결과를 쓰는 작업끼리, 그리고 시세·물품 쓰기끼리 순서대로 실행되게 한다. 모든 카탈로그 쓰기가 이 잠금을 가장 먼저
    잡는다. 트랜잭션 밖에서는 잠금이 바로 풀리므로 막는다 (SQLite는 FOR UPDATE가 없어서 Django가 막아 주지 않는다).
    """
    if not transaction.get_connection().in_atomic_block:
        raise TransactionManagementError("lock_catalog()는 트랜잭션 안에서만 부를 수 있습니다.")
    list(Market.objects.lock_all().values_list("id", flat=True))


def begin_catalog_change():
    """카탈로그 쓰기를 시작한다. 전역 잠금을 잡고 '이미 있던 문제'의 키를 돌려준다 (finish_catalog_change에 넘긴다).

    쓰기 전의 차단 문제 키에, 쓰기 전에 이미 계산할 수 없던 물품마다 BLOCKED_BY_SUB_PRODUCT 키를 더한다.
    그런 물품은 자기 문제만 고치고 이미 고장 난 하위 물품을 그대로 쓰면 원인이 '하위 물품 문제'로 바뀌는데,
    이것은 새 문제가 아니다 (I6). 쓰기 전에 계산할 수 있던 물품이 막히면 지금처럼 새 문제로 거절한다.
    """
    lock_catalog()
    recipes, product_ids, prices = _load()
    before = diagnose(recipes, product_ids, prices)
    already_blocked = {(BLOCKED_BY_SUB_PRODUCT, product_ids[name], None) for name in before.uncomputable}
    return before.blocking_keys | already_blocked


def finish_catalog_change(before_keys, *, focus=()):
    """카탈로그 쓰기를 마친다. 이번 쓰기가 새 차단 문제를 만들었으면 400, 아니면 모든 결과를 동기화한다.

    before_keys: begin_catalog_change()가 돌려준 이미 있던 문제의 키. 여기에 없는 차단 키가 새 문제다.

    focus: 이번에 쓴 물품 이름. 거절 메시지에 그 물품의 막힘을 적고, 순환 경로를 그 물품부터 적는다.
    400(BadRequest)은 호출한 서비스의 트랜잭션을 롤백해서 시세·물품 쓰기까지 함께 취소한다.
    """
    lock_catalog()  # 같은 트랜잭션에서 이미 잡았으면 바로 통과한다.
    recipes, product_ids, prices = _load()
    focus = list(focus)
    after = diagnose(recipes, product_ids, prices, focus=focus)
    new_keys = after.blocking_keys - before_keys
    if new_keys:
        raise BadRequest(rejection_message(select_rejection(after, new_keys, focus)))
    return _save(after.sheets, product_ids)


@transaction.atomic
def sync_all_results(*, create_missing=True, strict=False):
    """저장된 결과를 현재 레시피·시세에 맞춘다 (POST /result, recalculate_results 명령).

    create_missing이면 결과가 없는 물품의 결과도 만든다. 계산할 수 없는 물품은 건너뛰고 저장된 결과를 그대로 둔다.
    strict이면 대상 물품(create_missing이 아니면 결과가 있는 물품만) 중 계산할 수 없는 것이 있을 때 그 원인을 모아
    400이다. 이때는 아무것도 저장하지 않는다.
    """
    lock_catalog()
    recipes, product_ids, prices = _load()
    diagnosis = diagnose(recipes, product_ids, prices)
    stored = _stored_results()
    scope = [name for name in recipes if create_missing or product_ids[name] in stored]
    failed = [name for name in scope if name in diagnosis.uncomputable]
    if strict and failed:
        causes = {cause for name in failed for cause in diagnosis.causes.get(name, ())}
        # diagnosis.problems 순서(같은 물품 안에서는 레시피 순)를 지킨다.
        raise BadRequest(rejection_message(problem for problem in diagnosis.problems if problem in causes))
    sheets = {name: diagnosis.sheets[name] for name in scope if name in diagnosis.sheets}
    return _save(sheets, product_ids, stored)


def check_catalog():
    """시세·물품·결과가 서로 맞는지 점검한다 (GET /catalog/check). 저장하지 않고 잠그지 않는다. 쿼리는 4번이다.

    차단 문제(error)는 쓰기 API와 같은 진단(diagnose)으로 찾는다. 그 밖에 결과가 없거나 낡은 물품, 이름이 같은
    물품과 시세, 호두작 계산에 쓰는 물품의 결과 누락(warning), 쓰지 않는 시세(info)를 함께 알린다.
    """
    recipes, product_ids = load_catalog()
    markets = list(Market.objects.order_by("id").values_list("id", "name", "price"))
    stored = _stored_results()
    diagnosis = diagnose(recipes, product_ids, {name: price for _, name, price in markets})

    problems = [_blocking_problem(problem) for problem in diagnosis.problems]
    products = []
    for name in recipes:  # 물품 id 순
        product_id = product_ids[name]
        result, sheet = stored.get(product_id), diagnosis.sheets.get(name)
        if sheet is None:
            status = "error"  # 계산할 수 없다. 이유는 차단 문제에 있다.
        elif result is None:
            status = "missing"
            problems.append(_notice(MISSING_RESULT, name, product_id=product_id, product_name=name))
        elif not result.matches(sheet):
            status = "stale"
            problems.append(_notice(STALE_RESULT, name, product_id=product_id, product_name=name))
        else:
            status = "ok"
        products.append(ProductCheck(product_id, name, status, result.id if result else None))

    used_by = {}  # 시세 이름 → {물품 이름: None}. 물품 id 순이고, 한 물품이 같은 재료를 여러 줄 써도 한 번이다.
    for name, recipe in recipes.items():
        for item in recipe:
            if item.basic:
                used_by.setdefault(item.name, {})[name] = None
    for market_id, name, _ in markets:
        if name in product_ids:
            conflict = {"product_id": product_ids[name], "product_name": name, "material": name, "market_id": market_id}
            problems.append(_notice(NAME_CONFLICT, name, **conflict))
        if name not in used_by:
            problems.append(_notice(UNUSED_MARKET, name, material=name, market_id=market_id))

    # 호두나무 계산(GET /experience/walnut)은 이 물품의 결과가 없으면 400이다.
    ample_id = product_ids.get(AMPLE_PRODUCT_NAME)
    if ample_id not in stored:
        problems.append(
            _notice(REQUIRED_PRODUCT_MISSING, AMPLE_PRODUCT_NAME, product_id=ample_id, product_name=AMPLE_PRODUCT_NAME)
        )

    # 정렬이 안정적이라 같은 물품의 재료 문제는 진단 순서(레시피 순)를 지킨다.
    problems.sort(key=_check_problem_order)
    usages = [MarketUsage(market_id, name, price, tuple(used_by.get(name, ()))) for market_id, name, price in markets]
    return CatalogCheck(products=products, markets=usages, problems=problems, results=len(stored))


def _blocking_problem(problem):
    """진단의 차단 문제(diagnosis.Problem)를 점검 문제로 바꾼다."""
    return CheckProblem(
        problem.code,
        "error",
        problem.message,
        product_id=problem.product.id,
        product_name=problem.product.name,
        material=problem.material,
        related=problem.related,
        hint=problem.hint,
    )


def _notice(code, name, **fields):
    """경고·정보 문제. 메시지는 '{접두 문구} ({name})'이다."""
    severity, prefix, hint = NOTICES[code]
    return CheckProblem(code, severity, f"{prefix} ({name})", hint=hint, **fields)


def _check_problem_order(problem):
    return (
        SEVERITIES.index(problem.severity),
        CHECK_CODES.index(problem.code),
        problem.product_id is None,
        problem.product_id or 0,
        problem.market_id is None,
        problem.market_id or 0,
    )


def _load():
    """레시피(쿼리 2번)와 DB 시세(1번)를 읽는다. (recipes, product_ids, prices)"""
    recipes, product_ids = load_catalog()
    # 시세 읽기는 name을 첫 필드로 둔다. Postgres 잠금 테스트가 'SELECT "market"."name"' 조각으로 이 읽기를 찾는다.
    prices = dict(Market.objects.values_list("name", "price"))
    return recipes, product_ids, prices


def _stored_results():
    """저장된 결과를 물품 id → Result로 읽는다 (쿼리 1번)."""
    results = Result.objects.only("id", "product_id", "names", "counts", "prices", "total_price")
    return {result.product_id: result for result in results}


def _save(sheets, product_ids, stored=None):
    """계산한 비용(sheets, 물품 id 순)을 결과에 반영한다. 결과가 없으면 만들고, 값이 다른 결과만 제자리에서 고친다."""
    if stored is None:
        stored = _stored_results()
    now = timezone.now()
    created, updated, unchanged = [], [], 0
    for name, sheet in sheets.items():
        result = stored.get(product_ids[name])
        if result is None:
            result = Result(product_id=product_ids[name])
            result.apply_cost_sheet(sheet)
            created.append(result)
        elif result.matches(sheet):
            unchanged += 1
        else:
            result.apply_cost_sheet(sheet)
            result.updated_at = now
            updated.append(result)

    if created:
        try:
            with transaction.atomic():
                created = Result.objects.bulk_create(created)
        except IntegrityError:
            # 다른 요청이 같은 물품의 결과를 먼저 만든 경우 (product_id unique). 전역 잠금 아래에서는 일어나지 않는다.
            raise BadRequest(SAVE_CONFLICT_MESSAGE) from None
    if updated:
        fields = ["names", "counts", "prices", "total_price", "updated_at"]
        Result.objects.bulk_update(updated, fields, batch_size=500)
    return SyncReport(created=created, updated=len(updated), unchanged=unchanged, recalculated=len(stored))
