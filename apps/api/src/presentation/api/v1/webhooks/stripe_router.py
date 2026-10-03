from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.subscription.use_cases.handle_stripe_webhook import (
    HandleStripeWebhookInput,
    HandleStripeWebhookUseCase,
)
from src.domain.subscription.exceptions import InvalidStripeWebhookSignatureError
from src.infrastructure.database.repositories.admin_activity_repository import (
    SqlAlchemyAdminActivityRepository,
)
from src.infrastructure.database.repositories.subscription_repository import (
    SqlAlchemyPaymentEventRepository,
    SqlAlchemyPlanPriceRepository,
    SqlAlchemySubscriptionRepository,
)
from src.infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from src.infrastructure.database.session import get_db
from src.infrastructure.payment.stripe_client import StripeGateway

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe", status_code=status.HTTP_200_OK)
async def receive_stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: POST /webhooks/stripe — rota pública (sem JWT), chamada
    pelo Stripe a cada evento (build-context-09 §2.5 passo 5).
    Processamento síncrono aqui mesmo (decisão confirmada com o
    usuário em 2026-09-10) — diferente do webhook Evolution (RN-07),
    o trabalho é só leitura/escrita no Postgres, sem I/O pesado que
    justifique enfileirar em ARQ. Assinatura inválida: 400, sem
    processar nada.
    """
    payload = await request.body()

    use_case = HandleStripeWebhookUseCase(
        SqlAlchemySubscriptionRepository(db),
        SqlAlchemyPaymentEventRepository(db),
        SqlAlchemyPlanPriceRepository(db),
        StripeGateway(),
        SqlAlchemyUserRepository(db),
        SqlAlchemyAdminActivityRepository(db),
    )
    try:
        await use_case.execute(HandleStripeWebhookInput(payload=payload, sig_header=stripe_signature))
    except InvalidStripeWebhookSignatureError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid Stripe signature") from exc

    await db.commit()
    return {"status": "ok"}
