from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import models
from django.contrib.auth import get_user_model

from .models import Conversation, Message, UserPresence, NotificationMessage, Group, GroupMessage
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    PresenceSerializer,
    NotificationMessageSerializer,
    GroupSerializer,
    GroupMessageSerializer,
)
from pharmacies.models import Pharmacie


class ConversationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # Citoyen voit ses conversations
        if user.roles.filter(name="citoyen").exists():
            qs = (
                Conversation.objects.filter(citoyen=user)
                .select_related("pharmacie", "pharmacie__proprietaire")
                .prefetch_related("messages")
            )
        elif user.roles.filter(name="administrateur").exists() or user.is_staff:
            # L'admin voit toutes les conversations ou celles où il est impliqué
            # Ici on suppose que l'admin peut parler à n'importe quel pharmacien
            qs = (
                Conversation.objects.all()
                .select_related("pharmacie", "pharmacie__proprietaire", "citoyen")
                .prefetch_related("messages")
            )
        else:
            # Pharmacien voit les conversations de sa pharmacie
            pharmacie = Pharmacie.objects.filter(proprietaire=user).first()
            if not pharmacie:
                pharmacie = user.pharmacies_travail.first()
            if not pharmacie:
                return Response([])
            qs = (
                Conversation.objects.filter(pharmacie=pharmacie)
                .select_related("pharmacie", "pharmacie__proprietaire", "citoyen")
                .prefetch_related("messages")
            )

        serializer = ConversationSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    def post(self, request):
        pharmacie_id = request.data.get("pharmacie_id")
        pharmacien_id = request.data.get("pharmacien_id")

        if pharmacien_id:
            # Cas Admin : on cherche la pharmacie du pharmacien (propriétaire ou employé)
            from pharmacies.models import Pharmacie
            from django.db.models import Q
            pharmacie = Pharmacie.objects.filter(
                Q(proprietaire_id=pharmacien_id) | Q(pharmaciens__id=pharmacien_id)
            ).distinct().first()
            
            if not pharmacie:
                return Response({"detail": "Pharmacien non trouvé ou non rattaché à une pharmacie."}, status=404)
        elif pharmacie_id:
            # Cas Citoyen : par ID de pharmacie
            from pharmacies.models import Pharmacie
            pharmacie = get_object_or_404(Pharmacie, id=pharmacie_id, est_active=True)
        else:
            return Response({"detail": "ID requis."}, status=400)

        conv, created = Conversation.objects.get_or_create(
            citoyen=request.user,
            pharmacie=pharmacie,
        )
        serializer = ConversationSerializer(conv, context={"request": request})
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class MessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        conv = get_object_or_404(Conversation, id=conversation_id)
        user = request.user

        # Vérifier accès
        pharmacie = Pharmacie.objects.filter(proprietaire=user).first()
        if not pharmacie:
            pharmacie = user.pharmacies_travail.first()

        is_pharmacien = pharmacie and conv.pharmacie == pharmacie
        is_citoyen = conv.citoyen == user
        is_admin = user.is_staff or user.roles.filter(name="administrateur").exists()

        if not is_pharmacien and not is_citoyen and not is_admin:
            return Response({"detail": "Accès refusé."}, status=403)

        # Marquer les messages comme lus
        conv.messages.filter(lu=False).exclude(expediteur=user).update(lu=True)


        """NotificationMessage.objects.filter(
            destinataire=user,
            Conversation=conv,
            lu = False
        ).update (lu= True)"""
        
        messages = conv.messages.select_related("expediteur").all()
        return Response(MessageSerializer(messages, many=True).data)

    def post(self, request, conversation_id):
        conv = get_object_or_404(Conversation, id=conversation_id)
        contenu = request.data.get("contenu", "").strip()
        if not contenu:
            return Response({"detail": "Contenu requis."}, status=400)

        message = Message.objects.create(
            conversation=conv,
            expediteur=request.user,
            contenu=contenu,
        )

        # Déterminer les destinataires pour la persistance et le WS
        destinataires = []
        if request.user == conv.citoyen:
            # Notifier le propriétaire ET les employés
            destinataires.append(conv.pharmacie.proprietaire)
            destinataires += list(conv.pharmacie.pharmaciens.all())
        elif request.user.is_staff or request.user.has_role('administrateur'):
            # Si l'admin parle, on notifie soit le citoyen soit le pharmacien
            # On peut aussi notifier les deux ou laisser la logique actuelle
            if conv.citoyen != request.user:
                destinataires.append(conv.citoyen)
            if conv.pharmacie.proprietaire != request.user:
                destinataires.append(conv.pharmacie.proprietaire)
        else:
            # C'est un pharmacien qui parle -> on notifie le citoyen
            destinataires.append(conv.citoyen)

        # Nettoyer les doublons et les None
        destinataires = list(set([d for d in destinataires if d and d != request.user]))

        for d in destinataires:
            NotificationMessage.objects.create(
                destinataire=d,
                conversation=conv,
                message=message,
            )

        from django.utils import timezone
        conv.updated_at = timezone.now()
        conv.save(update_fields=["updated_at"])

        # NOTIFICATION TEMPS RÉEL (WebSocket)
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            
            # 1. Dans la conversation active (pour ceux qui sont déjà dedans)
            async_to_sync(channel_layer.group_send)(
                f'chat_{conversation_id}',
                {
                    'type': 'chat_message',
                    'message': MessageSerializer(message).data
                }
            )
            
            # 2. Notification globale aux destinataires (pour le badge rouge)
            for d in destinataires:
                async_to_sync(channel_layer.group_send)(
                    f'notif_user_{d.id}',
                    {
                        'type': 'notification_message',
                        'notification': {
                            'id': message.id,
                            'conversation_id': conversation_id,
                            'expediteur_nom': request.user.get_full_name(),
                            'contenu': message.contenu,
                            'created_at': message.created_at.isoformat(),
                        }
                    }
                )
        except Exception as e:
            print(f"Erreur notification direct: {e}")

        return Response(MessageSerializer(message).data, status=201)


