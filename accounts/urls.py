from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CustomTokenObtainPairView, CookieTokenRefreshView, LogoutView,
    UserViewSet, RoleViewSet, PermissionViewSet,
    RequestPasswordResetView, PasswordResetValidateView, PasswordResetConfirmView,
)

router = DefaultRouter()
router.register(r'users',       UserViewSet,       basename='user')
router.register(r'roles',       RoleViewSet,       basename='role')
router.register(r'permissions', PermissionViewSet, basename='permission')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include(router.urls)),


    # JWT
    path('auth/token/',         CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', CookieTokenRefreshView.as_view(),    name='token_refresh'),
    path('auth/logout/',        LogoutView.as_view(),                 name='logout'),

    # ✅ Reset password — préfixe cohérent, sans slash initial
    path('auth/password-reset/request/',
         RequestPasswordResetView.as_view(),  name='password_reset_request'),

    path('auth/password-reset/validate/<str:uidb64>/<str:token>/',
         PasswordResetValidateView.as_view(), name='password_reset_validate'),

    path('auth/password-reset/confirm/',
         PasswordResetConfirmView.as_view(),  name='password_reset_confirm'),
]
