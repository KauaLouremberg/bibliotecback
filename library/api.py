from django.db.models import Count
from ninja import Router

from accounts.auth import JwtAuth
from accounts.models import User
from accounts.schemas import MessageOut

from .models import InventoryBook, SocialPost
from .schemas import (
    FeedCollectionOut,
    FeedStatsOut,
    InventoryBookIn,
    InventoryBookOut,
    InventoryBookPreviewOut,
    InventoryBookUpdateIn,
    InventoryCollectionOut,
    InventoryStatsOut,
    OwnerOut,
    SocialPostIn,
    SocialPostOut,
    SocialPostUpdateIn,
)

router = Router(tags=["library"])


def _book_key(title: str, author: str) -> tuple[str, str]:
    return (title.strip().casefold(), author.strip().casefold())


def _owner_out(user: User) -> OwnerOut:
    return OwnerOut(id=user.pk, email=user.email, full_name=user.full_name or "")


def _book_preview(book: InventoryBook) -> InventoryBookPreviewOut:
    return InventoryBookPreviewOut(
        id=book.pk,
        title=book.title,
        author=book.author,
        has_physical_copy=book.has_physical_copy,
        sharing_status=book.sharing_status,
    )


def _need_counts(exclude_user_id: int | None = None) -> dict[tuple[str, str], int]:
    query = SocialPost.objects.filter(intent=SocialPost.Intent.NEED)
    if exclude_user_id is not None:
        query = query.exclude(owner_id=exclude_user_id)
    rows = (
        query.values("book_title", "book_author")
        .annotate(total=Count("id"))
        .order_by()
    )
    return {
        _book_key(row["book_title"], row["book_author"]): row["total"]
        for row in rows
    }


def _book_out(book: InventoryBook, viewer_id: int, match_count: int = 0) -> InventoryBookOut:
    return InventoryBookOut(
        id=book.pk,
        title=book.title,
        author=book.author,
        description=book.description,
        cover_url=book.cover_url,
        has_physical_copy=book.has_physical_copy,
        sharing_status=book.sharing_status,
        location_label=book.location_label,
        owner=_owner_out(book.owner),
        is_owner=book.owner_id == viewer_id,
        matches_waiting=match_count,
        created_at=book.created_at,
        updated_at=book.updated_at,
    )


