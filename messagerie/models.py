import uuid
from django.db import models
from django.conf import settings
from pharmacies.models import Pharmacie


class Conversation(models.Model):
    citoyen    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conversations_citoyen')
    pharmacie  = models.ForeignKey(Pharmacie, on_delete=models.CASCADE, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('citoyen', 'pharmacie')
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.citoyen.email} ↔ {self.pharmacie.nom}"


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    expediteur   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='messages_envoyes')
    contenu      = models.TextField()
    lu           = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class UserPresence(models.Model):
    user      = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='presence')
    en_ligne  = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {'Online' if self.en_ligne else 'Offline'}"


class Group(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom        = models.CharField(max_length=200)
    image      = models.ImageField(upload_to='groups/', null=True, blank=True)
    createur   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='groups_crees')
    membres    = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='groups_appartenance')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nom


class GroupMessage(models.Model):
    groupe     = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='messages')
    expediteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='group_messages_envoyes')
    contenu    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Group {self.groupe.nom} - {self.expediteur.email}"


class NotificationMessage(models.Model):
    destinataire = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications_messages')
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, null=True, blank=True)
    groupe       = models.ForeignKey(Group, on_delete=models.CASCADE, null=True, blank=True)
    message      = models.ForeignKey(Message, on_delete=models.CASCADE, null=True, blank=True)
    message_groupe = models.ForeignKey(GroupMessage, on_delete=models.CASCADE, null=True, blank=True)
    lu           = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class NotificationSysteme(models.Model):
    TYPE_CHOICES = [
        ('stock_faible',          'Stock faible'),
        ('rupture_stock',         'Rupture de stock'),
        ('expiration',            'Expiration proche'),
        ('reservation_confirmee', 'Réservation confirmée'),
        ('reservation_annulee',   'Réservation annulée'),
        ('reservation_recuperee', 'Réservation récupérée'),
        ('nouvelle_reservation',  'Nouvelle réservation'),
    ]

    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications_systeme'
    )
    type       = models.CharField(max_length=30, choices=TYPE_CHOICES)
    titre      = models.CharField(max_length=200)
    message    = models.TextField()
    lu         = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.type}] → {self.destinataire.email}"