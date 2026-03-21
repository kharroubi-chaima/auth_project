from rest_framework import serializers
from .models import Reservation


class ReservationSerializer(serializers.ModelSerializer):
    """Sérialiseur en lecture pour afficher une réservation."""

    medicament_nom    = serializers.CharField(source='medicament.nom',           read_only=True)
    pharmacie_nom     = serializers.CharField(source='stock.pharmacie.nom',      read_only=True)
    pharmacie_adresse = serializers.CharField(source='stock.pharmacie.adresse',  read_only=True)
    pharmacie_tel     = serializers.CharField(source='stock.pharmacie.telephone',read_only=True)
    prix_vente        = serializers.SerializerMethodField()
    minutes_restantes = serializers.IntegerField(read_only=True)

    class Meta:
        model  = Reservation
        fields = [
            'id',
            'medicament_nom',
            'pharmacie_nom', 'pharmacie_adresse', 'pharmacie_tel',
            'quantite', 'prix_vente',
            'statut', 'expire_at', 'minutes_restantes',
            'created_at',
        ]
        read_only_fields = fields

    def get_prix_vente(self, obj):
        prix = obj.stock.prix_vente or obj.medicament.prix_vente
        return float(prix) if prix else 0.0


class ReservationCreateSerializer(serializers.Serializer):
    """Sérialiseur pour créer une réservation."""
    stock_id = serializers.IntegerField()
    quantite = serializers.IntegerField(min_value=1, default=1)