from collections import Counter

from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from apps.common.exceptions import BadRequest
from apps.products.models import Material, Product
from apps.products.serializers import ProductInputSerializer
from apps.results.sync import begin_catalog_change, finish_catalog_change

DUPLICATE_PRODUCT_MESSAGE = "이미 추가된 물품입니다."


def list_products(name=None):
    queryset = Product.objects.with_materials().order_by("id")
    if name:
        queryset = queryset.filter(name__contains=name)
    return queryset


@transaction.atomic
def create_product(data):
    """물품을 재료와 함께 추가하고 결과도 만든다. 새 차단 문제(시세 없는 재료, 없는 하위 물품 등)가 생기면 400."""
    before = begin_catalog_change()
    if Product.objects.filter(name=data["name"]).exists():
        raise BadRequest(DUPLICATE_PRODUCT_MESSAGE)
    product = _insert_products_with_materials([data])[0]
    finish_catalog_change(before, focus=[product.name])
    return Product.objects.with_materials().get(pk=product.pk)


@transaction.atomic
def bulk_create_products(rows):
    """업로드한 물품 중 아직 없는 물품만 재료와 함께 추가한다.

    프론트엔드는 새 물품만이 아니라 로컬 카탈로그 전체를 보낸다. 이미 있는 물품은 건너뛰므로 검증도 하지 않는다
    (저장하지 않을 오래된 행 하나 때문에 업로드 전체가 막히지 않게). 새 물품끼리는 서로를 하위 물품으로 쓸 수 있고,
    새 물품 전부의 결과도 만든다.
    """
    names = [_row_name(row) for row in rows]
    duplicated = sorted(name for name, count in Counter(names).items() if name and count > 1)
    if duplicated:
        raise BadRequest(f"업로드 목록에 중복된 물품명이 있습니다. ({', '.join(duplicated)})")

    # 잠금을 잡은 뒤에 기존 이름을 읽어야, 동시에 들어온 업로드와 같은 물품을 두 번 넣으려다 실패하지 않는다.
    before = begin_catalog_change()
    existing = set(Product.objects.filter(name__in=[name for name in names if name]).values_list("name", flat=True))
    new_rows = [(index, row) for index, (row, name) in enumerate(zip(rows, names, strict=True)) if name not in existing]
    if not new_rows:
        raise BadRequest("새로 추가할 물품이 없습니다.")
    products = _insert_products_with_materials(_validate_new_rows(new_rows))
    finish_catalog_change(before, focus=[product.name for product in products])
    return list(Product.objects.with_materials().filter(pk__in=[product.pk for product in products]).order_by("id"))


@transaction.atomic
def update_product(data):
    """물품과 재료를 고치고, 이 물품과 이 물품을 (몇 단계든) 재료로 쓰는 물품의 결과를 제자리에서 다시 계산한다.

    이미 문제가 있던 물품도 새 문제를 만들지 않으면 고칠 수 있다.
    """
    materials = data.pop("materials")
    before = begin_catalog_change()
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
    finish_catalog_change(before, focus=[product.name])
    return Product.objects.with_materials().get(pk=product.pk)


@transaction.atomic
def delete_products(ids):
    """ids 중 찾아서 삭제한 물품 id 집합을 돌려준다."""
    before = begin_catalog_change()
    # 여러 물품을 잠그므로 항상 id 순서로 잠가 교착을 피한다.
    products = dict(Product.objects.select_for_update().filter(pk__in=ids).order_by("id").values_list("pk", "name"))
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
    finish_catalog_change(before)
    return set(products)


def _row_name(row):
    name = row.get("name")
    return name.strip() if isinstance(name, str) else None


def _validate_new_rows(indexed_rows):
    items, errors = [], {}
    for index, row in indexed_rows:
        serializer = ProductInputSerializer(data=row)
        if serializer.is_valid():
            items.append(serializer.validated_data)
        else:
            errors[index] = serializer.errors
    if errors:
        # 에러 위치는 업로드 목록의 원래 순서 기준 (예: products.3.count)
        raise ValidationError({"products": errors})
    return items


def _insert_products_with_materials(items):
    """검증된 물품 dict(재료 포함) 목록을 물품과 재료로 저장하고, 저장한 물품 목록을 돌려준다."""
    products = _save_new_products(
        [Product(**{key: value for key, value in item.items() if key != "materials"}) for item in items]
    )
    Material.objects.bulk_create(
        Material(product=product, **material)
        for product, item in zip(products, items, strict=True)
        for material in item["materials"]
    )
    return products


def _save_new_products(products):
    try:
        with transaction.atomic():
            return Product.objects.bulk_create(products)
    except IntegrityError:
        # 동시에 같은 이름이 추가된 경우 (name unique 제약)
        raise BadRequest(DUPLICATE_PRODUCT_MESSAGE) from None


def _create_materials(product, materials):
    Material.objects.bulk_create(Material(product=product, **material) for material in materials)
