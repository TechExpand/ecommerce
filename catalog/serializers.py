from decimal import Decimal
from rest_framework import serializers
from django.utils import timezone
from .models import Category, Product, Discount


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "description", "parent", "children")

    def get_children(self, obj):
        qs = obj.children.all()
        return CategorySerializer(qs, many=True).data


class DiscountSerializer(serializers.ModelSerializer):
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = Discount
        fields = "__all__"
        read_only_fields = ("created_by",)

    def validate(self, data):
        if data["discount_type"] == Discount.PERCENT and data["value"] > Decimal("100"):
            raise serializers.ValidationError("Percent discount cannot exceed 100.")

        start_at = data.get("start_at")
        end_at = data.get("end_at")
        if start_at and end_at and end_at < start_at:
            raise serializers.ValidationError("End date must be after start date.")
        return data

class ProductListSerializer(serializers.ModelSerializer):
    final_price = serializers.SerializerMethodField()
    owner = serializers.ReadOnlyField(source='owner.username')
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Product
        fields = ('id', 'name', 'price', 'final_price', 'stock_quantity', 'category', 'category_name', 'owner')

    def get_final_price(self, obj):
        return obj.get_final_price()


class ProductDetailSerializer(ProductListSerializer):
    discounts = DiscountSerializer(many=True, read_only=True)

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + (
            'description', 'created', 'discounts'
        )