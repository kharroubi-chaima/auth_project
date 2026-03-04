# localisations/models.py
import uuid
from django.db import models

class Gouvernorat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nom

    class Meta:
        ordering = ['nom']
        verbose_name_plural = "Gouvernorats"


class Delegation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=100)
    gouvernorat = models.ForeignKey(
        Gouvernorat,
        on_delete=models.CASCADE,
        related_name='delegations'
    )

    def __str__(self):
        return f"{self.nom} ({self.gouvernorat.nom})"

    class Meta:
        unique_together = ('nom', 'gouvernorat')
        ordering = ['gouvernorat__nom', 'nom']
        verbose_name_plural = "Délégations"