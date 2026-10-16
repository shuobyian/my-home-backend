from django.http import HttpResponse
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.params import paginate, query_page, query_str
from apps.products import services
from apps.products.serializers import (
    ProductBulkCreateSerializer,
    ProductInputSerializer,
    ProductSerializer,
    ProductUpdateSerializer,
)


class LoginInputSerializer(serializers.Serializer):
    password = serializers.CharField(trim_whitespace=False, allow_blank=True)


class ProductIdsSerializer(serializers.ListSerializer):
    child = serializers.IntegerField()


class LoginView(APIView):
    def post(self, request):
        serializer = LoginInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.login(serializer.validated_data["password"])
        return HttpResponse("", status=status.HTTP_201_CREATED)


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
        return Response(services.delete_products(serializer.validated_data))


class ProductBulkCreateView(APIView):
    def post(self, request):
        serializer = ProductBulkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        products = services.create_products(serializer.validated_data["products"])
        return Response(ProductSerializer(products, many=True).data, status=status.HTTP_201_CREATED)
