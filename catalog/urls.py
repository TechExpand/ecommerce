from rest_framework.routers import DefaultRouter
from django.urls import path, include

from catalog.views import CategoryViewSet, DiscountViewSet, ProductViewSet

router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='category')
router.register('products', ProductViewSet, basename='product')
router.register('discounts', DiscountViewSet, basename='discount')

# This exposes the router URLs as urlpatterns
urlpatterns = [
    path('', include(router.urls)),
]
