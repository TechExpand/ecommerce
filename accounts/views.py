from django.utils import timezone
import uuid
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from drf_spectacular.utils import extend_schema
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.permissions import IsSuperAdmin
from .serializers import (
    AcceptAdminInviteSerializer,
    AdminInviteSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    RegisterSerializer,
    ResendOTPSerializer,
    ResetPasswordSerializer,
    VerifyOTPSerializer,
)
from .utils import send_email


User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
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
    serializer_class = VerifyOTPSerializer

    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")
        reference_id = request.data.get("reference_id")

        if not all([email, otp, reference_id]):
            return Response({"detail": "Email, OTP, and reference_id are required."}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)

        # Use model’s built-in method for verification
        is_valid, message = user.verify_otp(otp, reference_id)

        if not is_valid:
            return Response({"detail": message}, status=400)

        # OTP is valid → activate user
        user.is_active = True
        user.otp_code = None
        user.otp_reference_id = None
        user.otp_created_at = None
        user.save(update_fields=["is_active", "otp_code", "otp_reference_id", "otp_created_at"])

        return Response({"message": "Account verified successfully"}, status=200)

class ResendOTPView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ResendOTPSerializer

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response({"detail": "Email is required"}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)

        # Generate new OTP and reference ID
        otp = get_random_string(6, allowed_chars="0123456789")
        reference_id = uuid.uuid4()

        user.otp_code = otp
        user.otp_reference_id = reference_id
        user.otp_created_at = timezone.now()
        user.save(update_fields=["otp_code", "otp_reference_id", "otp_created_at"])

        # Build email content
        template = f"""
            <h2>Verify your account</h2>
            <p>Hello {user.username},</p>
            <p>Your new OTP code is: <b>{otp}</b></p>
            <p>This code will expire in 10 minutes.</p>
            <p>Thank you for joining SimplyComply!</p>
        """

        # Send OTP email
        send_email(
            user.email,
            "Your OTP Verification Code",
            template,
        )

        return Response({
            "message": "OTP resent successfully",
            "reference_id": str(reference_id)
        }, status=status.HTTP_200_OK)


class ChangePasswordView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    @extend_schema(
        summary="Change user password",
        description="Allows an authenticated user to change their password by providing the old and new passwords.",
        request=ChangePasswordSerializer,
        responses={
            200: {"message": "Password changed successfully"},
            400: {"detail": "Incorrect old password or validation error"},
        },
        methods=["POST"],
        auth=["jwtAuth"],
        tags=["auth"],
    )
    def post(self, request):
        """Change the user's password (POST only)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response({"detail": "Incorrect old password"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return Response({"message": "Password changed successfully"}, status=status.HTTP_200_OK)


class ForgotPasswordView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ForgotPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)

        # Generate new OTP + reference ID
        reference_id, otp = user.generate_otp()

        template = f"""
            <h2>Reset Your Password</h2>
            <p>Hello {user.username},</p>
            <p>Your password reset OTP code is: <b>{otp}</b></p>
            <p>This code will expire in 10 minutes.</p>
            <p>Thank you for using SimplyComply!</p>
        """

        send_email(
            user.email,
            "Your Password Reset Code",
            template,
        )

        return Response({
            "message": "OTP sent successfully to your email",
            "reference_id": str(reference_id)
        })

class ResetPasswordView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ResetPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]
        reference_id = serializer.validated_data["reference_id"]
        new_password = serializer.validated_data["new_password"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)

        # Use your model’s verify_otp method
        is_valid, message = user.verify_otp(otp, reference_id)
        if not is_valid:
            return Response({"detail": message}, status=400)

        user.set_password(new_password)
        user.otp_code = None
        user.otp_reference_id = None
        user.otp_created_at = None
        user.save(update_fields=["password", "otp_code", "otp_reference_id", "otp_created_at"])

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
