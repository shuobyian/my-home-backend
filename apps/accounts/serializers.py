from django.contrib.auth import authenticate, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import User


class PasswordField(serializers.CharField):
    """비밀번호 입력. 앞뒤 공백도 비밀번호로 받는다."""

    def __init__(self, **kwargs):
        super().__init__(trim_whitespace=False, max_length=128, **kwargs)


def check_password_strength(password, user):
    """settings.AUTH_PASSWORD_VALIDATORS(길이, 흔한 비밀번호, 숫자만, 아이디와 비슷함)로 검사한다."""
    try:
        password_validation.validate_password(password, user)
    except DjangoValidationError as error:
        raise serializers.ValidationError(error.messages) from None


def check_current_password(user, password):
    if not user.check_password(password):
        raise serializers.ValidationError("비밀번호가 올바르지 않습니다.")
    return password


class UsernameField(serializers.CharField):
    """아이디 입력. 저장할 때(create_user)처럼 NFKC로 바꾼 뒤 검사하고 찾는다 (예: 전각 'ａ' → 'a')."""

    def to_internal_value(self, data):
        return User.normalize_username(super().to_internal_value(data))


class SignupSerializer(serializers.Serializer):
    username = UsernameField(max_length=150, validators=[User.username_validator])
    password = PasswordField()
    # 앞뒤 공백은 빼고 저장한다. 공백뿐이면 빈 값으로 본다.
    nickname = serializers.CharField(max_length=20)

    def validate(self, attrs):
        try:
            check_password_strength(attrs["password"], User(username=attrs["username"]))
        except serializers.ValidationError as error:
            raise serializers.ValidationError({"password": error.detail}) from None
        return attrs


class LoginSerializer(serializers.Serializer):
    username = UsernameField(max_length=150)
    password = PasswordField()

    def validate(self, attrs):
        user = authenticate(username=attrs["username"], password=attrs["password"])
        if user is None:
            # 없는 아이디인지 비밀번호가 틀렸는지 알려 주지 않는다.
            raise serializers.ValidationError("아이디 또는 비밀번호가 올바르지 않습니다.")
        return {"user": user}


class PasswordChangeSerializer(serializers.Serializer):
    """PUT /auth/password. context["user"]는 로그인한 회원."""

    currentPassword = PasswordField(source="current_password")
    newPassword = PasswordField(source="new_password")

    def validate_currentPassword(self, value):
        return check_current_password(self.context["user"], value)

    def validate_newPassword(self, value):
        check_password_strength(value, self.context["user"])
        return value


class WithdrawSerializer(serializers.Serializer):
    """DELETE /auth/me (탈퇴). context["user"]는 로그인한 회원."""

    password = PasswordField()

    def validate_password(self, value):
        return check_current_password(self.context["user"], value)


class UserSerializer(serializers.ModelSerializer):
    isAdmin = serializers.BooleanField(source="is_staff", read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "nickname", "isAdmin"]


class SessionSerializer(serializers.Serializer):
    """로그인 응답. token은 이후 요청의 Authorization: Bearer 헤더에 넣는다."""

    token = serializers.CharField()
    expiresAt = serializers.DateTimeField(source="expires_at")
    user = UserSerializer()
