from pydantic import BaseModel

from src.application.evolution.use_cases.get_bot_info import BotInfo


class BotInfoResponse(BaseModel):
    phone_number: str | None
    is_available: bool

    @classmethod
    def from_dto(cls, dto: BotInfo) -> "BotInfoResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-16
        Descrição: Converte a DTO BotInfo no schema de resposta HTTP.
        """
        return cls(phone_number=dto.phone_number, is_available=dto.is_available)
