from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.tokens import issue_token
from apps.common.exceptions import BadRequest


@transaction.atomic
def signup(username, password, nickname):
    try:
        with transaction.atomic():
            user = User.objects.create_user(username=username, password=password, nickname=nickname)
    except IntegrityError:
        raise BadRequest("이미 사용 중인 아이디입니다.") from None
    return issue_token(user)


@transaction.atomic
def change_password(user, password):
    """비밀번호를 바꾸고 모든 기기의 로그인을 끊은 뒤, 지금 기기에서 쓸 토큰을 새로 준다."""
    user.set_password(password)
    user.save(update_fields=["password"])
    # 만료 토큰은 issue_token이 한꺼번에 지운다. 여기서 같이 지우면 동시에 발급하는 요청과 서로 행을 잠가 교착된다.
    user.auth_tokens.filter(expires_at__gt=timezone.now()).delete()
    return issue_token(user)
