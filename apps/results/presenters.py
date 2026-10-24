"""결과 응답 모양 만들기 (기존 parseResult와 같은 응답 형식)와 데이터 점검 응답 모양."""

import math
from collections import Counter

from apps.common.dates import js_datetime
from apps.common.numbers import normalize
from apps.results.calculator import CostSheet

# 한 번에 여러 개 제작할 때 제작비 배율. 1~4개는 표, 5개 이상은 고정 배율.
CRAFTING_RATES = {1: 1, 2: 1.039, 3: 1.156, 4: 1.35}
BULK_CRAFTING_RATE = 1.613666 + 0.001555


def crafting_rate(count):
    if count >= 5:
        return BULK_CRAFTING_RATE
    return CRAFTING_RATES.get(count, 1)


def present_result(result, sheet: CostSheet | None = None, count=1):
    """결과 한 건을 count개 제작 기준으로 응답 형식에 맞춘다. sheet가 없으면 저장된 값을 쓴다."""
    if sheet is None:
        sheet = result.cost_sheet()
    product = result.product
    return {
        "id": result.id,
        "createdAt": js_datetime(result.created_at),
        "updatedAt": js_datetime(result.updated_at),
        "totalPrice": normalize(sheet.total_price * count),
        "name": product.name,
        "level": product.level,
        "tool": product.tool,
        "category": product.category,
        "product": {
            "id": product.id,
            "name": product.name,
            "level": product.level,
            "craftingPrice": product.crafting_price,
            "tool": product.tool,
            "category": product.category,
            "materials": [
                {"name": material.name, "basic": material.basic, "count": normalize(material.count * count)}
                for material in product.materials.all()
            ],
        },
        "craftingPrice": math.floor(product.crafting_price * count * crafting_rate(count)),
        "materials": [
            {
                "name": material.name,
                "price": normalize(material.price * count),
                "count": normalize(material.count * count),
            }
            for material in sheet.materials
        ],
    }


def present_catalog_check(check):
    """데이터 점검(GET /catalog/check) 응답. 키와 키 순서는 프론트엔드(types/catalog.ts)와 맞춘다."""
    severities = Counter(problem.severity for problem in check.problems)
    return {
        "summary": {
            "products": len(check.products),
            "markets": len(check.markets),
            "results": check.results,
            "errors": severities["error"],
            "warnings": severities["warning"],
            "infos": severities["info"],
        },
        "products": [
            {"id": product.id, "name": product.name, "status": product.status, "resultId": product.result_id}
            for product in check.products
        ],
        "markets": [
            {"id": market.id, "name": market.name, "price": market.price, "usedBy": list(market.used_by)}
            for market in check.markets
        ],
        "problems": [
            {
                "code": problem.code,
                "severity": problem.severity,
                "productId": problem.product_id,
                "productName": problem.product_name,
                "material": problem.material,
                "marketId": problem.market_id,
                "related": list(problem.related),
                "hint": problem.hint,
                "message": problem.message,
            }
            for problem in check.problems
        ],
    }
