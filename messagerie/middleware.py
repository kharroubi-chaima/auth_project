from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
import jwt


@database_sync_to_async
def get_user(token):
    from accounts.models import User
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        return User.objects.get(id=payload['user_id'])
    except Exception as e:
        print(f"JWT Decode Error: {e}")
        return AnonymousUser()


class JWTAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        query_string = parse_qs(scope['query_string'].decode())
        token = query_string.get('token', [None])[0]

        if token:
            scope['user'] = await get_user(token)
        else:
            # Essaie aussi depuis les cookies
            headers = dict(scope.get('headers', []))
            cookie_header = headers.get(b'cookie', b'').decode()
            token = None
            for part in cookie_header.split(';'):
                part = part.strip()
                if part.startswith('access_token='):
                    token = part.split('=', 1)[1]
                    break
            scope['user'] = await get_user(token) if token else AnonymousUser()
            if scope['user'].is_anonymous:
                print(f"WS Connection REJECTED: User is Anonymous (Token: {token[:10] if token else 'None'}...)")
            else:
                print(f"WS Connection ACCEPTED: User {scope['user'].email}")

        return await self.app(scope, receive, send)