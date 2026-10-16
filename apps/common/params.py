"""쿼리스트링 파싱 헬퍼.

NestJS 컨트롤러는 쿼리 값을 검증 없이 문자열로 받았다. 여기서는 빈 값은 '없음'으로 보고,
숫자가 아닌 값은 500 대신 400으로 응답한다.
"""

import math

from apps.common.exceptions import BadRequest


def query_str(request, name):
    value = request.query_params.get(name, "")
    return value if value != "" else None


def query_number(request, name, *, default=None, min_value=None, max_value=None):
    raw = query_str(request, name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise BadRequest(f"{name} 값은 숫자여야 합니다.") from None
    if not math.isfinite(value):
        raise BadRequest(f"{name} 값은 숫자여야 합니다.")
    if min_value is not None and value < min_value:
        raise BadRequest(f"{name} 값은 {min_value} 이상이어야 합니다.")
    if max_value is not None and value > max_value:
        raise BadRequest(f"{name} 값은 {max_value} 이하여야 합니다.")
    return value


def query_int(request, name, *, default=None, min_value=None, max_value=None, required=False):
    value = query_number(request, name, min_value=min_value, max_value=max_value)
    if value is None:
        if required:
            raise BadRequest(f"{name} 값이 필요합니다.")
        return default
    if not value.is_integer():
        raise BadRequest(f"{name} 값은 정수여야 합니다.")
    return int(value)


def query_page(request):
    """page/size 쿼리를 읽는다. size가 없으면 페이지 없이 전체를 조회한다 (기존 동작)."""
    page = query_int(request, "page", default=0, min_value=0)
    size = query_int(request, "size", min_value=1)
    return page, size


def paginate(queryset, page, size):
    """(현재 페이지 목록, 전체 개수)를 돌려준다."""
    if size is None:
        items = list(queryset)
        return items, len(items)
    offset = page * size
    return list(queryset[offset : offset + size]), queryset.count()
