from rest_framework.throttling import BaseThrottle

from apps.logs.models import ActivityLog


def record(request, action, *, user=None, username=None, report_id=None, detail=None):
    """활동 로그를 남긴다. user를 넘기지 않으면 요청한 회원(로그인했으면)으로 적는다."""
    if user is None and request.user.is_authenticated:
        user = request.user
    return ActivityLog.objects.create(
        action=action,
        user=user,
        username=(username if username is not None else getattr(user, "username", ""))[:150],
        report_id=report_id,
        detail=detail or {},
        # 요청 횟수 제한(throttle)과 같은 기준으로 클라이언트를 적는다 (X-Forwarded-For 전체, 없으면 REMOTE_ADDR).
        # 위조할 수 있는 값이라 참고용이다. settings의 DEFAULT_THROTTLE_CLASSES 설명을 본다.
        ip=(BaseThrottle().get_ident(request) or "")[:255],
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
    )
