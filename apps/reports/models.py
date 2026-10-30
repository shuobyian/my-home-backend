"""제보 게시판: 버그나 잘못된 수치·정보를 알린다."""

from django.conf import settings
from django.db import models


# 값과 이름은 프론트엔드(my-home-frontend src/types/enums.ts, domain/labels.ts)의 목록과 같아야 한다.
class ReportKind(models.TextChoices):
    DATA = "DATA", "잘못된 수치·정보"
    BUG = "BUG", "버그"


class ReportStatus(models.TextChoices):
    OPEN = "OPEN", "접수"
    RESOLVED = "RESOLVED", "반영"
    REJECTED = "REJECTED", "반려"


# 바꿀 값이 가리키는 데이터. 대상마다 바꿀 수 있는 값은 apps/reports/changes.py에 있다.
class ChangeTarget(models.TextChoices):
    EXPERIENCE = "EXPERIENCE", "레벨 경험치"
    MARKET = "MARKET", "시세"
    PRODUCT = "PRODUCT", "물품"
    MATERIAL = "MATERIAL", "물품 재료"


class Report(models.Model):
    """회원이 쓴 제보. 접수 상태일 때만 쓴 사람이 고치거나 지울 수 있고, 관리자가 처리(반영·반려)한다.

    쓴 회원이 탈퇴해도 제보는 남는다 (author가 null).
    """

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="reports")
    kind = models.CharField(max_length=20, choices=ReportKind.choices)
    title = models.CharField(max_length=100)
    content = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=ReportStatus.choices, default=ReportStatus.OPEN, db_index=True)
    # 관리자 답변 (처리 이유 등)
    answer = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"#{self.id} {self.title}"


class ReportChange(models.Model):
    """제보 하나에 담긴 '어느 값이 어떻게 바뀌어야 하는지' 한 줄 (예: 90레벨 경험치 9,500,000 → 10,000,000).

    대상(경험치·시세·물품·재료)은 외래 키 대신 id로 가리키고, 쓸 때의 이름(label)과 값(before)을 함께 적는다.
    관리자가 데이터를 고치거나 지워도 제보가 무엇을 말했는지 남는다.
    """

    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="changes")
    target = models.CharField(max_length=20, choices=ChangeTarget.choices)
    target_id = models.IntegerField()
    # 쓸 때의 대상 이름 (예: '90레벨', '나무', '식탁 · 판자')
    label = models.CharField(max_length=255)
    field = models.CharField(max_length=30)
    # 쓸 때의 값과 바른 값. 숫자·문자열을 그대로 담는다.
    before = models.JSONField()
    after = models.JSONField()

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.label} {self.field}: {self.before} → {self.after}"
