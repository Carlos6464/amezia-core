from dataclasses import dataclass

from src.domain.admin_activity.entities import AdminActivityEvent
from src.domain.admin_activity.repository import AdminActivityRepository


@dataclass
class GetAdminActivityResult:
    items: list[AdminActivityEvent]
    total: int


class GetAdminActivityUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-11
    Descrição: `GET /admin/activity` (build-context-11 §2.4/T4) — feed
    paginado de atividade recente, só `SELECT ... ORDER BY created_at
    DESC LIMIT`, sem nenhuma lógica de agregação (a lógica já rodou no
    momento da gravação, `message` já vem pronto pra exibir).
    """

    def __init__(self, admin_activity_repository: AdminActivityRepository) -> None:
        self._admin_activity_repository = admin_activity_repository

    async def execute(self, page: int, page_size: int) -> GetAdminActivityResult:
        items, total = await self._admin_activity_repository.list_paginated(page, page_size)
        return GetAdminActivityResult(items=items, total=total)
