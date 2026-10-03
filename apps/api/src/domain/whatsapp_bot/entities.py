import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from src.domain.whatsapp_bot.value_objects import BotMode

SESSION_TTL_MINUTES = 30


@dataclass
class WhatsappSession:
    """
    Autor: Carlos Adriano
    Data: 2026-09-09
    Descrição: Entidade de domínio da sessão do Bot WhatsApp — uma linha
    por usuário (build-context-07 §2.4), não por conversa/mensagem.
    Guarda o estado atual da máquina de 5 modos, o `phone_hash` usado
    para localizar a sessão a partir do número recebido no webhook (sem
    precisar decifrar `users.phone` — EncryptedString não é pesquisável
    por igualdade, RN-05), e `pending_action` (build-context-12 §2) — o
    rascunho de uma pergunta que o bot fez de volta ao usuário dentro do
    modo Registrar (categoria/parcelamento), que precisa sobreviver
    entre uma mensagem e a próxima (o WhatsApp não tem estado de
    conversa "em memória").
    """

    user_id: uuid.UUID
    phone_hash: str
    current_state: BotMode | None = None
    pending_action: dict[str, Any] | None = None
    id: int | None = None
    last_interaction_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_expired(self, now: datetime) -> bool:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: TTL de 30min de inatividade (build-context-07 §2.3) —
        checado no início do processamento de toda mensagem, antes de
        qualquer outra regra. Não expira a linha em si, só o estado
        atual (ver `reset_to_menu`).
        """
        return now - self.last_interaction_at > timedelta(minutes=SESSION_TTL_MINUTES)

    def reset_to_menu(self) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Volta ao estado Menu (`current_state = None`) — usado
        pelo TTL, pelo override global "0"/"menu" e pelo auto-retorno do
        modo Feedback após salvar. Também limpa `pending_action`
        (build-context-12) — qualquer pergunta em aberto do modo
        Registrar é descartada junto, nunca sobrevive a uma volta ao
        Menu.
        """
        self.current_state = None
        self.pending_action = None

    def transition_to(self, mode: BotMode) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Muda o estado atual da sessão para o modo informado —
        usado pelos handlers ao processar uma opção válida do Menu (ou
        para permanecer no mesmo modo em Registrar/Chat/Relatório).
        """
        self.current_state = mode

    def touch(self, now: datetime) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Atualiza `last_interaction_at` — chamado ao final do
        processamento de toda mensagem válida, reiniciando a janela do
        TTL de 30min.
        """
        self.last_interaction_at = now


@dataclass
class ProcessedBotMessage:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Registro de deduplicação de mensagens do Bot WhatsApp
    (RN-04, build-context-07 §2.4) — sem comportamento além de existir.
    A escrita real acontece via `ProcessedBotMessageRepository.try_mark_processed`
    (INSERT atômico com `ON CONFLICT DO NOTHING`); esta entidade só
    documenta a forma da linha.
    """

    whatsapp_instance_id: int
    whatsapp_message_id: str
    id: int | None = None
    processed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
