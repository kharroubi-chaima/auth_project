from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import models
from django.contrib.auth import get_user_model

from .models import Conversation, Message, UserPresence, Group, GroupMessage
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    PresenceSerializer,
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
        elif user.roles.filter(name="gérant").exists() or user.is_staff:
            # L'admin voit toutes les conversations ou celles où il est impliqué
            # Ici on suppose que l'admin peut parler à n'importe quel pharmacien
            qs = (
                Conversation.objects.all()
                .select_related("pharmacie", "pharmacie__proprietaire", "citoyen")
                .prefetch_related("messages")
            )
        else:
            # Pharmacien voit les conversations de toutes ses pharmacies (propriétaire ou employé)
            from django.db.models import Q
            qs = (
                Conversation.objects.filter(
                    Q(pharmacie__proprietaire=user) | Q(pharmacie__pharmaciens=user)
                )
                .distinct()
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

        is_pharmacien = (
            conv.pharmacie.proprietaire == user or
            conv.pharmacie.pharmaciens.filter(id=user.id).exists()
        )
        is_citoyen = conv.citoyen == user
        is_admin = user.is_staff or user.roles.filter(name="gérant").exists()

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
        elif request.user.is_staff or request.user.has_role('gérant'):
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
        if not (request.user.is_staff or request.user.has_role('gérant')):
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
        if group.createur != request.user and not group.membres.filter(id=request.user.id).exists():
            return Response({"detail": "Accès refusé."}, status=403)
        
        messages = group.messages.select_related("expediteur").all()
        return Response(GroupMessageSerializer(messages, many=True).data)

    def post(self, request, group_id):
        group = get_object_or_404(Group, id=group_id)
        if group.createur != request.user and not group.membres.filter(id=request.user.id).exists():
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
                f'group_chat_{group_id}',
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


class GroupMessageDetailView(APIView):
    """Permet d'éditer ou supprimer un message de groupe."""
    permission_classes = [IsAuthenticated]

    EDIT_WINDOW_MINUTES = 15

    def patch(self, request, message_id):
        message = get_object_or_404(GroupMessage, id=message_id)

        # Seul l'expéditeur du message peut le modifier
        if message.expediteur != request.user:
            return Response({"detail": "Non autorisé."}, status=403)

        # Vérifier la fenêtre de modification (15 minutes)
        from django.utils import timezone
        from datetime import timedelta
        delai = timezone.now() - message.created_at
        if delai > timedelta(minutes=self.EDIT_WINDOW_MINUTES):
            minutes_restantes = 0
            return Response(
                {"detail": f"Impossible de modifier un message après {self.EDIT_WINDOW_MINUTES} minutes."},
                status=403
            )

        contenu = request.data.get("contenu", "").strip()
        if not contenu:
            return Response({"detail": "Le contenu ne peut pas être vide."}, status=400)

        message.contenu = contenu
        message.save(update_fields=["contenu"])

        # NOTIFICATION TEMPS RÉEL (WebSocket) de la modification
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            
            async_to_sync(channel_layer.group_send)(
                f'group_chat_{message.groupe.id}',
                {
                    'type': 'group_message',
                    'message': GroupMessageSerializer(message).data
                }
            )
        except Exception as e:
            print(f"Erreur notification modification groupe: {e}")

        return Response(GroupMessageSerializer(message).data)

    def delete(self, request, message_id):
        message = get_object_or_404(GroupMessage, id=message_id)

        # Seul l'expéditeur ou un admin peut supprimer
        is_admin = request.user.is_staff or request.user.roles.filter(name="gérant").exists()
        if message.expediteur != request.user and not is_admin:
            return Response({"detail": "Non autorisé."}, status=403)

        message.delete()
        return Response(status=204)


class MessageDetailView(APIView):
    """Permet d'éditer ou supprimer un message individuel."""
    permission_classes = [IsAuthenticated]

    EDIT_WINDOW_MINUTES = 15

    def patch(self, request, message_id):
        message = get_object_or_404(Message, id=message_id)

        # Seul l'expéditeur du message peut le modifier
        if message.expediteur != request.user:
            return Response({"detail": "Non autorisé."}, status=403)

        # Vérifier la fenêtre de modification (15 minutes)
        from django.utils import timezone
        from datetime import timedelta
        delai = timezone.now() - message.created_at
        if delai > timedelta(minutes=self.EDIT_WINDOW_MINUTES):
            return Response(
                {"detail": f"Impossible de modifier un message après {self.EDIT_WINDOW_MINUTES} minutes."},
                status=403
            )

        contenu = request.data.get("contenu", "").strip()
        if not contenu:
            return Response({"detail": "Le contenu ne peut pas être vide."}, status=400)

        message.contenu = contenu
        message.save(update_fields=["contenu"])

        # NOTIFICATION TEMPS RÉEL (WebSocket) de la modification
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            
            async_to_sync(channel_layer.group_send)(
                f'chat_{message.conversation.id}',
                {
                    'type': 'chat_message',
                    'message': MessageSerializer(message).data
                }
            )
        except Exception as e:
            print(f"Erreur notification modification message: {e}")

        return Response(MessageSerializer(message).data)

    def delete(self, request, message_id):
        message = get_object_or_404(Message, id=message_id)

        # Seul l'expéditeur ou un admin peut supprimer
        is_admin = request.user.is_staff or request.user.roles.filter(name="gérant").exists()
        if message.expediteur != request.user and not is_admin:
            return Response({"detail": "Non autorisé."}, status=403)

        message.delete()
        return Response(status=204)

class NotificationsMarquerToutesLuesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        from django.db.models import Q
        if user.roles.filter(name="citoyen").exists():
            conversations = Conversation.objects.filter(citoyen=user)
        elif user.roles.filter(name="gérant").exists() or user.is_staff:
            conversations = Conversation.objects.all()
        else:
            conversations = Conversation.objects.filter(
                Q(pharmacie__proprietaire=user) | Q(pharmacie__pharmaciens=user)
            ).distinct()

        Message.objects.filter(
            conversation__in=conversations,
            lu=False
        ).exclude(expediteur=user).update(lu=True)
        return Response({"detail": "Toutes marquées comme lues."})


class NotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        from django.db.models import Q
        if user.roles.filter(name="citoyen").exists():
            conversations = Conversation.objects.filter(citoyen=user)
        elif user.roles.filter(name="gérant").exists() or user.is_staff:
            conversations = Conversation.objects.all()
        else:
            conversations = Conversation.objects.filter(
                Q(pharmacie__proprietaire=user) | Q(pharmacie__pharmaciens=user)
            ).distinct()

        recent_messages = Message.objects.filter(
            conversation__in=conversations
        ).exclude(expediteur=user).select_related("conversation__pharmacie", "expediteur").order_by('-created_at')[:15]

        data = []
        for msg in recent_messages:
            data.append({
                'id': msg.id,
                'conversation_id': msg.conversation.id,
                'pharmacie_nom': msg.conversation.pharmacie.nom,
                'expediteur_nom': f"{msg.expediteur.first_name} {msg.expediteur.last_name}".strip() or msg.expediteur.email,
                'contenu': msg.contenu,
                'lu': msg.lu,
                'created_at': msg.created_at.isoformat()
            })
        return Response(data)

    def patch(self, request, notif_id):
        message = get_object_or_404(Message, id=notif_id)
        user = request.user
        conv = message.conversation
        is_part = (
            conv.citoyen == user or
            conv.pharmacie.proprietaire == user or
            conv.pharmacie.pharmaciens.filter(id=user.id).exists() or
            user.is_staff or user.roles.filter(name="gérant").exists()
        )
        if not is_part:
            return Response({"detail": "Accès refusé."}, status=403)

        message.lu = True
        message.save(update_fields=["lu"])
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

class GroupDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, group_id):
        group = get_object_or_404(Group, id=group_id)
        if group.createur != request.user:
            return Response({"detail": "Seul le créateur peut renommer le groupe."}, status=403)
        
        nom = request.data.get("nom")
        if not nom:
            return Response({"detail": "Le nom du groupe est requis."}, status=400)
            
        group.nom = nom
        group.save(update_fields=["nom"])
        return Response(GroupSerializer(group).data)

    def delete(self, request, group_id):
        group = get_object_or_404(Group, id=group_id)
        if group.createur != request.user:
            return Response({"detail": "Seul le créateur peut supprimer le groupe."}, status=403)
            
        group.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GroupMemberView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, group_id):
        group = get_object_or_404(Group, id=group_id)
        if group.createur != request.user:
            return Response({"detail": "Seul le créateur peut ajouter des membres."}, status=403)
            
        membre_id = request.data.get("membre_id")
        if not membre_id:
            return Response({"detail": "L'ID du membre est requis."}, status=400)
            
        User = get_user_model()
        membre = get_object_or_404(User, id=membre_id)
        
        group.membres.add(membre)
        
        return Response(GroupSerializer(group).data)


class GroupMemberDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, group_id, membre_id):
        group = get_object_or_404(Group, id=group_id)
        
        # Un membre peut se retirer lui-même, ou le créateur peut le retirer
        if str(request.user.id) != membre_id and group.createur != request.user:
            return Response({"detail": "Non autorisé."}, status=403)
            
        # Le créateur ne peut pas être retiré
        if str(group.createur.id) == membre_id:
            return Response({"detail": "Le créateur ne peut pas être retiré du groupe."}, status=400)
            
        User = get_user_model()
        membre = get_object_or_404(User, id=membre_id)
        
        group.membres.remove(membre)
        
        return Response({"detail": "Membre retiré avec succès."})


class PharmacienListView(APIView):
    """Retourne la liste de tous les pharmaciens pour l'ajout dans un groupe."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        User = get_user_model()
        pharmaciens = User.objects.filter(roles__name='pharmacien').values('id', 'nom', 'prenom', 'email')
        data = [
            {
                'id': str(p['id']),
                'nom': f"{p.get('prenom', '')} {p.get('nom', '')}".strip() or p['email'],
                'email': p['email'],
            }
            for p in pharmaciens
        ]
        return Response(data)

