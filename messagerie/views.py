from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import Conversation, Message, PresencePharmacien, NotificationMessage
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    PresenceSerializer,
    NotificationMessageSerializer,
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
        # Seul le citoyen peut créer une conversation
        pharmacie_id = request.data.get("pharmacie_id")
        if not pharmacie_id:
            return Response({"detail": "pharmacie_id requis."}, status=400)

        pharmacie = get_object_or_404(Pharmacie, id=pharmacie_id, est_active=True)

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

        if not is_pharmacien and not is_citoyen:
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

        # Notifier l'autre participant
        if request.user == conv.citoyen:
            destinataire = conv.pharmacie.proprietaire
        else:
            destinataire = conv.citoyen

        if destinataire:
            NotificationMessage.objects.create(
                destinataire=destinataire,
                conversation=conv,
                message=message,
            )

        from django.utils import timezone

        conv.updated_at = timezone.now()
        conv.save(update_fields=["updated_at"])

        return Response(MessageSerializer(message).data, status=201)


class UpdatePresenceView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        en_ligne = request.data.get("en_ligne", True)
        user = request.user

        # Mettre à jour la présence de l'utilisateur connecté
        PresencePharmacien.objects.update_or_create(
            user=user, defaults={"en_ligne": en_ligne}
        )

        # Si c'est un employé, mettre à jour aussi le proprietaire de sa pharmacie
        pharmacie = Pharmacie.objects.filter(proprietaire=user).first()
        if not pharmacie:
            pharmacie = user.pharmacies_travail.first()

        if pharmacie and pharmacie.proprietaire:
            PresencePharmacien.objects.update_or_create(
                user=pharmacie.proprietaire, defaults={"en_ligne": en_ligne}
            )

        return Response({"ok": True})


class PresenceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pharmacie_id):
        pharmacie = get_object_or_404(Pharmacie, id=pharmacie_id)
        proprietaire = pharmacie.proprietaire
        if not proprietaire:
            return Response({"en_ligne": False, "last_seen": None})
        try:
            presence = proprietaire.presence
            return Response(PresenceSerializer(presence).data)
        except PresencePharmacien.DoesNotExist:
            return Response({"en_ligne": False, "last_seen": None})

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
            try:
                if p.proprietaire and p.proprietaire.presence.en_ligne:
                    en_ligne = True
            except Exception:
                pass
            data.append(
                {
                    "id": str(p.id),
                    "nom": p.nom,
                    "adresse": p.adresse,
                    "telephone": p.telephone,
                    "en_ligne": en_ligne,
                }
            )
        return Response(data)
