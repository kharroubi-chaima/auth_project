import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def envoyer_notification_ws(destinataire_id: int, type_notif: str, titre: str, message: str) -> bool:
    """
    Sauvegarde une NotificationSysteme en base et la pousse via WebSocket
    vers le groupe personnel de l'utilisateur (notif_user_{id}).
    Retourne True si succès, False sinon.
    """
    try:
        from .models import NotificationSysteme
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user = User.objects.filter(pk=destinataire_id).first()
        if not user:
            logger.warning(f"envoyer_notification_ws: utilisateur {destinataire_id} introuvable")
            return False

        notif = NotificationSysteme.objects.create(
            destinataire=user,
            type=type_notif,
            titre=titre,
            message=message,
        )

        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f'notif_user_{destinataire_id}',
                {
                    'type': 'notification_message',
                    'notification': {
                        'id':         notif.id,
                        'type':       type_notif,
                        'titre':      titre,
                        'message':    message,
                        'lu':         False,
                        'created_at': notif.created_at.isoformat(),
                    },
                }
            )
        return True

    except Exception as e:
        logger.error(f"Erreur notification WS (user {destinataire_id}): {e}")
        return False
