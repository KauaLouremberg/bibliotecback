from django.conf import settings
from ninja import Schema
from pydantic import EmailStr, Field, field_validator


def _institutional_suffix() -> str:
    return str(getattr(settings, "INSTITUTIONAL_EMAIL_DOMAIN", "aluno.wyden.edu.br")).strip().lower()


class RegisterIn(Schema):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)

    @field_validator("email")
    @classmethod
    def email_institutional(cls, v: str) -> str:
        suffix = _institutional_suffix()
        local = v.strip().lower()
        if not local.endswith(f"@{suffix}"):
            raise ValueError(f"E-mail deve ser institucional (@{suffix})")
        return local


class LoginIn(Schema):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def email_normalize(cls, v: str) -> str:
        return v.strip().lower()


class TokenPairOut(Schema):
    access: str
    refresh: str


class RefreshIn(Schema):
    refresh: str


class UserOut(Schema):
    id: int
    email: str
    full_name: str


class MessageOut(Schema):
    detail: str
