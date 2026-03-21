from django.contrib import admin
from .models import Reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display  = [
        'id', 'citoyen', 'medicament', 'quantite',
        'statut', 'expire_at', 'minutes_restantes', 'created_at'
    ]
    list_filter   = ['statut', 'created_at']
    search_fields = ['citoyen__email', 'medicament__nom', 'stock__pharmacie__nom']
    readonly_fields = ['created_at', 'updated_at', 'expire_at', 'minutes_restantes']
    ordering      = ['-created_at']

    def minutes_restantes(self, obj):
        return f"{obj.minutes_restantes} min"
    minutes_restantes.short_description = 'Temps restant'