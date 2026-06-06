from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

from accounts.models import User

from .models import SignalChatMessage, SignalChatThread, SocialPost


def serialize_chat_message(message: SignalChatMessage) -> dict:
    sender = message.sender
    return {
        "id": message.pk,
        "thread_id": message.thread_id,
        "sender_id": sender.pk,
        "sender_name": sender.full_name or sender.email,
        "body": message.body,
        "created_at": message.created_at.isoformat(),
    }


def broadcast_chat_message(message: SignalChatMessage) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        f"chat_{message.thread_id}",
        {
            "type": "chat.message",
            "message": serialize_chat_message(message),
        },
    )


def user_can_access_thread(user: User, thread: SignalChatThread) -> bool:
    return user.pk in {thread.initiator_id, thread.owner_id}


def get_thread_for_user(user: User, thread_id: int) -> SignalChatThread | None:
    thread = (
        SignalChatThread.objects.select_related("post", "initiator", "owner")
        .filter(pk=thread_id)
        .first()
    )
    if thread is None or not user_can_access_thread(user, thread):
        return None
    return thread


def open_signal_chat(post: SocialPost, initiator: User) -> tuple[SignalChatThread | None, str | None]:
    if initiator.pk == post.owner_id:
        return None, "Você não pode abrir chat consigo mesmo sobre o seu sinal."
    thread, _ = SignalChatThread.objects.get_or_create(
        post=post,
        initiator=initiator,
        defaults={"owner_id": post.owner_id},
    )
    return thread, None


def create_chat_message(thread: SignalChatThread, sender: User, body: str) -> SignalChatMessage | None:
    cleaned = body.strip()
    if not cleaned or len(cleaned) > 2000:
        return None
    if not user_can_access_thread(sender, thread):
        return None
    message = SignalChatMessage.objects.create(thread=thread, sender=sender, body=cleaned)
    SignalChatThread.objects.filter(pk=thread.pk).update(last_message_at=timezone.now())
    return message


def close_signal_chat(user: User, thread_id: int) -> tuple[bool, str | None]:
    thread = get_thread_for_user(user, thread_id)
    if thread is None:
        return False, "Conversa não encontrada."
    thread.delete()
    return True, None
