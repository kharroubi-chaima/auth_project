from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class Reservation(models.Model):
    """
    Réservation d'un médicament par un citoyen dans une pharmacie.
    - Expire automatiquement après 3h
    - Le stock n'est PAS déduit à la réservation
    - Il est déduit uniquement quand le pharmacien confirme la récupération
    - Si expirée sans récupération → stock retrouve sa disponibilité (jamais déduit)
    """

    STATUT_CHOICES = [
        ('active',    'Active'),
        ('recuperee', 'Récupérée'),
        ('expiree',   'Expirée'),
        ('annulee',   'Annulée'),
    ]

    citoyen    = models.ForeignKey(
                     settings.AUTH_USER_MODEL,
                     on_delete=models.CASCADE,
                     related_name='reservations',
                     verbose_name='Citoyen')
    stock      = models.ForeignKey(
                     'stock.StockPharmacie',
                     on_delete=models.CASCADE,
                     related_name='reservations',
                     verbose_name='Stock pharmacie')
    medicament = models.ForeignKey(
                     'stock.Medicament',
                     on_delete=models.CASCADE,
                     related_name='reservations',
                     verbose_name='Médicament')
    quantite   = models.PositiveIntegerField(default=1, verbose_name='Quantité réservée')
    statut     = models.CharField(
                     max_length=20,
                     choices=STATUT_CHOICES,
                     default='active',
                     verbose_name='Statut')
    expire_at  = models.DateTimeField(verbose_name='Expire le')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering     = ['-created_at']
        verbose_name = 'Réservation'
        verbose_name_plural = 'Réservations'

    def save(self, *args, **kwargs):
        # Définir expire_at à la création uniquement
        if not self.pk:
            self.expire_at = timezone.now() + timedelta(hours=3)
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"Réservation #{self.pk} — "
            f"{self.medicament.nom} × {self.quantite} "
            f"({self.statut})"
        )

    @property
    def est_expiree(self) -> bool:
        return timezone.now() > self.expire_at and self.statut == 'active'

    @property
    def minutes_restantes(self) -> int:
        if self.statut != 'active':
            return 0
        delta = self.expire_at - timezone.now()
        return max(0, int(delta.total_seconds() / 60))