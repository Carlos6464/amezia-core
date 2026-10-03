from typing import Protocol

from src.domain.admin_activity.entities import AdminActivityEvent


class AdminActivityRepository(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-09-11
    Descrição: Interface de persistência de `admin_activity_log`
    (build-context-11 §2.3) — implementada em
    infrastructure/database/repositories/admin_activity_repository.py.
    """

    async def create(self, event: AdminActivityEvent) -> AdminActivityEvent: ...

    async def list_paginated(
        self, page: int, page_size: int
    ) -> tuple[list[AdminActivityEvent], int]:
        """`ORDER BY created_at DESC` — feed do mais recente pro mais antigo, sem lógica de agregação."""
        ...
