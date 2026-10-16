from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.params import query_int, query_number
from apps.experiences import services
from apps.experiences.models import Experience


class ExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experience
        fields = ["id", "level", "amount"]


class ExperienceView(APIView):
    def get(self, request):
        return Response(ExperienceSerializer(services.list_experiences(), many=True).data)


class WalnutView(APIView):
    def get(self, request):
        return Response(
            services.walnut(
                present_level=query_int(request, "presentLevel", required=True),
                present_experience=query_int(request, "presentExperience", default=0, min_value=0),
                objective_level=query_int(request, "objectiveLevel"),
                production_percent=query_number(
                    request, "productionPercent", default=services.DEFAULT_PRODUCTION_PERCENT, min_value=0
                ),
            )
        )
