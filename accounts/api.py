from django.contrib.auth import authenticate
from django.db import IntegrityError
from ninja import File, Form, Router
from ninja.files import UploadedFile
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .auth import JwtAuth
from .models import User
from .schemas import LoginIn, MessageOut, ProfileUpdateIn, RefreshIn, RegisterIn, TokenPairOut, UserOut

router = Router(tags=["auth"])


def _tokens_for_user(user: User) -> TokenPairOut:
    refresh = RefreshToken.for_user(user)
    return TokenPairOut(access=str(refresh.access_token), refresh=str(refresh))


def _media_url(request, file_field) -> str:
    if not file_field:
        return ""
    return request.build_absolute_uri(file_field.url)


def _user_out(request, user: User) -> UserOut:
    return UserOut(
        id=user.pk,
        email=user.email,
        full_name=user.full_name or "",
        avatar_url=_media_url(request, user.avatar),
        course=user.course or "",
        semester=user.semester or "",
    )


@router.post("/register", response={201: TokenPairOut, 400: MessageOut})
def register(request, payload: RegisterIn):
    if User.objects.filter(email=payload.email).exists():
        return 400, MessageOut(detail="E-mail já cadastrado.")
    try:
        user = User.objects.create_user(
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name.strip(),
        )
    except IntegrityError:
        return 400, MessageOut(detail="Não foi possível criar conta.")
    return 201, _tokens_for_user(user)


@router.post("/login", response={200: TokenPairOut, 401: MessageOut})
def login(request, payload: LoginIn):
    user = authenticate(request, username=payload.email, password=payload.password)
    if user is None or not user.is_active:
        return 401, MessageOut(detail="Credenciais inválidas.")
    return 200, _tokens_for_user(user)


@router.post("/refresh", response={200: TokenPairOut, 401: MessageOut})
def refresh(request, payload: RefreshIn):
    try:
        old = RefreshToken(payload.refresh)
    except TokenError:
        return 401, MessageOut(detail="Refresh token inválido.")
    user_id = old.get("user_id")
    try:
        user = User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist:
        return 401, MessageOut(detail="Utilizador não encontrado.")
    new_refresh = RefreshToken.for_user(user)
    return 200, TokenPairOut(access=str(new_refresh.access_token), refresh=str(new_refresh))


@router.get("/me", response={200: UserOut}, auth=JwtAuth())
def me(request):
    u: User = request.auth
    return _user_out(request, u)


@router.patch("/profile", response={200: UserOut, 400: MessageOut}, auth=JwtAuth())
def update_profile(request, payload: ProfileUpdateIn):
    user: User = request.auth
    if payload.new_password and not user.check_password(payload.current_password or ""):
        return 400, MessageOut(detail="Palavra-passe atual inválida.")

    for field in ("full_name", "course", "semester"):
        value = getattr(payload, field)
        if value is not None:
            setattr(user, field, value)

    if payload.new_password:
        user.set_password(payload.new_password)

    user.save()
    return _user_out(request, user)


@router.patch("/profile/avatar", response={200: UserOut}, auth=JwtAuth())
def update_avatar(request, avatar: UploadedFile | None = File(None), remove_avatar: bool = Form(False)):
    user: User = request.auth
    if remove_avatar and user.avatar:
        user.avatar.delete(save=False)
        user.avatar = ""
    if avatar is not None:
        if user.avatar:
            user.avatar.delete(save=False)
        user.avatar.save(avatar.name, avatar)
    user.save(update_fields=["avatar"])
    return _user_out(request, user)
