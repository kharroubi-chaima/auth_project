from django.db import models
from django.conf import settings
from datetime import date, timedelta


class ATC(models.Model):
    nom         = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Categorie(models.Model):
    atc         = models.ForeignKey(
                      ATC, on_delete=models.CASCADE,
                      related_name='categories',
                      null=True, blank=True)
    nom         = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['nom']

    def __str__(self):
        return f"{self.atc} → {self.nom}"


class Medicament(models.Model):
    PROFIL_CHOICES = [
        ('enfant', 'Enfant'),
        ('adulte', 'Adulte'),
        ('tous', 'Tous'),
    ]

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
    symptomes_cibles   = models.TextField(blank=True, null=True, help_text="Symptômes spécifiques ciblés par le médicament")
    voie_administration= models.CharField(max_length=50, blank=True, null=True, help_text="Ex: Orale, Cutanée, Ophtalmique")
    profil_patient     = models.CharField(max_length=20, choices=PROFIL_CHOICES, default='tous', help_text="Profil ciblé par le médicament")
    quantite_stock     = models.PositiveIntegerField(default=0)
    seuil_alerte       = models.PositiveIntegerField(default=10)
    vecteur_semantique = models.JSONField(null=True, blank=True)
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

    def save(self, *args, **kwargs):
        # Si on ne met pas spécifiquement à jour le vecteur_semantique,
        # on le réinitialise pour forcer son recalcul lors de la prochaine recherche.
        update_fields = kwargs.get('update_fields')
        if update_fields is None or 'vecteur_semantique' not in update_fields:
            if update_fields is not None and 'quantite_stock' in update_fields and len(update_fields) == 1:
                # Ne pas vider le vecteur si on modifie juste le stock
                pass
            else:
                self.vecteur_semantique = None
                if update_fields is not None and 'vecteur_semantique' not in update_fields:
                    kwargs['update_fields'] = list(update_fields) + ['vecteur_semantique']
        super().save(*args, **kwargs)

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

    # — met à jour quantite_stock à chaque création
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            if self.type == 'entree':
                StockPharmacie.objects.filter(pk=self.stock_id).update(
                    quantite_stock=models.F('quantite_stock') + self.quantite
                )
            elif self.type == 'sortie':
                StockPharmacie.objects.filter(pk=self.stock_id).update(
                    quantite_stock=models.F('quantite_stock') - self.quantite
                )
            elif self.type == 'ajustement':
                StockPharmacie.objects.filter(pk=self.stock_id).update(
                    quantite_stock=models.F('quantite_stock') + self.quantite
                )
                
# ── Ventes ────────────────────────────────────────────────────────────────────

class Vente(models.Model):
    pharmacie    = models.ForeignKey(
                       'pharmacies.Pharmacie', on_delete=models.CASCADE,
                       related_name='ventes')
    created_by   = models.ForeignKey(
                       settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                       null=True, blank=True, related_name='ventes')
    total        = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    note         = models.TextField(blank=True, null=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Vente #{self.pk} — {self.pharmacie.nom} — {self.total} TND"

    def calculer_total(self):
        total = sum(l.sous_total for l in self.lignes.all())
        self.total = total
        self.save(update_fields=['total'])
        return total


class LigneVente(models.Model):
    vente          = models.ForeignKey(
                         Vente, on_delete=models.CASCADE,
                         related_name='lignes')
    medicament     = models.ForeignKey(
                         Medicament, on_delete=models.PROTECT,
                         related_name='lignes_vente')
    quantite       = models.PositiveIntegerField()
    prix_unitaire  = models.DecimalField(max_digits=10, decimal_places=3)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.medicament.nom} x{self.quantite}"

    @property
    def sous_total(self):
        return self.quantite * self.prix_unitaire


# ── Notifications ─────────────────────────────────────────────────────────────

class Notification(models.Model):
    TYPE_CHOICES = [
        ('stock_faible',          'Stock faible'),
        ('rupture_stock',         'Rupture de stock'),
        ('expiration',            'Expiration proche'),
        ('reservation_recuperee', 'Réservation récupérée'),  # ← AJOUT
    ]
    STATUT_CHOICES = [
        ('envoye', 'Envoyé'),
        ('echec',  'Échec'),
    ]

    pharmacie    = models.ForeignKey(
                       'pharmacies.Pharmacie', on_delete=models.CASCADE,
                       related_name='notifications')
    medicament   = models.ForeignKey(
                       'Medicament', on_delete=models.CASCADE,
                       related_name='notifications')
    type         = models.CharField(max_length=30, choices=TYPE_CHOICES)  # max_length augmenté pour le nouveau type
    message      = models.TextField()
    statut       = models.CharField(max_length=10, choices=STATUT_CHOICES)
    destinataire = models.CharField(max_length=20)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.type}] {self.medicament.nom} – {self.statut}"