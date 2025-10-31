from datetime import timedelta, timezone
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from django.conf import settings
import uuid


class User(AbstractUser):
    """
    Custom user model extending Django's AbstractUser.
    Adds role-based logic and phone validation.
    """

    email = models.EmailField(unique=True)

    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("seller", "Seller"),
        ("customer", "Customer"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="customer")

    phone = models.CharField(max_length=20, blank=True, null=True)

    def clean(self):
        """
        Ensure phone number is required for sellers and customers.
        """
        if self.role in ["seller", "customer"] and not self.phone:
            raise ValidationError(
                {"phone": "Phone number is required for sellers and customers."}
            )

    def save(self, *args, **kwargs):
        # Run validation before saving
        self.full_clean()
        super().save(*args, **kwargs)

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
    expires_at = models.DateTimeField(
        default=default_expires_at
    )  # use named function

    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()

    def mark_used(self):
        self.is_used = True
        self.save(update_fields=["is_used"])

    def __str__(self):
        return f"Admin invite for {self.email}"
