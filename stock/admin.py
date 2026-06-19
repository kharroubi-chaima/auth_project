from django.contrib import admin
from .models import Notification, Medicament

@admin.register(Medicament)
class MedicamentAdmin(admin.ModelAdmin):
    list_display = ['nom', 'dci', 'categorie', 'voie_administration', 'profil_patient', 'ordonnance_requise']
    list_filter = ['profil_patient', 'voie_administration', 'ordonnance_requise', 'categorie']
    search_fields = ['nom', 'dci', 'symptomes_cibles']
    readonly_fields = ['vecteur_semantique', 'created_at', 'updated_at']
    fieldsets = (
        ('Informations Générales', {
            'fields': ('nom', 'dci', 'categorie', 'description', 'profil_patient')
        }),
        ('Recherche Sémantique', {
            'fields': ('symptomes_cibles', 'voie_administration', 'vecteur_semantique')
        }),
        ('Prix et Stock', {
            'fields': ('prix_achat', 'prix_vente', 'quantite_stock', 'seuil_alerte', 'date_expiration', 'ordonnance_requise')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ['created_at', 'type', 'statut', 'medicament', 'pharmacie', 'destinataire']
    list_filter   = ['type', 'statut', 'created_at']
    search_fields = ['medicament__nom', 'pharmacie__nom', 'destinataire']
    readonly_fields = ['pharmacie', 'medicament', 'type', 'message', 'statut', 'destinataire', 'created_at']
    ordering      = ['-created_at']