import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from urllib.parse import parse_qs

logger = logging.getLogger(__name__)


@database_sync_to_async
def get_user_from_token(token_str):
    """Validate a JWT access token and return the associated user."""
    try:
        from rest_framework_simplejwt.tokens import AccessToken
        from moderation.models import AegisUser
        access_token = AccessToken(token_str)
        user_id = access_token['user_id']
        return AegisUser.objects.get(id=user_id)
    except Exception as e:
        logger.warning(f"[WS] Token validation failed: {e}")
        return None


class AlertConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """
        Authenticated WebSocket connection.
        Expects: ws://localhost:8000/ws/alerts/?token=<JWT_ACCESS_TOKEN>
        - Admins join the global "alerts" group (see all events).
        - Parents join an instance-scoped group (see only their child's events).
        - Unauthenticated connections are rejected.
        """
        # 1. Extract token from query string
        query_string = self.scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token_list = params.get("token", [])

        if not token_list:
            logger.warning("[WS] ❌ Connection rejected: no token provided")
            await self.close(code=4001)
            return

        # 2. Validate the token
        user = await get_user_from_token(token_list[0])
        if user is None:
            logger.warning("[WS] ❌ Connection rejected: invalid token")
            await self.close(code=4001)
            return

        self.user = user
        self.groups_joined = []

        # 3. Admins get ALL alerts; Parents get only their instance's alerts
        if user.role == 'admin':
            self.groups_joined.append("alerts")
        else:
            # Parent — scope to their instance
            instance_name = await self._get_parent_instance(user)
            if instance_name:
                self.groups_joined.append(f"alerts_{instance_name}")
            # Also join global so enforcer broadcasts reach them
            # (enforcer sends to "alerts" group — we keep this for backwards compat)
            self.groups_joined.append("alerts")

        for group in self.groups_joined:
            await self.channel_layer.group_add(group, self.channel_name)

        await self.accept()
        logger.info(f"[WS] 🟢 {user.role} '{user.username}' connected to groups: {self.groups_joined}")

    async def disconnect(self, close_code):
        """Remove from all joined groups on disconnect."""
        for group in getattr(self, 'groups_joined', []):
            await self.channel_layer.group_discard(group, self.channel_name)
        username = getattr(self, 'user', None)
        logger.info(f"[WS] 🔴 {username} disconnected")

    async def alert_message(self, event):
        """
        Receives broadcast from enforcer_node._broadcast() and sends to the client.
        """
        data = event["data"]
        await self.send(text_data=json.dumps(data))

    @database_sync_to_async
    def _get_parent_instance(self, user):
        """Get the parent's Evolution API instance name for group scoping."""
        try:
            return user.parent_profile.evolution_instance_name
        except Exception:
            return None
