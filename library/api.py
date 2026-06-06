import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.core.cache import cache
from django.db.models import Avg, Count, Q
from ninja import File, Form, Query, Router
from ninja.files import UploadedFile

from accounts.auth import JwtAuth
from accounts.models import User
from accounts.schemas import MessageOut

from .models import BookRating, InventoryBook, SignalChatMessage, SignalChatThread, SocialPost, TradeRequest
from .chat_services import (
    broadcast_chat_message,
    close_signal_chat,
    create_chat_message,
    get_thread_for_user,
    open_signal_chat,
)
from .schemas import (
    BookRatingIn,
    CatalogCollectionOut,
    CatalogQuery,
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
    SignalChatMessageCollectionOut,
    SignalChatMessageIn,
    SignalChatMessageOut,
    SignalChatOpenOut,
    SignalChatPostPreviewOut,
    SignalChatThreadCollectionOut,
    SignalChatThreadOut,
    TradeRequestCollectionOut,
    TradeRequestIn,
    TradeRequestOut,
    TradeRequestStatusIn,
)

router = Router(tags=["library"])

OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
OPEN_LIBRARY_COVER_BY_ID_URL = "https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
OPEN_LIBRARY_COVER_BY_ISBN_URL = "https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
CATALOG_GENRES = [
    "Literatura brasileira",
    "Romance",
    "Fantasia",
    "Ficção científica",
    "História",
    "Tecnologia",
    "Biografia",
    "Filosofia",
]
CATALOG_SUBJECTS = {
    "Literatura brasileira": "brazilian literature",
    "Romance": "romance",
    "Fantasia": "fantasy",
    "Ficção científica": "science fiction",
    "História": "history",
    "Tecnologia": "technology",
    "Biografia": "biography",
    "Filosofia": "philosophy",
}


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


def _first_item(value, default: str = "") -> str:
    if isinstance(value, list):
        return str(value[0]) if value else default
    if value is None:
        return default
    return str(value)


def _best_isbn(isbns) -> str:
    if not isinstance(isbns, list):
        return ""
    for isbn in isbns:
        value = str(isbn)
        if len(value) == 13:
            return value
    return str(isbns[0]) if isbns else ""


def _cover_url(doc: dict, isbn: str) -> str:
    cover_id = doc.get("cover_i")
    if cover_id:
        return OPEN_LIBRARY_COVER_BY_ID_URL.format(cover_id=cover_id)
    if isbn:
        return OPEN_LIBRARY_COVER_BY_ISBN_URL.format(isbn=isbn)
    return ""


def _description_from_doc(doc: dict) -> str:
    first_sentence = _first_item(doc.get("first_sentence"))
    if first_sentence:
        return first_sentence.strip()
    return ""


def _genre_from_doc(doc: dict, selected_genre: str) -> str:
    if selected_genre:
        return selected_genre
    subjects = doc.get("subject")
    if isinstance(subjects, list) and subjects:
        return str(subjects[0])[:120]
    return ""


def _open_library_search(search: str, genre: str) -> list[dict]:
    cache_key = f"open-library-search:{search.casefold()}:{genre.casefold()}"
    cached_docs = cache.get(cache_key)
    if isinstance(cached_docs, list):
        return cached_docs

    params = {
        "limit": "30",
        "fields": ",".join(
            [
                "key",
                "title",
                "author_name",
                "first_publish_year",
                "isbn",
                "cover_i",
                "publisher",
                "number_of_pages_median",
                "subject",
                "first_sentence",
            ]
        ),
    }
    subject = CATALOG_SUBJECTS.get(genre, genre)
    if search:
        params["q"] = search
    else:
        params["q"] = subject or "literature"
    if subject:
        params["subject"] = subject
    url = f"{OPEN_LIBRARY_SEARCH_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "Bibliotec/1.0"})
    try:
        with urlopen(request, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, TimeoutError):
        return []
    docs = payload.get("docs", [])
    if not isinstance(docs, list):
        return []
    cache.set(cache_key, docs, timeout=60 * 60)
    return docs


def _catalog_book_from_doc(doc: dict, selected_genre: str) -> dict:
    isbn = _best_isbn(doc.get("isbn"))
    author = _first_item(doc.get("author_name"))
    return {
        "id": str(doc.get("key") or f"{doc.get('title', '')}:{author}"),
        "title": str(doc.get("title") or "Sem título"),
        "author": author or "Autor desconhecido",
        "description": _description_from_doc(doc),
        "genre": _genre_from_doc(doc, selected_genre),
        "cover_url": _cover_url(doc, isbn),
        "published_year": doc.get("first_publish_year"),
        "publisher": _first_item(doc.get("publisher")),
        "isbn": isbn,
        "page_count": doc.get("number_of_pages_median"),
    }


