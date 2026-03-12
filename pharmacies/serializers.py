# pharmacies/serializers.py
from rest_framework import serializers
from datetime import datetime
from .models import (
    Pharmacie, HoraireTravail, HoraireRamadan,
    GardePharmacie, JourFerieTunisie, PeriodeRamadan
)
from localisations.serializers import DelegationSerializer


class PharmacieCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Pharmacie
        fields = [
            'nom', 'adresse', 'telephone', 'email',
            'categorie', 'delegation',
            'latitude', 'longitude',
            'est_active', 'proprietaire',
        ]
        extra_kwargs = {
            # proprietaire est assigné dans perform_create, pas envoyé par le frontend
            'proprietaire': {'required': False, 'read_only': True},
            'email'       : {'required': False, 'allow_null': True,  'allow_blank': True},
            'latitude'    : {'required': False, 'allow_null': True},
            'longitude'   : {'required': False, 'allow_null': True},
        }

    def validate(self, data):
        # ── Vérifier doublon par coordonnées GPS ──────────────
        lat = data.get('latitude')
        lng = data.get('longitude')
        if lat and lng:
            existante = Pharmacie.objects.filter(latitude=lat, longitude=lng)
            if self.instance:
                existante = existante.exclude(pk=self.instance.pk)
            if existante.exists():
                raise serializers.ValidationError({
                    'coordonnees': f"Une pharmacie existe déjà à ces coordonnées ({lat}, {lng})."
                })

        # ── Vérifier doublon par nom + adresse ────────────────
        nom    = data.get('nom')
        adresse = data.get('adresse')
        if nom and adresse:
            existante = Pharmacie.objects.filter(
                nom__iexact=nom,
                adresse__iexact=adresse
            )
            if self.instance:
                existante = existante.exclude(pk=self.instance.pk)
            if existante.exists():
                raise serializers.ValidationError({
                    'doublon': f"Une pharmacie '{nom}' existe déjà à cette adresse."
                })

        return data


class HoraireTravailSerializer(serializers.ModelSerializer):
    jour_nom = serializers.CharField(source='get_jour_display', read_only=True)

    class Meta:
        model  = HoraireTravail
        fields = [
            'id', 'jour', 'jour_nom', 'est_ouvert',
            'heure_ouverture', 'heure_fermeture',
            'pause_debut', 'pause_fin',
        ]


class HoraireRamadanSerializer(serializers.ModelSerializer):
    jour_nom = serializers.CharField(source='get_jour_display', read_only=True)

    class Meta:
        model  = HoraireRamadan
        fields = [
            'id', 'jour', 'jour_nom', 'est_ouvert',
            'heure_ouverture_1', 'heure_fermeture_1',
            'heure_ouverture_2', 'heure_fermeture_2',
        ]


class GardeSerializer(serializers.ModelSerializer):
    type_garde_nom = serializers.CharField(source='get_type_garde_display', read_only=True)

    class Meta:
        model  = GardePharmacie
        fields = [
            'id', 'type_garde', 'type_garde_nom',
            'date_debut', 'date_fin',
            'heure_debut', 'heure_fin',
        ]


class PharmacieListSerializer(serializers.ModelSerializer):
    delegation       = DelegationSerializer(read_only=True)
    est_ouverte      = serializers.SerializerMethodField()
    prochain_statut  = serializers.SerializerMethodField()
    proprietaire_nom = serializers.SerializerMethodField()

    class Meta:
        model  = Pharmacie
        fields = [
            'id', 'nom', 'adresse', 'telephone',
            'categorie', 'est_active',
            'delegation', 'latitude', 'longitude',
            'proprietaire', 'proprietaire_nom',
            'est_ouverte', 'prochain_statut',
        ]

    def get_est_ouverte(self, obj):
        now = datetime.now()
        return obj.verifier_ouverture(now.date(), now.time())

    def get_prochain_statut(self, obj):
        now     = datetime.now()
        jour    = now.date().weekday()
        horaire = HoraireTravail.objects.filter(
            pharmacie=obj, jour=jour, est_ouvert=True
        ).first()
        if horaire:
            if now.time() < horaire.heure_ouverture:
                return f"Ouvre à {horaire.heure_ouverture.strftime('%H:%M')}"
            elif now.time() < horaire.heure_fermeture:
                return f"Ferme à {horaire.heure_fermeture.strftime('%H:%M')}"
        return "Voir les horaires"

    def get_proprietaire_nom(self, obj):
        if obj.proprietaire:
            first = getattr(obj.proprietaire, 'first_name', '')
            last  = getattr(obj.proprietaire, 'last_name',  '')
            full  = f"{first} {last}".strip()
            return full or getattr(obj.proprietaire, 'username', '')
        return None


class PharmacieDetailSerializer(serializers.ModelSerializer):
    delegation       = DelegationSerializer(read_only=True)
    horaires         = HoraireTravailSerializer(many=True, read_only=True)
    horaires_ramadan = HoraireRamadanSerializer(many=True, read_only=True)
    gardes           = GardeSerializer(many=True, read_only=True)
    est_ouverte      = serializers.SerializerMethodField()
    proprietaire_nom = serializers.SerializerMethodField()

    class Meta:
        model  = Pharmacie
        fields = [
            'id', 'nom', 'adresse', 'telephone', 'email',
            'categorie', 'est_active',
            'proprietaire', 'proprietaire_nom',
            'delegation', 'latitude', 'longitude',
            'est_ouverte', 'horaires', 'horaires_ramadan', 'gardes',
        ]

    def get_est_ouverte(self, obj):
        now = datetime.now()
        return obj.verifier_ouverture(now.date(), now.time())

    def get_proprietaire_nom(self, obj):
        if obj.proprietaire:
            first = getattr(obj.proprietaire, 'first_name', '')
            last  = getattr(obj.proprietaire, 'last_name',  '')
            full  = f"{first} {last}".strip()
            return full or getattr(obj.proprietaire, 'username', '')
        return None


class JourFerieSerializer(serializers.ModelSerializer):
    class Meta:
        model  = JourFerieTunisie
        fields = ['id', 'nom', 'date', 'type_ferie']


class PeriodeRamadanSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PeriodeRamadan
        fields = ['id', 'annee', 'date_debut', 'date_fin']