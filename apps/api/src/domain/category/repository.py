import uuid
from typing import Protocol

from src.domain.category.entities import Category
from src.domain.shared.value_objects import PublicId


class CategoryRepository(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Interface de persistência do agregado Category —
    implementada em infrastructure/database/repositories/category_repository.py.
    O domínio depende só deste contrato, nunca de SQLAlchemy.
    """

    async def add(self, category: Category) -> Category: ...

    async def list_visible_to(self, user_id: uuid.UUID) -> list[Category]: ...

    async def get_by_public_id(self, public_id: PublicId) -> Category | None: ...

    async def get_by_id(self, id: int) -> Category | None: ...

    async def update(self, category: Category) -> Category: ...

    async def delete(self, category: Category) -> None: ...
