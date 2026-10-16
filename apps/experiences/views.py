from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.fields import INT32_MAX
from apps.common.params import query_int, query_number
from apps.experiences import services
from apps.experiences.serializers import ExperienceSerializer

# 생산 경험치 증가율(%) 상한
MAX_PRODUCTION_PERCENT = 10_000


class ExperienceView(APIView):
    def get(self, request):
        return Response(ExperienceSerializer(services.list_experiences(), many=True).data)


class WalnutView(APIView):
    def get(self, request):
        return Response(
            services.walnut(
                present_level=query_int(request, "presentLevel", required=True, max_value=INT32_MAX),
                present_experience=query_int(request, "presentExperience", default=0, min_value=0, max_value=INT32_MAX),
                objective_level=query_int(request, "objectiveLevel", max_value=INT32_MAX),
                production_percent=query_number(
                    request,
                    "productionPercent",
                    default=services.DEFAULT_PRODUCTION_PERCENT,
                    min_value=0,
                    max_value=MAX_PRODUCTION_PERCENT,
                ),
            )
        )
