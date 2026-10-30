from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.fields import INT32_MAX
from apps.common.params import paginate, query_choice, query_int, query_page, query_str
from apps.logs.models import Action, ActivityLog
from apps.logs.serializers import ActivityLogSerializer


class ActivityLogView(APIView):
    """활동 로그 목록 (최근 것부터). 관리자만 본다."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        page, size = query_page(request)
        logs = ActivityLog.objects.order_by("-id")
        if action := query_choice(request, "action", Action):
            logs = logs.filter(action=action)
        if username := query_str(request, "username"):
            logs = logs.filter(username__icontains=username)
        if (report_id := query_int(request, "reportId", min_value=1, max_value=INT32_MAX)) is not None:
            logs = logs.filter(report_id=report_id)
        items, total = paginate(logs, page, size)
        return Response({"totalElements": total, "content": ActivityLogSerializer(items, many=True).data})
