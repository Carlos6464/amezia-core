from dataclasses import dataclass

from src.application.admin.dtos import FeedbackWithUser
from src.domain.feedback.repository import FeedbackRepository
from src.domain.feedback.value_objects import FeedbackChannel
from src.domain.user.repository import UserRepository


@dataclass
class ListFeedbackResult:
    items: list[FeedbackWithUser]
    total: int


class ListFeedbackUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Lista paginada de feedbacks para o Admin (build-context-06
    §2.3/§2.9) — filtros de canal e busca no texto da mensagem. Hidrata
    cada item com nome/email do usuário (`feedback-card` da tela exibe
    isso), mesmo padrão de `GetTransactionUseCase` resolvendo a
    categoria via `get_by_id` — volume por página é pequeno (paginado),
    então N chamadas de `get_by_id` não é gargalo real.
    """

    def __init__(
        self, feedback_repository: FeedbackRepository, user_repository: UserRepository
    ) -> None:
        self._feedback_repository = feedback_repository
        self._user_repository = user_repository

    async def execute(
        self, page: int, page_size: int, channel: FeedbackChannel | None, search: str | None
    ) -> ListFeedbackResult:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Busca a página filtrada e hidrata cada item com o
        resumo do usuário que enviou o feedback.
        """
        items, total = await self._feedback_repository.list_paginated(
            page, page_size, channel, search
        )
        hydrated: list[FeedbackWithUser] = []
        for feedback in items:
            user = await self._user_repository.get_by_id(feedback.user_id)
            hydrated.append(FeedbackWithUser(feedback=feedback, user=user))
        return ListFeedbackResult(items=hydrated, total=total)
