from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PharmacieViewSet, PharmacieAdminViewSet,
    JourFerieViewSet, PeriodeRamadanViewSet,
    SuperAdminPharmacieViewSet, DemandesSuspensionViewSet,
    GardePharmacieViewSet, HoraireViewSet, HoraireRamadanViewSet,
    jours_feries_annee, mes_gardes, periodes_ramadan,
    dashboard_stats, mes_pharmaciens, ajouter_pharmacien,
    mes_citoyens, historique_citoyen, ma_pharmacie,
)

router = DefaultRouter()
router.register(r'pharmacies',               PharmacieViewSet,          basename='pharmacie')
router.register(r'admin/pharmacies',         PharmacieAdminViewSet,     basename='pharmacie-admin')
router.register(r'superadmin/pharmacies',    SuperAdminPharmacieViewSet,basename='superadmin-pharmacie')
router.register(r'jours-feries-crud',        JourFerieViewSet,          basename='jour-ferie')
router.register(r'periodes-ramadan',         PeriodeRamadanViewSet,     basename='periode-ramadan')
router.register(r'admin/demande-suspension', DemandesSuspensionViewSet, basename='suspensions')
router.register(r'gardes',                   GardePharmacieViewSet,     basename='gardes')
router.register(r'horaires',                 HoraireViewSet,            basename='horaires')
router.register(r'horaires-ramadan',         HoraireRamadanViewSet,     basename='horaires-ramadan')


urlpatterns = [
    path('admin/ma-pharmacie/',                        ma_pharmacie,       name='ma-pharmacie'),
    path('admin/mes-pharmaciens/',                     mes_pharmaciens,    name='mes-pharmaciens'),
    path('admin/ajouter-pharmacien/',                  ajouter_pharmacien, name='ajouter-pharmacien'),
    path('admin/mes-citoyens/',                        mes_citoyens,       name='mes-citoyens'),
    path('admin/historique-citoyen/<str:citoyen_id>/', historique_citoyen, name='historique-citoyen'),
    path('pharmacies/mes-gardes/',                     mes_gardes,         name='mes-gardes'),
    path('pharmacies/horaires/',                       HoraireViewSet.as_view({'get': 'list'}), name='pharmacie-horaires'), 
    path('pharmacies/horaires-ramadan/',                HoraireRamadanViewSet.as_view({'get': 'list'}), name='pharmacie-horaires-ramadan'),
    path('jours-feries-annee/',                        jours_feries_annee, name='jours-feries-annee'),
    path('periodes-ramadan-list/',                     periodes_ramadan,   name='periodes-ramadan-list'),
    path('dashboard/stats/',                           dashboard_stats,    name='dashboard-stats'),
    path('', include(router.urls)),
]