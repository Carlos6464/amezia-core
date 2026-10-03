from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.evolution.use_cases.connect_evolution_instance import (
    ConnectEvolutionInstanceUseCase,
)
from src.application.evolution.use_cases.create_evolution_instance import (
    CreateEvolutionInstanceInput,
    CreateEvolutionInstanceUseCase,
)
from src.application.evolution.use_cases.delete_evolution_instance import (
    DeleteEvolutionInstanceUseCase,
)
from src.application.evolution.use_cases.disconnect_evolution_instance import (
    DisconnectEvolutionInstanceUseCase,
)
from src.application.evolution.use_cases.get_evolution_instance import GetEvolutionInstanceUseCase
from src.application.evolution.use_cases.list_evolution_instances import (
    ListEvolutionInstancesUseCase,
)
from src.application.evolution.use_cases.sync_evolution_instance import (
    SyncEvolutionInstanceUseCase,
)
from src.application.evolution.use_cases.update_evolution_instance import (
    UpdateEvolutionInstanceInput,
    UpdateEvolutionInstanceUseCase,
)
from src.domain.evolution.exceptions import (
    DuplicateEvolutionInstanceNameError,
    EvolutionInstanceNotFoundError,
)
from src.domain.shared.value_objects import PublicId
from src.domain.user.entities import User
from src.infrastructure.config import get_settings
from src.infrastructure.database.repositories.sqlalchemy_evolution_instance_repository import (
    SqlAlchemyEvolutionInstanceRepository,
)
from src.infrastructure.database.session import get_db
from src.infrastructure.whatsapp.evolution_client import (
    EvolutionApiClient,
    EvolutionApiError,
    get_evolution_api_client,
)
from src.presentation.api.v1.admin.schemas import (
    EvolutionInstanceCreateRequest,
    EvolutionInstanceResponse,
    EvolutionInstanceUpdateRequest,
    PaginatedResponse,
)
from src.presentation.api.v1.dependencies.auth import get_current_admin_user

router = APIRouter(prefix="/admin/evolution-instances", tags=["admin"])


def _parse_instance_public_id(raw: str) -> PublicId:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Faz o parse do public_id de instância vindo da URL. Um
    ULID malformado é tratado como "não encontrado" (404), mesmo padrão
    de `_parse_transaction_public_id`.
    """
    try:
        return PublicId(raw)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evolution instance not found") from exc


@router.post("", response_model=EvolutionInstanceResponse, status_code=status.HTTP_201_CREATED)
async def create_evolution_instance(
    payload: EvolutionInstanceCreateRequest,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    evolution_client: EvolutionApiClient = Depends(get_evolution_api_client),
) -> EvolutionInstanceResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: POST /admin/evolution-instances — registra e cria a
    instância na Evolution API (build-context-06 §2.3).
    """
    repository = SqlAlchemyEvolutionInstanceRepository(db)
    use_case = CreateEvolutionInstanceUseCase(
        repository, evolution_client, SyncEvolutionInstanceUseCase(repository, evolution_client)
    )
    try:
        instance = await use_case.execute(
            CreateEvolutionInstanceInput(name=payload.name, webhook_url=payload.webhook_url)
        )
    except DuplicateEvolutionInstanceNameError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Instance name already in use") from exc
    except EvolutionApiError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    await db.commit()
    return EvolutionInstanceResponse.from_entity(instance)


