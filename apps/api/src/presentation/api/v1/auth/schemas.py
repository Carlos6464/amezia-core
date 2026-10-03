import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from src.domain.user.entities import User
from src.domain.user.value_objects import Phone

UserRole = Literal["user", "admin"]
UserLanguage = Literal["pt-BR", "en"]


class UserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    phone: str | None
    role: UserRole
    language: UserLanguage
    oauth_provider: str | None
    has_password: bool
    onboarding_completed: bool
    last_login_at: datetime | None
    created_at: datetime

    @classmethod
    def from_entity(cls, user: User) -> "UserResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-16
        Descrição: Converte a entidade de domínio User no schema de
        resposta HTTP — fronteira entre domínio e apresentação (`phone` já
        chega decifrado pelo `EncryptedString` do model). `has_password`
        (2026-08-15) nunca expõe o hash em si, só se existe um — o
        frontend usa isso pra decidir entre "definir senha" (conta
        só-OAuth) e "trocar senha" (já tem uma local). `onboarding_completed`
        (2026-08-16) é o que o frontend usa pra decidir se mostra o
        checklist/tour guiado no primeiro acesso.
        """
        return cls(
            id=user.id,
            name=user.name,
            email=str(user.email),
            phone=user.phone,
            role=user.role,
            language=user.language.value,
            oauth_provider=user.oauth_provider,
            has_password=user.password_hash is not None,
            onboarding_completed=user.onboarding_completed,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
        )


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    id_token: str


class UpdateProfileRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = None
    language: UserLanguage | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-19
        Descrição: Rejeita com 422 (`ValueError` → `pydantic.ValidationError`)
        qualquer `phone` que não seja um número completo e válido, com DDI —
        reusa o value object `Phone` (domain/user/value_objects.py) para não
        duplicar a regra do `phonenumbers`. `None` ou string vazia passam
        direto (campo não informado = "não alterar", ver
        `UpdateProfileUseCase`) — o Admin Profile (`admin-profile-page`)
        envia `phone: ""` sempre que o campo não é tocado (sem
        `normalizePhoneForSubmit` do painel cliente, que omite a chave),
        então tratar string vazia como "sem alteração" evita rejeitar o
        salvamento de nome só por o telefone estar em branco. Normaliza o
        valor salvo para E.164, igual ao que `phone_hash` espera.
        """
        if value is None or not value.strip():
            return None
        try:
            return str(Phone(value))
        except ValueError as exc:
            raise ValueError(
                "Invalid phone number — include the country code, e.g. +5511999990001"
            ) from exc


class UpdateOnboardingRequest(BaseModel):
    onboarding_completed: bool


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class SetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)


class RequestPasswordResetRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class AuthTokensResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str = "bearer"


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
