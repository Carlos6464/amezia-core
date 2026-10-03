import httpx
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from src.infrastructure.config import get_settings

_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


class GoogleOAuthClient:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Dois jeitos de resolver a identidade do usuário no Google,
    ambos retornando o mesmo formato de payload (`sub`/`email`/`name`):
    `verify_id_token` (Google Identity Services, o frontend já verificou
    localmente e manda o JWT pronto) e `exchange_code` (fluxo de
    redirect/popup OAuth2 clássico — o frontend só manda o `code` que o
    Google devolveu, este client troca por um access_token e busca o
    perfil). GOOGLE_OAUTH_CLIENT_ID/SECRET usados nos dois.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    def verify_id_token(self, id_token_value: str) -> dict | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Valida assinatura, expiração e `aud` (audience) do
        id_token contra as chaves públicas do Google. Retorna None (sem
        levantar exceção) se `GOOGLE_OAUTH_CLIENT_ID` não estiver
        configurado ou o token for inválido/adulterado/expirado.
        """
        if not self._settings.GOOGLE_OAUTH_CLIENT_ID:
            return None
        try:
            return google_id_token.verify_oauth2_token(
                id_token_value,
                google_requests.Request(),
                self._settings.GOOGLE_OAUTH_CLIENT_ID,
            )
        except ValueError:
            return None

    async def exchange_code(self, code: str) -> dict | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Troca o authorization code (recebido no callback do
        redirect OAuth2, `GET /auth/google/callback?code=...`) por um
        access_token junto ao Google, depois busca o perfil mínimo do
        usuário autenticado (`id`/`email`/`name`). Normaliza a chave
        `id` do endpoint de userinfo para `sub`, pro mesmo formato que
        `verify_id_token` já retorna — quem consome (LoginWithGoogleUseCase)
        não precisa saber qual dos dois caminhos foi usado. Retorna None
        (sem levantar exceção) em qualquer falha de rede/credencial, pro
        chamador tratar como "login inválido" de forma uniforme.
        """
        if (
            not self._settings.GOOGLE_OAUTH_CLIENT_ID
            or not self._settings.GOOGLE_OAUTH_CLIENT_SECRET
        ):
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                token_response = await client.post(
                    _GOOGLE_TOKEN_URL,
                    data={
                        "code": code,
                        "client_id": self._settings.GOOGLE_OAUTH_CLIENT_ID,
                        "client_secret": self._settings.GOOGLE_OAUTH_CLIENT_SECRET,
                        "redirect_uri": self._settings.GOOGLE_OAUTH_REDIRECT_URI,
                        "grant_type": "authorization_code",
                    },
                )
                token_response.raise_for_status()
                access_token = token_response.json()["access_token"]

                userinfo_response = await client.get(
                    _GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                userinfo_response.raise_for_status()
                payload = userinfo_response.json()
        except (httpx.HTTPError, KeyError):
            return None

        return {
            "sub": payload["id"],
            "email": payload["email"],
            "name": payload.get("name"),
        }
