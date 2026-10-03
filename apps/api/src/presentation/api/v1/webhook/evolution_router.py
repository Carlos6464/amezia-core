from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.evolution.use_cases.receive_evolution_webhook import (
    ReceiveEvolutionWebhookInput,
    ReceiveEvolutionWebhookUseCase,
)
from src.domain.evolution.exceptions import (
    EvolutionInstanceNotFoundError,
    InvalidWebhookSignatureError,
)
from src.domain.shared.value_objects import PublicId
from src.infrastructure.database.repositories.sqlalchemy_evolution_instance_repository import (
    SqlAlchemyEvolutionInstanceRepository,
)
from src.infrastructure.database.session import get_db
from src.infrastructure.queue.pool import get_arq_pool

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/evolution", status_code=status.HTTP_200_OK)
async def receive_evolution_webhook(
    request: Request,
    instance: str = Query(..., description="public_id (ULID) da EvolutionInstance"),
    secret: str = Query(..., description="webhook_secret configurado na instância"),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> dict[str, str]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: POST /webhook/evolution — rota **pública** (sem JWT),
    chamada pela própria Evolution API a cada evento (build-context-06
    §2.5, RN-07). `instance`/`secret` chegam via query string — é o
    próprio `webhook_url` configurado na instância
    (`UpdateEvolutionInstanceUseCase`/`CreateEvolutionInstanceUseCase`)
    que já embute esses dois valores, então a Evolution API não precisa
    saber que eles existem, só "chamar de volta a URL que foi dada".
    Responde 200 imediatamente após validar e enfileirar — nenhum
    processamento síncrono, nem leve (RN-07). Instância inexistente ou
    secret errado: 404/401 sem enfileirar nada.
    """
    body = await request.json()
    event = body.get("event", "")

    try:
        instance_public_id = PublicId(instance)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instance not found") from exc

    use_case = ReceiveEvolutionWebhookUseCase(SqlAlchemyEvolutionInstanceRepository(db), arq_pool)
    try:
        await use_case.execute(
            ReceiveEvolutionWebhookInput(
                instance_public_id=instance_public_id, secret=secret, event=event, payload=body
            )
        )
    except EvolutionInstanceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instance not found") from exc
    except InvalidWebhookSignatureError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook secret") from exc

    return {"status": "ok"}
