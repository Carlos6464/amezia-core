import uuid
from datetime import datetime
from typing import Protocol

from src.domain.whatsapp_bot.entities import WhatsappSession


class WhatsappSessionRepository(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Interface de persistência do agregado WhatsappSession —
    implementada em infrastructure/database/repositories/whatsapp_bot_repository.py.
    O domínio depende só deste contrato, nunca de SQLAlchemy.
    """

    async def get_by_phone_hash(self, phone_hash: str) -> WhatsappSession | None: ...

    async def create(self, session: WhatsappSession) -> WhatsappSession: ...

    async def update(self, session: WhatsappSession) -> WhatsappSession: ...


class ProcessedBotMessageRepository(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Interface de persistência da deduplicação de mensagens
    (RN-04) — `try_mark_processed` é a única operação exposta, pensada
    para ser um INSERT atômico com `ON CONFLICT DO NOTHING`.
    """

    async def try_mark_processed(self, instance_id: int, whatsapp_message_id: str) -> bool:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: True = inseriu agora (mensagem nova, deve processar).
        False = já existia (mensagem duplicada, deve ignorar).
        """
        ...

    async def set_user_id(
        self, instance_id: int, whatsapp_message_id: str, user_id: uuid.UUID
    ) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Preenche `user_id` na linha já inserida por
        `try_mark_processed` (build-context-09 §2.6) — chamado só
        depois do usuário ser resolvido a partir do telefone, um passo
        depois da idempotência (que continua sendo o 1º efeito
        colateral, RN-04, sem user_id conhecido ainda nesse ponto).
        Sustenta a contagem de `count_for_user_since` para o limite
        mensal de mensagens do Bot no Free.
        """
        ...

    async def count_for_user_since(self, user_id: uuid.UUID, since: datetime) -> int:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Conta mensagens processadas do usuário desde `since`
        (início do ciclo/mês atual) — usado pelo enforcement de
        `PlanLimits.whatsapp_bot_messages_per_month` (build-context-09
        §2.6), sem tabela nova (reaproveita `processed_bot_messages`).
        """
        ...

    async def list_distinct_active_user_ids_since(self, since: datetime) -> set[uuid.UUID]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: Usuários distintos com pelo menos 1 mensagem
        processada pelo bot desde `since` — uma das 3 fontes de
        "usuário ativo" do DAU/MAU do Admin (build-context-11 §2.2).
        Ignora linhas com `user_id IS NULL` (número não vinculado,
        RN-06 — não há usuário Amezia nenhum pra contar).
        """
        ...
