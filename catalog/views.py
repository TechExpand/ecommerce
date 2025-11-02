from rest_framework import status, viewsets, permissions
from rest_framework.exceptions import PermissionDenied
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from catalog.models import Category, Discount, Product
from catalog.serializers import (
    CategorySerializer,
    DiscountSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
)


@method_decorator(cache_page(60 * 10), name="list")
class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Lists top-level categories (cached for 10 minutes).
    Includes nested child categories.
    """
    # FIX 1 — Only top-level categories; order by name to prevent pagination warnings
    queryset = (
        Category.objects.filter(parent__isnull=True)
        .prefetch_related("children")
        .order_by("id")
    )
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]


class ProductViewSet(viewsets.ModelViewSet):
    """
    Product CRUD operations.
    Only sellers or admins can create, update, or delete products.
    """
    queryset = (
        Product.objects.select_related("category", "owner")
        .prefetch_related("discounts")
        .order_by("id")  # FIX 2 — ensures consistent pagination ordering
    )
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["category"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        return ProductDetailSerializer

    def perform_create(self, serializer):
        """
        Automatically assign owner and restrict to sellers/admins.
        """
        user = self.request.user
        if user.role not in ["seller", "admin"]:
            raise PermissionDenied("Only sellers or admins can create products.")
        serializer.save(owner=user)

    def perform_update(self, serializer):
        """
        Ensure only the product owner or admin can update.
        """
        user = self.request.user
        instance = self.get_object()
        if user != instance.owner and user.role != "admin":
            raise PermissionDenied("You can only update your own products.")
        serializer.save()

    def perform_destroy(self, instance):
        """
        Ensure only the product owner or admin can delete.
        """
        user = self.request.user
        if user != instance.owner and user.role != "admin":
            raise PermissionDenied("You can only delete your own products.")
        instance.delete()


class DiscountViewSet(viewsets.ModelViewSet):
    """
    Discount management.
    Only sellers or admins can create discounts for their own products.
    """
    queryset = Discount.objects.select_related("product", "created_by").order_by("id")
    serializer_class = DiscountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        user = request.user

        # Enforce role before validation
        if user.role not in ["seller", "admin"]:
            raise PermissionDenied("Only sellers or admins can create discounts.")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get product and ensure ownership
        product = serializer.validated_data.get("product")
        if not product:
            raise PermissionDenied("Product must be specified.")

        if product.owner != user and user.role != "admin":
            # Return 403 instead of 400 for ownership violation
            raise PermissionDenied("You can only add discounts to your own products.")

        serializer.save(created_by=user)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        if user != instance.created_by and user.role != "admin":
            raise PermissionDenied("You can only update your own discounts.")
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if user != instance.created_by and user.role != "admin":
            raise PermissionDenied("You can only delete your own discounts.")
        instance.delete()