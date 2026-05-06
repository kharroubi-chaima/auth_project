import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope['user']
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'

        if self.user.is_anonymous:
            await self.close()
            return

        # Vérifier accès à la conversation
        if not await self.can_access(self.conversation_id, self.user):
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Marquer pharmacien en ligne
        await self.set_presence(True)

    async def disconnect(self, _code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        await self.set_presence(False)

    async def receive(self, text_data):
        data = json.loads(text_data)
        contenu = data.get('contenu', '').strip()
        if not contenu:
            return

        message = await self.save_message(contenu)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': {
                    'id':           message.id,
                    'contenu':      message.contenu,
                    'expediteur_id': message.expediteur_id,
                    'expediteur_nom': f"{self.user.first_name} {self.user.last_name}".strip() or self.user.email,
                    'created_at':   message.created_at.isoformat(),
                    'lu':           message.lu,
                }
            }
        )

        # Notifier l'autre participant
        await self.notifier_destinataire(message)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event['message']))

    @database_sync_to_async
    def can_access(self, conversation_id, user):
        from .models import Conversation
        try:
            conv = Conversation.objects.select_related('citoyen', 'pharmacie').get(id=conversation_id)
            # Citoyen de la conversation
            if conv.citoyen == user:
                return True
            # Propriétaire ou pharmacien employé
            if conv.pharmacie.proprietaire == user:
                return True
            if user.pharmacies_travail.filter(id=conv.pharmacie.id).exists():
                return True
            return False
        except Conversation.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, contenu):
        from .models import Conversation, Message
        conv = Conversation.objects.get(id=self.conversation_id)
        conv.updated_at = timezone.now()
        conv.save(update_fields=['updated_at'])
        return Message.objects.create(
            conversation=conv,
            expediteur=self.user,
            contenu=contenu,
        )

    @database_sync_to_async
    def set_presence(self, en_ligne):
        from .models import PresencePharmacien
        from accounts.models import User
        user = User.objects.filter(pk=self.user.pk, roles__name='pharmacien').first()
        if user:
            PresencePharmacien.objects.update_or_create(
                user=user,
                defaults={'en_ligne': en_ligne}
            )

    @database_sync_to_async
    def notifier_destinataire(self, message):
        from .models import Conversation
        conv = Conversation.objects.select_related(
            'citoyen', 'pharmacie', 'pharmacie__proprietaire'
        ).get(id=self.conversation_id)

        # Destinataire = l'autre participant
        if message.expediteur == conv.citoyen:
            destinataire = conv.pharmacie.proprietaire
        else:
            destinataire = conv.citoyen

        if destinataire:
            from .models import NotificationMessage
            NotificationMessage.objects.create(
                destinataire=destinataire,
                conversation=conv,
                message=message,
            )


class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope['user']
        if self.user.is_anonymous:
            await self.close()
            return
        self.group_name = f'notif_user_{self.user.pk}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        # Envoyer les notifications non lues dès la connexion
        unread = await self.get_unread()
        if unread:
            await self.send(text_data=json.dumps({'type': 'unread_list', 'notifications': unread}))

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get('action') == 'mark_read':
            notif_id = data.get('id')
            if notif_id:
                await self.mark_as_read(notif_id)
        elif data.get('action') == 'mark_all_read':
            await self.mark_all_read()

    async def notification_message(self, event):
        await self.send(text_data=json.dumps(event['notification']))

    @database_sync_to_async
    def get_unread(self):
        from .models import NotificationSysteme
        return [
            {
                'id':         n.id,
                'type':       n.type,
                'titre':      n.titre,
                'message':    n.message,
                'lu':         n.lu,
                'created_at': n.created_at.isoformat(),
            }
            for n in NotificationSysteme.objects.filter(destinataire=self.user, lu=False)
        ]

    @database_sync_to_async
    def mark_as_read(self, notif_id):
        from .models import NotificationSysteme
        NotificationSysteme.objects.filter(pk=notif_id, destinataire=self.user).update(lu=True)

    @database_sync_to_async
    def mark_all_read(self):
        from .models import NotificationSysteme
        NotificationSysteme.objects.filter(destinataire=self.user, lu=False).update(lu=True)