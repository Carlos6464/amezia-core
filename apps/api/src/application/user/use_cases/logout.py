class LogoutUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Logout sob JWT stateless (RN-08) — não existe blacklist de
    token em banco, então não há estado de servidor a invalidar aqui. A
    limpeza do cookie de refresh é responsabilidade do router (resposta
    HTTP); o access token em memória no frontend é só descartado lá.
    """

    async def execute(self) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: No-op proposital — não há estado de servidor a
        invalidar sob JWT stateless (RN-08).
        """
        return
