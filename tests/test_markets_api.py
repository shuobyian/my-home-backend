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
        ([{"name": "금", "price": 1, "group": "X"}], '0.group: "X"은 유효하지 않은 선택입니다.'),
    ],
)
def test_market_validation_messages(client, catalog, items, message):
    response = put_markets(client, items)

    assert response.status_code == 400
    assert response.json()["message"] == message


def test_new_market_group_defaults_to_etc(client, catalog):
    response = put_markets(client, [{"name": "금", "price": 1}, {"name": "밀", "price": 2, "group": "CROP"}])

    assert response.status_code == 200
    assert [market["group"] for market in response.json()] == ["ETC", "CROP"]
    saved = dict(Market.objects.filter(name__in=["금", "밀"]).values_list("name", "group"))
    assert saved == {"금": "ETC", "밀": "CROP"}


def test_update_market_group_only_keeps_name_and_price(client, catalog):
    wood = Market.objects.get(name="나무")

    response = put_markets(client, [{"id": wood.id, "group": "TIMBER"}])

    assert response.status_code == 200
    assert response.json() == [{"id": wood.id, "name": "나무", "price": 10, "group": "TIMBER"}]
    wood.refresh_from_db()
    assert (wood.name, wood.price, wood.group) == ("나무", 10, "TIMBER")


def test_unknown_market_id_is_rejected(client, catalog):
    # 의도적 변경: 예전에는 모르는 id를 새 행으로 만들었다. 다른 관리자가 지운 시세를 고치면 같은 시세가
    # 새 id로 되살아나므로, 이제 400으로 거절하고 아무것도 저장하지 않는다.
    response = put_markets(client, [{"id": 999, "name": "금", "price": 1}])

    assert response.status_code == 400
    assert response.json()["message"] == "존재하지 않는 시세입니다. (id: 999)"
    assert not Market.objects.filter(name="금").exists()


def test_unknown_market_ids_are_listed_in_request_order_before_other_checks(client, catalog):
    wood = Market.objects.get(name="나무")
    items = [{"price": 1}, {"id": 999, "price": 1}, {"id": wood.id, "price": 2}, {"id": 998}, {"id": 999}]

    response = put_markets(client, items)

    # 새 시세의 name 누락({"price": 1})보다 모르는 id를 먼저 알린다. 같은 id는 한 번만 적는다.
    assert response.status_code == 400
    assert response.json()["message"] == "존재하지 않는 시세입니다. (id: 999, 998)"
    wood.refresh_from_db()
    assert wood.price == 10


def test_delete_markets_accepts_bare_id_list(client, catalog):
    gold = Market.objects.create(name="금", price=1000)

    response = client.delete("/market", [gold.id], format="json")

    assert response.status_code == 200
    assert response.json() == {"deletedIds": [gold.id]}
    assert not Market.objects.filter(pk=gold.id).exists()


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({}, "ids: 이 필드는 필수 항목입니다."),
        ({"ids": ["x"]}, "ids.0: 유효한 정수를 입력하세요."),
    ],
)
def test_delete_markets_validation_messages(client, catalog, body, message):
    response = client.delete("/market", body, format="json")

    assert response.status_code == 400
    assert response.json()["message"] == message


def test_update_markets_response_keeps_request_order(client, catalog):
    wood = Market.objects.get(name="나무")

    response = put_markets(client, [{"name": "은", "price": 2}, {"id": wood.id, "price": 3}])

    assert response.status_code == 200
    assert [market["name"] for market in response.json()] == ["은", "나무"]
    wood.refresh_from_db()
    assert (wood.name, wood.price) == ("나무", 3)


def test_update_markets_creates_missing_computable_results(client, catalog):
    client.post("/result")
    # '은'은 시세가 없는 재료다.
    extra = make_product("은세공", [("은", True, 1)])
    stand = make_product("받침", [("나무", True, 1)])
    wood = Market.objects.get(name="나무")

    response = put_markets(client, [{"id": wood.id, "price": 20}])

    # 의도적 변경: 시세를 저장하면 결과가 없던 물품 중 계산할 수 있는 것의 결과도 만든다 (결과 리스트에서 빠지지 않게).
    # 200이어야 은세공이 '실패해서 안 생겼다'가 아니라 '건너뛰어서 안 생겼다'가 된다.
    assert response.status_code == 200
    assert Result.objects.get(product=stand).total_price == 20
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


def test_update_markets_with_preexisting_problem_keeps_new_market(client, catalog):
    client.post("/result")
    # 의자가 쓰는 천 시세를 DB에서 지웠다 (이미 있던 문제).
    Market.objects.filter(name="천").delete()

    response = put_markets(client, [{"name": "금", "price": 1}])

    # 의도적 변경: 예전에는 이미 있던 문제 때문에 400이고 금도 저장되지 않았다.
    # 이제 이번 쓰기가 새로 만든 문제만 거절한다. 새로 생긴 문제로 롤백되는 경로는 test_catalog_sync에서 본다.
    assert response.status_code == 200
    assert Market.objects.filter(name="금").exists()


def test_empty_market_update_still_recalculates(client, catalog):
    client.post("/result")
    Market.objects.filter(name="천").delete()
    Market.objects.filter(name="나무").update(price=20)
    chair = Result.objects.values("names", "counts", "prices", "total_price").get(product=catalog["의자"])

    # 현재 동작 고정. 빈 목록도 결과 동기화를 실행한다.
    # 의도적 변경: 이미 있던 문제(천 시세 없음)로는 거절하지 않으므로 200이다 (예전에는 400).
    response = put_markets(client, [])

    assert response.status_code == 200
    assert response.json() == []
    assert Result.objects.get(product=catalog["판자"]).total_price == 60
    assert Result.objects.values("names", "counts", "prices", "total_price").get(product=catalog["의자"]) == chair


def test_lock_all_locks_every_market_in_id_order():
    query = Market.objects.lock_all().query

    assert query.select_for_update is True
    assert query.order_by == ("id",)
