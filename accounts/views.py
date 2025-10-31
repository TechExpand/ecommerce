from rest_framework import generics, status, permissions
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string

from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.permissions import IsSuperAdmin
from .serializers import (
    AcceptAdminInviteSerializer,
    AdminInviteSerializer,
    RegisterSerializer,
)
from .utils import send_email

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class LoginView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response({"detail": "Email and password are required."}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, email=email, password=password)

        if user is None:
            return Response({"detail": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({"detail": "Account not active. Please verify your OTP."}, status=status.HTTP_403_FORBIDDEN)

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response({
            "message": "Login successful.",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "phone": getattr(user, "phone", None),
            },
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
        }, status=status.HTTP_200_OK)


class VerifyOTPView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        phone = request.data.get("phone")
        otp = request.data.get("otp")
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)

        if user.otp_code == otp:
            user.is_active = True
            user.otp_code = None
            user.save()
            return Response({"message": "Account verified successfully"})
        return Response({"detail": "Invalid OTP"}, status=400)


class ResendOTPView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        phone = request.data.get("phone")
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)

        otp = get_random_string(6, allowed_chars="0123456789")
        user.otp_code = otp
        user.save()
        template = f"""
    <h2>Verify your account</h2>
    <p>Hello {user.username},</p>
    <p>Your OTP code is: <b>{user.otp_code}</b></p>
    <p>This code will expire in 10 minutes.</p>
    <p>Thank you for joining SimplyComply!</p>
    """
        # send OTP by Email
        send_email(
            user.email,
            "Your OTP Verification Code",
            template,
        )
        return Response({"message": "OTP resent successfully"})


class ChangePasswordView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def update(self, request):
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")

        if not user.check_password(old_password):
            return Response({"detail": "Incorrect old password"}, status=400)
        user.set_password(new_password)
        user.save()
        return Response({"message": "Password changed successfully"})


class ForgotPasswordView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        phone = request.data.get("phone")
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)

        otp = get_random_string(6, allowed_chars="0123456789")
        user.otp_code = otp
        user.save()
        template = f"""
    <h2>Verify your account</h2>
    <p>Hello {user.username},</p>
    <p>Your OTP code is: <b>{user.otp_code}</b></p>
    <p>This code will expire in 10 minutes.</p>
    <p>Thank you for joining SimplyComply!</p>
    """
        # send OTP by Email
        send_email(
            user.email,
            "Your OTP Verification Code",
            template,
        )
        return Response({"message": "OTP sent to your phone"})


class ResetPasswordView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        phone = request.data.get("phone")
        otp = request.data.get("otp")
        new_password = request.data.get("new_password")

        try:
            user = User.objects.get(phone=phone, otp_code=otp)
        except User.DoesNotExist:
            return Response({"detail": "Invalid OTP or phone"}, status=400)

        user.set_password(new_password)
        user.otp_code = None
        user.save()
        return Response({"message": "Password reset successful"})


class AdminInviteView(generics.CreateAPIView):
    """
    Only Super Admin can send an invitation to a new admin.
    """

    serializer_class = AdminInviteSerializer
    permission_classes = [IsSuperAdmin]


class AcceptAdminInviteView(generics.CreateAPIView):
    """
    Invited admin accepts the invitation and sets their password.
    """

    serializer_class = AcceptAdminInviteSerializer
    permission_classes = [permissions.AllowAny]
