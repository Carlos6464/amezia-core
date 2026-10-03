from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.evolution.use_cases.get_bot_info import GetBotInfoUseCase
from src.domain.user.entities import User
from src.infrastructure.database.repositories.sqlalchemy_evolution_instance_repository import (
    SqlAlchemyEvolutionInstanceRepository,
)
from src.infrastructure.database.session import get_db
from src.presentation.api.v1.bot.schemas import BotInfoResponse
from src.presentation.api.v1.dependencies.auth import get_current_user

router = APIRouter(prefix="/bot", tags=["bot"])


@router.get("/info", response_model=BotInfoResponse)
async def get_bot_info(
    _current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> BotInfoResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: GET /bot/info — número do bot WhatsApp + disponibilidade,
    pro passo "salvar número do bot" do onboarding. Exige só autenticação
    (qualquer usuário comum, não é rota de Admin) — não expõe nada além
    do número, que é informação pública por natureza (o próprio propósito
    é o usuário salvar/conversar com esse contato).
    """
    use_case = GetBotInfoUseCase(SqlAlchemyEvolutionInstanceRepository(db))
    result = await use_case.execute()
    return BotInfoResponse.from_dto(result)
