import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from src.domain.user.value_objects import DashboardCardPreference, Email, Language

UserRole = Literal["user", "admin"]


@dataclass
class User:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Entidade de domínio do usuário — identidade UUID gerada em
    Python (uuid4). Garante a invariante de que toda conta tem pelo menos
    um método de autenticação (senha local ou OAuth).
    """

    name: str
    email: Email
    password_hash: str | None = None
    phone: str | None = None
    phone_hash: str | None = None
    role: UserRole = "user"
    language: Language = Language.PT_BR
    oauth_provider: str | None = None
    oauth_id: str | None = None
    last_login_at: datetime | None = None
    monthly_budget_cents: int | None = None
    onboarding_completed: bool = False
    dashboard_layout: list[DashboardCardPreference] | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Valida a invariante de domínio a cada construção da
        entidade — inclusive quando montada a partir de dados vindos do
        banco (repository), não só em cadastros novos.
        """
        if self.password_hash is None and self.oauth_provider is None:
            raise ValueError("User must have either a password_hash or an oauth_provider")

    @property
    def is_oauth_only(self) -> bool:
        return self.password_hash is None