def _rating_data_for_viewer(books: list[InventoryBook], viewer_id: int) -> dict[int, int]:
    book_ids = [book.pk for book in books]
    if not book_ids:
        return {}
    return dict(
        BookRating.objects.filter(book_id__in=book_ids, user_id=viewer_id).values_list(
            "book_id",
            "rating",
        )
    )


def _with_rating_annotations(query):
    return query.annotate(
        average_rating_value=Avg("ratings__rating"),
        rating_count_value=Count("ratings", distinct=True),
    )


def _book_out(
    request,
    book: InventoryBook,
    viewer_id: int,
    match_count: int = 0,
    my_rating: int | None = None,
) -> InventoryBookOut:
    average_rating = getattr(book, "average_rating_value", None) or 0
    return InventoryBookOut(
        id=book.pk,
        title=book.title,
        author=book.author,
        description=book.description,
        genre=book.genre,
        published_year=book.published_year,
        publisher=book.publisher,
        isbn=book.isbn,
        page_count=book.page_count,
        cover_url=_media_url(request, book.cover_image, book.cover_url),
        has_physical_copy=book.has_physical_copy,
        sharing_status=book.sharing_status,
        location_label=book.location_label,
        owner=_owner_out(book.owner),
        is_owner=book.owner_id == viewer_id,
        matches_waiting=match_count,
        average_rating=round(float(average_rating), 1),
        rating_count=getattr(book, "rating_count_value", 0) or 0,
        my_rating=my_rating,
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
    for field in (
        "title",
        "author",
        "description",
        "genre",
        "published_year",
        "publisher",
        "isbn",
        "page_count",
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


def _parse_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value):
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _inventory_payload(
    title: str | None = None,
    author: str | None = None,
    description: str | None = None,
    genre: str | None = None,
    published_year=None,
    publisher: str | None = None,
    isbn: str | None = None,
    page_count=None,
    cover_url: str | None = None,
    has_physical_copy=None,
    sharing_status: str | None = None,
    location_label: str | None = None,
) -> InventoryBookIn:
    return InventoryBookIn(
        title=title or "",
        author=author or "",
        description=description or "",
        genre=genre or "",
        published_year=_parse_int(published_year),
        publisher=publisher or "",
        isbn=isbn or "",
        page_count=_parse_int(page_count),
        cover_url=cover_url or "",
        has_physical_copy=_parse_bool(has_physical_copy, default=False),
        sharing_status=sharing_status or "private",
        location_label=location_label or "",
    )


def _inventory_update_payload(
    title: str | None = None,
    author: str | None = None,
    description: str | None = None,
    genre: str | None = None,
    published_year=None,
    publisher: str | None = None,
    isbn: str | None = None,
    page_count=None,
    cover_url: str | None = None,
    has_physical_copy=None,
    sharing_status: str | None = None,
    location_label: str | None = None,
) -> InventoryBookUpdateIn:
    return InventoryBookUpdateIn(
        title=title,
        author=author,
        description=description,
        genre=genre,
        published_year=None if published_year is None else _parse_int(published_year),
        publisher=publisher,
        isbn=isbn,
        page_count=None if page_count is None else _parse_int(page_count),
        cover_url=cover_url,
        has_physical_copy=None if has_physical_copy is None else _parse_bool(has_physical_copy),
        sharing_status=sharing_status,
        location_label=location_label,
    )


def _apply_cover_change(
    book: InventoryBook,
    cover_image: UploadedFile | None,
    remove_cover,
):
    update_fields = set()
    if _parse_bool(remove_cover, default=False) and book.cover_image:
        book.cover_image.delete(save=False)
        book.cover_image = ""
        update_fields.add("cover_image")
    if _parse_bool(remove_cover, default=False) and book.cover_url:
        book.cover_url = ""
        update_fields.add("cover_url")
    if cover_image is not None:
        if book.cover_image:
            book.cover_image.delete(save=False)
        book.cover_image.save(cover_image.name, cover_image)
        update_fields.add("cover_image")
    if update_fields:
        update_fields.add("updated_at")
        book.save(update_fields=list(update_fields))


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
    books = list(_with_rating_annotations(InventoryBook.objects.filter(owner=owner).select_related("owner")))
    viewer_ratings = _rating_data_for_viewer(books, owner.pk)
    need_counts = _need_counts(exclude_user_id=owner.pk)
    items = []
    demand_matches = 0
    for book in books:
        matches = need_counts.get(_book_key(book.title, book.author), 0)
        demand_matches += matches
        items.append(
            _book_out(
                request,
                book,
                viewer_id=owner.pk,
                match_count=matches,
                my_rating=viewer_ratings.get(book.pk),
            )
        )
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
    query = _with_rating_annotations(
        InventoryBook.objects.exclude(owner=viewer)
        .exclude(sharing_status=InventoryBook.SharingStatus.PRIVATE)
        .select_related("owner")
    )
    if filters.search:
        query = query.filter(
            Q(title__icontains=filters.search)
            | Q(author__icontains=filters.search)
            | Q(genre__icontains=filters.search)
        )
    if filters.trade_status:
        query = query.filter(sharing_status=filters.trade_status)
    if filters.genre:
        query = query.filter(genre__icontains=filters.genre)
    books = list(query[:50])
    viewer_ratings = _rating_data_for_viewer(books, viewer.pk)
    need_counts = _need_counts(exclude_user_id=viewer.pk)
    items = []
    demand_matches = 0
    for book in books:
        matches = need_counts.get(_book_key(book.title, book.author), 0)
        demand_matches += matches
        items.append(
            _book_out(
                request,
                book,
                viewer_id=viewer.pk,
                match_count=matches,
                my_rating=viewer_ratings.get(book.pk),
            )
        )
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


@router.get("/catalog", response=CatalogCollectionOut, auth=JwtAuth())
def list_catalog(request, filters: CatalogQuery = Query(...)):
    docs = _open_library_search(filters.search, filters.genre)
    items = [_catalog_book_from_doc(doc, filters.genre) for doc in docs]
    return CatalogCollectionOut(items=items, genres=CATALOG_GENRES)


@router.post("/inventory", response={201: InventoryBookOut}, auth=JwtAuth())
def create_inventory_book(
    request,
    title: str = Form(...),
    author: str = Form(...),
    description: str = Form(""),
    genre: str = Form(""),
    published_year=Form(None),
    publisher: str = Form(""),
    isbn: str = Form(""),
    page_count=Form(None),
    cover_url: str = Form(""),
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
        genre=genre,
        published_year=published_year,
        publisher=publisher,
        isbn=isbn,
        page_count=page_count,
        cover_url=cover_url,
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
    genre: str | None = Form(None),
    published_year=Form(None),
    publisher: str | None = Form(None),
    isbn: str | None = Form(None),
    page_count=Form(None),
    cover_url: str | None = Form(None),
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
        genre=genre,
        published_year=published_year,
        publisher=publisher,
        isbn=isbn,
        page_count=page_count,
        cover_url=cover_url,
        has_physical_copy=has_physical_copy,
        sharing_status=sharing_status,
        location_label=location_label,
    )
    book = _apply_book_updates(book, payload)
    _apply_cover_change(book, cover_image=cover_image, remove_cover=remove_cover)
    return 200, _book_out(request, book, viewer_id=owner.pk)


@router.put("/inventory/{book_id}/rating", response={200: InventoryBookOut, 404: MessageOut}, auth=JwtAuth())
def rate_inventory_book(request, book_id: int, payload: BookRatingIn):
    viewer: User = request.auth
    visible_books = _with_rating_annotations(
        InventoryBook.objects.filter(
            Q(pk=book_id),
            Q(owner=viewer) | ~Q(sharing_status=InventoryBook.SharingStatus.PRIVATE),
        ).select_related("owner")
    )
    book = visible_books.first()
    if book is None:
        return 404, MessageOut(detail="Livro não encontrado para avaliação.")

    BookRating.objects.update_or_create(
        book=book,
        user=viewer,
        defaults={"rating": payload.rating},
    )
    book = visible_books.get(pk=book.pk)
    return 200, _book_out(request, book, viewer_id=viewer.pk, my_rating=payload.rating)


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


def _chat_message_out(message: SignalChatMessage) -> SignalChatMessageOut:
    sender = message.sender
    return SignalChatMessageOut(
        id=message.pk,
        thread_id=message.thread_id,
        sender_id=sender.pk,
        sender_name=sender.full_name or sender.email,
        body=message.body,
        created_at=message.created_at,
    )


def _chat_thread_out(thread: SignalChatThread, viewer_id: int) -> SignalChatThreadOut:
    post = thread.post
    initiator = thread.initiator
    owner = thread.owner
    is_owner = viewer_id == owner.pk
    other = initiator if is_owner else owner
    return SignalChatThreadOut(
        id=thread.pk,
        post=SignalChatPostPreviewOut(
            id=post.pk,
            book_title=post.book_title,
            book_author=post.book_author,
            intent=post.intent,
        ),
        initiator=_owner_out(initiator),
        owner=_owner_out(owner),
        is_owner=is_owner,
        other_participant=_owner_out(other),
        last_message_at=thread.last_message_at,
        created_at=thread.created_at,
    )


def _thread_messages(thread_id: int, limit: int = 50, before_id: int | None = None) -> tuple[list[SignalChatMessage], bool]:
    query = SignalChatMessage.objects.filter(thread_id=thread_id).select_related("sender").order_by("-id")
    if before_id is not None:
        query = query.filter(id__lt=before_id)
    rows = list(query[: limit + 1])
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]
    rows.reverse()
    return rows, has_more


