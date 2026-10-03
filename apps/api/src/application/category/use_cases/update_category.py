import uuid
from dataclasses import dataclass

from src.application.shared.ports import JobEnqueuer
from src.domain.category.entities import Category
from src.domain.category.exceptions import CategoryNotEditableError, CategoryNotFoundError
from src.domain.category.repository import CategoryRepository
from src.domain.shared.value_objects import PublicId


@dataclass
class UpdateCategoryInput:
    user_id: uuid.UUID
    public_id: PublicId
    name: str | None
    color: str | None
    icon: str | None


class UpdateCategoryUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-09
    Descrição: Atualiza name/color de uma categoria privada do próprio
    usuário. Categoria global levanta CategoryNotEditableError (RN-02,
    403); categoria privada de outro usuário levanta CategoryNotFoundError
    (RN-01 — não revela existência, 404). Renomear reenfileira a
    indexação do embedding do nome (build-context-12 §3.3).
    """

    def __init__(self, category_repository: CategoryRepository, job_enqueuer: JobEnqueuer) -> None:
        self._category_repository = category_repository
        self._job_enqueuer = job_enqueuer

    async def execute(self, input_data: UpdateCategoryInput) -> Category:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Atualiza os campos informados (parcial — só os não
        `None`) e, se `name` mudou, reenfileira `index_category_embedding`
        (build-context-12 §3.3) — cor/ícone sozinhos não afetam a
        checagem de duplicata semântica, só o nome.
        """
        category = await self._category_repository.get_by_public_id(input_data.public_id)
        if category is None:
            raise CategoryNotFoundError(str(input_data.public_id))
        if category.is_global:
            raise CategoryNotEditableError(str(input_data.public_id))
        if category.user_id != input_data.user_id:
            raise CategoryNotFoundError(str(input_data.public_id))

        name_changed = input_data.name is not None
        if input_data.name is not None:
            category.name = input_data.name
        if input_data.color is not None:
            category.color = input_data.color
        if input_data.icon is not None:
            category.icon = input_data.icon

        updated = await self._category_repository.update(category)
        if name_changed:
            await self._job_enqueuer.enqueue_job(
                "index_category_embedding", str(updated.user_id), updated.id, updated.name
            )
        return updated
