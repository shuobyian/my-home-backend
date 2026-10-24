"""회원과 로그인 토큰 모델."""

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as BaseUserManager
from django.db import models
from django.db.models.functions import Lower

# 관리자 계정의 닉네임. 관리자는 게임 캐릭터가 아니라서 닉네임 대신 이 이름으로 보인다.
ADMIN_NICKNAME = "관리자"


class UserManager(BaseUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        # createsuperuser는 닉네임을 묻지 않으므로 관리자 닉네임을 넣는다.
        extra_fields.setdefault("nickname", ADMIN_NICKNAME)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    """회원. is_staff가 True인 관리자만 물품·시세를 수정할 수 있다.

    기본 User를 쓰다가 바꾸려면 마이그레이션이 어려워서 처음부터 커스텀 모델로 둔다.
    """

    # 게임(놀러와 마이홈) 안의 닉네임. 필수이고, 게임과 달리 다른 회원과 같아도 된다.
    nickname = models.CharField(max_length=20)

    objects = UserManager()

    class Meta(AbstractUser.Meta):
        constraints = [
            # 'Admin'과 'admin'처럼 대소문자만 다른 아이디는 같은 아이디로 본다.
            models.UniqueConstraint(Lower("username"), name="user_username_ci_unique"),
            models.CheckConstraint(condition=~models.Q(nickname=""), name="user_nickname_not_blank"),
        ]


class AuthToken(models.Model):
    """로그인 토큰. 로그인(기기)마다 하나씩 만들고, 원문 대신 SHA-256 해시만 저장한다."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="auth_tokens")
    digest = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)

    def __str__(self):
        return f"{self.user_id} (~{self.expires_at:%Y-%m-%d %H:%M})"
