import json

import pytest

from apps.products.models import Category, Material, Product, Tool
from apps.results.models import Result

pytestmark = pytest.mark.django_db


def product_payload(name="새물품", **overrides):
    payload = {
        "name": name,
        "level": 10,
        "craftingPrice": 300,
        "tool": "BRAZIER",
        "category": "NORMAL",
        "materials": [{"name": "나무", "basic": True, "count": 2}],
    }
    return {**payload, **overrides}


def test_login(client):
    assert client.post("/product/login", {"password": "test-password"}, format="json").status_code == 201

    response = client.post("/product/login", {"password": "wrong"}, format="json")
    assert response.status_code == 400
    assert response.json() == {"statusCode": 400, "message": "비밀번호가 올바르지 않습니다.", "error": "Bad Request"}


def test_login_rejects_when_password_not_configured(client, settings):
    settings.LOGIN_PASSWORD = ""
    assert client.post("/product/login", {"password": ""}, format="json").status_code == 400


def test_list_products_with_page_and_name(client, catalog):
    response = client.get("/product", {"page": 0, "size": 2})
    body = response.json()

    assert response.status_code == 200
    assert body["totalElements"] == 3
    assert [product["name"] for product in body["content"]] == ["판자", "식탁"]
    assert body["content"][0] == {
        "id": catalog["판자"].id,
        "name": "판자",
        "level": 1,
        "craftingPrice": 50,
        "tool": "WOOD",
        "category": "NORMAL",
        "materials": [
            {
                "id": catalog["판자"].materials.get().id,
                "product_id": catalog["판자"].id,
                "name": "나무",
                "basic": True,
                "count": 3.0,
            }
        ],
    }

    filtered = client.get("/product", {"name": "자"}).json()
    assert [product["name"] for product in filtered["content"]] == ["판자", "의자"]


def test_list_without_size_returns_everything(client, catalog):
    assert client.get("/product").json()["totalElements"] == 3
    assert len(client.get("/product/").json()["content"]) == 3


def test_create_product(client, db):
    response = client.post("/product", product_payload(), format="json")

    assert response.status_code == 201
    product = Product.objects.get(name="새물품")
    assert response.json()["id"] == product.id
    assert list(product.materials.values_list("name", "basic", "count")) == [("나무", True, 2.0)]


def test_create_duplicate_product(client, catalog):
    response = client.post("/product", product_payload("판자"), format="json")

    assert response.status_code == 400
    assert response.json()["message"] == "이미 추가된 물품입니다."


def test_create_product_validation_error_format(client, db):
    response = client.post(
        "/product",
        product_payload(tool="HAMMER", materials=[{"name": "a,b", "basic": True, "count": 0}]),
        format="json",
    )

    body = response.json()
    assert response.status_code == 400
    assert body["statusCode"] == 400
    assert body["error"] == "Bad Request"
    assert "tool:" in body["message"]
    assert "materials.0.name:" in body["message"]
    assert "materials.0.count:" in body["message"]


def test_bulk_create_skips_existing_products(client, catalog):
    payload = {"products": [product_payload("판자"), product_payload("새물품1"), product_payload("새물품2")]}

    response = client.post("/product/all", payload, format="json")

    assert response.status_code == 201
    assert [product["name"] for product in response.json()] == ["새물품1", "새물품2"]
    assert Material.objects.filter(product__name__startswith="새물품").count() == 2
    # 기존 물품의 재료는 건드리지 않는다
    assert list(catalog["판자"].materials.values_list("name", flat=True)) == ["나무"]


def test_bulk_create_errors(client, catalog):
    nothing_new = client.post("/product/all", {"products": [product_payload("판자")]}, format="json")
    assert nothing_new.json()["message"] == "새로 추가할 물품이 없습니다."

    duplicated = client.post("/product/all", {"products": [product_payload("A"), product_payload("A")]}, format="json")
    assert duplicated.status_code == 400
    assert "중복된 물품명" in duplicated.json()["message"]
    assert not Product.objects.filter(name="A").exists()


