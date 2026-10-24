"""응답 JSON의 키와 키 순서를 고정한다 (프론트엔드가 보는 모양).

스냅샷 라이브러리 없이 기대 키 리스트를 코드에 직접 적고 `list(response.json())` 전체와 비교한다.
"""

import re

import pytest

from apps.markets.models import Market

pytestmark = pytest.mark.django_db

PRODUCT_KEYS = ["id", "name", "level", "craftingPrice", "tool", "category", "materials"]
MATERIAL_KEYS = ["id", "product_id", "name", "basic", "count"]
PAGE_KEYS = ["totalElements", "content"]
ERROR_KEYS = ["statusCode", "message", "error"]
RESULT_ROW_KEYS = ["id", "createdAt", "updatedAt", "product_id", "names", "counts", "prices", "totalPrice"]
PRESENTED_KEYS = [
    "id",
    "createdAt",
    "updatedAt",
    "totalPrice",
    "name",
    "level",
    "tool",
    "category",
    "product",
    "craftingPrice",
    "materials",
]
PRESENTED_PRODUCT_KEYS = ["id", "name", "level", "craftingPrice", "tool", "category", "materials"]
CHECK_KEYS = ["summary", "products", "markets", "problems"]
CHECK_SUMMARY_KEYS = ["products", "markets", "results", "errors", "warnings", "infos"]
CHECK_PRODUCT_KEYS = ["id", "name", "status", "resultId"]
CHECK_MARKET_KEYS = ["id", "name", "price", "usedBy"]
PROBLEM_KEYS = ["code", "severity", "productId", "productName", "material", "marketId", "related", "hint", "message"]
JS_DATETIME = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z"


def new_product(name="새물품"):
    return {
        "name": name,
        "level": 10,
        "craftingPrice": 300,
        "tool": "BRAZIER",
        "materials": [{"name": "나무", "basic": True, "count": 2}],
    }


def assert_presented(item):
    """결과 표시용 항목(목록, 계산기, 호두)의 키 순서를 확인한다."""
    assert list(item) == PRESENTED_KEYS
    assert list(item["product"]) == PRESENTED_PRODUCT_KEYS
    # 빈 리스트면 [0]이 실패하거나 아무것도 검증하지 못하므로 비어 있지 않음을 먼저 확인한다.
    assert item["product"]["materials"]
    assert list(item["product"]["materials"][0]) == ["name", "basic", "count"]
    assert item["materials"]
    assert list(item["materials"][0]) == ["name", "price", "count"]


def get_product(client, catalog):
    return client.get("/product").json()["content"][0]


def post_product(client, catalog):
    return client.post("/product", new_product(), format="json").json()


def put_product(client, catalog):
    body = {"id": catalog["판자"].id, "materials": [{"name": "나무", "basic": True, "count": 1}]}
    return client.put("/product", body, format="json").json()


def bulk_product(client, catalog):
    return client.post("/product/all", {"products": [new_product("일괄")]}, format="json").json()[0]


@pytest.mark.parametrize(
    "request_product",
    [get_product, post_product, put_product, bulk_product],
    ids=["get", "post", "put", "bulk"],
)
def test_product_key_order(client, catalog, request_product):
    body = request_product(client, catalog)

    assert list(body) == PRODUCT_KEYS
    assert body["materials"]
    assert list(body["materials"][0]) == MATERIAL_KEYS


def test_page_key_order(client, catalog):
    client.post("/result")

    assert list(client.get("/product").json()) == PAGE_KEYS
    assert list(client.get("/result").json()) == PAGE_KEYS


def test_delete_product_key_order(client, catalog):
    body = client.delete("/product", [catalog["식탁"].id], format="json").json()

    assert [list(item) for item in body] == [["raw", "affected"]]


def test_market_key_order(client, catalog):
    wood_id = Market.objects.get(name="나무").id

    assert list(client.get("/market").json()[0]) == ["id", "name", "price"]
    body = client.put("/market", [{"id": wood_id, "price": 11}], format="json").json()
    assert list(body[0]) == ["id", "name", "price"]


def test_delete_market_key_order(client, catalog):
    gold = Market.objects.create(name="금", price=1000)

    body = client.delete("/market", {"ids": [gold.id]}, format="json").json()

    assert list(body) == ["deletedIds"]


def test_catalog_check_key_order(client, catalog):
    # 결과를 만들지 않아서 MISSING_RESULT(물품 문제)와 REQUIRED_PRODUCT_MISSING(물품 없음)이 함께 나온다.
    Market.objects.create(name="금", price=1000)  # UNUSED_MARKET(시세 문제)

    body = client.get("/catalog/check").json()

    assert list(body) == CHECK_KEYS
    assert list(body["summary"]) == CHECK_SUMMARY_KEYS
    assert body["products"]
    assert all(list(product) == CHECK_PRODUCT_KEYS for product in body["products"])
    assert body["markets"]
    assert all(list(market) == CHECK_MARKET_KEYS for market in body["markets"])
    assert {problem["code"] for problem in body["problems"]} == {
        "MISSING_RESULT",
        "REQUIRED_PRODUCT_MISSING",
        "UNUSED_MARKET",
    }
    # 해당 없는 필드도 키는 항상 있다 (null이나 []).
    assert all(list(problem) == PROBLEM_KEYS for problem in body["problems"])


def test_create_result_key_order(client, catalog):
    body = client.post("/result").json()

    assert list(body[0]) == RESULT_ROW_KEYS
    assert re.fullmatch(JS_DATETIME, body[0]["createdAt"])
    assert re.fullmatch(JS_DATETIME, body[0]["updatedAt"])


def test_result_list_key_order(client, catalog):
    client.post("/result")

    assert_presented(client.get("/result").json()["content"][0])


def test_calculator_key_order(client, catalog):
    client.post("/result")
    # 기본 재료를 하나라도 빼면 400 에러 본문이 오므로 나무·못·천을 모두 넣는다.
    markets = [{"name": "나무", "price": 1}, {"name": "못", "price": 1}, {"name": "천", "price": 1}]

    body = client.post("/result/calculator", {"markets": markets}, format="json").json()

    assert list(body) == ["results"]
    assert_presented(body["results"][0])


def test_walnut_key_order(client, experiences, ample):
    body = client.get("/experience/walnut", {"presentLevel": 60}).json()

    assert list(body) == ["remindExperience", "remindCount", "ample"]
    assert list(body["ample"]) == ["result"]
    assert_presented(body["ample"]["result"])


def test_experience_key_order(client, experiences):
    assert list(client.get("/experience").json()[0]) == ["id", "level", "amount"]


@pytest.mark.parametrize(
    ("method", "kwargs", "status"),
    [
        ("post", {"data": {}, "format": "json"}, 400),
        ("patch", {}, 405),
        ("post", {"data": "name=a", "content_type": "application/x-www-form-urlencoded"}, 415),
    ],
    ids=["400", "405", "415"],
)
def test_error_key_order(client, method, kwargs, status):
    response = getattr(client, method)("/product", **kwargs)

    assert response.status_code == status
    assert list(response.json()) == ERROR_KEYS


def test_not_found_key_order(client, settings):
    settings.DEBUG = False

    response = client.get("/nothing")

    assert response.status_code == 404
    assert list(response.json()) == ERROR_KEYS


def test_too_large_key_order(client, settings):
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 100

    response = client.post("/product", new_product("a" * 200), format="json")

    assert response.status_code == 413
    assert list(response.json()) == ERROR_KEYS
