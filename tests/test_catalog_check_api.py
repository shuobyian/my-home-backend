"""데이터 점검(GET /catalog/check) 테스트: 문제 종류·정렬, 물품 상태, 시세 사용처."""

import pytest

from apps.experiences.services import AMPLE_PRODUCT_NAME
from apps.markets.models import Market
from apps.results.models import Result
from tests.factories import make_product

pytestmark = pytest.mark.django_db

HINT_SYNC = "'결과 다시 맞추기'를 누르세요."


def problem(code, severity, message, *, product=None, material=None, market=None, related=(), hint=None):
    return {
        "code": code,
        "severity": severity,
        "productId": product.id if product else None,
        "productName": product.name if product else None,
        "material": material,
        "marketId": market.id if market else None,
        "related": list(related),
        "hint": hint,
        "message": message,
    }


@pytest.fixture
def broken(client, catalog):
    """점검 문제 10종이 모두 나오는 상태.

    결과를 만든 뒤 DB를 직접 고쳐 문제를 만든다 (쓰기 API는 새 차단 문제를 거절한다).
    """
    assert client.post("/result").status_code == 201
    Market.objects.create(name="금", price=2**30)
    Market.objects.create(name="철", price=1)  # 쓰는 물품이 없다
    products = {
        **catalog,
        "불량품": make_product("불량품", [("없는물품", False, 1), ("못", False, 1)]),
        "책상": make_product("책상", [("판자", True, 1), ("은", True, 1)]),
        "고리A": make_product("고리A", [("고리B", False, 1)]),
        "고리B": make_product("고리B", [("고리A", False, 1)]),
        "금괴": make_product("금괴", [("금", True, 3)]),  # 3 x 2^30 > int32
        "책장": make_product("책장", [("책상", False, 1), ("판자", False, 1)]),
        "천": make_product("천", [("나무", True, 1)]),  # 시세 '천'과 이름이 같고 결과가 없다
    }
    Result.objects.filter(product=catalog["의자"]).update(total_price=1)
    return {"products": products, "markets": {market.name: market for market in Market.objects.all()}}


def test_check_reports_every_problem_in_order(client, broken):
    p, m = broken["products"], broken["markets"]

    response = client.get("/catalog/check")

    assert response.status_code == 200
    assert response.json()["problems"] == [
        problem(
            "UNKNOWN_SUB_PRODUCT",
            "error",
            "하위 재료에 잘못된 물품명이 있습니다. (불량품: 없는물품)",
            product=p["불량품"],
            material="없는물품",
        ),
        problem(
            "UNKNOWN_SUB_PRODUCT",
            "error",
            "하위 재료에 잘못된 물품명이 있습니다. (불량품: 못)",
            product=p["불량품"],
            material="못",
            hint="같은 이름의 시세가 있습니다. '최하위재료'로 바꾸세요.",
        ),
        problem(
            "MISSING_PRICE",
            "error",
            "시세 정보가 없는 재료가 있습니다. (책상: 판자)",
            product=p["책상"],
            material="판자",
            hint="같은 이름의 물품이 있습니다. '하위재료 O'로 바꾸세요.",
        ),
        problem(
            "MISSING_PRICE",
            "error",
            "시세 정보가 없는 재료가 있습니다. (책상: 은)",
            product=p["책상"],
            material="은",
            hint="새 재료라면 시세를 추가하고, 오타라면 레시피를 고치세요.",
        ),
        problem(
            "CIRCULAR_RECIPE",
            "error",
            "재료 구성에 순환 참조가 있습니다. (고리A → 고리B → 고리A)",
            product=p["고리A"],
            related=["고리A", "고리B", "고리A"],
        ),
        problem(
            "TOTAL_OVERFLOW",
            "error",
            "합계 금액이 너무 커서 저장할 수 없습니다. (금괴)",
            product=p["금괴"],
            hint="재료 개수나 시세를 확인하세요.",
        ),
        problem(
            "BLOCKED_BY_SUB_PRODUCT",
            "error",
            "하위 물품에 문제가 있어 계산할 수 없습니다. (책장 ← 책상)",
            product=p["책장"],
            related=["책상"],
            hint="먼저 하위 물품을 고치세요.",
        ),
        problem("MISSING_RESULT", "warning", "결과가 없습니다. (천)", product=p["천"], hint=HINT_SYNC),
        problem(
            "STALE_RESULT",
            "warning",
            "저장된 결과가 현재 레시피·시세와 다릅니다. (의자)",
            product=p["의자"],
            hint=HINT_SYNC,
        ),
        problem(
            "NAME_CONFLICT",
            "warning",
            "같은 이름의 물품과 시세가 있습니다. (천)",
            product=p["천"],
            material="천",
            market=m["천"],
            hint="'최하위재료'로 쓰면 시세 가격, '하위재료 O'로 쓰면 물품 레시피로 계산됩니다.",
        ),
        {
            **problem(
                "REQUIRED_PRODUCT_MISSING",
                "warning",
                f"호두작 계산에 쓰는 물품의 결과가 없습니다. ({AMPLE_PRODUCT_NAME})",
            ),
            "productName": AMPLE_PRODUCT_NAME,
        },
        problem(
            "UNUSED_MARKET",
            "info",
            "어떤 물품도 쓰지 않는 시세입니다. (철)",
            material="철",
            market=m["철"],
            hint="필요 없으면 삭제하세요.",
        ),
    ]


