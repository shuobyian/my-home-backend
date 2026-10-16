from datetime import timedelta

import pytest
from django.utils import timezone

from apps.markets.models import Market
from apps.results.models import Result
from tests.factories import make_product

pytestmark = pytest.mark.django_db


def put_markets(client, items):
    return client.put("/market", items, format="json")


def test_new_market_requires_name_and_price(client, catalog):
    response = put_markets(client, [{"price": 1}])

    assert response.status_code == 400
    assert response.json()["message"] == "새 시세에는 name과 price가 필요합니다."
    assert Market.objects.count() == 3


def test_duplicate_market_name_on_create_is_rejected(client, catalog):
    response = put_markets(client, [{"name": "못", "price": 1}])

    assert response.status_code == 400
    assert response.json()["message"] == "이미 존재하는 시세 이름입니다."


def test_rename_market_to_existing_name_is_rejected(client, catalog):
    wood = Market.objects.get(name="나무")

    response = put_markets(client, [{"id": wood.id, "name": "못"}])

    assert response.status_code == 400
    assert response.json()["message"] == "이미 존재하는 시세 이름입니다."
    wood.refresh_from_db()
    assert wood.name == "나무"


@pytest.mark.parametrize(
    ("items", "message"),
    [
        ([{"price": None}], "0.price: 이 필드는 null일 수 없습니다."),
        ([{"price": 1.5}], "0.price: 유효한 정수를 입력하세요."),
        ([{}, {"price": "x"}], "1.price: 유효한 정수를 입력하세요."),
        ([{"name": "a,b", "price": 1}], "0.name: 이름에 콤마(,)를 넣을 수 없습니다."),
    ],
)
def test_market_validation_messages(client, catalog, items, message):
    response = put_markets(client, items)

    assert response.status_code == 400
    assert response.json()["message"] == message


def test_unknown_market_id_creates_new_row(client, catalog):
    # 현재 동작 고정. 의도적으로 바꾸면 이 테스트도 함께 수정한다.
    response = put_markets(client, [{"id": 999, "name": "금", "price": 1}])

    assert response.status_code == 200
    created_id = response.json()[0]["id"]
    assert created_id == Market.objects.get(name="금").id
    assert created_id != 999


def test_update_markets_response_keeps_request_order(client, catalog):
    wood = Market.objects.get(name="나무")

    response = put_markets(client, [{"name": "은", "price": 2}, {"id": wood.id, "price": 3}])

    assert response.status_code == 200
    assert [market["name"] for market in response.json()] == ["은", "나무"]
    wood.refresh_from_db()
    assert (wood.name, wood.price) == ("나무", 3)


def test_update_markets_does_not_create_missing_results(client, catalog):
    client.post("/result")
    # '은'은 시세가 없는 재료다.
    extra = make_product("은세공", [("은", True, 1)])
    wood = Market.objects.get(name="나무")

    response = put_markets(client, [{"id": wood.id, "price": 20}])

    # 200이어야 '실패해서 안 생겼다'가 아니라 '건너뛰어서 안 생겼다'가 된다.
    assert response.status_code == 200
    assert not Result.objects.filter(product=extra).exists()


def test_update_markets_touches_updated_at_keeps_created_at(client, catalog):
    client.post("/result")
    past = timezone.now() - timedelta(days=1)
    Result.objects.update(updated_at=past)
    before = dict(Result.objects.values_list("id", "created_at"))
    wood = Market.objects.get(name="나무")

    response = put_markets(client, [{"id": wood.id, "price": 20}])

    assert response.status_code == 200
    rows = list(Result.objects.values_list("id", "created_at", "updated_at"))
    assert len(rows) == len(before) == 3
    for result_id, created_at, updated_at in rows:
        assert updated_at > past
        assert created_at == before[result_id]


def test_update_markets_rollback_discards_new_market(client, catalog):
    client.post("/result")
    # 천을 쓰는 결과는 의자 하나뿐이라 순회 순서와 상관없이 메시지가 정해진다.
    Market.objects.filter(name="천").delete()

    response = put_markets(client, [{"name": "금", "price": 1}])

    assert response.status_code == 400
    assert response.json()["message"] == "시세 정보가 없는 재료가 있습니다. (의자: 천)"
    assert not Market.objects.filter(name="금").exists()


def test_empty_market_update_still_recalculates(client, catalog):
    client.post("/result")
    Market.objects.filter(name="천").delete()

    # 현재 동작 고정. 빈 목록도 재계산을 실행한다.
    response = put_markets(client, [])

    assert response.status_code == 400
    assert response.json()["message"] == "시세 정보가 없는 재료가 있습니다. (의자: 천)"


def test_lock_all_locks_every_market_in_id_order():
    query = Market.objects.lock_all().query

    assert query.select_for_update is True
    assert query.order_by == ("id",)
