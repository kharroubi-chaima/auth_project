from django.urls import path
from .views import (
    PharmaciesOuvertesView,
    RecherchePharmacieView,
    ReservationListCreateView,
    AnnulerReservationView,
    MarquerRecupereeView,
)

urlpatterns = [
    path('pharmacies-ouvertes/',  PharmaciesOuvertesView.as_view(),    name='pharmacies-ouvertes'),
    path('recherche/',            RecherchePharmacieView.as_view(),    name='recherche-pharmacie'),
    path('',                      ReservationListCreateView.as_view(), name='reservation-list-create'),
    path('<int:pk>/annuler/',     AnnulerReservationView.as_view(),    name='reservation-annuler'),
    path('<int:pk>/recuperee/',   MarquerRecupereeView.as_view(),      name='reservation-recuperee'),
]