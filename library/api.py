from django.db.models import Count, Q
from ninja import File, Form, Query, Router
from ninja.files import UploadedFile

from accounts.auth import JwtAuth
from accounts.models import User
from accounts.schemas import MessageOut

from .models import InventoryBook, SocialPost, TradeRequest
from .schemas import (
    FeedCollectionOut,
    FeedStatsOut,
    DiscoverInventoryQuery,
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
    TradeRequestCollectionOut,
    TradeRequestIn,
    TradeRequestOut,
    TradeRequestStatusIn,
)

router = Router(tags=["library"])


def _book_key(title: str, author: str) -> tuple[str, str]:
    return (title.strip().casefold(), author.strip().casefold())


def _owner_out(user: User) -> OwnerOut:
    return OwnerOut(id=user.pk, email=user.email, full_name=user.full_name or "")


def _media_url(request, file_field, fallback: str) -> str:
    if file_field:
        return request.build_absolute_uri(file_field.url)
    return fallback


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


def _book_out(request, book: InventoryBook, viewer_id: int, match_count: int = 0) -> InventoryBookOut:
    return InventoryBookOut(
        id=book.pk,
        title=book.title,
        author=book.author,
        description=book.description,
        cover_url=_media_url(request, book.cover_image, book.cover_url),
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


def _trade_out(trade: TradeRequest, viewer_id: int) -> TradeRequestOut:
    return TradeRequestOut(
        id=trade.pk,
        status=trade.status,
        message=trade.message,
        requester=_owner_out(trade.requester),
        owner=_owner_out(trade.owner),
        book_requested=_book_preview(trade.book_requested),
        book_offered=_book_preview(trade.book_offered) if trade.book_offered else None,
        is_incoming=trade.owner_id == viewer_id,
        created_at=trade.created_at,
        updated_at=trade.updated_at,
    )


def _apply_book_updates(book: InventoryBook, payload: InventoryBookUpdateIn) -> InventoryBook:
    for field in ("title", "author", "description", "has_physical_copy", "sharing_status", "location_label"):
        value = getattr(payload, field)
        if value is not None:
            setattr(book, field, value)
    book.save()
    return book


def _parse_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _inventory_payload(
    title: str | None = None,
    author: str | None = None,
    description: str | None = None,
    has_physical_copy=None,
    sharing_status: str | None = None,
    location_label: str | None = None,
) -> InventoryBookIn:
    return InventoryBookIn(
        title=title or "",
        author=author or "",
        description=description or "",
        has_physical_copy=_parse_bool(has_physical_copy, default=False),
        sharing_status=sharing_status or "private",
        location_label=location_label or "",
    )


def _inventory_update_payload(
    title: str | None = None,
    author: str | None = None,
    description: str | None = None,
    has_physical_copy=None,
    sharing_status: str | None = None,
    location_label: str | None = None,
) -> InventoryBookUpdateIn:
    return InventoryBookUpdateIn(
        title=title,
        author=author,
        description=description,
        has_physical_copy=None if has_physical_copy is None else _parse_bool(has_physical_copy),
        sharing_status=sharing_status,
        location_label=location_label,
    )


def _apply_cover_change(
    book: InventoryBook,
    cover_image: UploadedFile | None,
    remove_cover,
):
    if _parse_bool(remove_cover, default=False) and book.cover_image:
        book.cover_image.delete(save=False)
        book.cover_image = ""
    if cover_image is not None:
        if book.cover_image:
            book.cover_image.delete(save=False)
        book.cover_image.save(cover_image.name, cover_image)
    book.save(update_fields=["cover_image"])


def _resolve_inventory_book(owner: User, inventory_book_id: int | None) -> InventoryBook | None:
    if inventory_book_id is None:
        return None
    return InventoryBook.objects.filter(pk=inventory_book_id, owner=owner).first()


def _resolve_public_requested_book(book_id: int) -> InventoryBook | None:
    return (
        InventoryBook.objects.exclude(sharing_status=InventoryBook.SharingStatus.PRIVATE)
        .select_related("owner")
        .filter(pk=book_id)
        .first()
    )


def _apply_post_updates(post: SocialPost, payload: SocialPostUpdateIn, owner: User) -> SocialPost:
    if payload.inventory_book_id != -1:
        post.inventory_book = _resolve_inventory_book(owner, payload.inventory_book_id)
    for field in ("intent", "book_title", "book_author", "caption", "location_label"):
        value = getattr(payload, field)
        if value is not None:
            setattr(post, field, value)
    post.save()
    return post


def _can_transition_trade(user: User, trade: TradeRequest, new_status: str) -> tuple[bool, str | None]:
    if new_status == TradeRequest.Status.ACCEPTED:
        if trade.owner_id != user.pk:
            return False, "Apenas o dono do livro pode aceitar a proposta."
        if trade.status != TradeRequest.Status.PENDING:
            return False, "Só propostas pendentes podem ser aceitas."
        return True, None
    if new_status == TradeRequest.Status.REJECTED:
        if trade.owner_id != user.pk:
            return False, "Apenas o dono do livro pode recusar a proposta."
        if trade.status != TradeRequest.Status.PENDING:
            return False, "Só propostas pendentes podem ser recusadas."
        return True, None
    if new_status == TradeRequest.Status.COMPLETED:
        if user.pk not in {trade.owner_id, trade.requester_id}:
            return False, "Apenas participantes da negociação podem concluí-la."
        if trade.status != TradeRequest.Status.ACCEPTED:
            return False, "Só propostas aceitas podem ser concluídas."
        return True, None
    return False, "Status inválido para atualização."


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
        items.append(_book_out(request, book, viewer_id=owner.pk, match_count=matches))
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
def discover_inventory(request, filters: DiscoverInventoryQuery = Query(...)):
    viewer: User = request.auth
    query = (
        InventoryBook.objects.exclude(owner=viewer)
        .exclude(sharing_status=InventoryBook.SharingStatus.PRIVATE)
        .select_related("owner")
    )
    if filters.search:
        query = query.filter(Q(title__icontains=filters.search) | Q(author__icontains=filters.search))
    if filters.trade_status:
        query = query.filter(sharing_status=filters.trade_status)
    books = list(query[:50])
    need_counts = _need_counts(exclude_user_id=viewer.pk)
    items = []
    demand_matches = 0
    for book in books:
        matches = need_counts.get(_book_key(book.title, book.author), 0)
        demand_matches += matches
        items.append(_book_out(request, book, viewer_id=viewer.pk, match_count=matches))
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
def create_inventory_book(
    request,
    title: str = Form(...),
    author: str = Form(...),
    description: str = Form(""),
    has_physical_copy=Form(False),
    sharing_status: str = Form("private"),
    location_label: str = Form(""),
    cover_image: UploadedFile | None = File(None),
):
    owner: User = request.auth
    payload = _inventory_payload(
        title=title,
        author=author,
        description=description,
        has_physical_copy=has_physical_copy,
        sharing_status=sharing_status,
        location_label=location_label,
    )
    book = InventoryBook.objects.create(owner=owner, **payload.dict())
    if cover_image is not None:
        book.cover_image.save(cover_image.name, cover_image)
    return 201, _book_out(request, book, viewer_id=owner.pk)


@router.patch("/inventory/{book_id}", response={200: InventoryBookOut, 404: MessageOut}, auth=JwtAuth())
def update_inventory_book(
    request,
    book_id: int,
    title: str | None = Form(None),
    author: str | None = Form(None),
    description: str | None = Form(None),
    has_physical_copy=Form(None),
    sharing_status: str | None = Form(None),
    location_label: str | None = Form(None),
    cover_image: UploadedFile | None = File(None),
    remove_cover=Form(False),
):
    owner: User = request.auth
    book = InventoryBook.objects.filter(pk=book_id, owner=owner).select_related("owner").first()
    if book is None:
        return 404, MessageOut(detail="Livro não encontrado no seu inventário.")
    payload = _inventory_update_payload(
        title=title,
        author=author,
        description=description,
        has_physical_copy=has_physical_copy,
        sharing_status=sharing_status,
        location_label=location_label,
    )
    book = _apply_book_updates(book, payload)
    _apply_cover_change(book, cover_image=cover_image, remove_cover=remove_cover)
    return 200, _book_out(request, book, viewer_id=owner.pk)


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


@router.post("/trades", response={201: TradeRequestOut, 400: MessageOut, 404: MessageOut}, auth=JwtAuth())
def create_trade_request(request, payload: TradeRequestIn):
    requester: User = request.auth
    requested_book = _resolve_public_requested_book(payload.book_requested_id)
    if requested_book is None:
        return 404, MessageOut(detail="Livro solicitado não encontrado.")
    if requested_book.owner_id == requester.pk:
        return 400, MessageOut(detail="Você não pode propor troca para um livro seu.")
    offered_book = _resolve_inventory_book(requester, payload.book_offered_id)
    if payload.book_offered_id is not None and offered_book is None:
        return 400, MessageOut(detail="Livro oferecido não encontrado no seu inventário.")
    trade = TradeRequest.objects.create(
        requester=requester,
        owner=requested_book.owner,
        book_requested=requested_book,
        book_offered=offered_book,
        message=payload.message,
    )
    trade = (
        TradeRequest.objects.select_related(
            "requester",
            "owner",
            "book_requested",
            "book_offered",
        )
        .get(pk=trade.pk)
    )
    return 201, _trade_out(trade, viewer_id=requester.pk)


@router.get("/trades/mine", response=TradeRequestCollectionOut, auth=JwtAuth())
def list_my_trades(request):
    viewer: User = request.auth
    incoming = list(
        TradeRequest.objects.filter(owner=viewer)
        .select_related("requester", "owner", "book_requested", "book_offered")
    )
    outgoing = list(
        TradeRequest.objects.filter(requester=viewer)
        .select_related("requester", "owner", "book_requested", "book_offered")
    )
    return TradeRequestCollectionOut(
        incoming=[_trade_out(trade, viewer_id=viewer.pk) for trade in incoming],
        outgoing=[_trade_out(trade, viewer_id=viewer.pk) for trade in outgoing],
    )


@router.patch(
    "/trades/{trade_id}/status",
    response={200: TradeRequestOut, 400: MessageOut, 404: MessageOut},
    auth=JwtAuth(),
)
def update_trade_status(request, trade_id: int, payload: TradeRequestStatusIn):
    viewer: User = request.auth
    trade = (
        TradeRequest.objects.filter(pk=trade_id)
        .select_related("requester", "owner", "book_requested", "book_offered")
        .first()
    )
    if trade is None:
        return 404, MessageOut(detail="Proposta não encontrada.")
    if viewer.pk not in {trade.owner_id, trade.requester_id}:
        return 404, MessageOut(detail="Proposta não encontrada.")
    allowed, detail = _can_transition_trade(viewer, trade, payload.status)
    if not allowed:
        return 400, MessageOut(detail=detail or "Atualização inválida.")
    trade.status = payload.status
    trade.save(update_fields=["status", "updated_at"])
    return 200, _trade_out(trade, viewer_id=viewer.pk)
