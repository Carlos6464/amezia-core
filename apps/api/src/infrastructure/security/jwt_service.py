from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from jose import JWTError, jwt

from src.infrastructure.config import get_settings

ALGORITHM = "HS256"

TokenType = Literal["access", "refresh", "password_reset", "report_view"]


class JwtService:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Encode/decode de JWT HS256 stateless (RN-08) — access,
    refresh e password_reset são todos JWT assinados com o mesmo
    JWT_SECRET, distinguidos pelo claim `type`. Nenhum é persistido em
    banco: refresh e reset são validados só pela assinatura/expiração
    (ver build-context-01 §2.6 para o fingerprint de senha do reset).
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    def create_access_token(self, user_id: str, role: str, language: str) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Emite o access token (TTL curto, claims sub/role/
        language/type). Usado após login/registro/refresh.
        """
        expires_delta = timedelta(minutes=self._settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        return self._encode(
            {"sub": user_id, "role": role, "language": language, "type": "access"}, expires_delta
        )

    def create_refresh_token(self, user_id: str) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Emite o refresh token (TTL longo, só sub+type) —
        guardado pelo router num cookie HttpOnly, nunca no corpo da
        resposta.
        """
        expires_delta = timedelta(days=self._settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        return self._encode({"sub": user_id, "type": "refresh"}, expires_delta)

    def create_password_reset_token(self, user_id: str, password_fingerprint: str) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Emite o token de reset de senha, com o fingerprint do
        password_hash atual embutido (`pwd_fp`) para invalidar o token
        automaticamente assim que a senha é trocada (build-context-01 §2.6).
        """
        expires_delta = timedelta(minutes=self._settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
        return self._encode(
            {"sub": user_id, "type": "password_reset", "pwd_fp": password_fingerprint},
            expires_delta,
        )

    def create_report_view_token(self, user_id: str) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-18
        Descrição: Emite o token de "link mágico" do relatório enviado
        pelo bot do WhatsApp (modo Relatório) — TTL curto, só sub+type,
        sem persistir nada em banco (mesmo espírito stateless de
        refresh/password_reset). Aceito só pelos 5 endpoints de leitura
        de `/reports` (`get_current_user_for_reports`), nunca pelo resto
        da API — `/reports/narrative` e qualquer outro endpoint exigem
        `type: "access"` estrito, então esse token nunca aciona geração
        de IA nem qualquer ação fora de visualizar relatórios.
        """
        expires_delta = timedelta(minutes=self._settings.REPORT_VIEW_TOKEN_EXPIRE_MINUTES)
        return self._encode({"sub": user_id, "type": "report_view"}, expires_delta)

    def decode(self, token: str, expected_type: TokenType) -> dict[str, Any] | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Decodifica e valida um JWT — assinatura, expiração e o
        claim `type` batendo com `expected_type`. Retorna None (nunca
        levanta exceção) para qualquer token inválido, ausente ou do tipo
        errado, deixando quem chama decidir o tratamento (401, etc.).
        """
        try:
            payload = jwt.decode(token, self._settings.JWT_SECRET, algorithms=[ALGORITHM])
        except JWTError:
            return None
        if payload.get("type") != expected_type:
            return None
        return payload

    def _encode(self, claims: dict[str, Any], expires_delta: timedelta) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Assina os claims com JWT_SECRET (HS256), adicionando o
        claim `exp` calculado a partir de `expires_delta`.
        """
        payload = {**claims, "exp": datetime.now(UTC) + expires_delta}
        return jwt.encode(payload, self._settings.JWT_SECRET, algorithm=ALGORITHM)
