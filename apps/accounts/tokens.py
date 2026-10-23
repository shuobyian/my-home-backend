"""로그인 토큰 발급·조회.

DRF가 설정(DEFAULT_AUTHENTICATION_CLASSES)을 읽을 때 authentication.py와 함께 import되므로
rest_framework.views를 import하는 모듈(apps.common.exceptions 등)을 여기서 import하지 않는다 (순환 import).
"""

import hashlib
import secrets

from django.conf import settings
from django.utils import timezone

from apps.accounts.models import AuthToken


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def issue_token(user):
    """로그인 토큰을 새로 만든다. 원문은 이 응답에서 한 번만 돌려주고 DB에는 해시만 남긴다."""
    now = timezone.now()
    # ponytail: 만료된 토큰은 발급할 때 한꺼번에 지운다. 로그인이 아주 많아지면 주기 작업으로 옮긴다.
    AuthToken.objects.filter(expires_at__lte=now).delete()
    raw = secrets.token_urlsafe(32)
    token = AuthToken.objects.create(user=user, digest=_digest(raw.encode()), expires_at=now + settings.AUTH_TOKEN_TTL)
    return {"token": raw, "expires_at": token.expires_at, "user": user}


def find_token(raw):
    """Authorization 헤더의 토큰(bytes)에 맞는 유효한 토큰. 없거나 만료됐거나 비활성 회원이면 None."""
    return (
        AuthToken.objects.select_related("user")
        .filter(digest=_digest(raw), expires_at__gt=timezone.now(), user__is_active=True)
        .first()
    )