@router.get("", response_model=PaginatedResponse[EvolutionInstanceResponse])
async def list_evolution_instances(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[EvolutionInstanceResponse]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: GET /admin/evolution-instances — listagem paginada.
    """
    use_case = ListEvolutionInstancesUseCase(SqlAlchemyEvolutionInstanceRepository(db))
    result = await use_case.execute(page, page_size)
    return PaginatedResponse.build(
        items=[EvolutionInstanceResponse.from_entity(item) for item in result.items],
        page=page,
        page_size=page_size,
        total=result.total,
    )


@router.get("/{public_id}", response_model=EvolutionInstanceResponse)
async def get_evolution_instance(
    public_id: str,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> EvolutionInstanceResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: GET /admin/evolution-instances/{public_id} — detalhe. As
    estatísticas de volume de mensagens (build-context-07, ainda não
    construído) não aparecem nesta resposta de propósito.
    """
    use_case = GetEvolutionInstanceUseCase(SqlAlchemyEvolutionInstanceRepository(db))
    try:
        instance = await use_case.execute(_parse_instance_public_id(public_id))
    except EvolutionInstanceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evolution instance not found") from exc
    return EvolutionInstanceResponse.from_entity(instance)


@router.patch("/{public_id}", response_model=EvolutionInstanceResponse)
async def update_evolution_instance(
    public_id: str,
    payload: EvolutionInstanceUpdateRequest,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    evolution_client: EvolutionApiClient = Depends(get_evolution_api_client),
) -> EvolutionInstanceResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: PATCH /admin/evolution-instances/{public_id} — atualiza
    name/webhook_url/is_active (build-context-06 §2.3).
    """
    use_case = UpdateEvolutionInstanceUseCase(
        SqlAlchemyEvolutionInstanceRepository(db), evolution_client
    )
    try:
        instance = await use_case.execute(
            UpdateEvolutionInstanceInput(
                public_id=_parse_instance_public_id(public_id),
                name=payload.name,
                webhook_url=payload.webhook_url,
                is_active=payload.is_active,
            )
        )
    except EvolutionInstanceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evolution instance not found") from exc
    except DuplicateEvolutionInstanceNameError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Instance name already in use") from exc
    except EvolutionApiError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    await db.commit()
    return EvolutionInstanceResponse.from_entity(instance)


@router.delete("/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evolution_instance(
    public_id: str,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    evolution_client: EvolutionApiClient = Depends(get_evolution_api_client),
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: DELETE /admin/evolution-instances/{public_id} — remove da
    Evolution API e do banco.
    """
    use_case = DeleteEvolutionInstanceUseCase(
        SqlAlchemyEvolutionInstanceRepository(db), evolution_client
    )
    try:
        await use_case.execute(_parse_instance_public_id(public_id))
    except EvolutionInstanceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evolution instance not found") from exc
    except EvolutionApiError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    await db.commit()


@router.post("/{public_id}/connect", response_model=EvolutionInstanceResponse)
async def connect_evolution_instance(
    public_id: str,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    evolution_client: EvolutionApiClient = Depends(get_evolution_api_client),
) -> EvolutionInstanceResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: POST /admin/evolution-instances/{public_id}/connect —
    inicia o pareamento, grava qr_code/qr_code_expires_at.
    """
    use_case = ConnectEvolutionInstanceUseCase(
        SqlAlchemyEvolutionInstanceRepository(db),
        evolution_client,
        get_settings().EVOLUTION_QR_CODE_TTL_SECONDS,
    )
    try:
        instance = await use_case.execute(_parse_instance_public_id(public_id))
    except EvolutionInstanceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evolution instance not found") from exc
    except EvolutionApiError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    await db.commit()
    return EvolutionInstanceResponse.from_entity(instance)


@router.post("/{public_id}/sync", response_model=EvolutionInstanceResponse)
async def sync_evolution_instance(
    public_id: str,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    evolution_client: EvolutionApiClient = Depends(get_evolution_api_client),
) -> EvolutionInstanceResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: POST /admin/evolution-instances/{public_id}/sync — refresh
    manual de status/phone_number/connected_at.
    """
    use_case = SyncEvolutionInstanceUseCase(
        SqlAlchemyEvolutionInstanceRepository(db), evolution_client
    )
    try:
        instance = await use_case.execute(_parse_instance_public_id(public_id))
    except EvolutionInstanceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evolution instance not found") from exc
    except EvolutionApiError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    await db.commit()
    return EvolutionInstanceResponse.from_entity(instance)


@router.post("/{public_id}/disconnect", response_model=EvolutionInstanceResponse)
async def disconnect_evolution_instance(
    public_id: str,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    evolution_client: EvolutionApiClient = Depends(get_evolution_api_client),
) -> EvolutionInstanceResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: POST /admin/evolution-instances/{public_id}/disconnect —
    logout da sessão pareada.
    """
    use_case = DisconnectEvolutionInstanceUseCase(
        SqlAlchemyEvolutionInstanceRepository(db), evolution_client
    )
    try:
        instance = await use_case.execute(_parse_instance_public_id(public_id))
    except EvolutionInstanceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evolution instance not found") from exc
    except EvolutionApiError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    await db.commit()
    return EvolutionInstanceResponse.from_entity(instance)
