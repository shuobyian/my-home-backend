import pytest

from apps.markets.models import Market
from apps.results.models import Result
from tests.conftest import make_product

pytestmark = pytest.mark.django_db


def test_create_missing_results(client, catalog):
    response = client.post("/result")

    assert response.status_code == 201
    assert len(response.json()) == 3
    table = Result.objects.get(product=catalog["식탁"])
    # 식탁 = 판자 2(나무 3씩) + 못 4  → 못이 얕은 단계라 먼저 나온다
    assert (table.names, table.counts, table.prices, table.total_price) == ("못,나무", "4,6", "20,60", 80)

    again = client.post("/result")
    assert again.status_code == 400
    assert again.json()["message"] == "추가할 결과가 없습니다."


def test_create_results_with_invalid_sub_material(client, catalog):
    make_product("불량품", [("없는물품", False, 1)])

    response = client.post("/result")

    assert response.status_code == 400
    assert "하위 재료에 잘못된 물품명이 있습니다." in response.json()["message"]
    assert not Result.objects.exists()  # 한 건이라도 실패하면 전부 취소


def test_list_results(client, catalog):
    client.post("/result")

    body = client.get("/result", {"page": 0, "size": 10, "count": 2}).json()

    assert body["totalElements"] == 3
    assert [result["name"] for result in body["content"]] == ["판자", "의자", "식탁"]  # level, name 순
    table = body["content"][2]
    assert table["materials"] == [{"name": "못", "price": 40, "count": 8}, {"name": "나무", "price": 120, "count": 12}]
    assert table["totalPrice"] == 160
    assert table["craftingPrice"] == 415  # floor(200 * 2 * 1.039)
    assert table["product"]["materials"] == [
        {"name": "판자", "basic": False, "count": 4},
        {"name": "못", "basic": True, "count": 8},
    ]
    assert table["product"]["craftingPrice"] == 200
    assert table["createdAt"].endswith("Z")


def test_list_results_filters(client, catalog):
    client.post("/result")

    assert [r["name"] for r in client.get("/result", {"tool": "FIRE_PIT"}).json()["content"]] == ["식탁"]
    assert [r["name"] for r in client.get("/result", {"category": "EVENT"}).json()["content"]] == ["의자"]
    assert [r["name"] for r in client.get("/result", {"name": "판"}).json()["content"]] == ["판자"]
    assert client.get("/result", {"tool": "HAMMER"}).status_code == 400
    assert client.get("/result", {"count": 0}).status_code == 400


def test_calculator_preview_does_not_save(client, catalog):
    client.post("/result")
    markets = [{"name": "나무", "price": 1}, {"name": "못", "price": 1}, {"name": "천", "price": 1}]

    response = client.post("/result/calculator", {"markets": markets}, format="json")

    assert response.status_code == 201
    results = {result["name"]: result for result in response.json()["results"]}
    assert results["식탁"]["totalPrice"] == 10
    assert results["식탁"]["id"] == Result.objects.get(product=catalog["식탁"]).id
    assert Result.objects.get(product=catalog["식탁"]).total_price == 80


def test_calculator_requires_results_for_all_products(client, catalog):
    response = client.post("/result/calculator", {"markets": []}, format="json")

    assert response.status_code == 400
    assert response.json()["message"] == "결과 정보가 없는 물품 (판자) 입니다."


def test_calculator_reports_missing_price(client, catalog):
    client.post("/result")

    response = client.post("/result/calculator", {"markets": [{"name": "나무", "price": 1}]}, format="json")

    assert response.status_code == 400
    assert "시세 정보가 없는 재료" in response.json()["message"]


def test_update_markets_recalculates_results(client, catalog):
    client.post("/result")
    wood = Market.objects.get(name="나무")

    response = client.put("/market", [{"id": wood.id, "name": "나무", "price": 20}], format="json")

    assert response.status_code == 200
    assert response.json() == [{"id": wood.id, "name": "나무", "price": 20}]
    table = Result.objects.get(product=catalog["식탁"])
    assert (table.names, table.counts, table.prices, table.total_price) == ("못,나무", "4,6", "20,120", 140)


def test_update_markets_rolls_back_when_recalculation_fails(client, catalog):
    client.post("/result")
    # 결과가 저장된 뒤 레시피가 잘못 바뀐 물품
    catalog["의자"].materials.filter(name="판자").update(name="없는물품")
    wood = Market.objects.get(name="나무")

    response = client.put("/market", [{"id": wood.id, "price": 999}], format="json")

    assert response.status_code == 400
    wood.refresh_from_db()
    assert wood.price == 10


def test_market_list_and_create(client, catalog):
    response = client.put("/market", [{"name": "금", "price": 1000}], format="json")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "금"
    assert [market["name"] for market in client.get("/market").json()] == ["나무", "못", "천", "금"]


def test_fractional_total_is_rounded_half_up_and_response_uses_material_sum(client, catalog):
    make_product("반쪽", [("나무", True, 0.25)])  # 나무 10원 x 0.25 = 2.5원

    client.post("/result")

    half = Result.objects.get(product__name="반쪽")
    assert (half.prices, half.total_price) == ("2.5", 3)  # 은행가 반올림이면 2
    body = client.get("/result", {"name": "반쪽", "count": 3}).json()["content"][0]
    assert body["totalPrice"] == 7.5
    assert body["materials"] == [{"name": "나무", "price": 7.5, "count": 0.75}]


def test_calculator_treats_empty_price_as_zero(client, catalog):
    """프론트엔드 입력칸을 비우면 price가 null로 오는데, 기존 서버는 0원으로 계산했다."""
    client.post("/result")
    markets = [{"name": "나무", "price": None}, {"name": "못", "price": 5}, {"name": "천", "price": 7}]

    response = client.post("/result/calculator", {"markets": markets}, format="json")

    assert response.status_code == 201
    results = {result["name"]: result for result in response.json()["results"]}
    assert results["식탁"]["totalPrice"] == 20


@pytest.mark.parametrize(
    "markets",
    [
        [{"name": "나무", "price": "Infinity"}],
        [{"name": "나무", "price": -1}],
        [{"name": "나무", "price": 1}, {"name": "나무", "price": 2}],
    ],
)
def test_calculator_rejects_invalid_prices(client, catalog, markets):
    client.post("/result")

    assert client.post("/result/calculator", {"markets": markets}, format="json").status_code == 400


def test_recalculate_command(catalog):
    from django.core.management import call_command

    make_product("새물품", [("천", True, 1)])
    call_command("recalculate_results")
    assert not Result.objects.exists()

    call_command("recalculate_results", "--create-missing")
    assert Result.objects.count() == 4

    Market.objects.filter(name="천").update(price=100)
    call_command("recalculate_results")
    assert Result.objects.get(product__name="새물품").total_price == 100


def test_recalculate_command_fails_without_saving(catalog):
    from django.core.management import call_command
    from django.core.management.base import CommandError

    call_command("recalculate_results", "--create-missing")
    Market.objects.filter(name="천").delete()

    with pytest.raises(CommandError, match="시세 정보가 없는 재료"):
        call_command("recalculate_results")
