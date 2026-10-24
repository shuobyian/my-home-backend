"""시세·물품·결과 연결 테스트: 카탈로그 쓰기 뒤 결과 자동 동기화와, 새 차단 문제만 거절하는 규칙."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.markets.models import Market
from apps.products.models import Material, Product
from apps.results.models import Result
from tests.factories import make_product

pytestmark = pytest.mark.django_db

RESULT_FIELDS = ("id", "created_at", "updated_at", "names", "counts", "prices", "total_price")


def product_payload(name="새물품", materials=None, **overrides):
    payload = {
        "name": name,
        "level": 10,
        "craftingPrice": 300,
        "tool": "BRAZIER",
        "category": "NORMAL",
        "materials": materials if materials is not None else [{"name": "나무", "basic": True, "count": 2}],
    }
    return {**payload, **overrides}


def basic(name, count):
    return {"name": name, "basic": True, "count": count}


def sub(name, count):
    return {"name": name, "basic": False, "count": count}


def results_by_name():
    return {row["product__name"]: row for row in Result.objects.values("product__name", *RESULT_FIELDS)}


def totals():
    return dict(Result.objects.values_list("product__name", "total_price"))


def test_create_product_creates_result(client, catalog):
    response = client.post("/product", product_payload(), format="json")

    assert response.status_code == 201
    result = Result.objects.get(product__name="새물품")
    assert (result.names, result.counts, result.prices, result.total_price) == ("나무", "2", "20", 20)
    assert "새물품" in [item["name"] for item in client.get("/result").json()["content"]]
    # 쓰기 끝의 동기화는 전체를 맞추므로 결과가 없던 기존 물품의 결과도 함께 생긴다.
    assert totals() == {"판자": 30, "식탁": 80, "의자": 44, "새물품": 20}


def test_bulk_create_creates_results_for_new_products(client, catalog):
    products = [
        product_payload("판자"),  # 이미 있는 물품은 건너뛴다
        product_payload("상위", [sub("하위", 2), basic("못", 1)]),
        product_payload("하위", [basic("나무", 2)]),
    ]

    response = client.post("/product/all", {"products": products}, format="json")

    assert response.status_code == 201
    assert [product["name"] for product in response.json()] == ["상위", "하위"]
    assert totals() == {"판자": 30, "식탁": 80, "의자": 44, "상위": 45, "하위": 20}


def test_update_product_recalculates_self_and_ancestors_in_place(client, catalog):
    assert client.post("/result").status_code == 201
    before = results_by_name()

    response = client.put("/product", {"id": catalog["판자"].id, "materials": [basic("나무", 10)]}, format="json")

    assert response.status_code == 200
    after = results_by_name()
    assert {name: row["total_price"] for name, row in after.items()} == {"판자": 100, "식탁": 220, "의자": 114}
    for name in ["판자", "식탁", "의자"]:
        assert after[name]["id"] == before[name]["id"]
        assert after[name]["created_at"] == before[name]["created_at"]
    # 카드에 보이는 레시피(product.materials)와 계산 결과(materials)가 서로 맞는다.
    listed = {item["name"]: item for item in client.get("/result").json()["content"]}
    assert listed["판자"]["product"]["materials"] == [{"name": "나무", "basic": True, "count": 10}]
    assert listed["판자"]["materials"] == [{"name": "나무", "price": 100, "count": 10}]
    assert listed["식탁"]["materials"] == [
        {"name": "못", "price": 20, "count": 4},
        {"name": "나무", "price": 200, "count": 20},
    ]


def test_update_only_touches_changed_rows(client, catalog):
    assert client.post("/result").status_code == 201
    past = timezone.now() - timedelta(days=1)
    Result.objects.update(updated_at=past)

    # 레시피는 그대로이고 제작비만 바꾼다 → 결과 값이 같으므로 어느 행도 갱신하지 않는다.
    payload = {"id": catalog["판자"].id, "craftingPrice": 70, "materials": [basic("나무", 3)]}
    assert client.put("/product", payload, format="json").status_code == 200
    assert set(Result.objects.values_list("updated_at", flat=True)) == {past}

    # 의자 레시피만 바꾸면 의자 결과만 갱신한다.
    payload = {"id": catalog["의자"].id, "materials": [sub("판자", 1), basic("천", 3)]}
    assert client.put("/product", payload, format="json").status_code == 200
    updated = {row["product__name"]: row["updated_at"] for row in Result.objects.values("product__name", "updated_at")}
    assert updated["판자"] == updated["식탁"] == past
    assert updated["의자"] > past
    assert Result.objects.get(product=catalog["의자"]).total_price == 51


def test_rename_product_keeps_result_ids(client, catalog):
    assert client.post("/result").status_code == 201
    before = dict(Result.objects.values_list("product_id", "id"))

    payload = {"id": catalog["판자"].id, "name": "널빤지", "materials": [basic("나무", 3)]}
    assert client.put("/product", payload, format="json").status_code == 200

    assert dict(Result.objects.values_list("product_id", "id")) == before
    assert totals() == {"널빤지": 30, "식탁": 80, "의자": 44}
    assert list(catalog["식탁"].materials.filter(basic=False).values_list("name", flat=True)) == ["널빤지"]


def test_missing_prices_rejected_listing_all(client, catalog):
    materials = [basic("은", 1), basic("나무", 1), basic("금", 2)]
    materials_before = Material.objects.count()

    response = client.post("/product", product_payload(materials=materials), format="json")

    assert response.status_code == 400
    assert response.json() == {
        "statusCode": 400,
        "message": "시세 정보가 없는 재료가 있습니다. (새물품: 은, 새물품: 금)",
        "error": "Bad Request",
    }
    # 물품, 재료, 결과 모두 저장하지 않는다 (기존 물품의 결과 동기화도 함께 취소된다).
    assert not Product.objects.filter(name="새물품").exists()
    assert Material.objects.count() == materials_before
    assert not Result.objects.exists()


def test_bulk_create_rejects_missing_prices_of_every_new_product(client, catalog):
    products = [product_payload("C", [basic("은", 1)]), product_payload("D", [sub("C", 1), basic("금", 1)])]

    response = client.post("/product/all", {"products": products}, format="json")

    assert response.status_code == 400
    # C를 쓰는 D는 자기 문제(금)가 있으므로 '하위 물품 막힘'은 따로 적지 않는다.
    assert response.json()["message"] == "시세 정보가 없는 재료가 있습니다. (C: 은, D: 금)"
    assert not Product.objects.filter(name__in=["C", "D"]).exists()


def test_basic_material_named_as_product_is_rejected(client, catalog):
    response = client.post("/product", product_payload(materials=[basic("판자", 1)]), format="json")

    assert response.status_code == 400
    assert response.json()["message"] == "시세 정보가 없는 재료가 있습니다. (새물품: 판자)"
    assert not Product.objects.filter(name="새물품").exists()


def test_new_product_on_broken_sub_product_is_rejected(client, catalog):
    # DB를 직접 고쳐서 판자가 시세 없는 재료를 쓰게 됐다 (이미 있던 문제).
    catalog["판자"].materials.update(name="은")

    response = client.post("/product", product_payload(materials=[sub("판자", 1)]), format="json")

    assert response.status_code == 400
    assert response.json()["message"] == (
        "시세 정보가 없는 재료가 있습니다. (판자: 은) 하위 물품에 문제가 있어 계산할 수 없습니다. (새물품 ← 판자)"
    )
    assert not Product.objects.filter(name="새물품").exists()


def test_preexisting_problem_does_not_block_other_writes(client, catalog):
    assert client.post("/result").status_code == 201
    chair = results_by_name()["의자"]
    # 의자가 쓰는 천 시세를 DB에서 지웠다 (이미 있던 문제).
    Market.objects.filter(name="천").delete()

    response = client.put("/product", {"id": catalog["판자"].id, "materials": [basic("나무", 5)]}, format="json")

    assert response.status_code == 200
    assert results_by_name()["판자"]["total_price"] == 50
    assert results_by_name()["식탁"]["total_price"] == 120
    # 계산할 수 없는 의자의 결과는 지우지 않고 마지막 값으로 둔다.
    assert results_by_name()["의자"] == chair

    wood = Market.objects.get(name="나무")
    assert client.put("/market", [{"id": wood.id, "price": 20}], format="json").status_code == 200
    assert results_by_name()["식탁"]["total_price"] == 220
    assert results_by_name()["의자"] == chair


def test_edit_of_legacy_broken_product_allowed_without_new_problem(client, catalog):
    assert client.post("/result").status_code == 201
    Market.objects.filter(name="천").delete()
    chair = catalog["의자"]

    # 문제(천)를 그대로 둔 채 다른 필드만 고쳐도 된다.
    payload = {"id": chair.id, "craftingPrice": 999, "materials": [sub("판자", 1), basic("천", 2)]}
    assert client.put("/product", payload, format="json").status_code == 200
    chair.refresh_from_db()
    assert chair.crafting_price == 999

    # 다른 시세 없는 재료로 바꾸면 새 문제라서 거절한다.
    payload = {"id": chair.id, "materials": [sub("판자", 1), basic("금", 2)]}
    response = client.put("/product", payload, format="json")
    assert response.status_code == 400
    assert response.json()["message"] == "시세 정보가 없는 재료가 있습니다. (의자: 금)"

    # 고치면 결과도 바로 다시 계산한다.
    payload = {"id": chair.id, "materials": [sub("판자", 1), basic("못", 2)]}
    assert client.put("/product", payload, format="json").status_code == 200
    assert Result.objects.get(product=chair).total_price == 40


def test_market_price_overflow_rejected_and_new_market_rolled_back(client, catalog):
    assert client.post("/result").status_code == 201
    before = results_by_name()
    wood = Market.objects.get(name="나무")

    response = client.put("/market", [{"id": wood.id, "price": 2**31 - 1}, {"name": "금", "price": 1}], format="json")

    assert response.status_code == 400
    assert response.json()["message"] == "합계 금액이 너무 커서 저장할 수 없습니다. (판자, 식탁, 의자)"
    assert not Market.objects.filter(name="금").exists()
    wood.refresh_from_db()
    assert wood.price == 10
    assert results_by_name() == before


def test_rename_market_propagates_to_basic_materials_and_results(client, catalog):
    assert client.post("/result").status_code == 201
    before = results_by_name()
    # '나무'라는 물품도 있고, 그 물품을 하위 물품(basic=False)으로 쓰는 레시피도 있다.
    make_product("나무", [("못", True, 1)])
    crate = make_product("나무상자", [("나무", False, 2)])
    wood = Market.objects.get(name="나무")

    response = client.put("/market", [{"id": wood.id, "name": "원목"}], format="json")

    assert response.status_code == 200
    assert response.json() == [{"id": wood.id, "name": "원목", "price": 10}]
    assert list(catalog["판자"].materials.values_list("name", "basic")) == [("원목", True)]
    # 시세가 아니라 물품을 가리키는 재료는 그대로다.
    assert list(crate.materials.values_list("name", "basic")) == [("나무", False)]
    after = results_by_name()
    assert after["판자"]["names"] == "원목"
    assert after["식탁"]["names"] == "못,원목"
    assert after["의자"]["names"] == "천,원목"
    assert after["나무상자"]["names"] == "못"
    assert {name: after[name]["id"] for name in before} == {name: row["id"] for name, row in before.items()}

    # 맞바꾸기는 시세 이름 unique 제약에 걸려 기존 메시지로 거절하고, 재료도 바꾸지 않는다.
    nail = Market.objects.get(name="못")
    swap = [{"id": wood.id, "name": "못"}, {"id": nail.id, "name": "원목"}]
    response = client.put("/market", swap, format="json")
    assert response.status_code == 400
    assert response.json()["message"] == "이미 존재하는 시세 이름입니다."
    assert list(catalog["판자"].materials.values_list("name", flat=True)) == ["원목"]
    assert list(catalog["식탁"].materials.values_list("name", flat=True)) == ["판자", "못"]


def test_rename_market_and_add_old_name_in_same_request(client, catalog):
    wood = Market.objects.get(name="나무")

    items = [{"id": wood.id, "name": "원목"}, {"name": "나무", "price": 1}]
    response = client.put("/market", items, format="json")

    # 재료는 요청 전 이름 기준으로 따라가므로 원목(10원)을 쓰고, 새 시세 나무(1원)는 쓰는 물품이 없다.
    assert response.status_code == 200
    assert list(catalog["판자"].materials.values_list("name", flat=True)) == ["원목"]
    assert Result.objects.get(product=catalog["판자"]).total_price == 30
    assert not Material.objects.filter(name="나무").exists()


def test_new_market_creates_results_of_now_computable_products(client, catalog):
    assert client.post("/result").status_code == 201
    # 시세가 아직 없는 재료(은)를 쓰는 물품 (이미 있던 문제)
    silver = make_product("은세공", [("은", True, 2)])
    assert client.post("/result").json() == []

    response = client.put("/market", [{"name": "은", "price": 50}], format="json")

    assert response.status_code == 200
    assert Result.objects.get(product=silver).total_price == 100


def test_delete_unused_market(client, catalog):
    assert client.post("/result").status_code == 201
    before = results_by_name()
    gold = Market.objects.create(name="금", price=1000)

    response = client.delete("/market", {"ids": [gold.id]}, format="json")

    assert response.status_code == 200
    assert response.json() == {"deletedIds": [gold.id]}
    assert list(Market.objects.order_by("id").values_list("name", flat=True)) == ["나무", "못", "천"]
    assert results_by_name() == before


def test_delete_used_market_rejected_with_sorted_pairs(client, catalog):
    make_product("가방", [("천", True, 1), ("못", True, 1), ("천", True, 2)])
    gold = Market.objects.create(name="금", price=1000)
    ids = [Market.objects.get(name=name).id for name in ["천", "못", "나무"]] + [gold.id]

    response = client.delete("/market", {"ids": ids}, format="json")

    assert response.status_code == 400
    # '물품명: 시세명'을 물품명 → 시세명 순으로, 중복 없이 적는다.
    assert response.json()["message"] == (
        "물품의 재료로 쓰이는 시세는 삭제할 수 없습니다. (가방: 못, 가방: 천, 식탁: 못, 의자: 천, 판자: 나무)"
    )
    # 쓰지 않는 금도 함께 남는다 (요청 전체를 취소한다).
    assert Market.objects.count() == 4


def test_delete_unknown_ids_ignored(client, catalog):
    gold = Market.objects.create(name="금", price=1000)

    response = client.delete("/market", {"ids": [999, gold.id, gold.id]}, format="json")

    assert response.status_code == 200
    assert response.json() == {"deletedIds": [gold.id]}
    empty = client.delete("/market", {"ids": []}, format="json")
    assert empty.status_code == 200
    assert empty.json() == {"deletedIds": []}
    assert Market.objects.count() == 3


def test_post_result_creates_missing_and_refreshes_stale_in_place(client, catalog):
    assert client.post("/result").status_code == 201
    table = Result.objects.get(product=catalog["식탁"])
    # DB를 직접 고쳐 결과가 낡았고, 결과가 없는 물품도 생겼다.
    Result.objects.filter(pk=table.pk).update(names="나무", counts="1", prices="1", total_price=1)
    extra = make_product("추가", [("나무", True, 1)])

    response = client.post("/result")

    assert response.status_code == 201
    assert [row["product_id"] for row in response.json()] == [extra.id]  # 새로 만든 결과만 돌려준다
    refreshed = Result.objects.get(product=catalog["식탁"])
    assert refreshed.pk == table.pk
    assert refreshed.created_at == table.created_at
    assert (refreshed.names, refreshed.counts, refreshed.prices, refreshed.total_price) == (
        "못,나무",
        "4,6",
        "20,60",
        80,
    )

    again = client.post("/result")
    assert again.status_code == 201
    assert again.json() == []


def test_walnut_reflects_ample_edit(client, experiences, ample):
    before = client.get("/experience/walnut", {"presentLevel": 60}).json()["ample"]["result"]
    ample_product = Product.objects.get(name="식물앰플-중급 가속")

    payload = {"id": ample_product.id, "materials": [basic("호두", 3)]}
    assert client.put("/product", payload, format="json").status_code == 200

    after = client.get("/experience/walnut", {"presentLevel": 60}).json()["ample"]["result"]
    assert after["id"] == before["id"]
    assert (before["totalPrice"], after["totalPrice"]) == (200, 300)
