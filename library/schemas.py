from datetime import datetime
from typing import Literal

from ninja import Field, Schema
from pydantic import field_validator


SharingStatusValue = Literal["private", "showcase", "loan", "exchange", "donation"]
PostIntentValue = Literal["need", "donation", "exchange", "loan", "offer"]
TradeStatusValue = Literal["pending", "accepted", "rejected", "completed"]


def _clean_text(value: str) -> str:
    return value.strip()


def _clean_optional_text(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip()


class OwnerOut(Schema):
    id: int
    full_name: str
    email: str


class InventoryBookPreviewOut(Schema):
    id: int
    title: str
    author: str
    has_physical_copy: bool
    sharing_status: SharingStatusValue


class InventoryBookIn(Schema):
    title: str = Field(min_length=2, max_length=255)
    author: str = Field(min_length=2, max_length=255)
    description: str = Field(default="", max_length=2000)
    genre: str = Field(default="", max_length=120)
    published_year: int | None = Field(default=None, ge=0, le=9999)
    publisher: str = Field(default="", max_length=160)
    isbn: str = Field(default="", max_length=32)
    page_count: int | None = Field(default=None, ge=0, le=9999)
    cover_url: str = Field(default="", max_length=500)
    has_physical_copy: bool = False
    sharing_status: SharingStatusValue = "private"
    location_label: str = Field(default="", max_length=120)

    @field_validator("title", "author")
    @classmethod
    def trim_required(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("description", "genre", "publisher", "isbn", "cover_url", "location_label")
    @classmethod
    def trim_optional(cls, value: str) -> str:
        return _clean_optional_text(value)


class InventoryBookUpdateIn(Schema):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    author: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    genre: str | None = Field(default=None, max_length=120)
    published_year: int | None = Field(default=None, ge=0, le=9999)
    publisher: str | None = Field(default=None, max_length=160)
    isbn: str | None = Field(default=None, max_length=32)
    page_count: int | None = Field(default=None, ge=0, le=9999)
    cover_url: str | None = Field(default=None, max_length=500)
    has_physical_copy: bool | None = None
    sharing_status: SharingStatusValue | None = None
    location_label: str | None = Field(default=None, max_length=120)

    @field_validator("title", "author")
    @classmethod
    def trim_required(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_text(value)

    @field_validator("description", "genre", "publisher", "isbn", "cover_url", "location_label")
    @classmethod
    def trim_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_optional_text(value)


class InventoryBookOut(Schema):
    id: int
    title: str
    author: str
    description: str
    genre: str
    published_year: int | None
    publisher: str
    isbn: str
    page_count: int | None
    cover_url: str
    has_physical_copy: bool
    sharing_status: SharingStatusValue
    location_label: str
    owner: OwnerOut
    is_owner: bool
    matches_waiting: int
    average_rating: float
    rating_count: int
    my_rating: int | None
    created_at: datetime
    updated_at: datetime


class InventoryStatsOut(Schema):
    total_books: int
    public_books: int
    donation_books: int
    demand_matches: int


class InventoryCollectionOut(Schema):
    items: list[InventoryBookOut]
    stats: InventoryStatsOut


class CatalogBookOut(Schema):
    id: str
    title: str
    author: str
    description: str
    genre: str
    cover_url: str
    published_year: int | None
    publisher: str
    isbn: str
    page_count: int | None


class CatalogCollectionOut(Schema):
    items: list[CatalogBookOut]
    genres: list[str]


class CatalogQuery(Schema):
    search: str = Field(default="", max_length=255)
    genre: str = Field(default="", max_length=120)

    @field_validator("search", "genre")
    @classmethod
    def trim_catalog_filter(cls, value: str) -> str:
        return _clean_optional_text(value)


class BookRatingIn(Schema):
    rating: int = Field(ge=1, le=5)


class SocialPostIn(Schema):
    intent: PostIntentValue
    book_title: str = Field(min_length=2, max_length=255)
    book_author: str = Field(min_length=2, max_length=255)
    caption: str = Field(default="", max_length=1200)
    location_label: str = Field(default="", max_length=120)
    inventory_book_id: int | None = None

    @field_validator("book_title", "book_author")
    @classmethod
    def trim_required(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("caption", "location_label")
    @classmethod
    def trim_optional(cls, value: str) -> str:
        return _clean_optional_text(value)


class SocialPostUpdateIn(Schema):
    intent: PostIntentValue | None = None
    book_title: str | None = Field(default=None, min_length=2, max_length=255)
    book_author: str | None = Field(default=None, min_length=2, max_length=255)
    caption: str | None = Field(default=None, max_length=1200)
    location_label: str | None = Field(default=None, max_length=120)
    inventory_book_id: int | None = -1

    @field_validator("book_title", "book_author")
    @classmethod
    def trim_required(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_text(value)

    @field_validator("caption", "location_label")
    @classmethod
    def trim_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_optional_text(value)


class SocialPostOut(Schema):
    id: int
    intent: PostIntentValue
    book_title: str
    book_author: str
    caption: str
    location_label: str
    owner: OwnerOut
    is_owner: bool
    inventory_book: InventoryBookPreviewOut | None
    created_at: datetime
    updated_at: datetime


class FeedStatsOut(Schema):
    need_posts: int
    donation_posts: int
    exchange_posts: int
    loan_posts: int


class FeedCollectionOut(Schema):
    items: list[SocialPostOut]
    stats: FeedStatsOut


class TradeRequestIn(Schema):
    book_requested_id: int
    book_offered_id: int | None = None
    message: str = Field(default="", max_length=500)

    @field_validator("message")
    @classmethod
    def trim_message(cls, value: str) -> str:
        return _clean_optional_text(value)


class TradeRequestStatusIn(Schema):
    status: Literal["accepted", "rejected", "completed"]


class TradeRequestOut(Schema):
    id: int
    status: TradeStatusValue
    message: str
    requester: OwnerOut
    owner: OwnerOut
    book_requested: InventoryBookPreviewOut
    book_offered: InventoryBookPreviewOut | None
    is_incoming: bool
    created_at: datetime
    updated_at: datetime


class TradeRequestCollectionOut(Schema):
    incoming: list[TradeRequestOut]
    outgoing: list[TradeRequestOut]


class DiscoverInventoryQuery(Schema):
    search: str = Field(default="", max_length=255)
    trade_status: Literal["loan", "exchange", "donation"] | None = None
    genre: str = Field(default="", max_length=120)

    @field_validator("search", "genre")
    @classmethod
    def trim_search(cls, value: str) -> str:
        return _clean_optional_text(value)
