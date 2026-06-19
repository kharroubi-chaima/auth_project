from django.urls import path
from .views_superadmin import (
    SuperAdminKPIView,
    SuperAdminPharmaciesKPIView,
    SuperAdminVentesJournalieresView,
    SuperAdminReservationsStatsView,
    SuperAdminDemandesStatsView,
    SuperAdminAlertesStockView,
    SuperAdminTop5MedicamentsView,
    SuperAdminNouvellesPharmaciesView,
    SuperAdminInscriptionsView,
    SuperAdminTopPharmaciesView,
    SuperAdminListeMedicamentsView,
    SuperAdminListePharmaciesView,
    SuperAdminListeDelegationsView,
    SuperAdminComparaisonPharmaciesView,
    SuperAdminTopDelegationView,
)

urlpatterns = [
    path('kpis/',                  SuperAdminKPIView.as_view(),                 name='superadmin-kpis'),
    path('pharmacies/',            SuperAdminPharmaciesKPIView.as_view(),       name='superadmin-pharmacies'),
    path('ventes/',                SuperAdminVentesJournalieresView.as_view(),  name='superadmin-ventes'),
    path('reservations/stats/',    SuperAdminReservationsStatsView.as_view(),   name='superadmin-reservations-stats'),
    path('demandes/stats/',        SuperAdminDemandesStatsView.as_view(),       name='superadmin-demandes-stats'),
    path('alertes/',               SuperAdminAlertesStockView.as_view(),        name='superadmin-alertes'),
    path('top-medicaments/',       SuperAdminTop5MedicamentsView.as_view(),     name='superadmin-top-medicaments'),
    path('nouvelles-pharmacies/',  SuperAdminNouvellesPharmaciesView.as_view(), name='superadmin-nouvelles-pharmacies'),
    path('inscriptions/',          SuperAdminInscriptionsView.as_view(),        name='superadmin-inscriptions'),
    path('top-pharmacies/',        SuperAdminTopPharmaciesView.as_view(),       name='superadmin-top-pharmacies'),

    # Rapports Personnalisés
    path('medicaments-liste/',     SuperAdminListeMedicamentsView.as_view(),    name='superadmin-medicaments-liste'),
    path('pharmacies-liste/',      SuperAdminListePharmaciesView.as_view(),     name='superadmin-pharmacies-liste'),
    path('delegations-liste/',     SuperAdminListeDelegationsView.as_view(),    name='superadmin-delegations-liste'),
    path('comparaison-pharmacies/', SuperAdminComparaisonPharmaciesView.as_view(), name='superadmin-comparaison-pharmacies'),
    path('top-delegation/',        SuperAdminTopDelegationView.as_view(),       name='superadmin-top-delegation'),
]