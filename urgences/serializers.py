from rest_framework import serializers
from .models import DemandeUrgente

class DemandeUrgenteSerializer(serializers.ModelSerializer):
    citoyen_nom       = serializers.SerializerMethodField()
    pharmacie_nom     = serializers.SerializerMethodField()
    minutes_restantes = serializers.SerializerMethodField()

    class Meta:
        model  = DemandeUrgente
        fields = [
            'id', 'type_demande', 'titre', 'description',
            'lat', 'lng', 'rayon_km', 'statut',
            'citoyen_nom', 'pharmacie_nom',
            'created_at', 'expire_at', 'minutes_restantes',
        ]

    def get_citoyen_nom(self, obj):
        if obj.citoyen:
            nom = f"{obj.citoyen.first_name} {obj.citoyen.last_name}".strip()
            return nom or obj.citoyen.username
        return '—'

    def get_pharmacie_nom(self, obj):
        if obj.pharmacie:
            return obj.pharmacie.nom  # ← champ 'nom' de votre modèle Pharmacie
        return None

    def get_minutes_restantes(self, obj):
        import math
        from django.utils import timezone
        if obj.expire_at and obj.statut == 'en_attente':
            diff = (obj.expire_at - timezone.now()).total_seconds()
            return max(0, math.ceil(diff / 60))
        return 0


class DemandeUrgenteCreateSerializer(serializers.Serializer):
    type_demande = serializers.ChoiceField(choices=['medicament', 'service'])
    titre        = serializers.CharField(max_length=200)
    description  = serializers.CharField(required=False, allow_blank=True, default='')
    lat          = serializers.FloatField()
    lng          = serializers.FloatField()
    rayon_km     = serializers.FloatField(required=False, default=10)