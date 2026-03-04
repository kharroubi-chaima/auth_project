# localisations/admin.py
from django.contrib import admin
from .models import Gouvernorat, Delegation


class DelegationInline(admin.TabularInline):
    model = Delegation
    extra = 0


@admin.register(Gouvernorat)
class GouvernoratAdmin(admin.ModelAdmin):
    list_display = ['nom', 'nombre_delegations']
    search_fields = ['nom']
    inlines = [DelegationInline]

    def nombre_delegations(self, obj):
        return obj.delegations.count()
    nombre_delegations.short_description = "Nb Délégations"


@admin.register(Delegation)
class DelegationAdmin(admin.ModelAdmin):
    list_display = ['nom', 'gouvernorat']
    list_filter = ['gouvernorat']
    search_fields = ['nom']