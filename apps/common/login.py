"""관리자 로그인 (POST /product/login).

Nest 호환으로 /product 아래 경로(apps/products/urls.py)에 있지만 물품과는 무관하다.
"""

import hmac

from django.conf import settings
from django.http import HttpResponse
from rest_framework import serializers, status
from rest_framework.views import APIView

from apps.common.exceptions import BadRequest


class LoginInputSerializer(serializers.Serializer):
    # 비밀번호가 없어도 기존 서버처럼 '비밀번호가 올바르지 않습니다.'로 응답한다.
    password = serializers.CharField(trim_whitespace=False, allow_blank=True, default="")


def check_login_password(password):
    expected = settings.LOGIN_PASSWORD
    # 비밀번호가 설정되지 않은 서버에서는 로그인을 허용하지 않는다.
    if not expected or not hmac.compare_digest(str(password).encode(), expected.encode()):
        raise BadRequest("비밀번호가 올바르지 않습니다.")


class LoginView(APIView):
    def post(self, request):
        serializer = LoginInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        check_login_password(serializer.validated_data["password"])
        return HttpResponse("", status=status.HTTP_201_CREATED)
