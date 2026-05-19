from django.conf import settings
from django.db import models


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
    cover_url = models.URLField(blank=True)
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
