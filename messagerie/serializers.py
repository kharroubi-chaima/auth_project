from rest_framework import serializers
from .models import Conversation, Message, PresencePharmacien, NotificationMessage
from django.contrib.auth import get_user_model

User = get_user_model()


class MessageSerializer(serializers.ModelSerializer):
    expediteur_nom = serializers.SerializerMethodField()
    expediteur_id  = serializers.CharField(source='expediteur.id', read_only=True)

    class Meta:
        model  = Message
        fields = ['id', 'conversation', 'expediteur_id', 'expediteur_nom', 'contenu', 'lu', 'created_at']
        read_only_fields = ['id', 'created_at', 'lu', 'expediteur_id', 'expediteur_nom']

    def get_expediteur_nom(self, obj):
        return f"{obj.expediteur.first_name} {obj.expediteur.last_name}".strip() or obj.expediteur.email


class ConversationSerializer(serializers.ModelSerializer):
    pharmacie_nom      = serializers.CharField(source='pharmacie.nom', read_only=True)
    pharmacie_id       = serializers.UUIDField(source='pharmacie.id', read_only=True)
    citoyen_nom        = serializers.SerializerMethodField()
    dernier_message    = serializers.SerializerMethodField()
    non_lus            = serializers.SerializerMethodField()
    pharmacien_en_ligne = serializers.SerializerMethodField()

    class Meta:
        model  = Conversation
        fields = [
            'id', 'pharmacie_id', 'pharmacie_nom',
            'citoyen_nom', 'dernier_message', 'non_lus',
            'pharmacien_en_ligne', 'created_at', 'updated_at',
        ]

    def get_citoyen_nom(self, obj):
        return f"{obj.citoyen.first_name} {obj.citoyen.last_name}".strip() or obj.citoyen.email

    def get_dernier_message(self, obj):
        msg = obj.messages.last()
        if not msg:
            return None
        return {'contenu': msg.contenu, 'created_at': msg.created_at.isoformat()}

    def get_non_lus(self, obj):
        user = self.context['request'].user
        return obj.messages.filter(lu=False).exclude(expediteur=user).count()

    def get_pharmacien_en_ligne(self, obj):
        try:
            proprietaire = obj.pharmacie.proprietaire
            if proprietaire:
                presence = proprietaire.presence
                return presence.en_ligne
        except Exception:
            pass
        return False


class PresenceSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PresencePharmacien
        fields = ['en_ligne', 'last_seen']


class NotificationMessageSerializer(serializers.ModelSerializer):
    conversation_id  = serializers.IntegerField(source='conversation.id', read_only=True)
    pharmacie_nom    = serializers.CharField(source='conversation.pharmacie.nom', read_only=True)
    expediteur_nom   = serializers.SerializerMethodField()
    contenu          = serializers.CharField(source='message.contenu', read_only=True)

    class Meta:
        model  = NotificationMessage
        fields = ['id', 'conversation_id', 'pharmacie_nom', 'expediteur_nom', 'contenu', 'lu', 'created_at']

    def get_expediteur_nom(self, obj):
        exp = obj.message.expediteur
        return f"{exp.first_name} {exp.last_name}".strip() or exp.email
    