@router.post(
    "/feed/{post_id}/chat/open",
    response={200: SignalChatOpenOut, 400: MessageOut, 404: MessageOut},
    auth=JwtAuth(),
)
def open_signal_chat_thread(request, post_id: int):
    viewer: User = request.auth
    post = SocialPost.objects.select_related("owner").filter(pk=post_id).first()
    if post is None:
        return 404, MessageOut(detail="Sinal não encontrado.")
    thread, error = open_signal_chat(post, viewer)
    if error:
        return 400, MessageOut(detail=error)
    thread = (
        SignalChatThread.objects.select_related("post", "initiator", "owner")
        .get(pk=thread.pk)
    )
    messages, _ = _thread_messages(thread.pk)
    return 200, SignalChatOpenOut(
        thread=_chat_thread_out(thread, viewer_id=viewer.pk),
        messages=[_chat_message_out(m) for m in messages],
    )


@router.get("/chats", response=SignalChatThreadCollectionOut, auth=JwtAuth())
def list_signal_chats(request):
    viewer: User = request.auth
    threads = list(
        SignalChatThread.objects.filter(Q(initiator=viewer) | Q(owner=viewer))
        .select_related("post", "initiator", "owner")
        .order_by("-last_message_at", "-created_at")
    )
    return SignalChatThreadCollectionOut(
        items=[_chat_thread_out(thread, viewer_id=viewer.pk) for thread in threads],
    )


