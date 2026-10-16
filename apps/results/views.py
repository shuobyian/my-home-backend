from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import BadRequest
from apps.common.params import paginate, query_int, query_page, query_str
from apps.products.models import Category, Tool
from apps.results import services
from apps.results.presenters import present_result
from apps.results.serializers import CalculatorInputSerializer, ResultSerializer


def _query_choice(request, name, choices):
    value = query_str(request, name)
    if value is not None and value not in choices.values:
        raise BadRequest(f"{name} 값이 올바르지 않습니다. ({', '.join(choices.values)})")
    return value


class ResultView(APIView):
    def get(self, request):
        page, size = query_page(request)
        count = query_int(request, "count", default=1, min_value=1)
        queryset = services.list_results(
            name=query_str(request, "name"),
            tool=_query_choice(request, "tool", Tool),
            category=_query_choice(request, "category", Category),
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
