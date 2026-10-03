import uuid
from dataclasses import dataclass

from src.domain.user.exceptions import InvalidOrExpiredTokenError
from src.domain.user.repository import UserRepository
from src.infrastructure.security.jwt_service import JwtService


@dataclass
class RefreshTokenInput:
    refresh_token: str


class RefreshTokenUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Emite um novo access_token a partir de um refresh_token
    válido (assinatura + type == "refresh" + expiração). Consulta o
    usuário só para montar os claims `role`/`language` do novo access
    token com o estado atual da conta (não existe claim de role/language
    no refresh token em si, por design — ver build-context-01 §2.6); não
    há tabela de refresh tokens nem qualquer estado de sessão persistido.
    """

    def __init__(self, user_repository: UserRepository, jwt_service: JwtService) -> None:
        self._user_repository = user_repository
        self._jwt_service = jwt_service

    async def execute(self, data: RefreshTokenInput) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Decodifica o refresh token, carrega o usuário atual e
        emite um novo access token com claims frescos.
        """
        payload = self._jwt_service.decode(data.refresh_token, "refresh")
        if payload is None:
            raise InvalidOrExpiredTokenError()

        user = await self._user_repository.get_by_id(uuid.UUID(payload["sub"]))
        if user is None:
            raise InvalidOrExpiredTokenError()

        return self._jwt_service.create_access_token(str(user.id), user.role, user.language.value)
