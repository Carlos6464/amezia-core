from typing import Any, Protocol


class PaymentGatewayPort(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Porta de domínio para o gateway de cobrança
    (build-context-09 §2.1) — implementada por `StripeGateway`
    (infrastructure/payment/stripe_client.py). Nenhum use case importa
    o SDK `stripe` diretamente (regra de dependência do Clean
    Architecture, PRD §5) — a Stripe é a única implementação prevista,
    mas os use cases só conhecem este contrato.
    """

    async def create_customer(self, email: str, name: str) -> str:
        """Cria um Customer no Stripe e devolve o `stripe_customer_id`."""
        ...

    async def create_product(self, name: str, description: str | None = None) -> str:
        """Cria um Produto (plano) no Stripe e devolve o `stripe_product_id`. Usado pelo Admin, não em runtime de checkout."""
        ...

    async def create_price(
        self, *, product_id: str, unit_amount_cents: int, currency: str, interval: str
    ) -> str:
        """
        Cria um Price recorrente vinculado a um Produto e devolve o
        `stripe_price_id`. Um Price é imutável em valor — trocar o preço
        de um plano sempre passa por aqui (Price novo) + `archive_price`
        (Price antigo), nunca por uma edição in-place.
        """
        ...

    async def archive_price(self, stripe_price_id: str) -> None:
        """Marca um Price como `active=false` no Stripe — para de aceitar assinatura nova, mas não afeta quem já está nele."""
        ...

    async def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        trial_period_days: int,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """Cria uma Checkout Session (modo assinatura) e devolve a URL de pagamento."""
        ...

    async def modify_subscription(self, stripe_subscription_id: str, price_id: str) -> dict[str, Any]:
        """Troca o preço de uma assinatura já ativa (upgrade/downgrade), com proration automática."""
        ...

    async def create_billing_portal_session(self, customer_id: str, return_url: str) -> str:
        """Cria uma sessão do Stripe Customer Portal e devolve a URL."""
        ...

    def construct_webhook_event(self, payload: bytes, sig_header: str) -> dict[str, Any]:
        """Valida a assinatura `Stripe-Signature` e devolve o evento decodificado."""
        ...
