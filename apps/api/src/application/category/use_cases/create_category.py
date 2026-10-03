import uuid
from dataclasses import dataclass

from src.application.shared.ports import JobEnqueuer
from src.domain.category.entities import Category
from src.domain.category.repository import CategoryRepository


@dataclass
class CreateCategoryInput:
    user_id: uuid.UUID
    name: str
    color: str
    icon: str


class CreateCategoryUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-09
    Descrição: Cria uma categoria privada para o usuário autenticado, sem
    limite de quantidade (limite de 3 removido a pedido do usuário — PRD
    §6.3). Nome duplicado no escopo é detectado pelo repositório via
    constraint do banco (DuplicateCategoryNameError). Enfileira a
    indexação do embedding do nome (build-context-12 §3.3), base da
    checagem de duplicata semântica no registro de despesa via bot.
    """

    def __init__(self, category_repository: CategoryRepository, job_enqueuer: JobEnqueuer) -> None:
        self._category_repository = category_repository
        self._job_enqueuer = job_enqueuer

    async def execute(self, input_data: CreateCategoryInput) -> Category:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Persiste a categoria e, na sequência, enfileira
        `index_category_embedding` (build-context-12 §3.3) — enfileirado
        depois do `add()` porque só aí a categoria tem `id` de verdade
        (job é polimórfico por `source_id`, o `id` interno).
        """
        category = Category(
            name=input_data.name,
            color=input_data.color,
            icon=input_data.icon,
            user_id=input_data.user_id,
            is_system=False,
        )
        created = await self._category_repository.add(category)
        await self._job_enqueuer.enqueue_job(
            "index_category_embedding", str(created.user_id), created.id, created.name
        )
        return created
