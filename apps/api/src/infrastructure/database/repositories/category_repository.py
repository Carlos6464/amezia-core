import uuid

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.category.entities import Category as CategoryEntity
from src.domain.category.exceptions import CategoryInUseError, DuplicateCategoryNameError
from src.domain.shared.value_objects import PublicId
from src.infrastructure.database.models.category import Category as CategoryModel


class SqlAlchemyCategoryRepository:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Implementação concreta de CategoryRepository via SQLAlchemy
    async — traduz entre a entidade de domínio Category e o model ORM.
    Duplicidade de nome (RN do módulo, índice único `ix_categories_user_name`)
    é detectada pela violação de constraint do banco, nunca por um SELECT
    prévio — evita condição de corrida entre a checagem e o insert.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, category: CategoryEntity) -> CategoryEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Persiste uma nova categoria. Traduz violação do índice
        único parcial (mesmo nome, case-insensitive, no mesmo escopo
        privado) em DuplicateCategoryNameError.
        """
        model = self._to_model(category)
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise DuplicateCategoryNameError(category.name) from exc
        await self._session.refresh(model)
        return self._to_entity(model)

    async def list_visible_to(self, user_id: uuid.UUID) -> list[CategoryEntity]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Globais (`user_id IS NULL`) + privadas do usuário
        informado (RN-01) — ordenadas com as globais primeiro, depois por
        nome, para a listagem ficar estável entre chamadas.
        """
        result = await self._session.execute(
            select(CategoryModel)
            .where(or_(CategoryModel.user_id.is_(None), CategoryModel.user_id == user_id))
            .order_by(CategoryModel.is_system.desc(), CategoryModel.name)
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def get_by_public_id(self, public_id: PublicId) -> CategoryEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Busca uma categoria pelo public_id (ULID), sem filtrar
        por dono — a checagem de posse é responsabilidade dos use cases
        de update/delete (RN-01/RN-02).
        """
        result = await self._session.execute(
            select(CategoryModel).where(CategoryModel.public_id == str(public_id))
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_id(self, id: int) -> CategoryEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Busca uma categoria pelo id interno (BIGINT) — usado
        por GetTransactionUseCase (build-context-03) para hidratar o
        resumo de categoria de uma transação a partir do seu
        `category_id`, que é o id interno, não o public_id.
        """
        model = await self._session.get(CategoryModel, id)
        return self._to_entity(model) if model else None

    async def update(self, category: CategoryEntity) -> CategoryEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Atualiza name/color de uma categoria privada já
        existente. Levanta ValueError se o `id` não corresponder a
        nenhuma linha — não deveria acontecer em uso normal, já que a
        entidade sempre vem de um get_by_public_id anterior.
        """
        model = await self._session.get(CategoryModel, category.id)
        if model is None:
            raise ValueError(f"Category {category.id} not found")
        model.name = category.name
        model.color = category.color
        model.icon = category.icon
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise DuplicateCategoryNameError(category.name) from exc
        await self._session.refresh(model)
        return self._to_entity(model)

    async def delete(self, category: CategoryEntity) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Remove uma categoria privada. Silenciosamente no-op se
        já não existir, em vez de levantar erro. Traduz a violação de FK
        `transactions.category_id ON DELETE RESTRICT` (build-context-03)
        em CategoryInUseError — categoria com transações associadas não
        pode ser excluída.
        """
        model = await self._session.get(CategoryModel, category.id)
        if model is None:
            return
        await self._session.delete(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise CategoryInUseError(str(category.public_id)) from exc

    def _to_entity(self, model: CategoryModel) -> CategoryEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Converte o model SQLAlchemy (infraestrutura) na
        entidade de domínio Category — fronteira entre as duas camadas.
        """
        return CategoryEntity(
            id=model.id,
            public_id=PublicId(model.public_id),
            name=model.name,
            color=model.color,
            icon=model.icon,
            user_id=model.user_id,
            is_system=model.is_system,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: CategoryEntity) -> CategoryModel:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Converte a entidade de domínio Category num model
        SQLAlchemy novo (ainda não persistido) — usado só por `add`.
        """
        return CategoryModel(
            public_id=str(entity.public_id),
            name=entity.name,
            color=entity.color,
            icon=entity.icon,
            user_id=entity.user_id,
            is_system=entity.is_system,
        )
