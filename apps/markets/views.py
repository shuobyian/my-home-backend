from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAdminOrReadOnly
from apps.markets import services
from apps.markets.serializers import MarketSerializer, MarketUpdateSerializer


class MarketView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request):
        return Response(MarketSerializer(services.list_markets(), many=True).data)

    def put(self, request):
        serializer = MarketUpdateSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        markets = services.update_markets(serializer.validated_data)
        return Response(MarketSerializer(markets, many=True).data)