def test_check_reports_product_status_and_summary(client, broken):
    p = broken["products"]
    result_ids = dict(Result.objects.values_list("product_id", "id"))
    stored = list(Result.objects.order_by("id").values_list("id", "names", "counts", "prices", "total_price"))

    body = client.get("/catalog/check").json()

    statuses = {
        "판자": "ok",
        "식탁": "ok",
        "의자": "stale",
        "불량품": "error",
        "책상": "error",
        "고리A": "error",
        "고리B": "error",
        "금괴": "error",
        "책장": "error",
        "천": "missing",
    }
    assert body["products"] == [
        {"id": p[name].id, "name": name, "status": status, "resultId": result_ids.get(p[name].id)}
        for name, status in statuses.items()
    ]
    assert body["summary"] == {"products": 10, "markets": 5, "results": 3, "errors": 7, "warnings": 4, "infos": 1}
    # 점검은 저장하지 않는다 (낡은 결과도, 빠진 결과도 그대로다).
    assert list(Result.objects.order_by("id").values_list("id", "names", "counts", "prices", "total_price")) == stored


def test_check_lists_market_usage(client, broken):
    m = broken["markets"]

    body = client.get("/catalog/check").json()

    # 하위 물품(basic=False)으로 쓴 '못'(불량품)이나 시세가 없는 '판자'(책상)는 사용처가 아니다.
    assert body["markets"] == [
        {"id": m["나무"].id, "name": "나무", "price": 10, "usedBy": ["판자", "천"]},
        {"id": m["못"].id, "name": "못", "price": 5, "usedBy": ["식탁"]},
        {"id": m["천"].id, "name": "천", "price": 7, "usedBy": ["의자"]},
        {"id": m["금"].id, "name": "금", "price": 2**30, "usedBy": ["금괴"]},
        {"id": m["철"].id, "name": "철", "price": 1, "usedBy": []},
    ]


def test_used_by_lists_each_product_once(client, catalog):
    make_product("가방", [("천", True, 1), ("천", True, 2)])

    body = client.get("/catalog/check").json()

    assert {market["name"]: market["usedBy"] for market in body["markets"]}["천"] == ["의자", "가방"]


def test_check_after_sync_leaves_only_required_product_warning(client, catalog):
    assert client.post("/result").status_code == 201

    body = client.get("/catalog/check").json()

    assert [product["status"] for product in body["products"]] == ["ok", "ok", "ok"]
    assert [item["code"] for item in body["problems"]] == ["REQUIRED_PRODUCT_MISSING"]


def test_check_after_sync_with_ample_leaves_only_info(client, catalog, ample):
    Market.objects.create(name="금", price=1000)
    assert client.post("/result").status_code == 201

    body = client.get("/catalog/check").json()

    assert {product["status"] for product in body["products"]} == {"ok"}
    assert [(item["code"], item["material"]) for item in body["problems"]] == [("UNUSED_MARKET", "금")]
    assert body["summary"] == {"products": 4, "markets": 5, "results": 4, "errors": 0, "warnings": 0, "infos": 1}


def test_required_product_without_result_points_to_product(client, catalog):
    ample = make_product(AMPLE_PRODUCT_NAME, [("호두", True, 2)])  # 호두 시세가 없어 결과를 만들 수 없다

    problems = client.get("/catalog/check").json()["problems"]

    required = [item for item in problems if item["code"] == "REQUIRED_PRODUCT_MISSING"]
    assert [(item["productId"], item["productName"]) for item in required] == [(ample.id, AMPLE_PRODUCT_NAME)]