@router.get(
    "/chats/{thread_id}",
    response={200: SignalChatThreadOut, 404: MessageOut},
    auth=JwtAuth(),
)
def get_signal_chat_thread(request, thread_id: int):
    viewer: User = request.auth
    thread = get_thread_for_user(viewer, thread_id)
    if thread is None:
        return 404, MessageOut(detail="Conversa não encontrada.")
    return 200, _chat_thread_out(thread, viewer_id=viewer.pk)


@router.delete(
    "/chats/{thread_id}",
    response={204: None, 404: MessageOut},
    auth=JwtAuth(),
)
def close_signal_chat_thread(request, thread_id: int):
    viewer: User = request.auth
    closed, error = close_signal_chat(viewer, thread_id)
    if not closed:
        return 404, MessageOut(detail=error or "Conversa não encontrada.")
    return 204, None


@router.get(
    "/chats/{thread_id}/messages",
    response={200: SignalChatMessageCollectionOut, 404: MessageOut},
    auth=JwtAuth(),
)
def list_signal_chat_messages(request, thread_id: int, before_id: int | None = None, limit: int = 50):
    viewer: User = request.auth
    thread = get_thread_for_user(viewer, thread_id)
    if thread is None:
        return 404, MessageOut(detail="Conversa não encontrada.")
    safe_limit = max(1, min(limit, 100))
    messages, has_more = _thread_messages(thread_id, limit=safe_limit, before_id=before_id)
    return 200, SignalChatMessageCollectionOut(
        items=[_chat_message_out(m) for m in messages],
        has_more=has_more,
    )


@router.post(
    "/chats/{thread_id}/messages",
    response={201: SignalChatMessageOut, 400: MessageOut, 404: MessageOut},
    auth=JwtAuth(),
)
def send_signal_chat_message(request, thread_id: int, payload: SignalChatMessageIn):
    viewer: User = request.auth
    thread = get_thread_for_user(viewer, thread_id)
    if thread is None:
        return 404, MessageOut(detail="Conversa não encontrada.")
    message = create_chat_message(thread, viewer, payload.body)
    if message is None:
        return 400, MessageOut(detail="Mensagem inválida.")
    message = SignalChatMessage.objects.select_related("sender").get(pk=message.pk)
    broadcast_chat_message(message)
    return 201, _chat_message_out(message)


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
