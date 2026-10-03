import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.user.entities import User as UserEntity
from src.domain.user.repository import UserFilters
from src.domain.user.value_objects import DashboardCard, DashboardCardPreference, Email, Language
from src.infrastructure.database.models.user import User as UserModel


def _dashboard_layout_to_entity(
    raw: list[dict[str, object]] | None,
) -> list[DashboardCardPreference] | None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: Converte o JSONB bruto (`[{"card": "...", "visible": bool}]`)
    na lista de VOs de domínio — `None` (nunca personalizado) passa
    direto. Um `card` fora do enum (não deveria acontecer, já que a
    escrita sempre passa pelo schema HTTP tipado) é ignorado em vez de
    quebrar a leitura da conta inteira.
    """
    if raw is None:
        return None
    preferences: list[DashboardCardPreference] = []
    for item in raw:
        try:
            preferences.append(
                DashboardCardPreference(card=DashboardCard(item["card"]), visible=bool(item["visible"]))
            )
        except ValueError:
            continue
    return preferences


def _dashboard_layout_to_json(
    preferences: list[DashboardCardPreference] | None,
) -> list[dict[str, object]] | None:
    """Converte a lista de VOs de domínio no JSON bruto persistido — inverso de `_dashboard_layout_to_entity`."""
    if preferences is None:
        return None
    return [{"card": pref.card.value, "visible": pref.visible} for pref in preferences]


def _first_of_month(year: int, month: int) -> date:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Primeiro dia de um mês (ano/mês normalizados) — usado por
    `count_new_users_by_month` para gerar os N pontos da série mensal.
    """
    return date(year, month, 1)


