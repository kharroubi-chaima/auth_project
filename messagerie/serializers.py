from rest_framework import serializers
from .models import Conversation, Message, UserPresence, Group, GroupMessage
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
    pharmacien_id      = serializers.CharField(source='pharmacie.proprietaire.id', read_only=True)
    pharmacien_nom     = serializers.SerializerMethodField()
    citoyen_id         = serializers.CharField(source='citoyen.id', read_only=True)
    citoyen_nom        = serializers.SerializerMethodField()
    dernier_message    = serializers.SerializerMethodField()
    non_lus            = serializers.SerializerMethodField()
    pharmacien_en_ligne = serializers.SerializerMethodField()
    citoyen_en_ligne = serializers.SerializerMethodField()
    partner_name = serializers.SerializerMethodField()
    partner_en_ligne = serializers.SerializerMethodField()

    class Meta:
        model  = Conversation
        fields = [
            'id', 'pharmacie_id', 'pharmacie_nom', 'pharmacien_id', 'pharmacien_nom',
            'citoyen_id', 'citoyen_nom', 'partner_name', 'partner_en_ligne',
            'dernier_message', 'non_lus',
            'pharmacien_en_ligne', 'citoyen_en_ligne', 'created_at', 'updated_at',
        ]

    def get_partner_name(self, obj):
        user = self.context['request'].user
        if user == obj.citoyen:
            # Si je suis le citoyen, mon partenaire est la pharmacie
            return obj.pharmacie.nom
        else:
            # Si je suis côté pharmacie, mon partenaire est le citoyen
            return f"{obj.citoyen.first_name} {obj.citoyen.last_name}".strip() or obj.citoyen.email

    def get_partner_en_ligne(self, obj):
        user = self.context['request'].user
        if user == obj.citoyen:
            return self.get_pharmacien_en_ligne(obj)
        else:
            return self.get_citoyen_en_ligne(obj)

    def get_pharmacien_nom(self, obj):
        if obj.pharmacie and obj.pharmacie.proprietaire:
            p = obj.pharmacie.proprietaire
            return f"{p.first_name} {p.last_name}".strip() or p.email
        return "Inconnu"

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
            # On vérifie si le propriétaire est en ligne
            proprietaire = obj.pharmacie.proprietaire
            if proprietaire and hasattr(proprietaire, 'presence') and proprietaire.presence.en_ligne:
                return True
            # Ou si un employé de la pharmacie est en ligne
            from accounts.models import User
            employes_ids = obj.pharmacie.pharmaciens.values_list('id', flat=True)
            if UserPresence.objects.filter(user_id__in=employes_ids, en_ligne=True).exists():
                return True
        except Exception:
            pass
        return False

    def get_citoyen_en_ligne(self, obj):
        try:
            return obj.citoyen.presence.en_ligne
        except Exception:
            return False


class PresenceSerializer(serializers.ModelSerializer):
    class Meta:
        model  = UserPresence
        fields = ['en_ligne', 'last_seen']


class GroupSerializer(serializers.ModelSerializer):
    createur_nom = serializers.SerializerMethodField()
    membres_count = serializers.IntegerField(source='membres.count', read_only=True)
    dernier_message = serializers.SerializerMethodField()
    membres = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ['id', 'nom', 'image', 'createur_id', 'createur_nom', 'membres_count', 'created_at', 'updated_at', 'dernier_message', 'membres']
        read_only_fields = ['id', 'created_at', 'updated_at', 'createur_id']

    def get_membres(self, obj):
        return [{'id': str(m.id), 'nom': f"{m.first_name} {m.last_name}".strip() or m.email} for m in obj.membres.all()]

    def get_createur_nom(self, obj):
        return f"{obj.createur.first_name} {obj.createur.last_name}".strip() or obj.createur.email

    def get_dernier_message(self, obj):
        msg = obj.messages.last()
        if not msg:
            return None
        return {
            'contenu': msg.contenu,
            'expediteur_nom': f"{msg.expediteur.first_name} {msg.expediteur.last_name}".strip() or msg.expediteur.email,
            'created_at': msg.created_at.isoformat()
        }


class GroupMessageSerializer(serializers.ModelSerializer):
    expediteur_nom = serializers.SerializerMethodField()
    expediteur_id = serializers.CharField(source='expediteur.id', read_only=True)

    class Meta:
        model = GroupMessage
        fields = ['id', 'groupe', 'expediteur_id', 'expediteur_nom', 'contenu', 'is_system', 'created_at']
        read_only_fields = ['id', 'created_at', 'expediteur_id', 'expediteur_nom']

    def get_expediteur_nom(self, obj):
        return f"{obj.expediteur.first_name} {obj.expediteur.last_name}".strip() or obj.expediteur.email


