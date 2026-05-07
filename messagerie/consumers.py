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

    async def disconnect(self, _code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

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
            # Admin ou staff
            if user.is_staff or user.roles.filter(name="administrateur").exists():
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
    def set_presence(self, user, en_ligne):
        from .models import UserPresence
        UserPresence.objects.update_or_create(
            user=user,
            defaults={'en_ligne': en_ligne}
        )

    async def notifier_destinataire(self, message):
        res = await self.get_or_create_notification(message)
        if not res:
            return
        
        destinataire_id, notif_id, conversation_id, expediteur_nom = res

        await self.channel_layer.group_send(
            f'notif_user_{destinataire_id}',
            {
                'type': 'notification_message',
                'notification': {
                    'id': notif_id,
                    'conversation_id': conversation_id,
                    'expediteur_nom': expediteur_nom,
                    'contenu': message.contenu,
                    'created_at': message.created_at.isoformat(),
                }
            }
        )

    @database_sync_to_async
    def get_or_create_notification(self, message):
        from .models import Conversation, NotificationMessage
        try:
            conv = Conversation.objects.select_related(
                'citoyen', 'pharmacie', 'pharmacie__proprietaire'
            ).get(id=self.conversation_id)

            if message.expediteur == conv.citoyen:
                destinataire = conv.pharmacie.proprietaire
            else:
                destinataire = conv.citoyen

            if not destinataire:
                return None

            notif = NotificationMessage.objects.create(
                destinataire=destinataire,
                conversation=conv,
                message=message,
            )
            
            expediteur_nom = f"{message.expediteur.first_name} {message.expediteur.last_name}".strip() or message.expediteur.email
            return (destinataire.pk, notif.id, conv.id, expediteur_nom)
        except Exception:
            return None


class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope['user']
        if self.user.is_anonymous:
            await self.close()
            return
        
        self.group_name = f'notif_user_{self.user.pk}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.channel_layer.group_add('global_presence', self.channel_name)
        await self.accept()
        
        # Marquer l'utilisateur en ligne globalement
        await self.set_presence(self.user, True)
        await self.diffuser_presence(True)
        
        # Envoyer les notifications non lues dès la connexion
        unread = await self.get_unread()
        if unread:
            await self.send(text_data=json.dumps({'type': 'unread_list', 'notifications': unread}))

    async def disconnect(self, close_code):
        try:
            if hasattr(self, 'user') and not self.user.is_anonymous:
                # Marquer l'utilisateur hors ligne globalement
                await self.set_presence(self.user, False)
                await self.diffuser_presence(False)
                
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
                await self.channel_layer.group_discard('global_presence', self.channel_name)
        except Exception as e:
            print(f"Error in disconnect: {e}")

    async def diffuser_presence(self, en_ligne):
        try:
            await self.channel_layer.group_send(
                'global_presence',
                {
                    'type': 'presence_change',
                    'user_id': str(self.user.id),
                    'en_ligne': en_ligne
                }
            )
        except: pass

    async def presence_change(self, event):
        try:
            await self.send(text_data=json.dumps(event))
        except: pass

    @database_sync_to_async
    def set_presence(self, user, en_ligne):
        from .models import UserPresence
        try:
            UserPresence.objects.update_or_create(
                user=user,
                defaults={'en_ligne': en_ligne}
            )
        except Exception as e:
            print(f"Presence error: {e}")

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get('action') == 'mark_read':
            notif_id = data.get('id')
            if notif_id:
                await self.mark_as_read(notif_id)
        elif data.get('action') == 'mark_all_read':
            await self.mark_all_read()

    async def notification_message(self, event):
        await self.send(text_data=json.dumps(event))

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


class GroupChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        self.group_id = self.scope['url_route']['kwargs']['group_id']
        self.room_group_name = f'group_chat_{self.group_id}'

        if self.user.is_anonymous:
            await self.close()
            return

        # Vérifier si l'utilisateur est membre du groupe
        if not await self.is_member(self.group_id, self.user):
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, _code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        contenu = data.get('contenu', '').strip()
        if not contenu:
            return

        message = await self.save_message(contenu)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'group_message',
                'message': {
                    'id':            message.id,
                    'contenu':       message.contenu,
                    'expediteur_id':  str(message.expediteur_id),
                    'expediteur_nom': f"{self.user.first_name} {self.user.last_name}".strip() or self.user.email,
                    'created_at':    message.created_at.isoformat(),
                }
            }
        )

        # Notifier tous les membres du groupe
        await self.notifier_membres(message)

    async def group_message(self, event):
        await self.send(text_data=json.dumps(event['message']))

    @database_sync_to_async
    def is_member(self, group_id, user):
        from .models import Group
        try:
            is_member = Group.objects.filter(id=group_id, membres=user).exists()
            if is_member: return True
            # Admin ou staff
            return user.is_staff or user.roles.filter(name="administrateur").exists()
        except Exception:
            return False

    @database_sync_to_async
    def save_message(self, contenu):
        from .models import Group, GroupMessage
        group = Group.objects.get(id=self.group_id)
        return GroupMessage.objects.create(
            groupe=group,
            expediteur=self.user,
            contenu=contenu,
        )

    async def notifier_membres(self, message):
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        
        # Récupérer les membres du groupe en async
        membres = await self.get_group_members()
        
        for membre_id in membres:
            if str(membre_id) == str(self.user.pk):
                continue
            
            await channel_layer.group_send(
                f'notif_user_{membre_id}',
                {
                    'type': 'notification_message',
                    'notification': {
                        'id': f"group-{message.id}",
                        'group_id': str(message.groupe_id),
                        'expediteur_nom': f"{self.user.first_name} {self.user.last_name}".strip() or self.user.email,
                        'contenu': message.contenu,
                        'created_at': message.created_at.isoformat(),
                    }
                }
            )

    @database_sync_to_async
    def get_group_members(self):
        from .models import Group
        group = Group.objects.get(id=self.group_id)
        return list(group.membres.values_list('id', flat=True))