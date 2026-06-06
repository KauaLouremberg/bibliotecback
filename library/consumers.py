import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from .chat_services import (
    broadcast_chat_message,
    create_chat_message,
    user_can_access_thread,
)
from .models import SignalChatThread


class SignalChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.thread_id = int(self.scope["url_route"]["kwargs"]["thread_id"])
        user = self.scope["user"]
        if isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return

        thread = await self._get_thread(self.thread_id)
        if thread is None or not user_can_access_thread(user, thread):
            await self.close(code=4403)
            return

        self.room_group_name = f"chat_{self.thread_id}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        user = self.scope["user"]
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return
        body = str(payload.get("body", "")).strip()
        if not body:
            return

        message = await self._save_message(self.thread_id, user, body)
        if message is None:
            return

        await self._broadcast(message)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({"type": "message", "message": event["message"]}))

    @database_sync_to_async
    def _get_thread(self, thread_id: int) -> SignalChatThread | None:
        return SignalChatThread.objects.filter(pk=thread_id).first()

    @database_sync_to_async
    def _save_message(self, thread_id: int, user, body: str):
        thread = SignalChatThread.objects.filter(pk=thread_id).first()
        if thread is None:
            return None
        return create_chat_message(thread, user, body)

    @database_sync_to_async
    def _broadcast(self, message):
        message = type(message).objects.select_related("sender").get(pk=message.pk)
        broadcast_chat_message(message)
