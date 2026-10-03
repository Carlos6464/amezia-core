import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.shared.value_objects import PublicId


@dataclass
class Category:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Entidade de domínio de categoria — global quando `user_id`
    é None (visível a todos, só leitura para usuário comum), privada
    quando pertence a um `user_id` (limite de 3 por usuário, validado na
    application layer). `is_system` marca as 7 categorias de seed
    (build-context-02 §2.3), nunca editáveis/excluíveis.
    """

    name: str
    color: str
    icon: str = "tag"
    user_id: uuid.UUID | None = None
    is_system: bool = False
    id: int | None = None
    public_id: PublicId = field(default_factory=PublicId.generate)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_global(self) -> bool:
        return self.user_id is None
