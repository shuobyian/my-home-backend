import hmac
from collections import Counter

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Prefetch

from apps.common.exceptions import BadRequest
from apps.products.models import Material, Product
from apps.results.services import check_recipes

DUPLICATE_PRODUCT_MESSAGE = "이미 추가된 물품입니다."


def products_with_materials():
    return Product.objects.prefetch_related(Prefetch("materials", queryset=Material.objects.order_by("id")))


def login(password):
    expected = settings.LOGIN_PASSWORD
    # 비밀번호가 설정되지 않은 서버에서는 로그인을 허용하지 않는다.
    if not expected or not hmac.compare_digest(str(password).encode(), expected.encode()):
        raise BadRequest("비밀번호가 올바르지 않습니다.")


def list_products(name=None):
    queryset = products_with_materials().order_by("id")
    if name:
        queryset = queryset.filter(name__contains=name)
    return queryset


@transaction.atomic
def create_product(data):
    materials = data.pop("materials")
    if Product.objects.filter(name=data["name"]).exists():
        raise BadRequest(DUPLICATE_PRODUCT_MESSAGE)
    product = _save_new_products([Product(**data)])[0]
    _create_materials(product, materials)
    check_recipes([product.name])
    return products_with_materials().get(pk=product.pk)


@transaction.atomic
def create_products(items):
    """업로드한 물품 중 아직 없는 물품만 재료와 함께 추가한다."""
    duplicated = sorted(name for name, count in Counter(item["name"] for item in items).items() if count > 1)
    if duplicated:
        raise BadRequest(f"업로드 목록에 중복된 물품명이 있습니다. ({', '.join(duplicated)})")

    existing = set(Product.objects.filter(name__in=[item["name"] for item in items]).values_list("name", flat=True))
    new_items = [item for item in items if item["name"] not in existing]
    if not new_items:
        raise BadRequest("새로 추가할 물품이 없습니다.")

    products = _save_new_products(
        [Product(**{key: value for key, value in item.items() if key != "materials"}) for item in new_items]
    )
    Material.objects.bulk_create(
        Material(product=product, **material)
        for product, item in zip(products, new_items, strict=True)
        for material in item["materials"]
    )
    check_recipes([product.name for product in products])
    return list(products_with_materials().filter(pk__in=[product.pk for product in products]).order_by("id"))


@transaction.atomic
def update_product(data):
    materials = data.pop("materials")
    product = Product.objects.select_for_update().filter(pk=data.pop("id")).first()
    if product is None:
        raise BadRequest("존재하지 않는 물품입니다.")
    if "name" in data and Product.objects.filter(name=data["name"]).exclude(pk=product.pk).exists():
        raise BadRequest(DUPLICATE_PRODUCT_MESSAGE)

    old_name = product.name
    for field, value in data.items():
        setattr(product, field, value)
    product.save()
    if product.name != old_name:
        # 레시피는 물품을 이름으로 가리키므로, 이 물품을 재료로 쓰는 다른 레시피도 새 이름으로 바꾼다.
        Material.objects.filter(basic=False, name=old_name).update(name=product.name)

    product.materials.all().delete()
    _create_materials(product, materials)
    check_recipes([product.name])
    return products_with_materials().get(pk=product.pk)


@transaction.atomic
def delete_products(ids):
    """기존 TypeORM DeleteResult 모양({raw, affected})을 id마다 돌려준다."""
    products = dict(Product.objects.select_for_update().filter(pk__in=ids).values_list("pk", "name"))
    references = list(
        Material.objects.filter(basic=False, name__in=products.values())
        .exclude(product_id__in=products)
        .order_by("product__name", "name")
        .values_list("product__name", "name")
        .distinct()
    )
    if references:
        # 지우면 그 물품을 재료로 쓰는 레시피를 계산할 수 없게 되어 시세 수정까지 막힌다.
        detail = ", ".join(f"{parent}: {name}" for parent, name in references)
        raise BadRequest(f"다른 물품의 재료로 쓰이는 물품은 삭제할 수 없습니다. ({detail})")

    # 재료(material)와 결과(result)는 CASCADE로 함께 지워진다.
    Product.objects.filter(pk__in=products).delete()
    return [{"raw": [], "affected": 1 if product_id in products else 0} for product_id in ids]


def _save_new_products(products):
    try:
        with transaction.atomic():
            return Product.objects.bulk_create(products)
    except IntegrityError:
        # 동시에 같은 이름이 추가된 경우 (name unique 제약)
        raise BadRequest(DUPLICATE_PRODUCT_MESSAGE) from None


def _create_materials(product, materials):
    Material.objects.bulk_create(Material(product=product, **material) for material in materials)
