import uuid
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from src.domain.user.entities import User, UserRole


@dataclass
class UserFilters:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Filtros aceitos por UserRepository.list_paginated() — usados
    pelo ListUsersUseCase do Admin (build-context-06 §2.3). `search` cobre
    nome/email (ambos em texto puro, sem EncryptedString — pesquisável
    direto em SQL, diferente do `description`/`title` de outros módulos).
    """

    search: str | None = None
    role: UserRole | None = None
    has_phone: bool | None = None


class UserRepository(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Interface de persistência do agregado User — implementada em
    infrastructure/database/repositories/user_repository.py. O domínio
    depende só deste contrato, nunca de SQLAlchemy.
    """

    async def get_by_id(self, user_id: uuid.UUID) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def get_by_phone_hash(self, phone_hash: str) -> User | None: ...

    async def get_by_oauth_id(self, oauth_provider: str, oauth_id: str) -> User | None: ...

    async def exists_by_email(self, email: str) -> bool: ...

    async def create(self, user: User) -> User: ...

    async def update(self, user: User) -> User: ...

    async def delete(self, user_id: uuid.UUID) -> None: ...

    async def list_paginated(
        self, filters: UserFilters, page: int, page_size: int
    ) -> tuple[list[User], int]: ...

    async def count_total(self) -> int: ...

    async def count_with_phone(self) -> int: ...

    async def count_new_users_by_month(self, months: int) -> list[tuple[date, int]]: ...
