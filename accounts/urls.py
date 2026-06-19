# accounts/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
 
from .views import (
    CustomTokenObtainPairView,
    CookieTokenRefreshView,
    LogoutView,
    UserViewSet,
    SuperAdminUserViewSet,
    RoleViewSet,
    PermissionViewSet,
    RequestPasswordResetView,
    PasswordResetValidateView,
    PasswordResetConfirmView,
    PasswordResetTotpVerifyView,
)
 
router = DefaultRouter()
router.register(r'users',      UserViewSet,          basename='user')
router.register(r'superadmin/users', SuperAdminUserViewSet, basename='superadmin-user')
router.register(r'roles',      RoleViewSet,          basename='role')
router.register(r'permissions', PermissionViewSet,   basename='permission')
 
urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────
    path('auth/login/',         CustomTokenObtainPairView.as_view(),  name='token_obtain'),
    path('auth/refresh/',       CookieTokenRefreshView.as_view(),     name='token_refresh'),
    path('auth/logout/',        LogoutView.as_view(),                 name='logout'),
 
    # ── Reset password (TOTP requis ici si activé) ────────────
    path('auth/password-reset/',
         RequestPasswordResetView.as_view(), name='password_reset_request'),
    path('auth/password-reset/validate/<uidb64>/<token>/',
         PasswordResetValidateView.as_view(), name='password_reset_validate'),
    path('auth/password-reset/confirm/',
         PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
 
    path('auth/password-reset/verify-totp/',
         PasswordResetTotpVerifyView.as_view(), name='password_reset_verify_totp'),
    # ── ViewSets ──────────────────────────────────────────────
    path('auth/', include(router.urls)),
]