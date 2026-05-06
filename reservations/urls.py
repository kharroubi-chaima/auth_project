from django.urls import path
from .views import (
    HistoriqueReservationsProprietaireView,
    PharmacienReservationsView,
    PharmaciesOuvertesView,
    RecherchePharmacieView,
    ReservationListCreateView,
    AnnulerReservationView,
    MarquerRecupereeView,
    HistoriqueReservationsView,
)

urlpatterns = [
    path('pharmacies-ouvertes/',         PharmaciesOuvertesView.as_view(),                     name='pharmacies-ouvertes'),
    path('recherche/',                   RecherchePharmacieView.as_view(),                     name='recherche-pharmacie'),
    path('historique/',                  HistoriqueReservationsView.as_view(),                 name='reservation-historique'),
    path('historique-proprietaire/',     HistoriqueReservationsProprietaireView.as_view(),     name='historique-proprietaire'),  # ← corrigé
    path('pharmacien/',                  PharmacienReservationsView.as_view(),                 name='pharmacien-reservations'),
    path('<int:pk>/annuler/',            AnnulerReservationView.as_view(),                     name='reservation-annuler'),
    path('<int:pk>/recuperee/',          MarquerRecupereeView.as_view(),                       name='reservation-recuperee'),
    path('',                             ReservationListCreateView.as_view(),                  name='reservation-list-create'),
]