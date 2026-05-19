from django.contrib import admin

from .models import InventoryBook, SocialPost


@admin.register(InventoryBook)
class InventoryBookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "owner", "sharing_status", "has_physical_copy", "updated_at")
    list_filter = ("sharing_status", "has_physical_copy")
    search_fields = ("title", "author", "owner__email", "owner__full_name")


@admin.register(SocialPost)
class SocialPostAdmin(admin.ModelAdmin):
    list_display = ("book_title", "book_author", "intent", "owner", "created_at")
    list_filter = ("intent",)
    search_fields = ("book_title", "book_author", "owner__email", "owner__full_name")
