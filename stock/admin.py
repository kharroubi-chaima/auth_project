from django.contrib import admin
from .models import Notification

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ['created_at', 'type', 'statut', 'medicament', 'pharmacie', 'destinataire']
    list_filter   = ['type', 'statut', 'created_at']
    search_fields = ['medicament__nom', 'pharmacie__nom', 'destinataire']
    readonly_fields = ['pharmacie', 'medicament', 'type', 'message', 'statut', 'destinataire', 'created_at']
    ordering      = ['-created_at']