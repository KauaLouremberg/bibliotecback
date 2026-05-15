from django.contrib.auth import authenticate
from django.db import IntegrityError
from ninja import Router
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .auth import JwtAuth
from .models import User
from .schemas import LoginIn, MessageOut, RefreshIn, RegisterIn, TokenPairOut, UserOut

router = Router(tags=["auth"])


def _tokens_for_user(user: User) -> TokenPairOut:
    refresh = RefreshToken.for_user(user)
    return TokenPairOut(access=str(refresh.access_token), refresh=str(refresh))


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
    return UserOut(id=u.pk, email=u.email, full_name=u.full_name or "")
