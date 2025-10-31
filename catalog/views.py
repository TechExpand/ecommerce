from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django_filters.rest_framework import DjangoFilterBackend

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
    queryset = Category.objects.filter(parent__isnull=True).prefetch_related("children")
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
        .all()
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
    queryset = Discount.objects.select_related("product", "created_by").all()
    serializer_class = DiscountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """
        Automatically link the discount to the user who created it.
        Prevents discounts for products not owned by the user.
        """
        user = self.request.user
        if user.role not in ["seller", "admin"]:
            raise PermissionDenied("Only sellers or admins can create discounts.")

        product = serializer.validated_data.get("product")
        if product.owner != user and user.role != "admin":
            raise PermissionDenied("You can only add discounts to your own products.")

        serializer.save(created_by=user)

    def perform_update(self, serializer):
        """
        Ensure only the creator or admin can edit a discount.
        """
        user = self.request.user
        instance = self.get_object()
        if user != instance.created_by and user.role != "admin":
            raise PermissionDenied("You can only update your own discounts.")
        serializer.save()

    def perform_destroy(self, instance):
        """
        Ensure only the creator or admin can delete a discount.
        """
        user = self.request.user
        if user != instance.created_by and user.role != "admin":
            raise PermissionDenied("You can only delete your own discounts.")
        instance.delete()