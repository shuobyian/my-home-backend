"""활동 로그(로그인 이력, 제보 이력 등)."""

from django.conf import settings
from django.db import models


# 값과 이름은 프론트엔드(my-home-frontend src/types/enums.ts LogActionType, domain/labels.ts)의 목록과 같아야 한다.
class Action(models.TextChoices):
    SIGNUP = "SIGNUP", "회원가입"
    LOGIN = "LOGIN", "로그인"
    LOGIN_FAILED = "LOGIN_FAILED", "로그인 실패"
    LOGOUT = "LOGOUT", "로그아웃"
    PROFILE_UPDATE = "PROFILE_UPDATE", "닉네임 변경"
    PASSWORD_CHANGE = "PASSWORD_CHANGE", "비밀번호 변경"
    WITHDRAW = "WITHDRAW", "회원 탈퇴"
    REPORT_CREATE = "REPORT_CREATE", "제보 작성"
    REPORT_UPDATE = "REPORT_UPDATE", "제보 수정"
    REPORT_DELETE = "REPORT_DELETE", "제보 삭제"
    REPORT_ANSWER = "REPORT_ANSWER", "제보 처리"


class ActivityLog(models.Model):
    """누가 언제 무엇을 했는지 남긴다. 고치거나 지우는 API는 없다.

    회원이 탈퇴해도 로그는 남도록 회원은 SET_NULL로 가리키고, 그때의 아이디를 따로 적는다.
    제보도 지워진 뒤에 이력을 볼 수 있도록 외래 키 대신 id만 적는다.
    ponytail: 오래된 로그를 지우지 않는다.
    쌓여서 DB 용량(Neon 무료 0.5GB)이 문제가 되면 보존 기간을 정해 주기적으로 지운다.
    """

    action = models.CharField(max_length=30, choices=Action.choices, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    # 기록할 때의 아이디. 로그인 실패는 입력한 아이디(없는 아이디일 수 있다)다.
    username = models.CharField(max_length=150, blank=True)
    report_id = models.IntegerField(null=True, db_index=True)
    # 바뀐 내용(수정 전후 등). 모양은 action마다 다르다.
    detail = models.JSONField(default=dict)
    ip = models.CharField(max_length=255, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.username}"
