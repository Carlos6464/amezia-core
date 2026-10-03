import uuid
from dataclasses import dataclass

from src.application.shared.ports import JobEnqueuer
from src.domain.category.exceptions import CategoryNotEditableError, CategoryNotFoundError
from src.domain.category.repository import CategoryRepository
from src.domain.shared.value_objects import PublicId


@dataclass
class DeleteCategoryInput:
    user_id: uuid.UUID
    public_id: PublicId


class DeleteCategoryUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-09
    Descrição: Remove uma categoria privada do próprio usuário — mesma
    checagem de posse do UpdateCategoryUseCase (RN-01/RN-02). Enfileira a
    remoção do embedding indexado (build-context-12 §3.3), pra checagem
    de duplicata semântica nunca sugerir uma categoria já excluída.
    """

    def __init__(self, category_repository: CategoryRepository, job_enqueuer: JobEnqueuer) -> None:
        self._category_repository = category_repository
        self._job_enqueuer = job_enqueuer

    async def execute(self, input_data: DeleteCategoryInput) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Remove a categoria e enfileira `delete_category_embedding`
        (build-context-12 §3.3) — mesma ordem de `CreateCategoryUseCase`
        (efeito de domínio primeiro, indexação depois).
        """
        category = await self._category_repository.get_by_public_id(input_data.public_id)
        if category is None:
            raise CategoryNotFoundError(str(input_data.public_id))
        if category.is_global:
            raise CategoryNotEditableError(str(input_data.public_id))
        if category.user_id != input_data.user_id:
            raise CategoryNotFoundError(str(input_data.public_id))

        await self._category_repository.delete(category)
        await self._job_enqueuer.enqueue_job("delete_category_embedding", category.id)
