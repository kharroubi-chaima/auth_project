from rest_framework import serializers
from .models import Reservation


class ReservationSerializer(serializers.ModelSerializer):
    medicament_nom    = serializers.CharField(source='medicament.nom',            read_only=True)
    pharmacie_nom     = serializers.CharField(source='stock.pharmacie.nom',       read_only=True)
    pharmacie_adresse = serializers.CharField(source='stock.pharmacie.adresse',   read_only=True)
    pharmacie_tel     = serializers.CharField(source='stock.pharmacie.telephone', read_only=True)
    prix_vente        = serializers.SerializerMethodField()
    minutes_restantes = serializers.IntegerField(read_only=True)

    # ✅ AJOUT : nom du citoyen pour la vue pharmacien
    citoyen_nom = serializers.SerializerMethodField()
    citoyen_email = serializers.EmailField(source='citoyen.email', read_only=True)

    class Meta:
        model  = Reservation
        fields = [
            'id',
            'stock_id',  # Nécessaire pour les opérations de création/mise à jour
            'medicament_nom',
            'pharmacie_nom', 'pharmacie_adresse', 'pharmacie_tel',
            'quantite', 'prix_vente',
            'statut', 'expire_at', 'minutes_restantes',
            'created_at',
            'citoyen_nom',   
            'citoyen_email', 
        ]
        read_only_fields = fields

    def get_prix_vente(self, obj):
        prix = obj.stock.prix_vente or obj.medicament.prix_vente
        return float(prix) if prix else 0.0

    def get_citoyen_nom(self, obj):
        if obj.citoyen:
            return f"{obj.citoyen.first_name} {obj.citoyen.last_name}".strip() or obj.citoyen.email
        return '—'


class ReservationCreateSerializer(serializers.Serializer):
    """Sérialiseur pour créer une réservation."""
    stock_id = serializers.IntegerField()
    quantite = serializers.IntegerField(min_value=1, default=1)