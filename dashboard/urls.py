# dashboard/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('kpis/',              views.KPIGenerauxView.as_view(),       name='dashboard-kpis'),
    path('ventes/',            views.VentesJournalieresView.as_view(), name='dashboard-ventes'),
    path('reservations/stats/', views.ReservationsStatsView.as_view(), name='dashboard-reservations'),
    path('demandes/stats/',    views.DemandesStatsView.as_view(),      name='dashboard-demandes'),
    path('alertes/',           views.AlertesStockView.as_view(),       name='dashboard-alertes'),
    path('top-medicaments/',   views.Top5MedicamentsView.as_view(),    name='dashboard-top-medicaments'),
    
    # Rapports personnalisés (Gérant)
    path('ventes-par-pharmacien/', views.VentesParPharmacienView.as_view(), name='ventes-par-pharmacien'),
    path('medicaments-liste/', views.ListeMedicamentsPharmacieView.as_view(), name='medicaments-liste'),
    path('comparaison-medicaments/', views.ComparaisonMedicamentsView.as_view(), name='comparaison-medicaments'),
]