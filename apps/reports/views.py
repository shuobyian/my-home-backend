from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.params import paginate, query_choice, query_page
from apps.reports import services
from apps.reports.models import ReportKind, ReportStatus
from apps.reports.serializers import ReportAnswerSerializer, ReportInputSerializer, ReportSerializer


class ReportListView(APIView):
    """제보 목록(최근 것부터)은 누구나 보고, 쓰기는 로그인한 회원만 한다."""

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        page, size = query_page(request)
        reports = services.list_reports(
            status=query_choice(request, "status", ReportStatus),
            kind=query_choice(request, "kind", ReportKind),
        )
        items, total = paginate(reports, page, size)
        return Response({"totalElements": total, "content": ReportSerializer(items, many=True).data})

    def post(self, request):
        serializer = ReportInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = services.create_report(request, serializer.validated_data)
        return Response(ReportSerializer(report).data, status=status.HTTP_201_CREATED)


class ReportDetailView(APIView):
    """PUT(고치기)은 쓴 사람, PATCH(처리)는 관리자, DELETE는 둘 다 할 수 있다."""

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, pk):
        return Response(ReportSerializer(services.get_report(pk)).data)

    def put(self, request, pk):
        serializer = ReportInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(ReportSerializer(services.update_report(request, pk, serializer.validated_data)).data)

    def patch(self, request, pk):
        if not request.user.is_staff:
            raise PermissionDenied("관리자만 제보를 처리할 수 있습니다.")
        serializer = ReportAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(ReportSerializer(services.answer_report(request, pk, serializer.validated_data)).data)

    def delete(self, request, pk):
        services.delete_report(request, pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
