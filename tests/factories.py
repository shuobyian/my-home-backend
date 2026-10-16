"""테스트 데이터 빌더. fixture가 아닌 일반 함수이고 assert를 두지 않는다."""

from apps.products.models import Material, Product


def make_product(name, materials, *, level=1, crafting_price=100, tool="WOOD", category="NORMAL"):
    product = Product.objects.create(
        name=name, level=level, crafting_price=crafting_price, tool=tool, category=category
    )
    Material.objects.bulk_create(
        Material(product=product, name=material_name, basic=is_basic, count=count)
        for material_name, is_basic, count in materials
    )
    return product
