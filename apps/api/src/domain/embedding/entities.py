import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class EmbeddingSourceType(str, Enum):
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Origem do texto-fonte que gerou o embedding — `source_id`
    é polimórfico conforme este valor (id de `transactions` ou de
    `conversation_messages`, nunca uma FK física, build-context-04 §2.2).
    """

    TRANSACTION = "transaction"
    CONVERSATION_MESSAGE = "conversation_message"
    CATEGORY = "category"


@dataclass
class Embedding:
    """
    Autor: Carlos Adriano
    Data: 2026-09-09
    Descrição: Vetor de embedding (Gemini `gemini-embedding-001`,
    `EMBEDDING_DIMENSION` dimensões) de um trecho de texto do usuário —
    base do RAG do Agente de IA e, desde o build-context-12, da checagem
    de duplicata semântica de categoria. `user_id` é denormalizado
    (RN-01): filtra por usuário antes de rodar a busca vetorial, em vez
    de exigir um JOIN para isolar o resultado. `None` só é válido para
    `source_type=CATEGORY` de uma categoria global (`categories.user_id
    IS NULL`, sem dono) — `TRANSACTION`/`CONVERSATION_MESSAGE` sempre
    pertencem a um usuário.
    """

    user_id: uuid.UUID | None
    source_type: EmbeddingSourceType
    source_id: int
    content: str
    embedding: list[float]
    id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
