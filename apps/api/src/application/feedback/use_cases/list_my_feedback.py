import uuid
from dataclasses import dataclass

from src.domain.feedback.entities import Feedback
from src.domain.feedback.repository import FeedbackRepository


@dataclass
class ListMyFeedbackResult:
    items: list[Feedback]
    total: int


class ListMyFeedbackUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: Histórico paginado de feedback do próprio usuário
    (build-context-08 §2.4) — alimenta a aba "Histórico" da tela web.
    Não confundir com a listagem administrativa (todos os usuários,
    filtros por tipo/NPS, busca) do build-context-06, que é um use case
    separado.
    """

    def __init__(self, feedback_repository: FeedbackRepository) -> None:
        self._feedback_repository = feedback_repository

    async def execute(self, user_id: uuid.UUID, page: int, page_size: int) -> ListMyFeedbackResult:
        """
        Autor: Carlos Adriano
        Data: 2026-08-16
        Descrição: Filtra sempre por `user_id` do chamador (RN-01) —
        nunca aceita filtro de outro usuário.
        """
        items, total = await self._feedback_repository.list_by_user(user_id, page, page_size)
        return ListMyFeedbackResult(items=items, total=total)
