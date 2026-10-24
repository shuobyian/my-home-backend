from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inventories import services
from apps.inventories.serializers import InventoryItemSerializer, InventoryUpdateSerializer


class InventoryView(APIView):
    """로그인한 회원 본인의 보유 재료."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(InventoryItemSerializer(services.list_inventory(request.user), many=True).data)

    def put(self, request):
        serializer = InventoryUpdateSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        inventory = services.update_inventory(request.user, serializer.validated_data)
        return Response(InventoryItemSerializer(inventory, many=True).data)
