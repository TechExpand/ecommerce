from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from catalog.models import Category, Product, Discount

User = get_user_model()


class CatalogModelTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="seller1",
            email="seller@example.com",
            password="pass123",
            role="seller",
            phone="+2348011111111",
        )
        self.category = Category.objects.create(name="Electronics")
        self.product = Product.objects.create(
            category=self.category,
            owner=self.user,
            name="iPhone 15",
            price=Decimal("1000.00"),
            stock_quantity=10,
        )

    def test_get_final_price_no_discount(self):
        self.assertEqual(self.product.get_final_price(), Decimal("1000.00"))

    def test_get_final_price_with_percent_discount(self):
        Discount.objects.create(
            product=self.product,
            created_by=self.user,
            discount_type=Discount.PERCENT,
            value=Decimal("10"),
        )
        self.assertEqual(self.product.get_final_price(), Decimal("900.00"))

    def test_get_final_price_with_fixed_discount(self):
        Discount.objects.create(
            product=self.product,
            created_by=self.user,
            discount_type=Discount.FIXED,
            value=Decimal("200"),
        )
        self.assertEqual(self.product.get_final_price(), Decimal("800.00"))

    def test_category_str(self):
        self.assertEqual(str(self.category), "Electronics")

    def test_product_str(self):
        self.assertEqual(str(self.product), "iPhone 15")


class CategoryViewSetTests(APITestCase):
    def setUp(self):
        Category.objects.all().delete()  # ensures consistent count
        self.root = Category.objects.create(name="Root")
        self.child = Category.objects.create(name="Child", parent=self.root)


    def test_list_top_level_categories(self):
         url = reverse("category-list")
         response = self.client.get(url)
         self.assertEqual(response.status_code, 200)
         results = response.data.get("results", response.data)
         self.assertEqual(len(results), 1)
         self.assertEqual(results[0]["name"], "Root")
         self.assertTrue("children" in results[0])


class ProductViewSetTests(APITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            username="seller",
            email="seller@example.com",
            password="pass123",
            role="seller",
            phone="+2348022222222",
        )
        self.customer = User.objects.create_user(
            username="customer",
            email="cust@example.com",
            password="pass123",
            role="customer",
            phone="+2348033333333",
        )
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="pass123",
            role="admin",
            phone="+2348044444444",
        )
        self.category = Category.objects.create(name="Electronics")
        self.product = Product.objects.create(
            category=self.category,
            owner=self.seller,
            name="MacBook Pro",
            price=Decimal("2000.00"),
            stock_quantity=5,
        )

    def test_list_products(self):
        url = reverse("product-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)

    def test_seller_can_create_product(self):
        client = APIClient()
        client.force_authenticate(self.seller)
        url = reverse("product-list")
        data = {
            "category": self.category.id,
            "name": "iPad",
            "price": "500.00",
            "stock_quantity": 20,
        }
        response = client.post(url, data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Product.objects.count(), 2)

    def test_customer_cannot_create_product(self):
        client = APIClient()
        client.force_authenticate(self.customer)
        url = reverse("product-list")
        data = {
            "category": self.category.id,
            "name": "TV",
            "price": "800.00",
            "stock_quantity": 10,
        }
        response = client.post(url, data)
        self.assertEqual(response.status_code, 403)

    def test_owner_can_update_product(self):
        client = APIClient()
        client.force_authenticate(self.seller)
        url = reverse("product-detail", args=[self.product.id])
        data = {"name": "MacBook Air"}
        response = client.patch(url, data)
        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "MacBook Air")

    def test_non_owner_cannot_update_product(self):
        client = APIClient()
        client.force_authenticate(self.customer)
        url = reverse("product-detail", args=[self.product.id])
        data = {"name": "Hackbook"}
        response = client.patch(url, data)
        self.assertEqual(response.status_code, 403)


class DiscountViewSetTests(APITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            username="seller",
            email="seller@example.com",
            password="pass123",
            role="seller",
            phone="+2348055555555",
        )
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="pass123",
            role="admin",
            phone="+2348066666666",
        )
        self.customer = User.objects.create_user(
            username="cust",
            email="cust@example.com",
            password="pass123",
            role="customer",
            phone="+2348077777777",
        )
        self.category = Category.objects.create(name="Electronics")
        self.product = Product.objects.create(
            category=self.category,
            owner=self.seller,
            name="Samsung TV",
            price=Decimal("1000.00"),
            stock_quantity=3,
        )

    def test_seller_can_create_discount(self):
        client = APIClient()
        client.force_authenticate(self.seller)
        url = reverse("discount-list")
        data = {
            "product": self.product.id,
            "discount_type": "fixed",
            "value": "100.00",
            "active": True,
        }
        response = client.post(url, data)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Discount.objects.exists())

    def test_customer_cannot_create_discount(self):
        client = APIClient()
        client.force_authenticate(self.customer)
        url = reverse("discount-list")
        data = {"product": self.product.id, "discount_type": "percent", "value": "10"}
        response = client.post(url, data)
        self.assertEqual(response.status_code, 403)

    def test_validate_percent_over_100_fails(self):
        client = APIClient()
        client.force_authenticate(self.seller)
        url = reverse("discount-list")
        data = {"product": self.product.id, "discount_type": "percent", "value": "150"}
        response = client.post(url, data)
        self.assertEqual(response.status_code, 400)

    def test_non_owner_cannot_create_discount_on_other_product(self):
        other_seller = User.objects.create_user(
            username="seller2",
            email="seller2@example.com",
            password="pass123",
            role="seller",
            phone="+2348088888888",
        )
        client = APIClient()
        client.force_authenticate(other_seller)
        url = reverse("discount-list")
        data = {"product": self.product.id, "discount_type": "fixed", "value": "50"}
        response = client.post(url, data)
        self.assertEqual(response.status_code, 403)
