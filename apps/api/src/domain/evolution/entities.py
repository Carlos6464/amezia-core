from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.evolution.value_objects import ConnectionStatus
from src.domain.shared.value_objects import PublicId


@dataclass
class EvolutionInstance:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Entidade de domínio da instância Evolution API que sustenta
    o Bot WhatsApp — a nível de plataforma, não por usuário (build-context-06
    §2.2: `evolution_instances.user_id` está fora do escopo do MVP1).
    `phone_number`/`webhook_secret` chegam já decifrados do repositório
    (EncryptedString, RN-05) — o domínio nunca lida com ciphertext.
    """

    name: str
    webhook_url: str
    webhook_secret: str
    phone_number: str | None = None
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    qr_code: str | None = None
    qr_code_expires_at: datetime | None = None
    is_active: bool = False
    connected_at: datetime | None = None
    last_message_at: datetime | None = None
    id: int | None = None
    public_id: PublicId = field(default_factory=PublicId.generate)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def webhook_callback_url(self) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: URL real registrada na Evolution API — `webhook_url`
        (o endpoint lógico, ex. `https://api.amezia.app/api/v1/webhook/evolution`)
        com `instance`/`secret` embutidos como query string (build-context-06
        §2.5). A rota pública do webhook lê os dois da própria URL que
        recebeu, sem depender da Evolution API suportar headers
        customizados de assinatura.
        """
        return f"{self.webhook_url}?instance={self.public_id}&secret={self.webhook_secret}"
