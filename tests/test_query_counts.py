"""목록·계산·쓰기 API의 쿼리 수 고정 (N+1 회귀 방지)."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.markets.models import Market
from apps.products.models import Product
from apps.products.recipes import load_catalog, load_recipes
from tests.factories import make_product

pytestmark = pytest.mark.django_db

# SQLite는 bulk 배치를 max_query_params(999)÷필드 수로 나눈다.
# Material 249행, Product 199행, Result bulk_update 142행 단위다. 그래서 n은 100 이하(3과 30)로 둔다.
SIZES = [3, 30]


def setup_base():
    Market.objects.create(name="나무", price=1)
    make_product("판자", [("나무", True, 1)])


def make_products(start, stop):
    for i in range(start, stop):
        make_product(f"물품{i:03d}", [("판자", False, 1), ("나무", True, 2)])


def upload_row(name):
    """POST /product/all 본문의 물품 한 개."""
    return {
        "name": name,
        "level": 10,
        "craftingPrice": 300,
        "tool": "BRAZIER",
        "materials": [{"name": "나무", "basic": True, "count": 2}],
    }


def measure(send):
    with CaptureQueriesContext(connection) as ctx:
        response = send()
    return response, len(ctx.captured_queries)


@pytest.mark.parametrize("n", SIZES)
def test_read_endpoints_query_count(client, django_assert_num_queries, n):
    setup_base()
    make_products(0, n)
    client.post("/result")

    with django_assert_num_queries(3):
        client.get("/result", {"page": 0, "size": 10, "count": 3})
    with django_assert_num_queries(2):
        client.get("/result")
    with django_assert_num_queries(3):
        client.get("/product", {"page": 0, "size": 10})
    with django_assert_num_queries(2):
        client.get("/product")
    with django_assert_num_queries(5):
        client.post("/result/calculator", {"markets": [{"name": "나무", "price": 1}]}, format="json")
    # 레시피 2 + 시세 1 + 결과 1
    with django_assert_num_queries(4):
        client.get("/catalog/check")


def test_walnut_query_count(client, experiences, ample, django_assert_num_queries):
    with django_assert_num_queries(3):
        client.get("/experience/walnut", {"presentLevel": 60})


def test_write_endpoints_query_count_does_not_grow(client):
    # 서로 다른 parametrize 인스턴스끼리는 비교할 수 없으므로 한 함수 안에서 두 번 잰다.
    # savepoint 구성이 바뀌어도 깨지지 않도록 정확한 숫자 대신 두 회차가 같은지만 본다.
    # 결과는 값이 바뀐 행만 갱신하므로, 회차마다 시세와 판자 레시피를 다르게 바꿔야 두 회차 모두 결과 UPDATE가 나간다.
    def measure_writes(wood_id, plank_id, value, names, new_name):
        plank = {"id": plank_id, "materials": [{"name": "나무", "basic": True, "count": value}]}
        # 삭제 대상: 아무도 쓰지 않는 시세와, 다른 레시피가 쓰지 않는 물품
        spare_market = Market.objects.create(name=f"여분{value}", price=1)
        spare_product = make_product(f"삭제{value}", [("나무", True, 1)])
        counts = []
        for send, status in [
            (lambda: client.post("/result"), 201),
            (lambda: client.put("/market", [{"id": wood_id, "price": value}], format="json"), 200),
            (
                lambda: client.post("/product/all", {"products": [upload_row(name) for name in names]}, format="json"),
                201,
            ),
            (lambda: client.post("/product", upload_row(new_name), format="json"), 201),
            # 판자를 바꾸면 판자를 재료로 쓰는 물품 전부(n개)의 결과가 바뀐다.
            (lambda: client.put("/product", plank, format="json"), 200),
            (lambda: client.delete("/market", {"ids": [spare_market.id]}, format="json"), 200),
            (lambda: client.delete("/product", [spare_product.id], format="json"), 200),
        ]:
            response, count = measure(send)
            assert response.status_code == status
            counts.append(count)
        return tuple(counts)

    setup_base()
    make_products(0, 3)
    wood_id = Market.objects.get(name="나무").id
    plank_id = Product.objects.get(name="판자").id
    first = measure_writes(wood_id, plank_id, 2, [f"업로드{i:03d}" for i in range(3)], "단건1")

    make_products(3, 30)
    second = measure_writes(wood_id, plank_id, 3, [f"업로드{i:03d}" for i in range(3, 33)], "단건2")

    assert first == second


def test_materials_are_prefetched_in_id_order(client, catalog):
    # SQLite는 ORDER BY가 없어도 id 순서로 돌려주지만 Postgres는 순서를 보장하지 않아서,
    # 행동 테스트로는 이 정렬이 빠진 것을 잡을 수 없다. 그래서 SQL에 정렬이 있는지 직접 본다.
    # 계산 경로의 레시피 정렬(product_id, id)은 test_recipes_are_loaded_in_recipe_order에서 따로 본다.
    client.post("/result")

    for path in ["/product", "/result"]:
        with CaptureQueriesContext(connection) as ctx:
            client.get(path)
        material_queries = [query["sql"] for query in ctx.captured_queries if 'FROM "material"' in query["sql"]]
        assert material_queries, path
        assert all('ORDER BY "material"."id" ASC' in sql for sql in material_queries), path


def test_recipes_are_loaded_in_recipe_order(catalog):
    # 계산기는 같은 단계 안에서 레시피 순서를 따르므로, 이 정렬이 결과 재료(names/counts/prices) 순서를 정한다.
    # 재료 id를 섞어 넣는 행동 테스트는 SQLite가 rowid(=id) 순으로 돌려줘서 정렬이 빠져도 통과하므로 SQL을 본다.
    with CaptureQueriesContext(connection) as ctx:
        load_recipes()

    material_queries = [query["sql"] for query in ctx.captured_queries if 'FROM "material"' in query["sql"]]
    assert len(material_queries) == 1
    assert 'ORDER BY "material"."product_id" ASC, "material"."id" ASC' in material_queries[0]


def test_load_catalog_reads_recipes_and_ids_in_two_queries(catalog, django_assert_num_queries):
    with django_assert_num_queries(2):
        recipes, product_ids = load_catalog()

    assert list(recipes) == ["판자", "식탁", "의자"]  # 물품 id 순
    assert product_ids == {name: product.id for name, product in catalog.items()}
    assert [ingredient.name for ingredient in recipes["식탁"]] == ["판자", "못"]
