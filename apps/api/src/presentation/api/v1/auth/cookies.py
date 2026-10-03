from fastapi import Response

from src.infrastructure.config import get_settings

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth/refresh"


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Grava o cookie HttpOnly de refresh (build-context-01 §2.6).
    `secure` é condicionado a ENVIRONMENT=production — em dev o nginx serve
    em HTTP puro (localhost:8080) e um cookie Secure literal não seria
    enviado pelo browser, quebrando o refresh silencioso localmente.
    Extraído de `auth/router.py` em 2026-08-15 (build-context-06) para o
    login do admin (`admin/auth_router.py`) reaproveitar exatamente o
    mesmo cookie — painéis cliente e admin são telas separadas, mas uma
    sessão só (RN-08), então o mesmo nome/path de cookie precisa valer
    nos dois.
    """
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )


def clear_refresh_cookie(response: Response) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Remove o cookie de refresh (logout e exclusão de conta) —
    o `path` precisa bater exatamente com o usado em `set_refresh_cookie`
    para o browser reconhecer como o mesmo cookie.
    """
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
