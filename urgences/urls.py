from django.urls import path
from .views import (
    DemandeUrgenteListCreateView,
    DemandeUrgenteProchesView,
    HistoriquePharmacienView,
    RepondreDemandeView,
    AnnulerDemandeView,
)

urlpatterns = [
    path('',           DemandeUrgenteListCreateView.as_view(), name='urgences-list-create'),
    path('proches/',   DemandeUrgenteProchesView.as_view(),    name='urgences-proches'),
    path('historique/',            HistoriquePharmacienView.as_view()),   # ← nouveau   
    path('<int:pk>/repondre/', RepondreDemandeView.as_view(),  name='urgences-repondre'),
    path('<int:pk>/annuler/',  AnnulerDemandeView.as_view(),   name='urgences-annuler'),
]