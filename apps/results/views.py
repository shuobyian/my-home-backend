from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.params import paginate, query_choice, query_int, query_page, query_str
from apps.common.permissions import IsAdminOrReadOnly
from apps.products.models import Category, Tool
from apps.results import services, sync
from apps.results.presenters import present_result
from apps.results.serializers import CalculatorInputSerializer, ResultSerializer

# 한 번에 계산할 수 있는 제작 개수 상한
MAX_CRAFT_COUNT = 1_000_000


class ResultView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request):
        page, size = query_page(request)
        count = query_int(request, "count", default=1, min_value=1, max_value=MAX_CRAFT_COUNT)
        queryset = services.list_results(
            name=query_str(request, "name"),
            tool=query_choice(request, "tool", Tool),
            category=query_choice(request, "category", Category),
        )
        results, total = paginate(queryset, page, size)
        return Response(
            {"totalElements": total, "content": [present_result(result, count=count) for result in results]}
        )

    def post(self, request):
        # 전체 동기화: 빠진 결과를 만들고 낡은 결과를 제자리에서 고친다. 응답은 이번에 새로 만든 결과 행만이다.
        report = sync.sync_all_results()
        return Response(ResultSerializer(report.created, many=True).data, status=status.HTTP_201_CREATED)


class CalculatorView(APIView):
    def post(self, request):
        serializer = CalculatorInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        prices = {market["name"]: market["price"] for market in serializer.validated_data["markets"]}
        results = [present_result(result, sheet) for result, sheet in services.preview_results(prices)]
        return Response({"results": results}, status=status.HTTP_201_CREATED)
