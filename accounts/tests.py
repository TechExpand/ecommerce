from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from accounts.models import Invitation
import uuid

User = get_user_model()


class RegisterTests(APITestCase):
    def test_register_customer_with_phone(self):
        """Customer registration works when phone is provided"""
        url = reverse("register")
        data = {
            "username": "customer1",
            "email": "customer1@example.com",
            "password": "testpass123",
            "phone": "+2348012345678",
            "role": "customer",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="customer1@example.com").exists())

    def test_register_customer_without_phone_fails(self):
        """Customer registration should fail if phone is missing"""
        url = reverse("register")
        data = {
            "username": "customer2",
            "email": "customer2@example.com",
            "password": "testpass123",
            "role": "customer",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone", str(response.data))

    def test_register_seller_without_phone_fails(self):
        """Seller registration should fail if phone is missing"""
        url = reverse("register")
        data = {
            "username": "seller1",
            "email": "seller1@example.com",
            "password": "testpass123",
            "role": "seller",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone", str(response.data))

    def test_register_invalid_role_fails(self):
        """Invalid role should not be accepted"""
        url = reverse("register")
        data = {
            "username": "random_user",
            "email": "random@example.com",
            "password": "testpass123",
            "role": "invalidrole",
            "phone": "+2348012345678",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class OTPTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="otp_user",
            email="otp@example.com",
            password="password123",
            phone="+2348011111111",
            role="customer",
            is_active=False,
        )
        self.user.generate_otp()

    def test_verify_valid_otp(self):
        """Ensure valid OTP verification activates user"""
        url = reverse("verify-otp")
        response = self.client.post(
            url,
            {
                "email": self.user.email,
                "otp": self.user.otp_code,
                "reference_id": str(self.user.otp_reference_id),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_verify_invalid_otp(self):
        """Invalid OTP should fail"""
        url = reverse("verify-otp")
        response = self.client.post(
            url,
            {
                "email": self.user.email,
                "otp": "999999",
                "reference_id": str(self.user.otp_reference_id),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resend_otp(self):
        """Ensure OTP resend regenerates code"""
        url = reverse("resend-otp")
        response = self.client.post(url, {"email": self.user.email})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("reference_id", response.data)


class LoginTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="login_user",
            email="login@example.com",
            password="password123",
            phone="+2348099999999",
            role="customer",
            is_active=True,
        )

    def test_login_successful(self):
        """Ensure login succeeds for active user"""
        url = reverse("login")
        response = self.client.post(
            url, {"email": "login@example.com", "password": "password123"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", response.data)

    def test_login_invalid_password(self):
        """Ensure invalid password fails"""
        url = reverse("login")
        response = self.client.post(
            url, {"email": "login@example.com", "password": "wrongpass"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_unverified_user(self):
        """Ensure unverified users can't log in"""
        user = User.objects.create_user(
            username="unverified",
            email="unverified@example.com",
            password="password123",
            role="customer",
            phone="+2348088888888",
            is_active=False,
        )
        url = reverse("login")
        response = self.client.post(
            url, {"email": "unverified@example.com", "password": "password123"}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PasswordResetTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reset_user",
            email="reset@example.com",
            password="password123",
            is_active=True,
            phone="+2348022222222",
            role="customer",
        )
        self.user.generate_otp()

    def test_forgot_password(self):
        """Forgot password sends OTP"""
        url = reverse("forgot-password")
        response = self.client.post(url, {"email": self.user.email})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("reference_id", response.data)

    def test_reset_password_valid(self):
        """Ensure valid reset OTP allows password change"""
        url = reverse("reset-password")
        response = self.client.post(
            url,
            {
                "email": self.user.email,
                "otp": self.user.otp_code,
                "reference_id": str(self.user.otp_reference_id),
                "new_password": "newpass456",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass456"))

    def test_reset_password_invalid_otp(self):
        """Invalid OTP should fail password reset"""
        url = reverse("reset-password")
        response = self.client.post(
            url,
            {
                "email": self.user.email,
                "otp": "000000",
                "reference_id": str(self.user.otp_reference_id),
                "new_password": "newpass456",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AdminInviteTests(APITestCase):
    def setUp(self):
        self.super_admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="admin123"
        )
        self.client.force_authenticate(self.super_admin)

    def test_invite_admin_successfully(self):
        """Ensure superadmin can invite a new admin"""
        url = reverse("invite-admin")
        response = self.client.post(url, {"email": "newadmin@example.com"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Invitation.objects.filter(email="newadmin@example.com").exists())

    def test_non_super_admin_cannot_invite(self):
        """Ensure normal user cannot invite"""
        normal_user = User.objects.create_user(
            username="normal",
            email="normal@example.com",
            password="password123",
            role="customer",
            phone="+2348077777777",
        )
        self.client.force_authenticate(normal_user)
        url = reverse("invite-admin")
        response = self.client.post(url, {"email": "noadmin@example.com"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AcceptAdminInviteTests(APITestCase):
    def setUp(self):
        # Create inviter user to satisfy FK constraint
        self.inviter = User.objects.create_superuser(
            username="superinviter",
            email="superinviter@example.com",
            password="admin123",
        )
        # Create invitation with valid invited_by reference
        self.invite = Invitation.objects.create(
            email="invited@example.com",
            invited_by=self.inviter,
        )

    def test_accept_valid_invite(self):
        """Ensure invited admin can accept valid invite"""
        url = reverse("accept-admin-invite")
        response = self.client.post(
            url,
            {"token": str(self.invite.token), "password": "securePass123"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="invited@example.com").exists())

    def test_accept_invalid_token(self):
        """Invalid token should fail"""
        url = reverse("accept-admin-invite")
        response = self.client.post(
            url,
            {"token": str(uuid.uuid4()), "password": "securePass123"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
