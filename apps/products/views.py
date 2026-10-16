from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.params import paginate, query_page, query_str
from apps.products import services
from apps.products.serializers import (
    ProductBulkCreateSerializer,
    ProductIdsSerializer,
    ProductInputSerializer,
    ProductSerializer,
    ProductUpdateSerializer,
)


class ProductView(APIView):
    def get(self, request):
        page, size = query_page(request)
        products, total = paginate(services.list_products(name=query_str(request, "name")), page, size)
        return Response({"totalElements": total, "content": ProductSerializer(products, many=True).data})

    def post(self, request):
        serializer = ProductInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = services.create_product(serializer.validated_data)
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)

    def put(self, request):
        serializer = ProductUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = services.update_product(serializer.validated_data)
        return Response(ProductSerializer(product).data)

    def delete(self, request):
        serializer = ProductIdsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        deleted = services.delete_products(ids)
        # 기존 TypeORM DeleteResult 모양({raw, affected})을 요청한 id마다 (순서·중복 그대로) 돌려준다.
        return Response([{"raw": [], "affected": 1 if product_id in deleted else 0} for product_id in ids])


class ProductBulkCreateView(APIView):
    def post(self, request):
        serializer = ProductBulkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        products = services.bulk_create_products(serializer.validated_data["products"])
        return Response(ProductSerializer(products, many=True).data, status=status.HTTP_201_CREATED)
