from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/messagerie/(?P<conversation_id>\d+)/', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/messagerie/group/(?P<group_id>[0-9a-f-]+)/', consumers.GroupChatConsumer.as_asgi()),
    re_path(r'ws/notifications/', consumers.NotificationConsumer.as_asgi()),
]