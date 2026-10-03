import uuid
from typing import Protocol

from src.domain.feedback.entities import Feedback
from src.domain.feedback.value_objects import FeedbackChannel


class FeedbackRepository(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: Interface de persistência do agregado Feedback —
    implementada em
    infrastructure/database/repositories/feedback_repository.py. `create`
    é reaproveitado pelos dois canais (web/whatsapp); `list_by_user`
    alimenta o histórico do próprio usuário (build-context-08);
    `list_paginated`/`count_total` seguem servindo a listagem
    administrativa (build-context-06).
    """

    async def create(self, feedback: Feedback) -> Feedback: ...

    async def list_by_user(
        self, user_id: uuid.UUID, page: int, page_size: int
    ) -> tuple[list[Feedback], int]: ...

    async def list_paginated(
        self, page: int, page_size: int, channel: FeedbackChannel | None, search: str | None
    ) -> tuple[list[Feedback], int]: ...

    async def count_total(self) -> int: ...
