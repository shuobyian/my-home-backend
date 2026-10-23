from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import services
from apps.accounts.serializers import (
    LoginSerializer,
    PasswordChangeSerializer,
    SessionSerializer,
    SignupSerializer,
    UserSerializer,
    WithdrawSerializer,
)
from apps.accounts.tokens import issue_token


class SignupView(APIView):
    # 토큰을 붙이면 쓰로틀이 IP 대신 회원별로 세어 우회되므로, 가입·로그인은 토큰을 읽지 않는다.
    authentication_classes = []
    throttle_scope = "signup"

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = services.signup(**serializer.validated_data)
        return Response(SessionSerializer(session).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    authentication_classes = []
    throttle_scope = "auth"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = issue_token(serializer.validated_data["user"])
        return Response(SessionSerializer(session).data)


class LogoutView(APIView):
    def post(self, request):
        # 이 기기의 토큰만 지운다. 토큰이 없거나 이미 만료됐어도 성공으로 본다.
        if request.auth is not None:
            request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "auth"

    def get_throttles(self):
        # 비밀번호를 확인하는 탈퇴만 횟수를 제한한다.
        return super().get_throttles() if self.request.method == "DELETE" else []

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def delete(self, request):
        serializer = WithdrawSerializer(data=request.data, context={"user": request.user})
        serializer.is_valid(raise_exception=True)
        # 토큰도 함께 지워진다 (CASCADE).
        request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "auth"

    def put(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"user": request.user})
        serializer.is_valid(raise_exception=True)
        session = services.change_password(request.user, serializer.validated_data["new_password"])
        return Response(SessionSerializer(session).data)
