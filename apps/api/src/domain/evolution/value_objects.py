from enum import Enum


class ConnectionStatus(str, Enum):
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Estado de conexão de uma EvolutionInstance com o WhatsApp —
    atualizado por sync manual (SyncEvolutionInstanceUseCase) ou por
    evento de webhook (CONNECTION_UPDATE, build-context-06 §2.5).
    """

    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"

    @classmethod
    def from_raw(cls, raw_state: str) -> "ConnectionStatus":
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Traduz o estado bruto da Evolution API (`open`/
        `connecting`/`close`) para ConnectionStatus — reaproveitado tanto
        pelo refresh manual (SyncEvolutionInstanceUseCase) quanto pelo
        job do webhook (CONNECTION_UPDATE), única fonte da tradução.
        Qualquer valor desconhecido cai em DISCONNECTED (conservador).
        """
        return {"open": cls.CONNECTED, "connecting": cls.CONNECTING, "close": cls.DISCONNECTED}.get(
            raw_state, cls.DISCONNECTED
        )
