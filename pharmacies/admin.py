# pharmacies/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import *


class HoraireTravailInline(admin.TabularInline):
    model = HoraireTravail
    extra = 0
    fields = ['jour', 'est_ouvert', 'heure_ouverture', 'heure_fermeture', 'pause_debut', 'pause_fin']


class HoraireRamadanInline(admin.TabularInline):
    model = HoraireRamadan
    extra = 0
    fields = ['jour', 'est_ouvert', 'heure_ouverture_1', 'heure_fermeture_1', 'heure_ouverture_2', 'heure_fermeture_2']


class GardeInline(admin.TabularInline):
    model = GardePharmacie
    extra = 1
    fields = ['type_garde', 'date_debut', 'date_fin', 'heure_debut', 'heure_fin']


@admin.register(Pharmacie)
class PharmacieAdmin(admin.ModelAdmin):
    list_display = ['nom', 'delegation', 'telephone', 'statut_badge', 'est_active']
    list_filter = ['est_active', 'delegation__gouvernorat', 'delegation']
    search_fields = ['nom', 'adresse', 'telephone']
    inlines = [HoraireTravailInline, HoraireRamadanInline, GardeInline]
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'adresse', 'telephone', 'email', 'delegation', 'proprietaire', 'est_active')
        }),
        ('Localisation GPS', {
            'fields': ('latitude', 'longitude'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def statut_badge(self, obj):
        now = timezone.now()
        est_ouverte = obj.verifier_ouverture(now.date(), now.time())
        if est_ouverte:
            return format_html(
                '<span style="background:#e8f5e9;color:#2e7d32;padding:3px 10px;'
                'border-radius:12px;font-weight:bold;">✅ Ouverte</span>'
            )
        return format_html(
            '<span style="background:#ffebee;color:#c62828;padding:3px 10px;'
            'border-radius:12px;font-weight:bold;">❌ Fermée</span>'
        )
    statut_badge.short_description = "Statut"


@admin.register(JourFerieTunisie)
class JourFerieAdmin(admin.ModelAdmin):
    list_display = ['nom', 'date', 'type_ferie']
    list_filter = ['type_ferie']
    ordering = ['date']


@admin.register(GardePharmacie)
class GardeAdmin(admin.ModelAdmin):
    list_display = ['pharmacie', 'type_garde', 'date_debut', 'date_fin']
    list_filter = ['type_garde']
    search_fields = ['pharmacie__nom']
    ordering = ['date_debut']


@admin.register(PeriodeRamadan)
class PeriodeRamadanAdmin(admin.ModelAdmin):
    list_display = ['annee', 'date_debut', 'date_fin']
    ordering = ['-annee']