def _shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Desloca (ano, mês) em `offset` meses (positivo ou
    negativo), normalizando o ano quando o mês sai do intervalo 1-12.
    """
    total = (year * 12 + month - 1) + offset
    new_year, new_month = divmod(total, 12)
    return new_year, new_month + 1


class SqlAlchemyUserRepository:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Implementação concreta de UserRepository via SQLAlchemy
    async — traduz entre a entidade de domínio User e o model ORM. A
    criptografia/decriptografia de `phone` acontece de forma transparente
    no `EncryptedString` do model, não aqui.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> UserEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Busca um usuário pela PK. Retorna None se não existir —
        quem chama decide se isso é um erro (ex.: UserNotFoundError).
        """
        model = await self._session.get(UserModel, user_id)
        return self._to_entity(model) if model else None

    async def get_by_email(self, email: str) -> UserEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Busca um usuário pelo email (único). Usado no login e
        no cadastro (checar duplicidade) e no account linking do Google.
        """
        result = await self._session.execute(select(UserModel).where(UserModel.email == email))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_phone_hash(self, phone_hash: str) -> UserEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Busca um usuário pelo hash determinístico do telefone
        (HMAC-SHA256, `infrastructure/security/phone_hasher.py`) — usado
        pelo Bot WhatsApp (build-context-07 §2.6) para resolver o
        usuário a partir do número que mandou a mensagem, já que `phone`
        é criptografado (AES) e não é pesquisável por igualdade em SQL.
        """
        result = await self._session.execute(
            select(UserModel).where(UserModel.phone_hash == phone_hash)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_oauth_id(self, oauth_provider: str, oauth_id: str) -> UserEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Busca um usuário pelo par (oauth_provider, oauth_id) —
        primeira tentativa do LoginWithGoogleUseCase, antes de cair para
        busca por email (account linking) ou criação de conta nova.
        """
        result = await self._session.execute(
            select(UserModel).where(
                UserModel.oauth_provider == oauth_provider,
                UserModel.oauth_id == oauth_id,
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def exists_by_email(self, email: str) -> bool:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Checagem leve de duplicidade de email (sem carregar a
        entidade inteira) usada pelo RegisterUserUseCase.
        """
        result = await self._session.execute(select(UserModel.id).where(UserModel.email == email))
        return result.scalar_one_or_none() is not None

    async def create(self, user: UserEntity) -> UserEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Persiste um novo usuário. `flush()` + `refresh()` para
        devolver a entidade com os defaults gerados pelo banco (created_at,
        updated_at) já preenchidos, sem precisar de um commit explícito
        aqui (fica a cargo do router, que também controla a transação).
        """
        model = self._to_model(user)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def update(self, user: UserEntity) -> UserEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Atualiza todos os campos mutáveis de um usuário
        existente a partir da entidade de domínio. Levanta ValueError se o
        `id` não corresponder a nenhuma linha — não deveria acontecer em
        uso normal, já que a entidade sempre vem de um `get_by_*` anterior.
        """
        model = await self._session.get(UserModel, user.id)
        if model is None:
            raise ValueError(f"User {user.id} not found")
        model.name = user.name
        model.email = str(user.email)
        model.password_hash = user.password_hash
        model.phone = user.phone
        model.phone_hash = user.phone_hash
        model.role = user.role
        model.language = user.language.value
        model.oauth_provider = user.oauth_provider
        model.oauth_id = user.oauth_id
        model.last_login_at = user.last_login_at
        model.monthly_budget_cents = user.monthly_budget_cents
        model.onboarding_completed = user.onboarding_completed
        model.dashboard_layout = _dashboard_layout_to_json(user.dashboard_layout)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def delete(self, user_id: uuid.UUID) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Exclui a conta (DeleteAccountUseCase). Silenciosamente
        no-op se o usuário já não existir, em vez de levantar erro.
        """
        model = await self._session.get(UserModel, user_id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()

    async def list_paginated(
        self, filters: UserFilters, page: int, page_size: int
    ) -> tuple[list[UserEntity], int]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Lista paginada de usuários para o Admin (build-context-06
        §2.3) — mais recentes primeiro. `search` roda em SQL (`ILIKE`
        sobre nome/email), diferente de campos criptografados: nem `name`
        nem `email` usam `EncryptedString`.
        """
        conditions = []
        if filters.search:
            pattern = f"%{filters.search}%"
            conditions.append(or_(UserModel.name.ilike(pattern), UserModel.email.ilike(pattern)))
        if filters.role is not None:
            conditions.append(UserModel.role == filters.role)
        if filters.has_phone is not None:
            conditions.append(
                UserModel.phone.isnot(None) if filters.has_phone else UserModel.phone.is_(None)
            )

        count_result = await self._session.execute(
            select(func.count()).select_from(UserModel).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self._session.execute(
            select(UserModel)
            .where(*conditions)
            .order_by(UserModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [self._to_entity(model) for model in result.scalars().all()]
        return items, total

    async def count_total(self) -> int:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Total de usuários cadastrados — KPI da Visão Geral do
        Admin.
        """
        result = await self._session.execute(select(func.count()).select_from(UserModel))
        return result.scalar_one()

    async def count_with_phone(self) -> int:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Usuários com WhatsApp vinculado (`phone IS NOT NULL`) —
        KPI da Visão Geral do Admin. Checagem de presença, não de valor —
        não precisa decifrar o `EncryptedString`.
        """
        result = await self._session.execute(
            select(func.count()).select_from(UserModel).where(UserModel.phone.isnot(None))
        )
        return result.scalar_one()

    async def count_new_users_by_month(self, months: int) -> list[tuple[date, int]]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Série mensal de novos usuários, dos `months` meses
        corridos até o mês atual (inclusive), em ordem cronológica
        crescente — alimenta o gráfico de linha da Visão Geral do Admin.
        Um mês sem cadastro nenhum aparece com contagem 0 (nunca omitido).
        """
        today = datetime.now(UTC).date()
        points: list[tuple[date, int]] = []
        for offset in range(months - 1, -1, -1):
            year, month = _shift_month(today.year, today.month, -offset)
            next_year, next_month = _shift_month(year, month, 1)
            range_start = datetime(year, month, 1, tzinfo=UTC)
            range_end = datetime(next_year, next_month, 1, tzinfo=UTC)
            result = await self._session.execute(
                select(func.count())
                .select_from(UserModel)
                .where(UserModel.created_at >= range_start, UserModel.created_at < range_end)
            )
            points.append((_first_of_month(year, month), result.scalar_one()))
        return points

    def _to_entity(self, model: UserModel) -> UserEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Converte o model SQLAlchemy (infraestrutura) na entidade
        de domínio User — fronteira entre as duas camadas.
        """
        return UserEntity(
            id=model.id,
            name=model.name,
            email=Email(model.email),
            password_hash=model.password_hash,
            phone=model.phone,
            phone_hash=model.phone_hash,
            role=model.role,
            language=Language(model.language),
            oauth_provider=model.oauth_provider,
            oauth_id=model.oauth_id,
            last_login_at=model.last_login_at,
            monthly_budget_cents=model.monthly_budget_cents,
            onboarding_completed=model.onboarding_completed,
            dashboard_layout=_dashboard_layout_to_entity(model.dashboard_layout),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: UserEntity) -> UserModel:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Converte a entidade de domínio User num model
        SQLAlchemy novo (ainda não persistido) — usado só por `create`.
        """
        return UserModel(
            id=entity.id,
            name=entity.name,
            email=str(entity.email),
            password_hash=entity.password_hash,
            phone=entity.phone,
            phone_hash=entity.phone_hash,
            role=entity.role,
            language=entity.language.value,
            oauth_provider=entity.oauth_provider,
            oauth_id=entity.oauth_id,
            last_login_at=entity.last_login_at,
        )
