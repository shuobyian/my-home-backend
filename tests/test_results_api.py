from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.markets.models import Market
from apps.results.calculator import CraftingCalculator, Ingredient
from apps.results.models import Result
from tests.factories import make_product

pytestmark = pytest.mark.django_db


def test_create_missing_results(client, catalog):
    response = client.post("/result")

    assert response.status_code == 201
    assert len(response.json()) == 3
    table = Result.objects.get(product=catalog["식탁"])
    # 식탁 = 판자 2(나무 3씩) + 못 4  → 못이 얕은 단계라 먼저 나온다
    assert (table.names, table.counts, table.prices, table.total_price) == ("못,나무", "4,6", "20,60", 80)

    # POST /result는 이제 전체 동기화라 할 일이 없어도 성공한다 (새로 만든 결과가 없으면 빈 목록).
    again = client.post("/result")
    assert again.status_code == 201
    assert again.json() == []


def test_create_results_with_invalid_sub_material(client, catalog):
    make_product("불량품", [("없는물품", False, 1)])

    response = client.post("/result")

    # 의도적 변경: 예전에는 한 건이라도 실패하면 전부 취소(400)했다. 이제 계산할 수 있는 결과는 모두 만들고
    # 계산할 수 없는 물품만 건너뛴다. 고장 난 물품 하나가 다른 물품의 결과까지 막지 않게 하기 위해서다.
    assert response.status_code == 201
    expected = [catalog[name].id for name in ["판자", "식탁", "의자"]]
    assert [result["product_id"] for result in response.json()] == expected
    assert not Result.objects.filter(product__name="불량품").exists()


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


def test_update_markets_ignores_preexisting_problems(client, catalog):
    client.post("/result")
    # 결과가 저장된 뒤 레시피가 잘못 바뀐 물품 (DB 직접 수정)
    catalog["의자"].materials.filter(name="판자").update(name="없는물품")
    chair_before = Result.objects.values("id", "names", "counts", "prices", "total_price").get(product=catalog["의자"])
    wood = Market.objects.get(name="나무")

    response = client.put("/market", [{"id": wood.id, "price": 999}], format="json")

    # 의도적 변경: 예전에는 이미 고장 난 레시피 하나 때문에 시세 수정 전체가 400으로 막혔다.
    # 이제 이번 쓰기가 새로 만든 문제만 거절하고, 고장 난 물품의 결과는 마지막 값으로 둔다.
    assert response.status_code == 200
    wood.refresh_from_db()
    assert wood.price == 999
    assert Result.objects.get(product=catalog["판자"]).total_price == 2997
    chair_after = Result.objects.values("id", "names", "counts", "prices", "total_price").get(product=catalog["의자"])
    assert chair_after == chair_before


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
    make_product("새물품", [("천", True, 1)])
    call_command("recalculate_results")
    assert not Result.objects.exists()

    call_command("recalculate_results", "--create-missing")
    assert Result.objects.count() == 4

    Market.objects.filter(name="천").update(price=100)
    call_command("recalculate_results")
    assert Result.objects.get(product__name="새물품").total_price == 100


def test_recalculate_command_fails_without_saving(catalog):
    call_command("recalculate_results", "--create-missing")
    Market.objects.filter(name="천").delete()

    with pytest.raises(CommandError, match="시세 정보가 없는 재료"):
        call_command("recalculate_results")


def test_calculator_preview_has_no_storage_limit(client, catalog):
    client.post("/result")
    markets = [{"name": "나무", "price": 10**12}, {"name": "못", "price": 5}, {"name": "천", "price": 7}]

    response = client.post("/result/calculator", {"markets": markets}, format="json")

    assert response.status_code == 201
    results = {result["name"]: result for result in response.json()["results"]}
    assert results["식탁"]["totalPrice"] == 6 * 10**12 + 20


def test_result_total_over_integer_column_is_not_saved(client, catalog):
    Market.objects.filter(name="나무").update(price=2**31 - 1)

    response = client.post("/result")

    # 의도적 변경: POST /result는 저장할 수 없는 물품을 건너뛰고 201이다 (나머지 물품의 결과는 만든다).
    # 쓰기가 합계 초과를 새로 만들면 400인 경로는 test_catalog_sync의 시세 초과 테스트가 맡는다.
    assert response.status_code == 201
    assert response.json() == []
    assert not Result.objects.exists()
    # 저장하지 못한 이유는 엄격 모드(관리 명령)가 모두 알린다.
    with pytest.raises(CommandError) as error:
        call_command("recalculate_results", "--create-missing", stdout=StringIO())
    assert str(error.value).endswith("합계 금액이 너무 커서 저장할 수 없습니다. (판자, 식탁, 의자)")