def test_update_product_replaces_materials(client, catalog):
    plank = catalog["판자"]
    payload = {
        "id": plank.id,
        "craftingPrice": 70,
        "materials": [{"name": "나무", "basic": True, "count": 4}, {"name": "못", "basic": True, "count": 1}],
    }

    response = client.put("/product", payload, format="json")

    assert response.status_code == 200
    plank.refresh_from_db()
    assert plank.crafting_price == 70
    assert plank.name == "판자"  # 보내지 않은 필드는 유지
    assert list(plank.materials.order_by("id").values_list("name", "count")) == [("나무", 4.0), ("못", 1.0)]


def test_update_unknown_product(client, db):
    response = client.put("/product", {"id": 999, "materials": []}, format="json")
    assert response.status_code == 400
    assert response.json()["message"] == "존재하지 않는 물품입니다."


def test_delete_products_cascades(client, catalog):
    client.post("/result")
    table = catalog["식탁"]

    response = client.delete("/product", [table.id, 999], format="json")

    assert response.status_code == 200
    assert response.json() == [{"raw": [], "affected": 1}, {"raw": [], "affected": 0}]
    assert not Product.objects.filter(pk=table.pk).exists()
    assert not Material.objects.filter(product_id=table.pk).exists()
    assert not Result.objects.filter(product_id=table.pk).exists()


def test_delete_accepts_frontend_ids_body(client, catalog):
    """프론트엔드는 {"ids": [...]}로 보낸다 (기존 서버는 이 형식을 처리하지 못했다)."""
    ids = [catalog["식탁"].id, catalog["의자"].id]

    response = client.delete("/product", {"ids": ids}, format="json")

    assert response.json() == [{"raw": [], "affected": 1}, {"raw": [], "affected": 1}]
    assert not Product.objects.filter(pk__in=ids).exists()


def test_delete_product_used_by_other_recipe_is_rejected(client, catalog):
    response = client.delete("/product", [catalog["판자"].id], format="json")

    assert response.status_code == 400
    assert response.json()["message"] == "다른 물품의 재료로 쓰이는 물품은 삭제할 수 없습니다. (식탁: 판자, 의자: 판자)"
    assert Product.objects.filter(pk=catalog["판자"].pk).exists()

    # 그 물품을 쓰는 물품과 함께 지우면 된다
    ids = [catalog["판자"].id, catalog["식탁"].id, catalog["의자"].id]
    assert client.delete("/product", ids, format="json").status_code == 200


def test_rename_product_updates_recipes_that_use_it(client, catalog):
    plank = catalog["판자"]
    payload = {"id": plank.id, "name": "널빤지", "materials": [{"name": "나무", "basic": True, "count": 3}]}

    assert client.put("/product", payload, format="json").status_code == 200

    assert list(catalog["식탁"].materials.filter(basic=False).values_list("name", flat=True)) == ["널빤지"]
    assert client.post("/result").status_code == 201


def test_create_product_with_unknown_sub_product_is_rejected(client, catalog):
    payload = product_payload(materials=[{"name": "없는물품", "basic": False, "count": 1}])

    response = client.post("/product", payload, format="json")

    assert response.status_code == 400
    assert response.json()["message"] == "하위 재료에 잘못된 물품명이 있습니다. (새물품: 없는물품)"
    assert not Product.objects.filter(name="새물품").exists()


def test_bulk_create_allows_references_within_upload(client, db):
    products = [
        product_payload("상위", materials=[{"name": "하위", "basic": False, "count": 2}]),
        product_payload("하위"),
    ]

    assert client.post("/product/all", {"products": products}, format="json").status_code == 201


