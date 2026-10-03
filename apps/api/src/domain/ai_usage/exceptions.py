class AiUsageLimitExceededError(Exception):
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Levantada por `CheckAiUsageLimitUseCase` quando o usuário
    já atingiu o limite mensal do plano para `agent_chat`/
    `report_narrative` (build-context-10 §2.5) — capturada na camada
    que fala com o usuário (job ARQ do chat/narrativa, ou o handler do
    bot) para virar um evento de falha (web) ou a mensagem fixa de
    upgrade do catálogo (WhatsApp), nunca um 500 genérico.
    """

    def __init__(self, feature: str) -> None:
        self.feature = feature
        super().__init__(f"AI usage limit exceeded for feature '{feature}'")
