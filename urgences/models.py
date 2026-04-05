from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from pharmacies.models import Pharmacie


class DemandeUrgente(models.Model):
    TYPE_CHOICES = [
        ('medicament', 'Médicament'),
        ('service',    'Service'),
    ]
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('acceptee',   'Acceptée'),
        ('refusee',    'Refusée'),
        ('expiree',    'Expirée'),
    ]

    citoyen        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='demandes_urgentes')
    type_demande   = models.CharField(max_length=20, choices=TYPE_CHOICES)
    titre          = models.CharField(max_length=200)
    description    = models.TextField(blank=True)
    lat            = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng            = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    rayon_km       = models.FloatField(default=10)
    statut         = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    pharmacie      = models.ForeignKey('pharmacies.Pharmacie', null=True, blank=True, on_delete=models.SET_NULL, related_name='demandes_recues')
    created_at     = models.DateTimeField(auto_now_add=True)
    expire_at      = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.pk:
            self.expire_at = timezone.now() + timedelta(hours=2)
        super().save(*args, **kwargs)

    @property
    def est_expiree(self):
        return timezone.now() > self.expire_at

    def __str__(self):
        return f"{self.titre} — {self.citoyen}"