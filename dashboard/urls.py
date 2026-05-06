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
    

]