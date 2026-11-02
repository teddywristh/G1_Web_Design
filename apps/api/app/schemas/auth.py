"""Authentication inputs deliberately never expose passwords in validation errors."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.schemas import UserOut


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: SecretStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Invalid email")
        return value

    @field_validator("password")
    @classmethod
    def password_size(cls, value):
        encoded = value.get_secret_value().encode("utf-8")
        if not 1 <= len(encoded) <= 72 or b"\x00" in encoded:
            raise ValueError("Password must contain 1–72 UTF-8 bytes and no NUL")
        return value


class Register(Login):
    displayName: str = Field(min_length=1, max_length=120)

    @field_validator("password")
    @classmethod
    def new_password_size(cls, value):
        if len(value.get_secret_value().encode("utf-8")) < 8:
            raise ValueError("Password must contain at least 8 UTF-8 bytes")
        return value

    @field_validator("displayName")
    @classmethod
    def normalize_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Display name required")
        return value


class GoogleSignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    credential: SecretStr

    @field_validator("credential")
    @classmethod
    def credential_size(cls, value):
        if not 20 <= len(value.get_secret_value()) <= 8192:
            raise ValueError("Invalid credential")
        return value


class SessionUser(BaseModel):
    user: UserOut
    csrfToken: str


class SessionInfo(BaseModel):
    id: str
    createdAt: datetime
    expiresAt: datetime
    current: bool
    active: bool


class SessionPage(BaseModel):
    items: list[SessionInfo]
    nextCursor: str | None
