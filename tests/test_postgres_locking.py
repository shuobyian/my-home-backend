"""Postgres 전용 잠금(select_for_update)·트랜잭션 경계 테스트.

계약: 공개 쓰기 서비스(update_markets, sync_all_results, create_product, bulk_create_products, update_product,
delete_products)는 스스로 atomic을 연다. 호출부가 이미 atomic이라는 이유로 지우지 않는다.
모두 lock_catalog()(시세 lock_all)를 가장 먼저 잡는다 (apps.results.sync).
바꾸려면 이 테스트를 약하게 고치지 말고 따로 논의한다.

ATOMIC_REQUESTS가 없어서 요청은 autocommit으로 돈다. 서비스의 @transaction.atomic이 빠지면 select_for_update가
TransactionManagementError를 낸다(운영에서는 500). 테스트 클라이언트가 이 예외를 그대로 올리므로 테스트가 실패한다.
sync_all_results는 관리 명령이 트랜잭션 없이 바로 부르므로 API와 별도로 직접 불러서도 확인한다.
SQL 단언은 잠금 쿼리가 실제로 나가는지, 그리고 시세는 읽기·쓰기보다, 물품은 쓰기보다 먼저 나가는지를 본다.
SQLite는 FOR UPDATE를 만들지 않으므로 Postgres(TEST_DATABASE_URL)에서만 돈다.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.markets.models import Market
from apps.results.sync import sync_all_results

pytestmark = [
    pytest.mark.skipif(connection.vendor != "postgresql", reason="Postgres 전용"),
    pytest.mark.django_db(transaction=True),
]


def capture(send):
    """요청을 보내고 응답과 실행된 SQL 목록을 돌려준다."""
    with CaptureQueriesContext(connection) as ctx:
        response = send()
    return response, [query["sql"] for query in ctx.captured_queries]


def positions(sqls, *fragments):
    """fragments를 모두 포함하는 쿼리의 위치(실행 순서) 목록."""
    return [index for index, sql in enumerate(sqls) if all(fragment in sql for fragment in fragments)]


def test_market_update_locks_prices_before_writing(client, catalog):
    assert client.post("/result").status_code == 201
    wood = Market.objects.get(name="나무")

    response, sqls = capture(lambda: client.put("/market", [{"id": wood.id, "price": 20}], format="json"))

    assert response.status_code == 200
    # 시세 수정 시작 시의 잠금(begin_catalog_change)과 결과 동기화 전 재잠금(finish_catalog_change), 두 번이다.
    # 하나만 있어도 통과하게 쓰면 앞쪽 잠금이 빠져도 잡지 못한다.
    locks = positions(sqls, 'FROM "market"', "FOR UPDATE")
    assert len(locks) == 2
    writes = positions(sqls, 'UPDATE "market"') + positions(sqls, 'INSERT INTO "market"')
    assert writes
    assert locks[0] < min(writes)


def test_result_creation_locks_prices_before_reading_them(client, catalog):
    response, sqls = capture(lambda: client.post("/result"))

    assert response.status_code == 201
    locks = positions(sqls, 'FROM "market"', "FOR UPDATE")
    # 시세 조회(sync._load). Postgres에서는 SELECT "market"."name" AS "name", "market"."price" AS "price" 꼴이다.
    price_reads = positions(sqls, 'SELECT "market"."name"', '"market"."price"', 'FROM "market"')
    inserts = positions(sqls, 'INSERT INTO "result"')
    assert locks
    assert price_reads
    assert inserts
    assert locks[0] < price_reads[0]
    assert locks[0] < inserts[0]


@pytest.mark.parametrize(
    "send",
    [
        pytest.param(
            lambda client, catalog: client.put(
                "/product",
                {
                    "id": catalog["판자"].id,
                    "craftingPrice": 70,
                    "materials": [{"name": "나무", "basic": True, "count": 3}],
                },
                format="json",
            ),
            id="update",
        ),
        # 식탁은 다른 레시피가 재료로 쓰지 않으므로 삭제할 수 있다.
        pytest.param(
            lambda client, catalog: client.delete("/product", [catalog["식탁"].id], format="json"),
            id="delete",
        ),
    ],
)
def test_product_writes_lock_rows(client, catalog, send):
    response, sqls = capture(lambda: send(client, catalog))

    assert response.status_code == 200
    locks = positions(sqls, 'FROM "product"', "FOR UPDATE")
    # 물품은 잠금 쿼리(select_for_update)가 곧 대상 행을 처음 읽는 쿼리라서 시세처럼 따로 비교할 앞선 읽기가 없다.
    # 그 뒤의 SELECT(중복 이름·참조 확인, 레시피 검증, 다시 읽기)는 모두 잠금 뒤에 나가므로 쓰기만 기준으로 둔다.
    writes = positions(sqls, 'UPDATE "product"') + positions(sqls, 'DELETE FROM "material"')
    writes += positions(sqls, 'DELETE FROM "product"')
    assert locks
    assert writes
    assert locks[0] < min(writes)


def test_sync_all_results_opens_its_own_transaction(client, catalog):
    # 결과 행이 없거나 값이 그대로면 bulk_update가 UPDATE를 내지 않으므로, 결과를 만든 뒤 시세를 바꿔 둔다.
    assert client.post("/result").status_code == 201
    Market.objects.filter(name="나무").update(price=20)

    _, sqls = capture(sync_all_results)

    locks = positions(sqls, 'FROM "market"', "FOR UPDATE")
    price_reads = positions(sqls, 'SELECT "market"."name"', '"market"."price"', 'FROM "market"')
    writes = positions(sqls, 'UPDATE "result"')
    assert locks
    assert price_reads
    assert writes
    assert locks[0] < price_reads[0]
    assert locks[0] < writes[0]