def _post_out(post: SocialPost, viewer_id: int) -> SocialPostOut:
    return SocialPostOut(
        id=post.pk,
        intent=post.intent,
        book_title=post.book_title,
        book_author=post.book_author,
        caption=post.caption,
        location_label=post.location_label,
        owner=_owner_out(post.owner),
        is_owner=post.owner_id == viewer_id,
        inventory_book=_book_preview(post.inventory_book) if post.inventory_book else None,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


def _apply_book_updates(book: InventoryBook, payload: InventoryBookUpdateIn) -> InventoryBook:
    for field in (
        "title",
        "author",
        "description",
        "cover_url",
        "has_physical_copy",
        "sharing_status",
        "location_label",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(book, field, value)
    book.save()
    return book


def _resolve_inventory_book(owner: User, inventory_book_id: int | None) -> InventoryBook | None:
    if inventory_book_id is None:
        return None
    return InventoryBook.objects.filter(pk=inventory_book_id, owner=owner).first()


def _apply_post_updates(post: SocialPost, payload: SocialPostUpdateIn, owner: User) -> SocialPost:
    if payload.inventory_book_id != -1:
        post.inventory_book = _resolve_inventory_book(owner, payload.inventory_book_id)
    for field in ("intent", "book_title", "book_author", "caption", "location_label"):
        value = getattr(payload, field)
        if value is not None:
            setattr(post, field, value)
    post.save()
    return post


@router.get("/inventory/mine", response=InventoryCollectionOut, auth=JwtAuth())
def list_my_inventory(request):
    owner: User = request.auth
    books = list(InventoryBook.objects.filter(owner=owner).select_related("owner"))
    need_counts = _need_counts(exclude_user_id=owner.pk)
    items = []
    demand_matches = 0
    for book in books:
        matches = need_counts.get(_book_key(book.title, book.author), 0)
        demand_matches += matches
        items.append(_book_out(book, viewer_id=owner.pk, match_count=matches))
    public_books = sum(1 for book in books if book.sharing_status != InventoryBook.SharingStatus.PRIVATE)
    donation_books = sum(
        1 for book in books if book.sharing_status == InventoryBook.SharingStatus.DONATION
    )
    return InventoryCollectionOut(
        items=items,
        stats=InventoryStatsOut(
            total_books=len(books),
            public_books=public_books,
            donation_books=donation_books,
            demand_matches=demand_matches,
        ),
    )


@router.get("/inventory/discover", response=InventoryCollectionOut, auth=JwtAuth())
def discover_inventory(request):
    viewer: User = request.auth
    books = list(
        InventoryBook.objects.exclude(owner=viewer)
        .exclude(sharing_status=InventoryBook.SharingStatus.PRIVATE)
        .select_related("owner")[:50]
    )
    need_counts = _need_counts(exclude_user_id=viewer.pk)
    items = []
    demand_matches = 0
    for book in books:
        matches = need_counts.get(_book_key(book.title, book.author), 0)
        demand_matches += matches
        items.append(_book_out(book, viewer_id=viewer.pk, match_count=matches))
    public_books = len(books)
    donation_books = sum(
        1 for book in books if book.sharing_status == InventoryBook.SharingStatus.DONATION
    )
    return InventoryCollectionOut(
        items=items,
        stats=InventoryStatsOut(
            total_books=len(books),
            public_books=public_books,
            donation_books=donation_books,
            demand_matches=demand_matches,
        ),
    )


@router.post("/inventory", response={201: InventoryBookOut}, auth=JwtAuth())
def create_inventory_book(request, payload: InventoryBookIn):
    owner: User = request.auth
    book = InventoryBook.objects.create(owner=owner, **payload.dict())
    return 201, _book_out(book, viewer_id=owner.pk)


@router.patch("/inventory/{book_id}", response={200: InventoryBookOut, 404: MessageOut}, auth=JwtAuth())
def update_inventory_book(request, book_id: int, payload: InventoryBookUpdateIn):
    owner: User = request.auth
    book = InventoryBook.objects.filter(pk=book_id, owner=owner).select_related("owner").first()
    if book is None:
        return 404, MessageOut(detail="Livro não encontrado no seu inventário.")
    book = _apply_book_updates(book, payload)
    return 200, _book_out(book, viewer_id=owner.pk)


@router.delete("/inventory/{book_id}", response={204: None, 404: MessageOut}, auth=JwtAuth())
def delete_inventory_book(request, book_id: int):
    owner: User = request.auth
    deleted, _ = InventoryBook.objects.filter(pk=book_id, owner=owner).delete()
    if deleted == 0:
        return 404, MessageOut(detail="Livro não encontrado no seu inventário.")
    return 204, None


@router.get("/feed", response=FeedCollectionOut, auth=JwtAuth())
def list_feed(request):
    viewer: User = request.auth
    posts = list(SocialPost.objects.select_related("owner", "inventory_book"))
    stats = FeedStatsOut(
        need_posts=sum(1 for post in posts if post.intent == SocialPost.Intent.NEED),
        donation_posts=sum(1 for post in posts if post.intent == SocialPost.Intent.DONATION),
        exchange_posts=sum(1 for post in posts if post.intent == SocialPost.Intent.EXCHANGE),
        loan_posts=sum(1 for post in posts if post.intent == SocialPost.Intent.LOAN),
    )
    return FeedCollectionOut(
        items=[_post_out(post, viewer_id=viewer.pk) for post in posts],
        stats=stats,
    )


@router.post("/feed", response={201: SocialPostOut, 400: MessageOut}, auth=JwtAuth())
def create_post(request, payload: SocialPostIn):
    owner: User = request.auth
    inventory_book = _resolve_inventory_book(owner, payload.inventory_book_id)
    if payload.inventory_book_id is not None and inventory_book is None:
        return 400, MessageOut(detail="Livro do inventário não encontrado.")
    post = SocialPost.objects.create(
        owner=owner,
        inventory_book=inventory_book,
        intent=payload.intent,
        book_title=payload.book_title,
        book_author=payload.book_author,
        caption=payload.caption,
        location_label=payload.location_label,
    )
    return 201, _post_out(post, viewer_id=owner.pk)


@router.patch("/feed/{post_id}", response={200: SocialPostOut, 400: MessageOut, 404: MessageOut}, auth=JwtAuth())
def update_post(request, post_id: int, payload: SocialPostUpdateIn):
    owner: User = request.auth
    post = SocialPost.objects.filter(pk=post_id, owner=owner).select_related("owner", "inventory_book").first()
    if post is None:
        return 404, MessageOut(detail="Sinal não encontrado.")
    if (
        payload.inventory_book_id not in (-1, None)
        and _resolve_inventory_book(owner, payload.inventory_book_id) is None
    ):
        return 400, MessageOut(detail="Livro do inventário não encontrado.")
    post = _apply_post_updates(post, payload, owner)
    return 200, _post_out(post, viewer_id=owner.pk)


@router.delete("/feed/{post_id}", response={204: None, 404: MessageOut}, auth=JwtAuth())
def delete_post(request, post_id: int):
    owner: User = request.auth
    deleted, _ = SocialPost.objects.filter(pk=post_id, owner=owner).delete()
    if deleted == 0:
        return 404, MessageOut(detail="Sinal não encontrado.")
    return 204, None
