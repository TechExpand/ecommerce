from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
import uuid

class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    is_verified = models.BooleanField(default=False)

    otp_code = models.CharField(max_length=6, blank=True, null=True)
    otp_reference_id = models.UUIDField(blank=True, null=True, editable=False)
    otp_created_at = models.DateTimeField(blank=True, null=True)

    ROLE_CHOICES = [
        ("customer", "Customer"),
        ("seller", "Seller"),
        ("admin", "Admin"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="customer")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def clean(self):
        if self.role in ["seller", "customer"] and not self.phone and not self.is_superuser:
            raise ValidationError({"phone": "Phone number is required for sellers and customers."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def generate_otp(self):
        """Generates a new OTP and reference ID."""
        from random import randint

        self.otp_code = str(randint(100000, 999999))
        self.otp_reference_id = uuid.uuid4()
        self.otp_created_at = timezone.now()
        self.save(update_fields=["otp_code", "otp_reference_id", "otp_created_at"])
        return self.otp_reference_id, self.otp_code

    def verify_otp(self, otp, reference_id):
        """Validates OTP and reference ID."""
        if str(self.otp_reference_id) != str(reference_id):
            return False, "Invalid or expired OTP session"
        if self.otp_code != otp:
            return False, "Invalid OTP"
        if self.otp_created_at and timezone.now() > self.otp_created_at + timedelta(minutes=10):
            return False, "OTP expired"
        return True, "Verified"

    def __str__(self):
        return f"{self.username} ({self.role})"




def default_expires_at():
    return timezone.now() + timedelta(days=3)


class Invitation(models.Model):
    email = models.EmailField(unique=True)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_admin_invitations",
    )
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_expires_at)

    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()

    def mark_used(self):
        self.is_used = True
        self.save(update_fields=["is_used"])

    def __str__(self):
        return f"Admin invite for {self.email}"
