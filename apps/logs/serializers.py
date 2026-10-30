from rest_framework import serializers

from apps.logs.models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    userId = serializers.IntegerField(source="user_id", read_only=True)
    reportId = serializers.IntegerField(source="report_id", read_only=True)
    userAgent = serializers.CharField(source="user_agent", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = ActivityLog
        fields = ["id", "action", "userId", "username", "reportId", "detail", "ip", "userAgent", "createdAt"]
