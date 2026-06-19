from rest_framework import serializers
from datetime import datetime
from .models import (
    DemandesSuspension,
    Pharmacie,
    HoraireTravail,
    HoraireRamadan,
    GardePharmacie,
    JourFerieTunisie,
    PeriodeRamadan,
)
from localisations.serializers import DelegationSerializer


class PharmacieCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pharmacie
        fields = [
            "nom",
            "adresse",
            "telephone",
            "email",
            "categorie",
            "delegation",
            "latitude",
            "longitude",
            "est_active",
            "proprietaire",
        ]
        extra_kwargs = {
            "proprietaire": {"required": False, "read_only": True},
            "email": {"required": False, "allow_null": True, "allow_blank": True},
            "latitude": {"required": False, "allow_null": True},
            "longitude": {"required": False, "allow_null": True},
        }

    def validate(self, data):
        lat = data.get("latitude")
        lng = data.get("longitude")
        categorie = data.get("categorie", "A")

        if lat is None or lng is None:
            raise serializers.ValidationError(
                {
                    "coordonnees": "Les coordonnées GPS (latitude et longitude) sont obligatoires pour enregistrer une pharmacie."
                }
            )

        lat_f = float(lat)
        lng_f = float(lng)

        # 1. Vérification géographique (Tunisie seulement)
        if not (30.0 <= lat_f <= 37.6) or not (7.0 <= lng_f <= 12.0):
            raise serializers.ValidationError(
                {
                    "coordonnees": "La localisation géographique de la pharmacie doit être située impérativement en Tunisie."
                }
            )

        # 2. Vérification réglementaire CNOPT (distances minimales)
        active_pharmacies = Pharmacie.objects.filter(est_active=True)
        if self.instance:
            active_pharmacies = active_pharmacies.exclude(pk=self.instance.pk)

        for p in active_pharmacies:
            if p.latitude is not None and p.longitude is not None:
                dist = p.distance_km(lat_f, lng_f) * 1000  # conversion en mètres
                
                # Pharmacie de catégorie A (de jour) : distance minimale = 200 mètres entre deux officines A
                if categorie == "A" and p.categorie == "A":
                    if dist < 200:
                        raise serializers.ValidationError(
                            {
                                "coordonnees": (
                                    f"Réglementation CNOPT non respectée : Une pharmacie de catégorie A "
                                    f"('{p.nom}') est située à {int(dist)} mètres (minimum requis : 200m)."
                                )
                            }
                        )
                
                # Pharmacie de catégorie B (de nuit) : distance minimale = 500 mètres entre deux officines B
                elif categorie == "B" and p.categorie == "B":
                    if dist < 500:
                        raise serializers.ValidationError(
                            {
                                "coordonnees": (
                                    f"Réglementation CNOPT non respectée : Une pharmacie de catégorie B "
                                    f"('{p.nom}') est située à {int(dist)} mètres (minimum requis : 500m)."
                                )
                            }
                        )

        # Coordonnées exactes identiques
        existante = Pharmacie.objects.filter(latitude=lat, longitude=lng)
        if self.instance:
            existante = existante.exclude(pk=self.instance.pk)
        if existante.exists():
            raise serializers.ValidationError(
                {
                    "coordonnees": f"Une pharmacie existe déjà à ces coordonnées exactes ({lat}, {lng})."
                }
            )

        nom = data.get("nom")
        adresse = data.get("adresse")
        if nom and adresse:
            existante = Pharmacie.objects.filter(
                nom__iexact=nom, adresse__iexact=adresse
            )
            if self.instance:
                existante = existante.exclude(pk=self.instance.pk)
            if existante.exists():
                raise serializers.ValidationError(
                    {"doublon": f"Une pharmacie '{nom}' existe déjà à cette adresse."}
                )
        return data


class HoraireTravailSerializer(serializers.ModelSerializer):
    pharmacie_nom = serializers.CharField(source='pharmacie.nom', read_only=True)

    class Meta:
        model  = HoraireTravail
        fields = [
            'id', 'pharmacie', 'pharmacie_nom', 'jour',
            'est_ouvert', 'heure_ouverture', 'heure_fermeture',
            'pause_debut', 'pause_fin',
        ]


class HoraireRamadanSerializer(serializers.ModelSerializer):
    pharmacie_nom = serializers.CharField(source='pharmacie.nom', read_only=True)
    jour_nom = serializers.CharField(source="get_jour_display", read_only=True)

    class Meta:
        model = HoraireRamadan
        fields = [
            'id', 'pharmacie', 'pharmacie_nom', 'jour', 'est_ouvert',
            'heure_ouverture_1', 'heure_fermeture_1',
            'heure_ouverture_2', 'heure_fermeture_2',
        ]


class GardeSerializer(serializers.ModelSerializer):
    type_garde_nom = serializers.CharField(
        source="get_type_garde_display", read_only=True
    )

    class Meta:
        model = GardePharmacie
        fields = [
            "id",
            "type_garde",
            "type_garde_nom",
            "date_debut",
            "date_fin",
            "heure_debut",
            "heure_fin",
        ]


