import json
from channels.generic.websocket import AsyncWebsocketConsumer
import logging

logger = logging.getLogger(__name__)

class AlertConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """
        When Angular creates the WebSocket (ws://localhost:8000/ws/alerts/),
        this function accepts the connection and adds them to the "alerts" broadcast group.
        """
        self.group_name = "alerts"

        # Join the broadcast group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        # Accept the front-end connection
        await self.accept()
        logger.info(f"[WS] 🟢 Angular Dashboard connected to {self.group_name}")

    async def disconnect(self, close_code):
        """When Angular closes the tab, we remove them from the group."""
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        logger.info("[WS] 🔴 Angular Dashboard disconnected")

    async def alert_message(self, event):
        """
        This is the function that gets called by our views.py `_push_websocket_alert`!
        It receives the data from Django internally, and sends it directly over the internet to Angular.
        """
        data = event["data"]

        # Send message to WebSocket
        await self.send(text_data=json.dumps(data))
