"""잠금(select_for_update)·트랜잭션 경계 테스트. 대부분 Postgres 전용이다.

계약: 공개 쓰기 서비스(update_markets, delete_markets, sync_all_results, create_product, bulk_create_products,
update_product, delete_products)는 스스로 atomic을 연다. 호출부가 이미 atomic이라는 이유로 지우지 않는다.
모두 lock_catalog()(시세 lock_all)를 가장 먼저 잡는다 (apps.results.sync). 그래서 카탈로그 쓰기끼리 순서대로 돈다.
바꾸려면 이 테스트를 약하게 고치지 말고 따로 논의한다.

ATOMIC_REQUESTS가 없어서 요청은 autocommit으로 돈다. 서비스의 @transaction.atomic이 빠지면 select_for_update가
TransactionManagementError를 낸다(운영에서는 500). 테스트 클라이언트가 이 예외를 그대로 올리므로 테스트가 실패한다.
sync_all_results는 관리 명령이 트랜잭션 없이 바로 부르므로 API와 별도로 직접 불러서도 확인한다.
SQL 단언은 잠금 쿼리가 실제로 나가는지, 그리고 시세는 읽기·쓰기보다, 물품은 쓰기보다 먼저 나가는지를 본다.
SQLite는 FOR UPDATE를 만들지 않으므로 SQL 단언은 Postgres(TEST_DATABASE_URL)에서만 돈다.
lock_catalog()가 트랜잭션 밖 호출을 막는지는 SQLite에서도 본다 (SQLite에서는 Django가 막아 주지 않는다).
"""

import pytest
from django.db import connection, transaction
from django.db.transaction import TransactionManagementError
from django.test.utils import CaptureQueriesContext

from apps.markets.models import Market
from apps.results.sync import lock_catalog, sync_all_results

pytestmark = pytest.mark.django_db(transaction=True)
postgres_only = pytest.mark.skipif(connection.vendor != "postgresql", reason="Postgres 전용")


def capture(send):
    """요청을 보내고 응답과 실행된 SQL 목록을 돌려준다."""
    with CaptureQueriesContext(connection) as ctx:
        response = send()
    return response, [query["sql"] for query in ctx.captured_queries]


def positions(sqls, *fragments):
    """fragments를 모두 포함하는 쿼리의 위치(실행 순서) 목록."""
    return [index for index, sql in enumerate(sqls) if all(fragment in sql for fragment in fragments)]


@postgres_only
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


@postgres_only
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


@postgres_only
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


@postgres_only
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


def new_product(name):
    return {
        "name": name,
        "level": 1,
        "craftingPrice": 1,
        "tool": "WOOD",
        "materials": [{"name": "나무", "basic": True, "count": 1}],
    }


def create_product(client, targets):
    return client.post("/product", new_product("새물품"), format="json")


def bulk_create_products(client, targets):
    return client.post("/product/all", {"products": [new_product("일괄1"), new_product("일괄2")]}, format="json")


def update_product(client, targets):
    body = {"id": targets["판자"].id, "craftingPrice": 70, "materials": [{"name": "나무", "basic": True, "count": 4}]}
    return client.put("/product", body, format="json")


def delete_product(client, targets):
    return client.delete("/product", [targets["식탁"].id], format="json")  # 다른 레시피가 쓰지 않는 물품


def delete_market(client, targets):
    return client.delete("/market", {"ids": [targets["금"].id]}, format="json")  # 쓰는 물품이 없는 시세


@postgres_only
@pytest.mark.parametrize(
    ("send", "status"),
    [
        (create_product, 201),
        (bulk_create_products, 201),
        (update_product, 200),
        (delete_product, 200),
        (delete_market, 200),
    ],
    ids=["create", "bulk", "update", "delete", "delete-market"],
)
def test_catalog_writes_take_market_lock_first(client, catalog, send, status):
    assert client.post("/result").status_code == 201
    targets = {**catalog, "금": Market.objects.create(name="금", price=1000)}

    response, sqls = capture(lambda: send(client, targets))

    assert response.status_code == status
    locks = positions(sqls, 'FROM "market"', "FOR UPDATE")
    # SELECT ... FOR UPDATE에도 UPDATE가 들어 있으므로 쓰기는 문장 맨 앞으로 찾는다.
    writes = [index for index, sql in enumerate(sqls) if sql.lstrip().startswith(("INSERT", "UPDATE", "DELETE"))]
    material_reads = positions(sqls, 'FROM "material"')
    assert locks
    assert writes
    assert material_reads
    # 다른 카탈로그 쓰기와 순서대로 돌도록 전역 잠금을 가장 먼저 잡고, 잠근 뒤에 레시피를 읽는다.
    assert locks[0] < min(writes)
    assert locks[0] < material_reads[0]


@postgres_only
def test_product_delete_locks_rows_in_id_order(client, catalog):
    ids = [catalog["의자"].id, catalog["식탁"].id]  # 다른 레시피가 쓰지 않는 물품, 요청은 id 역순

    response, sqls = capture(lambda: client.delete("/product", ids, format="json"))

    assert response.status_code == 200
    locks = [sqls[index] for index in positions(sqls, 'FROM "product"', "FOR UPDATE")]
    assert locks
    # 여러 물품을 잠그는 쿼리끼리 같은 순서로 잠가야 교착이 생기지 않는다.
    assert all('ORDER BY "product"."id"' in sql for sql in locks)


def test_lock_catalog_requires_transaction(catalog):
    # transaction=True라 테스트가 atomic으로 감싸이지 않는다. 트랜잭션 밖에서 잡은 잠금은 바로 풀리므로 막는다.
    with pytest.raises(TransactionManagementError):
        lock_catalog()

    with transaction.atomic():
        lock_catalog()
