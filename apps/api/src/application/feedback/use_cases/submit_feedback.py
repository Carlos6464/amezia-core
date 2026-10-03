import uuid
from dataclasses import dataclass

from src.domain.feedback.entities import Feedback
from src.domain.feedback.repository import FeedbackRepository
from src.domain.feedback.value_objects import FeedbackChannel, FeedbackType


@dataclass
class SubmitFeedbackInput:
    user_id: uuid.UUID
    channel: FeedbackChannel
    message: str
    type: FeedbackType | None = None
    nps_score: int | None = None
    subject: str | None = None


class SubmitFeedbackUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: Cria um feedback do usuário (build-context-08 §2.4) —
    reaproveitado pelos dois canais: o router web (`POST /feedback`,
    `channel=web`, todos os campos do formulário) e o handler do modo
    Feedback do Bot WhatsApp (`channel=whatsapp`, `type`/`nps_score`/
    `subject` sempre `None`). Mesma validação, mesma tabela — só muda
    quem chama e com quais campos preenchidos.
    """

    def __init__(self, feedback_repository: FeedbackRepository) -> None:
        self._feedback_repository = feedback_repository

    async def execute(self, input_data: SubmitFeedbackInput) -> Feedback:
        """
        Autor: Carlos Adriano
        Data: 2026-08-16
        Descrição: Aplica o default `other` quando `type` não é informado
        (mesmo comportamento para os dois canais) e persiste — as
        invariantes de mensagem/NPS são validadas no construtor da
        entidade.
        """
        feedback = Feedback(
            user_id=input_data.user_id,
            message=input_data.message,
            channel=input_data.channel,
            type=input_data.type or FeedbackType.OTHER,
            nps_score=input_data.nps_score,
            subject=input_data.subject,
        )
        return await self._feedback_repository.create(feedback)
