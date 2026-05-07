from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse

def debug_view(request):
    return HttpResponse("DEBUG OK")

urlpatterns = [
    path('debug/', debug_view),
    path('admin/', admin.site.urls),

    # 1. Dashboard routes (Pharmacien)
    path('api/dashboard/',            include('dashboard.urls')),
    
    # 2. SuperAdmin Dashboard
    path('api/superadmin/dashboard/', include('dashboard.urls_superadmin')),

    # 3. Specific Apps
    path('api/localisations/',        include('localisations.urls')),
    path('api/stock/',                include('stock.urls')),
    path('api/reservations/',         include('reservations.urls')),
    path('api/urgences/',             include('urgences.urls')),
    path('api/messagerie/',           include('messagerie.urls')),

    # 4. Consolidate general API prefixes to avoid shadowing
    # accounts.urls (mostly /auth/) and pharmacies.urls (various)
    path('api/', include('accounts.urls')),
    path('api/', include('pharmacies.urls')),
]