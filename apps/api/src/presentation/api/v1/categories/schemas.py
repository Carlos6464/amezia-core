from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from src.application.category.dtos import CategoryWithUsage
from src.domain.category.entities import Category

CategoryScope = Literal["global", "private"]

# Espelha o registro de ícones do frontend
# (apps/web/.../ui/category-icon/category-icons.ts) — os paths do Lucide
# ficam só no frontend (é quem renderiza SVG), o backend só valida que a
# chave escolhida é uma das suportadas.
CategoryIcon = Literal[
    "utensils",
    "house",
    "car",
    "heart-pulse",
    "graduation-cap",
    "party-popper",
    "shopping-bag",
    "smartphone",
    "shirt",
    "plane",
    "dog",
    "gift",
    "coffee",
    "dumbbell",
    "film",
    "music",
    "fuel",
    "wifi",
    "briefcase",
    "piggy-bank",
    "receipt",
    "baby",
    "sparkles",
    "tag",
]


class CategoryResponse(BaseModel):
    public_id: str
    name: str
    color: str
    icon: str
    scope: CategoryScope
    is_system: bool
    created_at: datetime
    transaction_count: int
    total_amount: Decimal

    @classmethod
    def from_entity(cls, category: Category) -> "CategoryResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Converte a entidade de domínio Category no schema de
        resposta HTTP — `scope` é derivado de `user_id IS NULL`, o
        `user_id` cru nunca é serializado (RN-01). Usado pelos endpoints
        de criar/atualizar, que não têm (nem precisam buscar) uso
        agregado — categoria recém-criada/editada sempre tem
        `transaction_count=0`. Para a listagem, com uso real, ver
        `from_dto`.
        """
        return cls(
            public_id=str(category.public_id),
            name=category.name,
            color=category.color,
            icon=category.icon,
            scope="global" if category.is_global else "private",
            is_system=category.is_system,
            created_at=category.created_at,
            transaction_count=0,
            total_amount=Decimal("0.00"),
        )

    @classmethod
    def from_dto(cls, dto: CategoryWithUsage) -> "CategoryResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Converte a DTO de aplicação CategoryWithUsage (usada
        por `GET /categories`) no schema de resposta HTTP, incluindo o
        uso agregado real — diferente de `from_entity`, que zera esses
        campos por não ter esse dado em mãos.
        """
        category = dto.category
        return cls(
            public_id=str(category.public_id),
            name=category.name,
            color=category.color,
            icon=category.icon,
            scope="global" if category.is_global else "private",
            is_system=category.is_system,
            created_at=category.created_at,
            transaction_count=dto.transaction_count,
            total_amount=(Decimal(dto.total_amount_cents) / 100).quantize(Decimal("0.01")),
        )


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    icon: CategoryIcon


class CategoryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    icon: CategoryIcon | None = None
