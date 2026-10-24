"""시세·물품·결과를 잇는 곳: 카탈로그 쓰기의 전역 잠금, 쓰기 전후 진단, 결과 동기화.

모든 카탈로그 쓰기 서비스(물품 추가·수정·삭제, 시세 수정)는 자기 트랜잭션 안에서 같은 흐름을 따른다.
    before = begin_catalog_change()              # 잠금 → 레시피·시세 읽기 → 진단
    ... 시세/물품/재료 쓰기 ...
    finish_catalog_change(before, focus=[...])   # 다시 진단 → 새 차단 문제면 400(전부 롤백) → 결과 동기화

그래서 쓰기 API가 성공하면 계산할 수 있는 모든 물품의 결과가 현재 레시피·시세와 같다. 이미 있던 문제(레거시 데이터,
DB 직접 수정)는 다른 쓰기를 막지 않고, 그런 물품의 저장된 결과는 지우지 않고 마지막 값으로 둔다.
결과는 지우고 다시 만들지 않고 제자리에서 갱신한다 (id·createdAt 보존, 값이 바뀐 행만 updatedAt 갱신).

이 모듈은 products.services, markets.services를 import하지 않는다 (그쪽이 이 모듈을 부른다).
"""

from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.transaction import TransactionManagementError
from django.utils import timezone

from apps.common.exceptions import BadRequest
from apps.markets.models import Market
from apps.products.recipes import load_catalog
from apps.results.diagnosis import diagnose, rejection_message, select_rejection
from apps.results.models import Result

SAVE_CONFLICT_MESSAGE = "결과를 저장하지 못했습니다. 잠시 후 다시 시도해 주세요."


@dataclass(frozen=True)
class SyncReport:
    """결과 동기화 결과. created는 새로 만든 결과(물품 id 순), recalculated는 동기화 전에 저장돼 있던 결과 수다."""

    created: list[Result]
    updated: int
    unchanged: int
    recalculated: int


def lock_catalog():
    """카탈로그 쓰기의 전역 잠금. 시세 행 전체를 id 순서로 잠근다 (Market.lock_all).

    결과를 쓰는 작업끼리, 그리고 시세·물품 쓰기끼리 순서대로 실행되게 한다. 모든 카탈로그 쓰기가 이 잠금을 가장 먼저
    잡는다. 트랜잭션 밖에서는 잠금이 바로 풀리므로 막는다 (SQLite는 FOR UPDATE가 없어서 Django가 막아 주지 않는다).
    """
    if not transaction.get_connection().in_atomic_block:
        raise TransactionManagementError("lock_catalog()는 트랜잭션 안에서만 부를 수 있습니다.")
    list(Market.objects.lock_all().values_list("id", flat=True))


def begin_catalog_change():
    """카탈로그 쓰기를 시작한다. 전역 잠금을 잡고 쓰기 전의 차단 문제 키를 돌려준다 (finish_catalog_change에 넘긴다)."""
    lock_catalog()
    return diagnose(*_load()).blocking_keys


def finish_catalog_change(before_keys, *, focus=()):
    """카탈로그 쓰기를 마친다. 이번 쓰기가 새 차단 문제를 만들었으면 400, 아니면 모든 결과를 동기화한다.

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
