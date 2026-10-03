from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.category.use_cases.create_category import (
    CreateCategoryInput,
    CreateCategoryUseCase,
)
from src.application.category.use_cases.delete_category import (
    DeleteCategoryInput,
    DeleteCategoryUseCase,
)
from src.application.category.use_cases.list_categories import ListCategoriesUseCase
from src.application.category.use_cases.update_category import (
    UpdateCategoryInput,
    UpdateCategoryUseCase,
)
from src.domain.category.exceptions import (
    CategoryInUseError,
    CategoryNotEditableError,
    CategoryNotFoundError,
    DuplicateCategoryNameError,
)
from src.domain.shared.value_objects import PublicId
from src.domain.user.entities import User
from src.infrastructure.database.repositories.category_repository import (
    SqlAlchemyCategoryRepository,
)
from src.infrastructure.database.repositories.transaction_repository import (
    SqlAlchemyTransactionRepository,
)
from src.infrastructure.database.session import get_db
from src.infrastructure.queue.pool import get_arq_pool
from src.presentation.api.v1.categories.schemas import (
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
)
from src.presentation.api.v1.dependencies.auth import (
    get_current_user,
    get_current_user_or_report_viewer,
)

router = APIRouter(prefix="/categories", tags=["categories"])


def _parse_public_id(raw: str) -> PublicId:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Faz o parse do public_id vindo da URL. Um ULID malformado
    é tratado como "não encontrado" (404), nunca como erro de validação —
    RN-01 (não revelar detalhe interno) se aplica igual a um ULID válido
    mas inexistente.
    """
    try:
        return PublicId(raw)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found") from exc


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> CategoryResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-09-09
    Descrição: POST /categories — cria categoria privada do usuário
    autenticado, sem limite de quantidade (nome único no escopo).
    """
    use_case = CreateCategoryUseCase(
        category_repository=SqlAlchemyCategoryRepository(db), job_enqueuer=arq_pool
    )
    try:
        category = await use_case.execute(
            CreateCategoryInput(
                user_id=current_user.id,
                name=payload.name,
                color=payload.color,
                icon=payload.icon,
            )
        )
    except DuplicateCategoryNameError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Category name already exists"
        ) from exc

    await db.commit()
    return CategoryResponse.from_entity(category)


@router.get("", response_model=list[CategoryResponse])
async def list_categories(
    current_user: User = Depends(get_current_user_or_report_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[CategoryResponse]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: GET /categories — globais + privadas do usuário
    autenticado (RN-01), sem paginação. Único endpoint de listagem — não
    há GET /categories/{public_id}. Cada categoria vem com uso agregado
    (transaction_count/total_amount) desde 2026-08-11 — antes disso
    (build-context-02) essas colunas ficavam com placeholder no
    frontend, à espera de Transações existir. Aceita `report_view`
    (2026-08-18, link mágico do bot) além do access token normal — só
    esse GET; criar/editar/excluir categoria continuam com
    `get_current_user` estrito. Necessário pro dropdown de filtro por
    categoria funcionar na tela de Relatórios compartilhada.
    """
    use_case = ListCategoriesUseCase(
        category_repository=SqlAlchemyCategoryRepository(db),
        transaction_repository=SqlAlchemyTransactionRepository(db),
    )
    categories = await use_case.execute(current_user.id)
    return [CategoryResponse.from_dto(item) for item in categories]


@router.patch("/{public_id}", response_model=CategoryResponse)
async def update_category(
    public_id: str,
    payload: CategoryUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> CategoryResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: PATCH /categories/{public_id} — atualização parcial de
    name/color de uma categoria privada do próprio usuário.
    """
    use_case = UpdateCategoryUseCase(
        category_repository=SqlAlchemyCategoryRepository(db), job_enqueuer=arq_pool
    )
    try:
        category = await use_case.execute(
            UpdateCategoryInput(
                user_id=current_user.id,
                public_id=_parse_public_id(public_id),
                name=payload.name,
                color=payload.color,
                icon=payload.icon,
            )
        )
    except CategoryNotEditableError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Category is read-only") from exc
    except CategoryNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found") from exc
    except DuplicateCategoryNameError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Category name already exists"
        ) from exc

    await db.commit()
    return CategoryResponse.from_entity(category)


@router.delete("/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    public_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: DELETE /categories/{public_id} — remove categoria privada
    do próprio usuário. Retorna 409 se houver transações associadas
    (build-context-03, FK `ON DELETE RESTRICT`).
    """
    use_case = DeleteCategoryUseCase(
        category_repository=SqlAlchemyCategoryRepository(db), job_enqueuer=arq_pool
    )
    try:
        await use_case.execute(
            DeleteCategoryInput(user_id=current_user.id, public_id=_parse_public_id(public_id))
        )
    except CategoryNotEditableError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Category is read-only") from exc
    except CategoryNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found") from exc
    except CategoryInUseError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Category has transactions and cannot be deleted"
        ) from exc

    await db.commit()
