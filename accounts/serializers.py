from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.crypto import get_random_string
from .models import Invitation, User
from .utils import send_email, send_email
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.tokens import RefreshToken


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["username", "email", "phone", "password", "role"]

    def validate(self, data):
        role = data.get("role", "customer")

        if role not in ["seller", "customer"]:
            raise serializers.ValidationError(
                "You can only register as a seller or customer."
            )

        if role == "seller" and not data.get("phone"):
            raise serializers.ValidationError("Phone number is required for sellers.")

        return data

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        user.is_active = False  # wait for OTP verification
        user.otp_code = get_random_string(6, allowed_chars="0123456789")
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
        return user


class AdminInviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = ["email"]

    def validate(self, data):
        user = self.context["request"].user
        # Only super admins can send invites
        if not user.is_superuser:
            raise serializers.ValidationError(
                "Only super admins can invite new admins."
            )
        return data

    def create(self, validated_data):
        inviter = self.context["request"].user
        invitation = Invitation.objects.create(invited_by=inviter, **validated_data)

        # Generate acceptance link
        link = f"https://yourfrontend.com/invite/accept/?token={invitation.token}"
        subject = "You're invited to join the Easy Money Broker Admin Panel"
        template = f"""
        <h2>Admin Invitation</h2>
        <p>Hello,</p>
        <p>You’ve been invited to join the <b>Easy Money Broker Admin Panel</b>.</p>
        <p>Click below to set your password and activate your account:</p>
        <a href="{link}" target="_blank">Accept Invitation</a>
        <p>This link expires in 3 days.</p>
        """

        send_email(invitation.email, subject, template)
        return invitation
    
class AcceptAdminInviteSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)
    token = serializers.CharField(write_only=True)  # change from SerializerMethodField

    def validate(self, attrs):
        token = attrs.get("token")

        try:
            invitation = Invitation.objects.get(token=token)
        except Invitation.DoesNotExist:
            raise serializers.ValidationError("Invalid or expired invitation token.")

        if not invitation.is_valid():
            raise serializers.ValidationError("Invitation expired or already used.")

        validate_password(attrs["password"])
        attrs["invitation"] = invitation
        return attrs

    def create(self, validated_data):
        invitation = validated_data["invitation"]
        password = validated_data["password"]

        user = User.objects.create_user(
            username=invitation.email.split("@")[0],
            email=invitation.email,
            role="admin",
            is_staff=True,
            is_superuser=False,
        )
        user.set_password(password)
        user.save()

        invitation.mark_used()

        refresh = RefreshToken.for_user(user)
        return {"user": user, "token": str(refresh.access_token)}