def test_update_creating_cycle_is_rejected(client, catalog):
    plank = catalog["판자"]
    payload = {"id": plank.id, "materials": [{"name": "식탁", "basic": False, "count": 1}]}

    response = client.put("/product", payload, format="json")

    assert response.status_code == 400
    assert "순환 참조" in response.json()["message"]
    assert list(plank.materials.values_list("name", flat=True)) == ["나무"]


@pytest.mark.parametrize("count", ["NaN", "Infinity", "inf", 0, -1, 1_000_001])
def test_invalid_material_count_is_rejected(client, db, count):
    payload = product_payload(materials=[{"name": "나무", "basic": True, "count": count}])

    response = client.post("/product", payload, format="json")

    assert response.status_code == 400
    assert not Product.objects.exists()


def test_overflowing_json_number_is_rejected(client, db):
    # 1e999는 JSON 파싱 단계에서 inf가 된다
    body = json.dumps(product_payload()).replace('"count": 2', '"count": 1e999')

    response = client.generic("POST", "/product", body, content_type="application/json")

    assert response.status_code == 400
    assert not Product.objects.exists()


def test_integer_out_of_db_range_is_rejected(client, db):
    response = client.post("/product", product_payload(level=2**31), format="json")

    assert response.status_code == 400
    assert response.json()["message"].startswith("level:")


def test_login_without_password(client):
    response = client.post("/product/login", {}, format="json")

    assert response.status_code == 400
    assert response.json()["message"] == "비밀번호가 올바르지 않습니다."


def test_request_body_over_limit_is_rejected(client, settings, db):
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 100

    response = client.post("/product", product_payload(name="a" * 200), format="json")

    assert response.status_code == 413
    assert response.json() == {
        "statusCode": 413,
        "message": "request entity too large",
        "error": "Request Entity Too Large",
    }


def test_unknown_route_uses_nest_error_format(client, settings):
    settings.DEBUG = False
    response = client.get("/nothing")

    assert response.status_code == 404
    assert response.json() == {"statusCode": 404, "message": "Cannot GET /nothing", "error": "Not Found"}


def test_product_name_search_is_literal(client, catalog):
    # catalog에는 %나 _가 들어간 이름이 없다는 전제다
    assert client.get("/product", {"name": "_"}).json()["content"] == []


# djangorestframework==3.16.1 한국어 번역에 묶인 문구다.
# 버전을 올릴 때 깨지면 회귀로 보고, 테스트를 고쳐 맞추지 않는다.
def test_method_not_allowed(client, db):
    response = client.patch("/product", {}, format="json")

    assert response.status_code == 405
    assert response.json()["message"] == '메서드 "PATCH"는 허용되지 않습니다.'
    assert response.json()["error"] == "Method Not Allowed"


def test_form_body_is_unsupported(client, db):
    response = client.post("/product", "name=a", content_type="application/x-www-form-urlencoded")

    assert response.status_code == 415
    # message에는 요청한 미디어 타입이 들어가므로 비교하지 않는다
    assert response.json()["error"] == "Unsupported Media Type"


def test_malformed_json(client, db):
    response = client.generic("POST", "/product", "{bad", content_type="application/json")

    assert response.status_code == 400
    assert response.json()["message"].startswith("JSON parse error - ")


