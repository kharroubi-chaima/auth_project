# auth_project/urls.py
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from accounts.views import CookieTokenRefreshView, CustomTokenObtainPairView, LogoutView
from rest_framework_simplejwt.views import TokenBlacklistView


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    #path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/localisations/', include('localisations.urls')),
    path('api/', include('pharmacies.urls')),
    path('api/token/logout/',  LogoutView.as_view()),  
    path('api/token/refresh/', CookieTokenRefreshView.as_view()),
]