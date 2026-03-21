from django.db import models
from django.conf import settings
from datetime import date, timedelta


class Categorie(models.Model):
    nom         = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Medicament(models.Model):
    nom                = models.CharField(max_length=200)
    dci                = models.CharField(max_length=200, blank=True, null=True)
    categorie          = models.ForeignKey(
                             Categorie, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='medicaments')
    prix_achat         = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    prix_vente         = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    date_expiration    = models.DateField(null=True, blank=True)
    ordonnance_requise = models.BooleanField(default=False)
    description        = models.TextField(blank=True, null=True)
    quantite_stock     = models.PositiveIntegerField(default=0)
    seuil_alerte       = models.PositiveIntegerField(default=10)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nom']

    def __str__(self):
        return self.nom

    @property
    def expire_bientot(self) -> bool:
        if not self.date_expiration:
            return False
        return self.date_expiration <= date.today() + timedelta(days=30)

    @property
    def stock_faible(self) -> bool:
        return 0 < self.quantite_stock <= self.seuil_alerte

    @property
    def en_rupture(self) -> bool:
        return self.quantite_stock == 0


class StockPharmacie(models.Model):
    pharmacie      = models.ForeignKey(
                         'pharmacies.Pharmacie', on_delete=models.CASCADE,
                         related_name='stocks')
    medicament     = models.ForeignKey(
                         Medicament, on_delete=models.CASCADE,
                         related_name='stocks')
    quantite_stock = models.PositiveIntegerField(default=0)
    seuil_alerte   = models.PositiveIntegerField(default=10)
    prix_vente     = models.DecimalField(
                         max_digits=10, decimal_places=3,
                         null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('pharmacie', 'medicament')

    def __str__(self):
        return f"{self.medicament.nom} — {self.pharmacie.nom}"

    @property
    def stock_faible(self) -> bool:
        return 0 < self.quantite_stock <= self.seuil_alerte

    @property
    def en_rupture(self) -> bool:
        return self.quantite_stock == 0


class MouvementStock(models.Model):
    TYPE_CHOICES = [
        ('entree',     'Entrée'),
        ('sortie',     'Sortie'),
        ('ajustement', 'Ajustement'),
    ]
    stock      = models.ForeignKey(
                     StockPharmacie, on_delete=models.CASCADE,
                     related_name='mouvements')
    type       = models.CharField(max_length=20, choices=TYPE_CHOICES)
    quantite   = models.IntegerField()
    motif      = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
                     settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                     null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.type} {self.quantite} — {self.stock}"


# ── Ventes ────────────────────────────────────────────────────────────────────

class Vente(models.Model):
    """
    Représente une vente complète (panier).
    Une vente contient plusieurs LigneVente.
    """
    pharmacie    = models.ForeignKey(
                       'pharmacies.Pharmacie', on_delete=models.CASCADE,
                       related_name='ventes')
    created_by   = models.ForeignKey(
                       settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                       null=True, blank=True, related_name='ventes')
    # Total calculé et sauvegardé au moment de la vente
    total        = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    note         = models.TextField(blank=True, null=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Vente #{self.pk} — {self.pharmacie.nom} — {self.total} TND"

    def calculer_total(self):
        """Recalcule et sauvegarde le total depuis les lignes."""
        total = sum(l.sous_total for l in self.lignes.all())
        self.total = total
        self.save(update_fields=['total'])
        return total


class LigneVente(models.Model):
    """
    Une ligne dans une vente : un médicament, une quantité, un prix unitaire.
    Le prix_unitaire est figé au moment de la vente (même si prix_vente change après).
    """
    vente          = models.ForeignKey(
                         Vente, on_delete=models.CASCADE,
                         related_name='lignes')
    medicament     = models.ForeignKey(
                         Medicament, on_delete=models.PROTECT,
                         related_name='lignes_vente')
    quantite       = models.PositiveIntegerField()
    # Prix figé au moment de la vente
    prix_unitaire  = models.DecimalField(max_digits=10, decimal_places=3)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.medicament.nom} x{self.quantite}"

    @property
    def sous_total(self):
        return self.quantite * self.prix_unitaire