class PharmacieListSerializer(serializers.ModelSerializer):
    delegation = DelegationSerializer(read_only=True)
    est_ouverte = serializers.SerializerMethodField()
    prochain_statut = serializers.SerializerMethodField()
    proprietaire_nom = serializers.SerializerMethodField()

    class Meta:
        model = Pharmacie
        fields = [
            "id",
            "nom",
            "adresse",
            "telephone",
            "categorie",
            "est_active",
            "delegation",
            "latitude",
            "longitude",
            "proprietaire",
            "proprietaire_nom",
            "est_ouverte",
            "prochain_statut",
        ]

    def get_est_ouverte(self, obj):
        now = datetime.now()
        return obj.verifier_ouverture(now.date(), now.time())

    def get_prochain_statut(self, obj):
        now = datetime.now()
        jour = now.date().weekday()
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
            first = getattr(obj.proprietaire, "first_name", "")
            last = getattr(obj.proprietaire, "last_name", "")
            full = f"{first} {last}".strip()
            return full or getattr(obj.proprietaire, "username", "")
        return None


class PharmacieDetailSerializer(serializers.ModelSerializer):
    delegation = DelegationSerializer(read_only=True)
    horaires = HoraireTravailSerializer(many=True, read_only=True)
    horaires_ramadan = HoraireRamadanSerializer(many=True, read_only=True)
    gardes = GardeSerializer(many=True, read_only=True)
    est_ouverte = serializers.SerializerMethodField()
    proprietaire_nom = serializers.SerializerMethodField()

    class Meta:
        model = Pharmacie
        fields = [
            "id",
            "nom",
            "adresse",
            "telephone",
            "email",
            "categorie",
            "est_active",
            "proprietaire",
            "proprietaire_nom",
            "delegation",
            "latitude",
            "longitude",
            "est_ouverte",
            "horaires",
            "horaires_ramadan",
            "gardes",
        ]

    def get_est_ouverte(self, obj):
        now = datetime.now()
        return obj.verifier_ouverture(now.date(), now.time())

    def get_proprietaire_nom(self, obj):
        if obj.proprietaire:
            first = getattr(obj.proprietaire, "first_name", "")
            last = getattr(obj.proprietaire, "last_name", "")
            full = f"{first} {last}".strip()
            return full or getattr(obj.proprietaire, "username", "")
        return None


class MesGardesSerializer(serializers.ModelSerializer):
    type_garde_nom = serializers.CharField(
        source="get_type_garde_display", read_only=True
    )
    heure_debut = serializers.TimeField(read_only=True)
    heure_fin = serializers.TimeField(read_only=True)

    class Meta:
        model = GardePharmacie
        fields = [
            "id",
            "type_garde",
            "type_garde_nom",
            "date_debut",
            "date_fin",
            "heure_debut",
            "heure_fin",
        ]


class JourFerieSerializer(serializers.ModelSerializer):
    class Meta:
        model = JourFerieTunisie
        fields = ["id", "nom", "date", "type_ferie"]


class PeriodeRamadanSerializer(serializers.ModelSerializer):
    class Meta:
        model = PeriodeRamadan
        fields = ["id", "annee", "date_debut", "date_fin"]


class DemandesSuspensionSerializer(serializers.ModelSerializer):
    pharmacie_nom = serializers.CharField(source="pharmacie.nom", read_only=True)
    demandeur_nom = serializers.CharField(
        source="demandeur.get_full_name", read_only=True
    )
    traite_par_nom = serializers.CharField(
        source="traite_par.get_full_name", read_only=True
    )

    class Meta:
        model = DemandesSuspension
        fields = [
            "id",
            "pharmacie",
            "pharmacie_nom",
            "demandeur_nom",
            "motif",
            "statut",
            "date_demande",
            "commentaire_superadmin",
            "date_traitement",
            "traite_par_nom",
        ]
        read_only_fields = ["statut", "date_demande", "pharmacie", "date_traitement", "traite_par_nom"]


class GardePharmacieSerializer(serializers.ModelSerializer):
    pharmacie_nom = serializers.CharField(source="pharmacie.nom", read_only=True)
    delegation_nom = serializers.CharField(
        source="pharmacie.delegation.nom", read_only=True
    )

    class Meta:
        model = GardePharmacie
        fields = [
            "id",
            "pharmacie",
            "pharmacie_nom",
            "delegation_nom",
            "type_garde",
            "date_debut",
            "date_fin",
            "heure_debut",
            "heure_fin",
        ]
        extra_kwargs = {"pharmacie": {"required": False}}


# ── Serializer propriétaire ───────────────────────────────────────────────────
class ProprietaireSerializer(serializers.Serializer):
    first_name = serializers.CharField(source="first_name")
    last_name = serializers.CharField(source="last_name")
    email = serializers.EmailField(source="email")
    telephone = serializers.CharField(source="telephone", default=None)


# ── Serializer admin (ma-pharmacie) ──────────────────────────────────────────
class PharmacieAdminSerializer(serializers.ModelSerializer):
    delegation = DelegationSerializer(read_only=True)
    proprietaire = serializers.SerializerMethodField()

    class Meta:
        model = Pharmacie
        fields = [
            "id",
            "nom",
            "adresse",
            "telephone",
            "email",
            "categorie",
            "est_active",
            "created_at",
            "delegation",
            "proprietaire",
        ]

    def get_proprietaire(self, obj):
        p = obj.proprietaire
        if not p:
            return None
        return {
            "first_name": getattr(p, "first_name", "") or "",
            "last_name": getattr(p, "last_name", "") or "",
            "email": getattr(p, "email", "") or "",
            "telephone": getattr(p, "telephone", None),
        }
