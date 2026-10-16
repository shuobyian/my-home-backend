from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.params import paginate, query_choice, query_int, query_page, query_str
from apps.products.models import Category, Tool
from apps.results import services
from apps.results.presenters import present_result
from apps.results.serializers import CalculatorInputSerializer, ResultSerializer

# 한 번에 계산할 수 있는 제작 개수 상한
MAX_CRAFT_COUNT = 1_000_000


class ResultView(APIView):
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
        results = services.create_missing_results()
        return Response(ResultSerializer(results, many=True).data, status=status.HTTP_201_CREATED)


class CalculatorView(APIView):
    def post(self, request):
        serializer = CalculatorInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        prices = {market["name"]: market["price"] for market in serializer.validated_data["markets"]}
        return Response({"results": services.preview_results(prices)}, status=status.HTTP_201_CREATED)
