import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class AdminActivityEvent:
    """
    Autor: Carlos Adriano
    Data: 2026-09-11
    Descrição: Uma linha do feed "Atividade recente" da Visão Geral do
    Admin (build-context-11 §2.3) — gravada de forma best-effort (não
    bloqueia o fluxo principal) pelo módulo que o evento pertence
    (cadastro → `user`, upgrade/downgrade/cancelamento → `subscription`).
    `event_type` é `str` livre, não enum Postgres — a lista de eventos
    cresce conforme novos módulos quiserem aparecer no feed, sem exigir
    migration a cada um. `message` já vem pronto pra exibir (montado no
    momento da gravação, nunca recalculado na leitura).
    """

    event_type: str
    message: str
    user_id: uuid.UUID | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
