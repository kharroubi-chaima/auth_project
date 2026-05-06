from django.urls import path
from .views import (
    ConversationListCreateView,
    MessageListView,
    PresenceView,
    NotificationsView,
    PharmaciesDisponiblesView,
    UpdatePresenceView, 
    NotificationsMarquerToutesLuesView,  

)

urlpatterns = [
    path('conversations/', ConversationListCreateView.as_view()),
    path('conversations/<int:conversation_id>/messages/', MessageListView.as_view()),
    path('pharmacies-disponibles/', PharmaciesDisponiblesView.as_view()),
    path('presence/update/', UpdatePresenceView.as_view()),      # ← AVANT la ligne suivante
    path('presence/<str:pharmacie_id>/', PresenceView.as_view()),# ← APRÈS
    path('notifications/', NotificationsView.as_view()),
    path('notifications/marquer-toutes-lues/', NotificationsMarquerToutesLuesView.as_view()),  # ← ajouter
    path('notifications/<int:notif_id>/lue/', NotificationsView.as_view()),

]