def test_health(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.content == b"Hello World!"


def test_tool_values_match_frontend():
    """프론트엔드 src/apis/type/Tool.ts, Category.ts와 같은 값이어야 한다."""
    assert Tool.values == [
        "WOOD",
        "FIRE_PIT",
        "SEWING_MACHINE",
        "LEATHER",
        "BRAZIER",
        "POTTERY_WHEEL",
        "ALCHEMY_KETTLE",
        "MIMI",
    ]
    assert Category.values == ["NORMAL", "EVENT"]


def test_mimi_tool_is_accepted(client, catalog):
    created = client.post("/product", product_payload("미미요리", tool="MIMI"), format="json")
    assert created.status_code == 201

    product_id = created.json()["id"]
    edited = client.put("/product", {"id": product_id, "tool": "MIMI", "materials": []}, format="json")
    assert edited.status_code == 200

    client.post("/result")
    filtered = client.get("/result", {"tool": "MIMI"}).json()["content"]
    assert [result["name"] for result in filtered] == ["미미요리"]


def test_bulk_create_ignores_invalid_rows_of_existing_products(client, catalog):
    """프론트엔드는 로컬 카탈로그 전체를 보낸다. 건너뛸 기존 물품 행은 검증하지 않는다."""
    stale = product_payload(" 판자", materials=[{"name": "나무", "basic": True, "count": 0}], tool="")
    payload = {"products": [stale, product_payload("새물품")]}

    response = client.post("/product/all", payload, format="json")

    assert response.status_code == 201
    assert [product["name"] for product in response.json()] == ["새물품"]


def test_bulk_create_reports_error_position_in_original_list(client, catalog):
    broken = product_payload("새물품", materials=[{"name": "나무", "basic": True, "count": 0}])
    payload = {"products": [product_payload("판자"), product_payload("좋은물품"), broken]}

    response = client.post("/product/all", payload, format="json")

    assert response.status_code == 400
    assert response.json()["message"].startswith("products.2.materials.0.count:")
    assert not Product.objects.filter(name="좋은물품").exists()


def test_update_to_existing_name_is_rejected(client, catalog):
    plank = catalog["판자"]
    payload = {"id": plank.id, "name": "식탁", "materials": []}

    response = client.put("/product", payload, format="json")

    assert response.json() == {"statusCode": 400, "message": "이미 추가된 물품입니다.", "error": "Bad Request"}
    plank.refresh_from_db()
    assert plank.name == "판자"
    assert list(plank.materials.values_list("name", flat=True)) == ["나무"]


def test_update_with_own_name_is_allowed(client, catalog):
    plank = catalog["판자"]
    payload = {"id": plank.id, "name": "판자", "materials": [{"name": "나무", "basic": True, "count": 3}]}

    assert client.put("/product", payload, format="json").status_code == 200


def test_rename_rolls_back_when_recipe_check_fails(client, catalog):
    plank = catalog["판자"]
    payload = {"id": plank.id, "name": "널빤지", "materials": [{"name": "식탁", "basic": False, "count": 1}]}

    response = client.put("/product", payload, format="json")

    assert response.status_code == 400
    assert response.json()["message"] == "재료 구성에 순환 참조가 있습니다. (널빤지 → 식탁 → 널빤지)"
    # 이름 변경은 basic=False인 '판자' 재료 전체를 바꾸므로, 그 재료를 쓰는 식탁과 의자까지 되돌려졌는지 본다.
    assert set(Product.objects.values_list("name", flat=True)) == {"판자", "식탁", "의자"}
    assert list(catalog["식탁"].materials.order_by("id").values_list("name", flat=True)) == ["판자", "못"]
    assert list(catalog["의자"].materials.order_by("id").values_list("name", flat=True)) == ["판자", "천"]
    assert list(plank.materials.values_list("name", flat=True)) == ["나무"]


def test_bulk_create_rolls_back_when_sub_product_unknown(client, catalog):
    before = Material.objects.count()
    payload = {"products": [product_payload("C", materials=[{"name": "없음", "basic": False, "count": 1}])]}

    response = client.post("/product/all", payload, format="json")

    assert response.status_code == 400
    assert response.json()["message"] == "하위 재료에 잘못된 물품명이 있습니다. (C: 없음)"
    assert not Product.objects.filter(name="C").exists()
    assert Material.objects.count() == before


def test_bulk_create_duplicate_names_message_is_sorted_and_stripped(client, db):
    payload = {"products": [product_payload(name) for name in ["B", "A", " B", "A"]]}

    response = client.post("/product/all", payload, format="json")

    assert response.json()["message"] == "업로드 목록에 중복된 물품명이 있습니다. (A, B)"


def test_create_product_defaults_category_to_normal(client, db):
    payload = product_payload()
    del payload["category"]

    response = client.post("/product", payload, format="json")

    assert response.status_code == 201
    assert response.json()["category"] == "NORMAL"
    assert Product.objects.get(name="새물품").category == "NORMAL"


def test_delete_with_empty_and_repeated_ids(client, catalog):
    empty = client.delete("/product", [], format="json")
    assert empty.status_code == 200
    assert empty.json() == []

    table_id = catalog["식탁"].id
    repeated = client.delete("/product", [table_id, table_id], format="json")
    assert repeated.json() == [{"raw": [], "affected": 1}, {"raw": [], "affected": 1}]


# djangorestframework==3.16.1 한국어 번역과 LANGUAGE_CODE=ko-kr에 의존한다.
# 깨지면 프론트엔드에 보이는 문구가 바뀐 것이므로 기대값이 아니라 구현을 맞춘다.
def test_missing_fields_message_format(client, db):
    response = client.post("/product", {}, format="json")

    assert response.json()["message"] == (
        "name: 이 필드는 필수 항목입니다., level: 이 필드는 필수 항목입니다., "
        "craftingPrice: 이 필드는 필수 항목입니다., tool: 이 필드는 필수 항목입니다., "
        "materials: 이 필드는 필수 항목입니다."
    )


# djangorestframework==3.16.1 한국어 번역과 LANGUAGE_CODE=ko-kr에 의존한다.
# 깨지면 프론트엔드에 보이는 문구가 바뀐 것이므로 기대값이 아니라 구현을 맞춘다.
def test_name_validation_message_order(client, db):
    payload = product_payload(name="a,b" + "x" * 300, materials=[{"name": "c,d", "basic": True, "count": 1}])

    response = client.post("/product", payload, format="json")

    assert response.json()["message"] == (
        "name: 이름에 콤마(,)를 넣을 수 없습니다., name: 이 필드의 글자 수가 255 이하인지 확인하세요., "
        "materials.0.name: 이름에 콤마(,)를 넣을 수 없습니다."
    )


# djangorestframework==3.16.1 한국어 번역과 LANGUAGE_CODE=ko-kr에 의존한다.
# 깨지면 프론트엔드에 보이는 문구가 바뀐 것이므로 기대값이 아니라 구현을 맞춘다.
def test_update_name_validation_message_order(client, catalog):
    payload = {"id": catalog["판자"].id, "name": "a,b" + "x" * 300, "materials": []}

    response = client.put("/product", payload, format="json")

    assert response.json()["message"] == (
        "name: 이름에 콤마(,)를 넣을 수 없습니다., name: 이 필드의 글자 수가 255 이하인지 확인하세요."
    )


# djangorestframework==3.16.1 한국어 번역과 LANGUAGE_CODE=ko-kr에 의존한다.
# 깨지면 프론트엔드에 보이는 문구가 바뀐 것이므로 기대값이 아니라 구현을 맞춘다.
def test_update_validation_message_order(client, db):
    payload = {"id": "x", "name": "a,b", "category": "Z"}

    response = client.put("/product", payload, format="json")

    assert response.json()["message"] == (
        "id: 유효한 정수를 입력하세요., name: 이름에 콤마(,)를 넣을 수 없습니다., "
        'category: "Z"은 유효하지 않은 선택입니다., materials: 이 필드는 필수 항목입니다.'
    )


# djangorestframework==3.16.1 한국어 번역과 LANGUAGE_CODE=ko-kr에 의존한다.
# 깨지면 프론트엔드에 보이는 문구가 바뀐 것이므로 기대값이 아니라 구현을 맞춘다.
def test_bulk_create_name_with_comma_message(client, catalog):
    payload = {"products": [product_payload("판자"), product_payload("a,b")]}

    response = client.post("/product/all", payload, format="json")

    assert response.json()["message"] == "products.1.name: 이름에 콤마(,)를 넣을 수 없습니다."
