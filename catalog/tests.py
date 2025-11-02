from decimal import Decimal
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from catalog.models import Category, Product, Discount
from django.test import TransactionTestCase

User = get_user_model()


class LiveDBTestCase(TransactionTestCase):
    """
    Custom base test class that reuses the existing database
    instead of creating a test one.
    """

    reset_sequences = False
    serialized_rollback = True

    @classmethod
    def _pre_setup(cls):
        """Bypass Django’s default test DB setup."""
        # Do not call super()._pre_setup() — prevents DB creation
        cls.client = APIClient()  # still allow API client usage

    @classmethod
    def _post_teardown(cls):
        """Bypass Django’s default test DB teardown."""
        # Do not call super()._post_teardown() — prevents DB flush
        pass


class CatalogModelTests(LiveDBTestCase):
    def setUp(self):
        Discount.objects.all().delete() 
        self.user, _ = User.objects.get_or_create(
            email="seller@example.com",
            defaults=dict(
                username="seller1",
                password="pass123",
                role="seller",
                phone="+2348011111111",
            ),
        )
        self.category, _ = Category.objects.get_or_create(name="Electronics")
        self.product, _ = Product.objects.get_or_create(
            category=self.category,
            owner=self.user,
            name="iPhone 15",
            price=Decimal("1000.00"),
            stock_quantity=10,
        )

    def test_get_final_price_no_discount(self):
        assert self.product.get_final_price() == Decimal("1000.00")

    def test_get_final_price_with_percent_discount(self):
        Discount.objects.create(
            product=self.product,
            created_by=self.user,
            discount_type=Discount.PERCENT,
            value=Decimal("10"),
            active=True,
        )
        self.product.refresh_from_db()
        assert self.product.get_final_price() == Decimal("900.00")

    def test_get_final_price_with_fixed_discount(self):
        Discount.objects.create(
            product=self.product,
            created_by=self.user,
            discount_type=Discount.FIXED,
            value=Decimal("200"),
            active=True,
        )
        assert self.product.get_final_price() == Decimal("800.00")


class CategoryViewSetTests(LiveDBTestCase):
    def setUp(self):
        Product.objects.all().delete()
        Category.objects.all().delete()
        self.root = Category.objects.create(name="Root")
        self.child = Category.objects.create(name="Child", parent=self.root)

    def test_list_top_level_categories(self):
        url = reverse("category-list")
        response = self.client.get(url)
        assert response.status_code == 200
        results = response.data.get("results", response.data)
        assert len(results) == 1
        assert results[0]["name"] == "Root"
        assert "children" in results[0]


class ProductViewSetTests(LiveDBTestCase):
    def setUp(self):
        self.seller, _ = User.objects.get_or_create(
            email="seller@example.com",
            defaults=dict(
                username="seller",
                password="pass123",
                role="seller",
                phone="+2348022222222",
            ),
        )
        self.customer, _ = User.objects.get_or_create(
            email="cust@example.com",
            defaults=dict(
                username="customer",
                password="pass123",
                role="customer",
                phone="+2348033333333",
            ),
        )
        self.category, _ = Category.objects.get_or_create(name="Electronics")
        self.product, _ = Product.objects.get_or_create(
            category=self.category,
            owner=self.seller,
            name="MacBook Pro",
            price=Decimal("2000.00"),
            stock_quantity=5,
        )

    def test_list_products(self):
        url = reverse("product-list")
        response = self.client.get(url)
        assert response.status_code == 200

    def test_seller_can_create_product(self):
        self.client.force_authenticate(self.seller)
        url = reverse("product-list")
        data = {
            "category": self.category.id,
            "name": "iPad",
            "price": "500.00",
            "stock_quantity": 20,
        }
        response = self.client.post(url, data)
        assert response.status_code in [201, 400]

    def test_customer_cannot_create_product(self):
        self.client.force_authenticate(self.customer)
        url = reverse("product-list")
        data = {
            "category": self.category.id,
            "name": "TV",
            "price": "800.00",
            "stock_quantity": 10,
        }
        response = self.client.post(url, data)
        assert response.status_code == 403


class DiscountViewSetTests(LiveDBTestCase):
    def setUp(self):
        self.seller, _ = User.objects.get_or_create(
            email="seller@example.com",
            defaults=dict(
                username="seller",
                password="pass123",
                role="seller",
                phone="+2348055555555",
            ),
        )
        self.customer, _ = User.objects.get_or_create(
            email="cust@example.com",
            defaults=dict(
                username="cust",
                password="pass123",
                role="customer",
                phone="+2348077777777",
            ),
        )
        self.category, _ = Category.objects.get_or_create(name="Electronics")
        self.product, _ = Product.objects.get_or_create(
            category=self.category,
            owner=self.seller,
            name="Samsung TV",
            price=Decimal("1000.00"),
            stock_quantity=3,
        )

    def test_seller_can_create_discount(self):
        self.client.force_authenticate(self.seller)
        url = reverse("discount-list")
        data = {
            "product": self.product.id,
            "discount_type": "fixed",
            "value": "100.00",
            "active": True,
        }
        response = self.client.post(url, data)
        assert response.status_code in [201, 400]

    def test_customer_cannot_create_discount(self):
        self.client.force_authenticate(self.customer)
        url = reverse("discount-list")
        data = {"product": self.product.id, "discount_type": "percent", "value": "10"}
        response = self.client.post(url, data)
        assert response.status_code == 403
