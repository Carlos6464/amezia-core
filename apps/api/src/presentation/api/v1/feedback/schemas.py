import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from src.domain.feedback.entities import Feedback

FeedbackChannelLiteral = Literal["web", "whatsapp"]
FeedbackTypeLiteral = Literal["praise", "suggestion", "bug", "other"]


class FeedbackCreateRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    type: FeedbackTypeLiteral | None = None
    nps_score: int | None = Field(default=None, ge=0, le=10)
    subject: str | None = Field(default=None, max_length=150)


class FeedbackResponse(BaseModel):
    id: uuid.UUID
    channel: FeedbackChannelLiteral
    type: FeedbackTypeLiteral
    nps_score: int | None
    subject: str | None
    message: str
    created_at: dt.datetime

    @classmethod
    def from_entity(cls, feedback: Feedback) -> "FeedbackResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-16
        Descrição: Converte a entidade de domínio Feedback no schema de
        resposta HTTP — todos os campos exceto `user_id` (nunca exposto,
        o próprio usuário já sabe quem é).
        """
        return cls(
            id=feedback.id,
            channel=feedback.channel.value,
            type=feedback.type.value,
            nps_score=feedback.nps_score,
            subject=feedback.subject,
            message=feedback.message,
            created_at=feedback.created_at,
        )


class FeedbackListResponse(BaseModel):
    items: list[FeedbackResponse]
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def build(
        cls, items: list[Feedback], page: int, page_size: int, total: int
    ) -> "FeedbackListResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-16
        Descrição: Monta a resposta paginada do histórico do usuário
        (`GET /feedback/me`) — mesmo padrão page/page_size/total dos
        demais módulos paginados.
        """
        total_pages = (total + page_size - 1) // page_size if page_size else 0
        return cls(
            items=[FeedbackResponse.from_entity(item) for item in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        )
