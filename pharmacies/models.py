# pharmacies/models.py
import uuid
import math
from django.db import models
from django.conf import settings
from localisations.models import Delegation

JOURS_SEMAINE = [
    (0, 'Lundi'), (1, 'Mardi'), (2, 'Mercredi'),
    (3, 'Jeudi'), (4, 'Vendredi'), (5, 'Samedi'), (6, 'Dimanche'),
]


class Pharmacie(models.Model):
    CATEGORIE_CHOICES = [
        ('A', 'Catégorie A - Jour (8h30→19h30)'),
        ('B', 'Catégorie B - Nuit (19h30→8h30)'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom          = models.CharField(max_length=100)
    adresse      = models.TextField()
    telephone    = models.CharField(max_length=20)
    email        = models.EmailField(blank=True, null=True)
    categorie    = models.CharField(max_length=1, choices=CATEGORIE_CHOICES, default='A')
    delegation   = models.ForeignKey(
        Delegation, on_delete=models.SET_NULL,
        null=True, related_name='pharmacies'
    )
    latitude     = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude    = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    est_active   = models.BooleanField(default=True)
    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pharmacies'
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nom} (Cat. {self.categorie})"

    def verifier_ouverture(self, date, heure):
        from datetime import time

        # ── 1. Pharmacie catégorie B → ouverte la nuit ────────
        if self.categorie == 'B':
            # Nuit = après 19h30 OU avant 8h30 (traverse minuit)
            return heure >= time(19, 30) or heure <= time(8, 30)

        # ── 2. Jour férié → ouverte seulement si de garde ─────
        jour_ferie = JourFerieTunisie.objects.filter(date=date).first()
        if jour_ferie:
            return GardePharmacie.objects.filter(
                pharmacie=self,
                date_debut__lte=date,
                date_fin__gte=date
            ).exists()

        # ── 3. Dimanche → ouverte seulement si de garde ───────
        if date.weekday() == 6:
            return GardePharmacie.objects.filter(
                pharmacie=self,
                date_debut__lte=date,
                date_fin__gte=date
            ).exists()

        # ── 4. De garde en semaine → continu 8h30→19h30 ───────
        garde = GardePharmacie.objects.filter(
            pharmacie=self,
            date_debut__lte=date,
            date_fin__gte=date
        ).first()
        if garde:
            return time(8, 30) <= heure <= time(19, 30)

        # ── 5. Période Ramadan ─────────────────────────────────
        periode_ramadan = PeriodeRamadan.objects.filter(
            date_debut__lte=date,
            date_fin__gte=date
        ).first()

        jour_semaine = date.weekday()

        if periode_ramadan:
            horaire = HoraireRamadan.objects.filter(
                pharmacie=self,
                jour=jour_semaine
            ).first()

            # Pas d'horaire Ramadan en base → fallback CNOPT officiel
            if not horaire:
                if jour_semaine == 6:           # Dimanche → fermé
                    return False
                if jour_semaine == 5:           # Samedi → 08h30→13h00
                    return time(8, 30) <= heure <= time(13, 0)
                # Lundi→Vendredi → 08h30→17h00
                return time(8, 30) <= heure <= time(17, 0)

            if not horaire.est_ouvert:
                return False

            # Tranche 1 (matin)
            tranche1 = (
                horaire.heure_ouverture_1 is not None and
                horaire.heure_fermeture_1 is not None and
                horaire.heure_ouverture_1 <= heure <= horaire.heure_fermeture_1
            )
            # Tranche 2 (soir) — optionnelle
            tranche2 = (
                horaire.heure_ouverture_2 is not None and
                horaire.heure_fermeture_2 is not None and
                horaire.heure_ouverture_2 <= heure <= horaire.heure_fermeture_2
            )
            return bool(tranche1 or tranche2)

        # ── 6. Horaire normal catégorie A ──────────────────────
        # Samedi → matin seulement
        if jour_semaine == 5:
            return time(8, 30) <= heure <= time(13, 0)

        # Lundi→Vendredi : matin + après-midi (avec pause déjeuner)
        matin      = time(8, 30) <= heure <= time(13, 0)
        apres_midi = time(15, 0) <= heure <= time(19, 30)
        return matin or apres_midi

    def distance_km(self, lat, lng):
        if not self.latitude or not self.longitude:
            return float('inf')
        R    = 6371
        dlat = math.radians(float(self.latitude) - lat)
        dlng = math.radians(float(self.longitude) - lng)
        a    = math.sin(dlat/2)**2 + \
               math.cos(math.radians(lat)) * \
               math.cos(math.radians(float(self.latitude))) * \
               math.sin(dlng/2)**2
        return R * 2 * math.asin(math.sqrt(a))

    class Meta:
        ordering = ['nom']


class HoraireTravail(models.Model):
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pharmacie       = models.ForeignKey(Pharmacie, on_delete=models.CASCADE, related_name='horaires')
    jour            = models.IntegerField(choices=JOURS_SEMAINE)
    est_ouvert      = models.BooleanField(default=True)
    heure_ouverture = models.TimeField(null=True, blank=True)
    heure_fermeture = models.TimeField(null=True, blank=True)
    pause_debut     = models.TimeField(null=True, blank=True)
    pause_fin       = models.TimeField(null=True, blank=True)

    class Meta:
        unique_together = ('pharmacie', 'jour')

    def __str__(self):
        return f"{self.pharmacie.nom} - {self.get_jour_display()}"


class HoraireRamadan(models.Model):
    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pharmacie         = models.ForeignKey(Pharmacie, on_delete=models.CASCADE, related_name='horaires_ramadan')
    jour              = models.IntegerField(choices=JOURS_SEMAINE)
    est_ouvert        = models.BooleanField(default=True)
    heure_ouverture_1 = models.TimeField(null=True, blank=True)
    heure_fermeture_1 = models.TimeField(null=True, blank=True)
    heure_ouverture_2 = models.TimeField(null=True, blank=True)   # optionnel (ex: soir après iftar)
    heure_fermeture_2 = models.TimeField(null=True, blank=True)

    class Meta:
        unique_together = ('pharmacie', 'jour')

    def __str__(self):
        return f"{self.pharmacie.nom} - Ramadan {self.get_jour_display()}"


class PeriodeRamadan(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    annee      = models.IntegerField(unique=True)
    date_debut = models.DateField()
    date_fin   = models.DateField()

    def __str__(self):
        return f"Ramadan {self.annee}"

    class Meta:
        ordering = ['-annee']


class JourFerieTunisie(models.Model):
    TYPE_CHOICES = [('fixe', 'Fixe'), ('religieux', 'Religieux')]
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom        = models.CharField(max_length=150)
    date       = models.DateField()
    type_ferie = models.CharField(max_length=20, choices=TYPE_CHOICES)

    def __str__(self):
        return f"{self.nom} ({self.date})"

    class Meta:
        ordering = ['date']


class GardePharmacie(models.Model):
    TYPE_GARDE = [
        ('jour',     'Garde de Jour A — 8h30 à 19h30'),
        ('nuit',     'Garde de Nuit B — 19h30 à 8h30'),
        ('dimanche', 'Garde Dimanche'),
        ('ferie',    'Garde Jour Férié'),
    ]
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pharmacie  = models.ForeignKey(Pharmacie, on_delete=models.CASCADE, related_name='gardes')
    type_garde = models.CharField(max_length=20, choices=TYPE_GARDE)
    date_debut = models.DateField()
    date_fin   = models.DateField()

    @property
    def heure_debut(self):
        from datetime import time
        return time(19, 30) if self.pharmacie.categorie == 'B' else time(8, 30)

    @property
    def heure_fin(self):
        from datetime import time
        return time(8, 30) if self.pharmacie.categorie == 'B' else time(19, 30)

    def __str__(self):
        return f"{self.pharmacie.nom} - {self.get_type_garde_display()} ({self.date_debut})"

    class Meta:
        ordering = ['date_debut']