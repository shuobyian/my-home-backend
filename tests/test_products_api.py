import pytest

from apps.products.models import Material, Product
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


def test_delete_products_cascades(client, catalog):
    client.post("/result")
    plank = catalog["판자"]

    response = client.delete("/product", [plank.id, 999], format="json")

    assert response.status_code == 200
    assert response.json() == [{"raw": [], "affected": 1}, {"raw": [], "affected": 0}]
    assert not Product.objects.filter(pk=plank.pk).exists()
    assert not Material.objects.filter(product_id=plank.pk).exists()
    assert not Result.objects.filter(product_id=plank.pk).exists()


def test_unknown_route_uses_nest_error_format(client, settings):
    settings.DEBUG = False
    response = client.get("/nothing")

    assert response.status_code == 404
    assert response.json() == {"statusCode": 404, "message": "Cannot GET /nothing", "error": "Not Found"}


def test_health(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.content == b"Hello World!"