class UpdatePresenceView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        en_ligne = request.data.get("en_ligne", True)
        user = request.user

        # Mettre à jour la présence de l'utilisateur connecté
        UserPresence.objects.update_or_create(
            user=user, defaults={"en_ligne": en_ligne}
        )

        # Si c'est un pharmacien employé, on pourrait vouloir notifier sa pharmacie (optionnel)
        return Response({"ok": True})


class PresenceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        # On peut maintenant chercher la présence par n'importe quel user_id (UUID)
        user = get_object_or_404(get_user_model(), id=user_id)
        try:
            presence = user.presence
            return Response(PresenceSerializer(presence).data)
        except UserPresence.DoesNotExist:
            return Response({"en_ligne": False, "last_seen": None})


class GroupListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Un utilisateur voit les groupes dont il est membre ou qu'il a créé
        user = request.user
        qs = Group.objects.filter(models.Q(membres=user) | models.Q(createur=user)).distinct()
        return Response(GroupSerializer(qs, many=True).data)

    def post(self, request):
        # Seul un admin ou superadmin peut créer un groupe (selon la demande)
        if not (request.user.is_staff or request.user.has_role('administrateur')):
            return Response({"detail": "Seuls les administrateurs peuvent créer des groupes."}, status=403)
        
        nom = request.data.get("nom")
        membres_ids = request.data.get("membres", [])
        
        if not nom:
            return Response({"detail": "Le nom du groupe est requis."}, status=400)
        
        group = Group.objects.create(nom=nom, createur=request.user)
        
        if membres_ids:
            if isinstance(membres_ids, str):
                membres_ids = [membres_ids]
            group.membres.add(*membres_ids)
        
        # Le créateur est toujours membre
        group.membres.add(request.user)
        
        return Response(GroupSerializer(group).data, status=201)


class GroupMessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, group_id):
        group = get_object_or_404(Group, id=group_id)
        if not group.membres.filter(id=request.user.id).exists():
            return Response({"detail": "Accès refusé."}, status=403)
        
        messages = group.messages.select_related("expediteur").all()
        return Response(GroupMessageSerializer(messages, many=True).data)

    def post(self, request, group_id):
        group = get_object_or_404(Group, id=group_id)
        if not group.membres.filter(id=request.user.id).exists():
            return Response({"detail": "Accès refusé."}, status=403)
        
        contenu = request.data.get("contenu", "").strip()
        if not contenu:
            return Response({"detail": "Contenu requis."}, status=400)
        
        message = GroupMessage.objects.create(
            groupe=group,
            expediteur=request.user,
            contenu=contenu
        )
        
        group.save() # Pour update updated_at
        
        # NOTIFICATION TEMPS RÉEL AUX MEMBRES
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            
            # 1. Diffuser dans le groupe de discussion
            async_to_sync(channel_layer.group_send)(
                f'chat_group_{group_id}',
                {
                    'type': 'group_message',
                    'message': GroupMessageSerializer(message).data
                }
            )
            
            # 2. Notifier les membres individuellement (pour l'icône de notification)
            membres = group.membres.all()
            for membre in membres:
                if membre.id == request.user.id:
                    continue
                
                # Persistance
                NotificationMessage.objects.create(
                    destinataire=membre,
                    groupe=group,
                    message_groupe=message
                )

                async_to_sync(channel_layer.group_send)(
                    f'notif_user_{membre.id}',
                    {
                        'type': 'notification_message',
                        'notification': {
                            'id': f"group-{message.id}",
                            'group_id': str(group.id),
                            'expediteur_nom': request.user.get_full_name(),
                            'contenu': message.contenu,
                            'created_at': message.created_at.isoformat(),
                        }
                    }
                )
        except Exception as e:
            print(f"Erreur notification groupe: {e}")
        
        return Response(GroupMessageSerializer(message).data, status=201)

class NotificationsMarquerToutesLuesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        NotificationMessage.objects.filter(
            destinataire=request.user, lu=False
        ).update(lu=True)
        return Response({"detail": "Toutes marquées comme lues."})
    
    
class NotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = NotificationMessage.objects.filter(
            destinataire=request.user, lu=False
        ).select_related("conversation__pharmacie", "message__expediteur")
        return Response(NotificationMessageSerializer(qs, many=True).data)

    def patch(self, request, notif_id):
        notif = get_object_or_404(
            NotificationMessage, id=notif_id, destinataire=request.user
        )
        notif.lu = True
        notif.save(update_fields=["lu"])
        return Response({"detail": "Marquée comme lue."})


class NotificationSystemeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import NotificationSysteme
        qs = NotificationSysteme.objects.filter(destinataire=request.user, lu=False)
        data = [
            {
                'id':         n.id,
                'type':       n.type,
                'titre':      n.titre,
                'message':    n.message,
                'lu':         n.lu,
                'created_at': n.created_at.isoformat(),
            }
            for n in qs
        ]
        return Response(data)

    def patch(self, request, notif_id=None):
        from .models import NotificationSysteme
        qs = NotificationSysteme.objects.filter(destinataire=request.user)
        if notif_id:
            qs = qs.filter(pk=notif_id)
        qs.update(lu=True)
        return Response({'detail': 'Marquée(s) comme lue(s).'})


class PharmaciesDisponiblesView(APIView):
    """Liste des pharmacies actives avec statut en ligne du pharmacien."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        pharmacies = Pharmacie.objects.filter(est_active=True).select_related(
            "proprietaire__presence", "delegation"
        )
        data = []
        for p in pharmacies:
            en_ligne = False
            # La pharmacie est en ligne si le propriétaire OU un employé est en ligne
            ids_interesses = [p.proprietaire_id] if p.proprietaire_id else []
            ids_interesses += list(p.pharmaciens.values_list('id', flat=True))
            
            if UserPresence.objects.filter(user_id__in=ids_interesses, en_ligne=True).exists():
                en_ligne = True
                
            data.append(
                {
                    "id": str(p.id),
                    "nom": p.nom,
                    "adresse": p.adresse,
                    "telephone": p.telephone,
                    "en_ligne": en_ligne,
                    "proprietaire_id": str(p.proprietaire_id) if p.proprietaire_id else None,
                }
            )
        return Response(data)
