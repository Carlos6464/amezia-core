import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.feedback.exceptions import (
    EmptyFeedbackMessageError,
    FeedbackMessageTooLongError,
    InvalidNpsScoreError,
)
from src.domain.feedback.value_objects import FeedbackChannel, FeedbackType

MAX_MESSAGE_LENGTH = 1000


@dataclass
class Feedback:
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: Entidade de domínio de feedback (build-context-08 §2.2) —
    mensagem livre, canal de origem, tipo, nota NPS opcional e assunto
    curto opcional. Sem `PublicId`/ULID: não existe endpoint `show`
    individual, só criação e listagem, então o `id` (UUID) nunca precisa
    de um identificador externo próprio.
    """

    user_id: uuid.UUID
    message: str
    channel: FeedbackChannel
    type: FeedbackType = FeedbackType.OTHER
    nps_score: int | None = None
    subject: str | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-16
        Descrição: Valida as invariantes do agregado — mensagem
        obrigatória (1–1000 caracteres) e nota NPS, quando informada,
        dentro do intervalo 0–10.
        """
        if not self.message.strip():
            raise EmptyFeedbackMessageError("Feedback message cannot be empty")
        if len(self.message) > MAX_MESSAGE_LENGTH:
            raise FeedbackMessageTooLongError(
                f"Feedback message cannot exceed {MAX_MESSAGE_LENGTH} characters"
            )
        if self.nps_score is not None and not (0 <= self.nps_score <= 10):
            raise InvalidNpsScoreError("NPS score must be between 0 and 10")
