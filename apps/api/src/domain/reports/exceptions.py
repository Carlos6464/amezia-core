class InvalidPeriodRangeError(Exception):
    pass


class ReportsThrottleExceededError(Exception):
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Levantada quando o usuário excede o limite de 10 gerações
    de narrativa por minuto (build-context-05 §2.7). `retry_after_seconds`
    é o tempo restante da janela Redis atual, usado pelo router para
    montar o header `Retry-After` do 429.
    """

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__("AI narrative throttle exceeded")
