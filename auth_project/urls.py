from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from accounts.views import CookieTokenRefreshView, CustomTokenObtainPairView, LogoutView
    

router = DefaultRouter()


urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include(router.urls)),


    # ✅ accounts EN PREMIER (sinon pharmacies.urls prend tout)
    path('api/', include('accounts.urls')),
    path('api/', include('pharmacies.urls')),

    # Tokens directs
    path('api/token/',         CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/logout/',  LogoutView.as_view()),
    path('api/token/refresh/', CookieTokenRefreshView.as_view()),

    # Autres apps
    path('api/localisations/', include('localisations.urls')),
    
    # urls.py principal
    path('api/stock/', include('stock.urls')),
    path('api/reservations/', include('reservations.urls')),

]