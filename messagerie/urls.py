from django.urls import path
from .views import (
    ConversationListCreateView,
    MessageListView,
    PresenceView,
    NotificationsView,
    PharmaciesDisponiblesView,
    UpdatePresenceView, 
    NotificationsMarquerToutesLuesView,
    GroupListCreateView,
    GroupMessageListView,
    GroupMessageDetailView,
    GroupDetailView,
    GroupMemberView,
    GroupMemberDetailView,
    NotificationSystemeView,
    PharmacienListView,
    MessageDetailView,
)

urlpatterns = [
    path('conversations/', ConversationListCreateView.as_view()),
    path('conversations/<int:conversation_id>/messages/', MessageListView.as_view()),
    path('pharmacies-disponibles/', PharmaciesDisponiblesView.as_view()),
    path('presence/update/', UpdatePresenceView.as_view()),      # ← AVANT la ligne suivante
    path('presence/<uuid:user_id>/', PresenceView.as_view()),
    path('admin/conversations/', ConversationListCreateView.as_view()),
    path('admin/conversations/<int:conversation_id>/messages/', MessageListView.as_view()),
    path('groups/', GroupListCreateView.as_view()),
    path('groups/<uuid:group_id>/', GroupDetailView.as_view()),
    path('groups/<uuid:group_id>/members/', GroupMemberView.as_view()),
    path('groups/<uuid:group_id>/members/<uuid:membre_id>/', GroupMemberDetailView.as_view()),
    path('groups/<uuid:group_id>/messages/', GroupMessageListView.as_view()),
    path('groups/messages/<int:message_id>/', GroupMessageDetailView.as_view()),
    path('conversations/messages/<int:message_id>/', MessageDetailView.as_view()),
    path('notifications/', NotificationsView.as_view()),
    path('notifications/marquer-toutes-lues/', NotificationsMarquerToutesLuesView.as_view()),  # ← ajouter
    path('notifications/<int:notif_id>/lue/', NotificationsView.as_view()),
    path('system-notifications/', NotificationSystemeView.as_view()),
    path('system-notifications/<int:notif_id>/lue/', NotificationSystemeView.as_view()),
    path('pharmaciens/', PharmacienListView.as_view()),

]