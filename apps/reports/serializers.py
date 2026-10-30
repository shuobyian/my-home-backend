from rest_framework import serializers

from apps.accounts.models import User
from apps.common.fields import Int32Field
from apps.reports.changes import resolve_change
from apps.reports.models import ChangeTarget, Report, ReportChange, ReportKind, ReportStatus

# 제보 하나에 담을 수 있는 바꿀 값의 수
MAX_CHANGES = 20


class ReportChangeInputSerializer(serializers.Serializer):
    """바꿀 값 한 줄. value는 그 필드의 바른 값이다 (숫자는 숫자로, 도구·분류는 enum 값으로)."""

    target = serializers.ChoiceField(choices=ChangeTarget.choices)
    targetId = Int32Field(source="target_id")
    field = serializers.CharField(max_length=30)
    value = serializers.JSONField()

    def validate(self, attrs):
        return resolve_change(attrs["target"], attrs["target_id"], attrs["field"], attrs["value"])


class ReportInputSerializer(serializers.Serializer):
    """POST /report, PUT /report/<id>. 바꿀 값(changes)은 통째로 교체한다."""

    kind = serializers.ChoiceField(choices=ReportKind.choices)
    title = serializers.CharField(max_length=100)
    content = serializers.CharField(max_length=5000, allow_blank=True, default="")
    changes = ReportChangeInputSerializer(many=True, max_length=MAX_CHANGES, default=list)

    def validate(self, attrs):
        if not attrs["content"] and not attrs["changes"]:
            raise serializers.ValidationError("내용이나 바꿀 값을 입력해주세요.")
        seen = set()
        for change in attrs["changes"]:
            key = (change["target"], change["target_id"], change["field"])
            if key in seen:
                # 같은 값에 바른 값이 둘이면 어느 쪽인지 알 수 없다.
                raise serializers.ValidationError(f"같은 값을 두 번 넣었습니다. ({change['label']} {change['field']})")
            seen.add(key)
        return attrs


class ReportAnswerSerializer(serializers.Serializer):
    """PATCH /report/<id> (관리자 처리). 보낸 필드만 바꾼다."""

    status = serializers.ChoiceField(choices=ReportStatus.choices, required=False)
    answer = serializers.CharField(max_length=2000, allow_blank=True, required=False)


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "nickname"]


class ReportChangeSerializer(serializers.ModelSerializer):
    targetId = serializers.IntegerField(source="target_id")

    class Meta:
        model = ReportChange
        fields = ["target", "targetId", "label", "field", "before", "after"]


class ReportSerializer(serializers.ModelSerializer):
    # 탈퇴한 회원의 제보는 null
    author = AuthorSerializer(read_only=True)
    changes = ReportChangeSerializer(many=True, read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Report
        fields = ["id", "kind", "title", "content", "status", "answer", "author", "changes", "createdAt", "updatedAt"]
