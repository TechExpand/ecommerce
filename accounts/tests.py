from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.utils.crypto import get_random_string
from accounts.models import User, Invitation


class RegisterTests(APITestCase):
    def test_register_customer_successfully(self):
        """Customer can register successfully with valid data."""
        url = reverse("register")
        data = {
            "username": "john_doe",
            "email": "john@example.com",
            "phone": "+2348012345678",
            "password": "strongpass123",
            "role": "customer",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="john@example.com").exists())

    def test_register_without_phone_for_seller_fails(self):
        """Seller registration should fail without phone."""
        url = reverse("register")
        data = {
            "username": "sellsomething",
            "email": "seller@example.com",
            "password": "strongpass123",
            "role": "seller",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Phone number is required", str(response.data))


class OTPVerificationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            phone="08012345678",
            password="testpass123",
            role="customer",
            is_active=False,
        )
        self.user.otp_code = "123456"
        self.user.save()

    def test_verify_correct_otp(self):
        url = reverse("verify-otp")
        response = self.client.post(url, {"phone": "08012345678", "otp": "123456"})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertIsNone(self.user.otp_code)

    def test_verify_wrong_otp(self):
        url = reverse("verify-otp")
        response = self.client.post(url, {"phone": "08012345678", "otp": "999999"})
        self.assertEqual(response.status_code, 400)

    def test_resend_otp(self):
        url = reverse("resend-otp")
        response = self.client.post(url, {"phone": "08012345678"})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.otp_code)


class LoginTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="loginuser",
            email="login@example.com",
            password="testpass123",
            phone="08011112222",
            is_active=True,
        )

    def test_login_success(self):
        url = reverse("login")
        response = self.client.post(url, {"email": "login@example.com", "password": "testpass123"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data["tokens"])

    def test_login_wrong_password(self):
        url = reverse("login")
        response = self.client.post(url, {"email": "login@example.com", "password": "wrongpass"})
        self.assertEqual(response.status_code, 401)


class ForgotAndResetPasswordTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="forgotuser",
            email="forgot@example.com",
            phone="08100000000",
            password="oldpass123",
            role="customer",
            is_active=True,
        )

    def test_forgot_password_generates_otp(self):
        url = reverse("forgot-password")
        response = self.client.post(url, {"phone": "08100000000"})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.otp_code)

    def test_reset_password_success(self):
        otp = get_random_string(6, allowed_chars="0123456789")
        self.user.otp_code = otp
        self.user.save()
        url = reverse("reset-password")
        data = {"phone": "08100000000", "otp": otp, "new_password": "newpass123"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass123"))


class ChangePasswordTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="changepass",
            email="changepass@example.com",
            password="oldpass123",
            phone="08133333333",
            is_active=True,
        )
        self.client.force_authenticate(self.user)

    def test_change_password_success(self):
        url = reverse("change-password")
        data = {"old_password": "oldpass123", "new_password": "newpass456"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass456"))


class AdminInviteTests(APITestCase):
    def setUp(self):
        self.super_admin = User.objects.create_superuser(
            username="super",
            email="super@example.com",
            password="superpass123"
        )
        self.client.force_authenticate(self.super_admin)

    def test_superadmin_can_invite_admin(self):
        url = reverse("invite-admin")
        data = {"email": "newadmin@example.com"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Invitation.objects.filter(email="newadmin@example.com").exists())

    def test_non_superadmin_cannot_invite(self):
        user = User.objects.create_user(phone="09075214442", username="normal", email="normal@example.com", password="1234")
        client = APIClient()
        client.force_authenticate(user)
        url = reverse("invite-admin")
        response = client.post(url, {"email": "blocked@example.com"})
        self.assertEqual(response.status_code, 403)


class AcceptAdminInviteTests(APITestCase):
    def setUp(self):
        inviter = User.objects.create_superuser(username="super", email="super@example.com", password="superpass123")
        self.invite = Invitation.objects.create(
            email="invited@example.com",
            invited_by=inviter
        )

    def test_accept_invite_success(self):
        url = reverse("accept-admin-invite")
        data = {"token": str(self.invite.token), "password": "newadminpass"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 201)
        self.invite.refresh_from_db()
        self.assertTrue(self.invite.is_used)
        self.assertTrue(User.objects.filter(email="invited@example.com").exists())

    def test_accept_invalid_invite(self):
        url = reverse("accept-admin-invite")
        data = {"token": "00000000-0000-0000-0000-000000000000", "password": "failpass"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 400)