from django.contrib import admin

from .models import BookRating, InventoryBook, SignalChatMessage, SignalChatThread, SocialPost, TradeRequest


@admin.register(InventoryBook)
class InventoryBookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "genre", "owner", "sharing_status", "has_physical_copy", "updated_at")
    list_filter = ("sharing_status", "has_physical_copy", "genre")
    search_fields = ("title", "author", "genre", "isbn", "owner__email", "owner__full_name")


@admin.register(BookRating)
class BookRatingAdmin(admin.ModelAdmin):
    list_display = ("book", "user", "rating", "updated_at")
    list_filter = ("rating",)
    search_fields = ("book__title", "book__author", "user__email", "user__full_name")


@admin.register(SocialPost)
class SocialPostAdmin(admin.ModelAdmin):
    list_display = ("book_title", "book_author", "intent", "owner", "created_at")
    list_filter = ("intent",)
    search_fields = ("book_title", "book_author", "owner__email", "owner__full_name")


@admin.register(SignalChatThread)
class SignalChatThreadAdmin(admin.ModelAdmin):
    list_display = ("post", "initiator", "owner", "last_message_at", "created_at")
    search_fields = (
        "post__book_title",
        "initiator__email",
        "owner__email",
    )


@admin.register(SignalChatMessage)
class SignalChatMessageAdmin(admin.ModelAdmin):
    list_display = ("thread", "sender", "created_at")
    search_fields = ("body", "sender__email")


@admin.register(TradeRequest)
class TradeRequestAdmin(admin.ModelAdmin):
    list_display = ("book_requested", "requester", "owner", "status", "created_at")
    list_filter = ("status",)
    search_fields = (
        "book_requested__title",
        "book_requested__author",
        "requester__email",
        "requester__full_name",
        "owner__email",
        "owner__full_name",
    )
