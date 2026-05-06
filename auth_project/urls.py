from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # accounts — monté sous api/ car accounts/urls.py préfixe déjà auth/
    # → /api/auth/login/, /api/auth/users/, etc.
    path('api/', include('accounts.urls')),

    # pharmacies — UN SEUL montage, supprimez l'ancien doublon
    # pharmacies/urls.py préfixe déjà pharmacies/ via le router
    # → /api/pharmacies/..., /api/admin/mes-pharmaciens/, etc.
    path('api/', include('pharmacies.urls')),

    # Localisations
    path('api/localisations/', include('localisations.urls')),

    # Autres apps
    path('api/stock/',        include('stock.urls')),
    path('api/reservations/', include('reservations.urls')),
    path('api/urgences/',     include('urgences.urls')),
    path('api/dashboard/',    include('dashboard.urls')),
    path('api/superadmin/dashboard/', include('dashboard.urls_superadmin')),
    path('api/messagerie/', include('messagerie.urls')),

]