from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.admin_activity.entities import AdminActivityEvent
from src.infrastructure.database.models.admin_activity import AdminActivityLog as AdminActivityModel


class SqlAlchemyAdminActivityRepository:
    """
    Autor: Carlos Adriano
    Data: 2026-09-11
    Descrição: Implementação concreta de `AdminActivityRepository`
    (build-context-11 §2.1) via SQLAlchemy async.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, event: AdminActivityEvent) -> AdminActivityEvent:
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: Persiste uma linha do feed — chamada de forma
        best-effort pelos módulos que geram o evento (cadastro,
        upgrade/downgrade/cancelamento de assinatura), nunca deve
        propagar uma falha que derrube o fluxo principal de quem chama.
        """
        model = AdminActivityModel(
            id=event.id,
            event_type=event.event_type,
            user_id=event.user_id,
            message=event.message,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return AdminActivityEvent(
            id=model.id,
            event_type=model.event_type,
            user_id=model.user_id,
            message=model.message,
            created_at=model.created_at,
        )

    async def list_paginated(
        self, page: int, page_size: int
    ) -> tuple[list[AdminActivityEvent], int]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: `ORDER BY created_at DESC` — feed do mais recente pro
        mais antigo, sem lógica de agregação (build-context-11 §2.3).
        """
        total_result = await self._session.execute(
            select(func.count()).select_from(AdminActivityModel)
        )
        total = total_result.scalar_one()

        result = await self._session.execute(
            select(AdminActivityModel)
            .order_by(AdminActivityModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [
            AdminActivityEvent(
                id=model.id,
                event_type=model.event_type,
                user_id=model.user_id,
                message=model.message,
                created_at=model.created_at,
            )
            for model in result.scalars().all()
        ]
        return items, total
