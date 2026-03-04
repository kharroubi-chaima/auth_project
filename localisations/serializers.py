# localisations/serializers.py
from rest_framework import serializers
from .models import Gouvernorat, Delegation

class GouvernoratSerializer(serializers.ModelSerializer):
    nombre_delegations = serializers.SerializerMethodField()

    class Meta:
        model = Gouvernorat
        fields = ['id', 'nom', 'nombre_delegations']

    def get_nombre_delegations(self, obj):
        return obj.delegations.count()


class DelegationSerializer(serializers.ModelSerializer):
    gouvernorat_nom = serializers.CharField(source='gouvernorat.nom', read_only=True)
    gouvernorat = GouvernoratSerializer(read_only=True)
    class Meta:
        model = Delegation
        fields = ['id', 'nom', 'gouvernorat', 'gouvernorat_nom']