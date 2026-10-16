import re

from django.urls import re_path


def route(path, view, name=None):
    """끝의 슬래시 유무와 관계없이 매칭되는 URL 패턴 (Express 기본 라우팅과 동일)."""
    pattern = rf"^{re.escape(path)}/?$" if path else r"^$"
    return re_path(pattern, view, name=name)
