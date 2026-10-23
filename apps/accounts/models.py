"""회원과 로그인 토큰 모델."""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    """회원. is_staff가 True인 관리자만 물품·시세를 수정할 수 있다.

    기본 User를 쓰다가 바꾸려면 마이그레이션이 어려워서 처음부터 커스텀 모델로 둔다.
    """

    class Meta(AbstractUser.Meta):
        constraints = [
            # 'Admin'과 'admin'처럼 대소문자만 다른 아이디는 같은 아이디로 본다.
            models.UniqueConstraint(Lower("username"), name="user_username_ci_unique"),
        ]


class AuthToken(models.Model):
    """로그인 토큰. 로그인(기기)마다 하나씩 만들고, 원문 대신 SHA-256 해시만 저장한다."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="auth_tokens")
    digest = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)

    def __str__(self):
        return f"{self.user_id} (~{self.expires_at:%Y-%m-%d %H:%M})"
