import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.user.entities import User
from src.infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from src.infrastructure.database.session import get_db
from src.infrastructure.security.jwt_service import JwtService

_bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Dependency global — decodifica o access token do header
    Authorization e carrega o usuário correspondente. Base do isolamento
    por user_id (RN-01) em todos os módulos a partir daqui: o user_id nunca
    vem do client, sempre do JWT.
    """
    jwt_service = JwtService()
    payload = jwt_service.decode(credentials.credentials, "access")
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )

    repository = SqlAlchemyUserRepository(db)
    user = await repository.get_by_id(uuid.UUID(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_current_user_or_report_viewer(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Autor: Carlos Adriano
    Data: 2026-08-18
    Descrição: Variante de `get_current_user` usada pelos endpoints de
    leitura que a tela de Relatórios compartilhada (`/reports/shared`,
    link mágico do bot) precisa pra funcionar de verdade "com filtro e
    tudo" — os 5 GETs de `/reports` e `GET /categories` (popula o
    dropdown de filtro por categoria). Aceita tanto o access token
    normal quanto o `report_view` do link mágico, pra a mesma tela
    funcionar tanto logado no app quanto aberta a partir do WhatsApp
    sem login. Tenta "access" primeiro (caso mais comum, usuário logado
    no app) e só decodifica de novo como "report_view" se o primeiro
    falhar — nunca aceita nenhum outro tipo. Deliberadamente **não**
    usada em endpoints de escrita nem em `/reports/narrative` (único
    POST do módulo de Relatórios, continua com `get_current_user`
    estrito): um `report_view` nunca deve conseguir criar/editar/
    excluir nada, nem disparar geração de IA.
    """
    jwt_service = JwtService()
    payload = jwt_service.decode(credentials.credentials, "access") or jwt_service.decode(
        credentials.credentials, "report_view"
    )
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )

    repository = SqlAlchemyUserRepository(db)
    user = await repository.get_by_id(uuid.UUID(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_current_admin_user(user: User = Depends(get_current_user)) -> User:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Dependency global — exige que o usuário autenticado tenha
    role "admin". Usada pelos endpoints do módulo Admin (build-context-06).
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )
    return user
