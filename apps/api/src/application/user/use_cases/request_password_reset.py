import hashlib
from dataclasses import dataclass

from src.domain.user.repository import UserRepository
from src.infrastructure.email.resend_client import ResendEmailClient
from src.infrastructure.security.jwt_service import JwtService


def password_fingerprint(password_hash: str) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Fingerprint (16 chars de um SHA-256) do password_hash atual
    — embutido no token de reset (claim pwd_fp) para simular "uso único"
    sem tabela de tokens: ao trocar a senha, o hash muda e qualquer token
    de reset emitido antes deixa de bater o fingerprint (build-context-01 §2.6).
    """
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


@dataclass
class RequestPasswordResetInput:
    email: str


class RequestPasswordResetUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Sempre responde como sucesso (o router retorna 200 mesmo
    aqui não fazendo nada) — não revela se o email existe nem se a conta é
    só-OAuth (sem senha pra resetar). Só dispara o email via Resend quando
    existe conta local de fato.
    """

    def __init__(
        self,
        user_repository: UserRepository,
        jwt_service: JwtService,
        email_client: ResendEmailClient,
    ) -> None:
        self._user_repository = user_repository
        self._jwt_service = jwt_service
        self._email_client = email_client

    async def execute(self, data: RequestPasswordResetInput) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Se existir conta local com esse email, gera o token de
        reset e dispara o email; caso contrário não faz nada — em ambos os
        casos o router responde 200 (anti-enumeração de email).
        """
        user = await self._user_repository.get_by_email(data.email)
        if user is None or user.password_hash is None:
            return

        token = self._jwt_service.create_password_reset_token(
            str(user.id), password_fingerprint(user.password_hash)
        )
        await self._email_client.send_password_reset_email(
            str(user.email), token, user.language.value
        )