def test_list_and_calculator_order_same_level_by_name(client, catalog):
    # id 순서(나 → 가)와 이름 순서(가 → 나)가 반대가 되게 만든다
    make_product("나", [("나무", True, 1)], level=1)
    make_product("가", [("나무", True, 1)], level=1)
    client.post("/result")
    markets = [{"name": "나무", "price": 1}, {"name": "못", "price": 1}, {"name": "천", "price": 1}]

    listed = [result["name"] for result in client.get("/result").json()["content"]]
    previewed = client.post("/result/calculator", {"markets": markets}, format="json").json()["results"]

    assert listed == ["가", "나", "판자", "의자", "식탁"]
    assert [result["name"] for result in previewed] == ["가", "나", "판자", "의자", "식탁"]


def test_calculator_missing_price_message_names_first_failing_product(client, catalog):
    """정렬 순서(레벨·이름)와 첫 실패 물품에 묶인 문구다. 깨지면 정렬이나 순회가 바뀐 것이다."""
    client.post("/result")

    response = client.post("/result/calculator", {"markets": [{"name": "나무", "price": 1}]}, format="json")

    assert response.status_code == 400
    assert response.json()["message"] == "시세 정보가 없는 재료가 있습니다. (의자: 천)"


def test_create_results_invalid_sub_material_message(client, catalog):
    make_product("불량품", [("없는물품", False, 1)])

    # 의도적 변경: POST /result는 불량품을 건너뛰고 201이라 이 문구를 응답으로 주지 않는다.
    # 같은 문구를 엄격 모드 동기화(관리 명령)가 그대로 알리는지 본다.
    assert client.post("/result").status_code == 201
    with pytest.raises(CommandError) as error:
        call_command("recalculate_results", "--create-missing", stdout=StringIO())

    assert str(error.value).endswith(" 하위 재료에 잘못된 물품명이 있습니다. (불량품: 없는물품)")


def test_result_matches_compares_stored_columns():
    sheet = CraftingCalculator({"R": [Ingredient("나무", True, 0.25)]}, {"나무": 10}).calculate("R")
    result = Result(names="나무", counts="0.25", prices="2.5", total_price=3)

    assert Result.cost_fields_of(sheet) == ("나무", "0.25", "2.5", 3)
    assert result.matches(sheet)
    result.total_price = 2
    assert not result.matches(sheet)


def test_create_missing_results_only_adds_missing(client, catalog):
    client.post("/result")
    existing = set(Result.objects.values_list("product_id", "id"))
    extra = make_product("추가", [("나무", True, 1)])

    response = client.post("/result")

    assert response.status_code == 201
    assert [result["product_id"] for result in response.json()] == [extra.id]
    assert existing <= set(Result.objects.values_list("product_id", "id"))


def test_recalculate_command_rolls_back_when_create_missing_fails(catalog):
    call_command("recalculate_results", "--create-missing", stdout=StringIO())
    Market.objects.filter(name="나무").update(price=1000)
    make_product("불량품", [("없는물품", False, 1)])

    with pytest.raises(CommandError) as error:
        call_command("recalculate_results", "--create-missing", stdout=StringIO())

    assert str(error.value) == (
        "재계산하지 못해 아무것도 저장하지 않았습니다. 하위 재료에 잘못된 물품명이 있습니다. (불량품: 없는물품)"
    )
    # 먼저 실행된 재계산(나무 1000원)까지 함께 취소됐다
    assert dict(Result.objects.values_list("product__name", "total_price")) == {"판자": 30, "식탁": 80, "의자": 44}


def test_recalculate_command_create_missing_with_nothing_missing(catalog):
    call_command("recalculate_results", "--create-missing", stdout=StringIO())
    out = StringIO()

    call_command("recalculate_results", "--create-missing", stdout=out, no_color=True)

    assert out.getvalue() == "결과 3건을 재계산하고 0건을 새로 만들었습니다.\n"


def test_paginate_pages(client, catalog):
    client.post("/result")

    second = client.get("/result", {"page": 1, "size": 2}).json()
    assert [result["name"] for result in second["content"]] == ["식탁"]
    assert second["totalElements"] == 3

    assert client.get("/result", {"page": 5, "size": 2}).json() == {"totalElements": 3, "content": []}


def test_query_choice_messages(client, catalog):
    client.post("/result")
    tool_message = (
        "tool 값이 올바르지 않습니다. "
        "(WOOD, FIRE_PIT, SEWING_MACHINE, LEATHER, BRAZIER, POTTERY_WHEEL, ALCHEMY_KETTLE, MIMI)"
    )

    assert client.get("/result", {"tool": "HAMMER"}).json() == {
        "statusCode": 400,
        "message": tool_message,
        "error": "Bad Request",
    }
    assert client.get("/result", {"category": "X"}).json()["message"] == (
        "category 값이 올바르지 않습니다. (NORMAL, EVENT)"
    )
    # tool을 category보다 먼저 검사한다
    assert client.get("/result", {"tool": "HAMMER", "category": "XXX"}).json()["message"] == tool_message

    empty = client.get("/result", {"tool": ""})
    assert empty.status_code == 200
    assert len(empty.json()["content"]) == 3  # 빈 값은 필터 없음


def test_result_name_search_is_literal(client, catalog):
    # catalog에는 %나 _가 들어간 이름이 없다는 전제다
    client.post("/result")

    assert client.get("/result", {"name": "%"}).json()["content"] == []
