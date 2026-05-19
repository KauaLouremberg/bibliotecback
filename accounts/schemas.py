from ninja import Schema
from pydantic import EmailStr, Field, model_validator, field_validator


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
    avatar_url: str
    course: str
    semester: str


class ProfileUpdateIn(Schema):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    course: str | None = Field(default=None, max_length=120)
    semester: str | None = Field(default=None, max_length=60)
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("full_name", "course", "semester")
    @classmethod
    def trim_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @model_validator(mode="after")
    def validate_password_change(self):
        if self.new_password and not self.current_password:
            raise ValueError("Informe a palavra-passe atual para definir uma nova.")
        return self


class MessageOut(Schema):
    detail: str
