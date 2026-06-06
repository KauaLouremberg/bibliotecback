import logging

from accounts.models import User

from .models import LibraryNotification, SignalChatMessage, SignalChatThread, TradeRequest

logger = logging.getLogger(__name__)


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    if max_len <= 1:
        return text[:max_len]
    return text[: max_len - 1].rstrip() + "…"


def _actor_label(user: User) -> str:
    return (user.full_name or "").strip() or user.email


def notify(
    *,
    recipient_id: int,
    kind: str,
    title: str,
    body: str,
    actor_id: int | None = None,
    thread_id: int | None = None,
    trade_id: int | None = None,
    post_id: int | None = None,
) -> None:
    if recipient_id == actor_id:
        return
    LibraryNotification.objects.create(
        recipient_id=recipient_id,
        kind=kind,
        title=_truncate(title, 255),
        body=_truncate(body, 500),
        actor_id=actor_id,
        thread_id=thread_id,
        trade_id=trade_id,
        post_id=post_id,
    )


def notify_chat_started(thread: SignalChatThread, *, created: bool) -> None:
    if not created:
        return
    post = thread.post
    initiator = thread.initiator
    notify(
        recipient_id=thread.owner_id,
        kind=LibraryNotification.Kind.CHAT_STARTED,
        title="Nova conversa sobre seu sinal",
        body=f"{_actor_label(initiator)} quer falar sobre «{post.book_title}».",
        actor_id=initiator.pk,
        thread_id=thread.pk,
        post_id=post.pk,
    )


def notify_chat_message(message: SignalChatMessage, thread: SignalChatThread) -> None:
    sender = message.sender
    recipient_id = thread.owner_id if sender.pk == thread.initiator_id else thread.initiator_id
    preview = message.body if len(message.body) <= 120 else f"{message.body[:117]}..."
    notify(
        recipient_id=recipient_id,
        kind=LibraryNotification.Kind.CHAT_MESSAGE,
        title=f"Mensagem de {_actor_label(sender)}",
        body=preview,
        actor_id=sender.pk,
        thread_id=thread.pk,
        post_id=thread.post_id,
    )


def notify_trade_received(trade: TradeRequest) -> None:
    book = trade.book_requested
    notify(
        recipient_id=trade.owner_id,
        kind=LibraryNotification.Kind.TRADE_RECEIVED,
        title="Nova proposta de troca",
        body=f"{_actor_label(trade.requester)} quer negociar «{book.title}».",
        actor_id=trade.requester_id,
        trade_id=trade.pk,
    )


def notify_trade_status(trade: TradeRequest, *, new_status: str, actor_id: int) -> None:
    book = trade.book_requested
    recipient_id = trade.requester_id if actor_id == trade.owner_id else trade.owner_id
    actor = trade.owner if actor_id == trade.owner_id else trade.requester

    labels = {
        TradeRequest.Status.ACCEPTED: ("Proposta aceita", f"{_actor_label(trade.owner)} aceitou «{book.title}»."),
        TradeRequest.Status.REJECTED: ("Proposta recusada", f"{_actor_label(trade.owner)} recusou «{book.title}»."),
        TradeRequest.Status.COMPLETED: (
            "Negociação concluída",
            f"{_actor_label(actor)} marcou «{book.title}» como concluída.",
        ),
    }
    kind_map = {
        TradeRequest.Status.ACCEPTED: LibraryNotification.Kind.TRADE_ACCEPTED,
        TradeRequest.Status.REJECTED: LibraryNotification.Kind.TRADE_REJECTED,
        TradeRequest.Status.COMPLETED: LibraryNotification.Kind.TRADE_COMPLETED,
    }
    title, body = labels.get(new_status, ("Atualização de troca", f"Status de «{book.title}» mudou."))
    kind = kind_map.get(new_status, LibraryNotification.Kind.TRADE_ACCEPTED)
    notify(
        recipient_id=recipient_id,
        kind=kind,
        title=title,
        body=body,
        actor_id=actor_id,
        trade_id=trade.pk,
    )


def safe_notify_trade_status(trade: TradeRequest, *, new_status: str, actor_id: int) -> None:
    try:
        notify_trade_status(trade, new_status=new_status, actor_id=actor_id)
    except Exception:
        logger.exception("Falha ao criar notificação de troca %s (status=%s)", trade.pk, new_status)


def safe_notify_trade_received(trade: TradeRequest) -> None:
    try:
        notify_trade_received(trade)
    except Exception:
        logger.exception("Falha ao criar notificação de proposta recebida %s", trade.pk)
