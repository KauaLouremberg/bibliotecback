from ninja import Schema
from pydantic import EmailStr, Field, field_validator


class RegisterIn(Schema):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)

    @field_validator("email")
    @classmethod
    def email_normalize(cls, v: str) -> str:
        return v.strip().lower()


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
