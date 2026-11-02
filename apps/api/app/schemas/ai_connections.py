"""Provider options and credentials. Secret input is excluded from representations."""

from typing import Literal

from pydantic import Field, SecretStr, field_validator

from app.schemas import Input, Output

Provider = Literal["openai", "anthropic", "deepseek", "openrouter"]
CredentialSource = Literal["auto", "personal", "shared", "chatgpt"]


class ConnectionPut(Input):
    apiKey: SecretStr
    expectedVersion: int = Field(ge=0)
    enabled: bool = True

    @field_validator("apiKey")
    @classmethod
    def valid_key(cls, value):
        key = value.get_secret_value()
        if not 10 <= len(key) <= 4096 or any(c.isspace() for c in key):
            raise ValueError("Enter a nonempty API key without whitespace")
        return value


class ConnectionOut(Output):
    provider: Provider
    scope: Literal["personal", "shared"]
    configured: bool
    enabled: bool
    version: int
    origin: Literal["stored", "environment", "none"]
