import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.inventories.models import InventoryItem
from apps.markets.models import Market

pytestmark = pytest.mark.django_db


def member_client(username="회원1"):
    user = User.objects.create_user(username=username, password="correct-horse-42", nickname="늘흰")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def markets(db):
    return {
        market.name: market
        for market in Market.objects.bulk_create(
            [Market(name="나무", price=10), Market(name="못", price=5), Market(name="천", price=7)]
        )
    }


@pytest.mark.parametrize(("method", "body"), [("get", None), ("put", [])])
def test_inventory_requires_login(method, body):
    response = getattr(APIClient(), method)("/inventory", body, format="json")

    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Bearer"


def test_new_member_has_empty_inventory():
    assert member_client().get("/inventory").json() == []


def test_save_returns_whole_inventory_in_market_order(markets):
    client = member_client()
    client.put("/inventory", [{"marketId": markets["천"].id, "count": 4}], format="json")

    response = client.put("/inventory", [{"marketId": markets["나무"].id, "count": 120}], format="json")

    expected = [
        {"marketId": markets["나무"].id, "name": "나무", "count": 120},
        {"marketId": markets["천"].id, "name": "천", "count": 4},
    ]
    assert response.status_code == 200
    assert response.json() == expected
    assert client.get("/inventory").json() == expected


def test_save_updates_count_and_zero_removes_item(markets):
    client = member_client()
    wood, nail = markets["나무"].id, markets["못"].id
    client.put("/inventory", [{"marketId": wood, "count": 3}, {"marketId": nail, "count": 2}], format="json")

    response = client.put("/inventory", [{"marketId": wood, "count": 0}, {"marketId": nail, "count": 9}], format="json")

    assert response.json() == [{"marketId": nail, "name": "못", "count": 9}]
    assert InventoryItem.objects.count() == 1


def test_members_have_separate_inventories(markets):
    first, second = member_client("회원1"), member_client("회원2")
    first.put("/inventory", [{"marketId": markets["나무"].id, "count": 3}], format="json")

    second.put("/inventory", [{"marketId": markets["나무"].id, "count": 50}], format="json")

    assert first.get("/inventory").json()[0]["count"] == 3
    assert second.get("/inventory").json()[0]["count"] == 50


def test_save_rejects_unknown_market_without_saving_others(markets):
    body = [{"marketId": markets["나무"].id, "count": 1}, {"marketId": 999, "count": 1}]

    response = member_client().put("/inventory", body, format="json")

    assert response.status_code == 400
    assert response.json()["message"] == "존재하지 않는 시세입니다. (id: 999)"
    assert not InventoryItem.objects.exists()


def test_save_rejects_duplicated_market(markets):
    wood = markets["나무"].id
    body = [{"marketId": wood, "count": 1}, {"marketId": wood, "count": 2}]

    response = member_client().put("/inventory", body, format="json")

    assert response.status_code == 400
    assert response.json()["message"] == f"중복된 시세가 있습니다. (id: {wood})"
    assert not InventoryItem.objects.exists()


@pytest.mark.parametrize("count", [-1, 1.5, None, "많이", 2**31])
def test_save_rejects_invalid_count(markets, count):
    response = member_client().put("/inventory", [{"marketId": markets["나무"].id, "count": count}], format="json")

    assert response.status_code == 400
    assert response.json()["message"].startswith("0.count:")


def test_save_rejects_non_list_body():
    response = member_client().put("/inventory", {"marketId": 1, "count": 1}, format="json")

    assert response.status_code == 400


def test_market_rename_and_delete_follow_inventory(client, markets):
    member = member_client()
    cloth = markets["천"].id
    member.put("/inventory", [{"marketId": cloth, "count": 4}], format="json")

    assert client.put("/market", [{"id": cloth, "name": "비단"}], format="json").status_code == 200
    assert member.get("/inventory").json() == [{"marketId": cloth, "name": "비단", "count": 4}]

    assert client.delete("/market", {"ids": [cloth]}, format="json").status_code == 200
    assert member.get("/inventory").json() == []


def test_withdraw_removes_inventory(markets):
    User.objects.create_user(username="회원1", password="correct-horse-42", nickname="늘흰")
    login = APIClient().post("/auth/login", {"username": "회원1", "password": "correct-horse-42"}, format="json")
    member = APIClient()
    member.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['token']}")
    member.put("/inventory", [{"marketId": markets["나무"].id, "count": 1}], format="json")

    assert member.delete("/auth/me", {"password": "correct-horse-42"}, format="json").status_code == 204

    assert not InventoryItem.objects.exists()
