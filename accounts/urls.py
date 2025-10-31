from django.urls import path
from .views import (
    AcceptAdminInviteView, AdminInviteView, RegisterView,
    VerifyOTPView, ResendOTPView, LoginView,
    ForgotPasswordView, ResetPasswordView, ChangePasswordView
)
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("resend-otp/", ResendOTPView.as_view(), name="resend-otp"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("invite/admin/", AdminInviteView.as_view(), name="invite-admin"),
    path("invite/admin/accept/", AcceptAdminInviteView.as_view(), name="accept-admin-invite"),
]
