from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/chats/<int:thread_id>/", consumers.SignalChatConsumer.as_asgi()),
]
