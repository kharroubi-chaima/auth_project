# pharmacies/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PharmacieViewSet,
    PharmacieAdminViewSet,
    JourFerieViewSet,
    PeriodeRamadanViewSet,
    jours_feries_annee,
    mes_gardes,
    periodes_ramadan,
    dashboard_stats,
)

router = DefaultRouter()
router.register(r'pharmacies',        PharmacieViewSet,       basename='pharmacie')
router.register(r'admin/pharmacies',  PharmacieAdminViewSet,  basename='pharmacie-admin')
router.register(r'jours-feries-crud', JourFerieViewSet,       basename='jour-ferie')
router.register(r'periodes-ramadan',  PeriodeRamadanViewSet,  basename='periode-ramadan')

urlpatterns = [
    path('', include(router.urls)),
    path('jours-feries/',    jours_feries_annee, name='jours-feries'),  
    path('ramadan/',         periodes_ramadan,   name='ramadan'),       
    path('dashboard/stats/', dashboard_stats,    name='dashboard-stats'),
    path('pharmacien/mes-gardes/', mes_gardes, name='mes-gardes'),
]