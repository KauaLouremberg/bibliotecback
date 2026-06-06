from django.conf import settings
from django.db import models
from django.db.models import Q


class InventoryBook(models.Model):
    class SharingStatus(models.TextChoices):
        PRIVATE = "private", "Privado"
        SHOWCASE = "showcase", "Exibir no perfil"
        LOAN = "loan", "Disponível para empréstimo"
        EXCHANGE = "exchange", "Disponível para troca"
        DONATION = "donation", "Disponível para doação"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inventory_books",
    )
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    genre = models.CharField(max_length=120, blank=True)
    published_year = models.PositiveSmallIntegerField(null=True, blank=True)
    publisher = models.CharField(max_length=160, blank=True)
    isbn = models.CharField(max_length=32, blank=True)
    page_count = models.PositiveSmallIntegerField(null=True, blank=True)
    cover_url = models.URLField(blank=True)
    cover_image = models.FileField(upload_to="books/covers/", blank=True)
    has_physical_copy = models.BooleanField(default=False)
    sharing_status = models.CharField(
        max_length=24,
        choices=SharingStatus.choices,
        default=SharingStatus.PRIVATE,
    )
    location_label = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at", "title"]

    def __str__(self) -> str:
        return f"{self.title} - {self.owner}"


class BookRating(models.Model):
    book = models.ForeignKey(
        InventoryBook,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="book_ratings",
    )
    rating = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["book", "user"], name="unique_book_rating_per_user"),
            models.CheckConstraint(
                condition=Q(rating__gte=1) & Q(rating__lte=5),
                name="book_rating_between_1_and_5",
            ),
        ]
        ordering = ["-updated_at", "-created_at"]

    def __str__(self) -> str:
        return f"{self.book_id}:{self.user_id}={self.rating}"


class SocialPost(models.Model):
    class Intent(models.TextChoices):
        NEED = "need", "Procuro este livro"
        DONATION = "donation", "Estou doando"
        EXCHANGE = "exchange", "Quero trocar"
        LOAN = "loan", "Posso emprestar"
        OFFER = "offer", "Tenho este livro disponível"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_posts",
    )
    inventory_book = models.ForeignKey(
        InventoryBook,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="social_posts",
    )
    intent = models.CharField(max_length=24, choices=Intent.choices)
    book_title = models.CharField(max_length=255)
    book_author = models.CharField(max_length=255)
    caption = models.TextField(blank=True)
    location_label = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-updated_at"]

    def __str__(self) -> str:
        return f"{self.intent}:{self.book_title} - {self.owner}"


class SignalChatThread(models.Model):
    post = models.ForeignKey(
        SocialPost,
        on_delete=models.CASCADE,
        related_name="chat_threads",
    )
    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="signal_chats_started",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="signal_chats_received",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["post", "initiator"],
                name="unique_signal_chat_per_post_initiator",
            ),
        ]
        ordering = ["-last_message_at", "-created_at"]

    def __str__(self) -> str:
        return f"chat:post={self.post_id} initiator={self.initiator_id}"


class SignalChatMessage(models.Model):
    thread = models.ForeignKey(
        SignalChatThread,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="signal_chat_messages",
    )
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"msg:{self.thread_id} from {self.sender_id}"


class TradeRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        ACCEPTED = "accepted", "Aceita"
        REJECTED = "rejected", "Recusada"
        COMPLETED = "completed", "Concluída"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trade_requests_sent",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trade_requests_received",
    )
    book_requested = models.ForeignKey(
        InventoryBook,
        on_delete=models.CASCADE,
        related_name="trade_requests_received",
    )
    book_offered = models.ForeignKey(
        InventoryBook,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trade_requests_offered",
    )
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING)
    message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-updated_at"]

    def __str__(self) -> str:
        return f"trade:{self.book_requested} {self.requester}->{self.owner}"
