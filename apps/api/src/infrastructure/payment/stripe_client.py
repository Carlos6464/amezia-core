from decimal import Decimal
from typing import Any

import stripe

from src.domain.subscription.exceptions import InvalidStripeWebhookSignatureError
from src.infrastructure.config import get_settings


def _json_safe(value: Any) -> Any:
    """
    Autor: Carlos Adriano
    Data: 2026-09-11
    Descrição: Normaliza recursivamente valores `Decimal` (achado real,
    2026-09-11: `stripe.Event.to_dict()` do `stripe-python` 15.x traz
    alguns campos numéricos como `Decimal`, ex. `tax` de
    `customer.subscription.updated`) pra `float` antes de o evento
    virar `raw_payload` (`payment_events`, coluna `JSONB`) —
    `json.dumps` não serializa `Decimal` por padrão, e sem isso o
    webhook falha com `500` ao tentar auditar o evento, mesmo já tendo
    processado a assinatura com sucesso. Só afeta a cópia de auditoria
    (`raw_payload` é só para consulta/depuração, nunca fonte de
    verdade de valor monetário — isso é sempre `plan_prices`/Stripe).
    """
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


class StripeGateway:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Implementação de `PaymentGatewayPort` via SDK oficial
    `stripe` (build-context-09 §2.1/T5) — único adapter de cobrança do
    projeto. A `api_key` é passada explicitamente em cada chamada (em
    vez de mutar `stripe.api_key` global no construtor), porque esta
    classe é instanciada por requisição — mutar estado global do
    módulo a cada request é uma fonte real de corrida num servidor
    assíncrono, mesmo com uma única chave por ambiente.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.STRIPE_SECRET_KEY
        self._webhook_secret = settings.STRIPE_WEBHOOK_SECRET

    async def create_customer(self, email: str, name: str) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Cria um Customer no Stripe — chamado por
        `StartCheckoutUseCase` só quando a Subscription ainda não tem
        `stripe_customer_id` (1º checkout do usuário).
        """
        customer = await stripe.Customer.create_async(
            email=email, name=name, api_key=self._api_key
        )
        return customer.id

    async def create_product(self, name: str, description: str | None = None) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Cria um Produto no Stripe (build-context-09,
        catálogo dinâmico de preços) — chamado por
        `CreateOrUpdatePlanPriceUseCase` (Admin) só na 1ª vez que um
        preço é cadastrado pra um plano; produtos existentes são
        reaproveitados via `plan_limits.stripe_product_id`.
        """
        product = await stripe.Product.create_async(
            name=name, description=description, api_key=self._api_key
        )
        return product.id

    async def create_price(
        self, *, product_id: str, unit_amount_cents: int, currency: str, interval: str
    ) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Cria um Price recorrente vinculado a um Produto —
        a API do Stripe não permite editar `unit_amount`/`currency`/
        `recurring` de um Price já existente (só `active`/`metadata`/
        `nickname`/`lookup_key`), então toda "edição de preço" no
        Admin passa por aqui (Price novo) + `archive_price` (Price
        antigo), nunca por uma atualização in-place.
        """
        price = await stripe.Price.create_async(
            product=product_id,
            unit_amount=unit_amount_cents,
            currency=currency,
            recurring={"interval": interval},
            api_key=self._api_key,
        )
        return price.id

    async def archive_price(self, stripe_price_id: str) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: `active=false` — o Price para de aceitar assinatura
        nova, mas assinaturas já ativas nele continuam cobrando o
        mesmo valor até serem migradas explicitamente.
        """
        await stripe.Price.modify_async(stripe_price_id, active=False, api_key=self._api_key)

    async def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        trial_period_days: int,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Cria uma Checkout Session em modo assinatura
        (build-context-09 §2.5 passo 1) — Stripe hospeda o formulário
        de pagamento, o Amezia nunca coleta dado de cartão.
        """
        session = await stripe.checkout.Session.create_async(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            subscription_data={"trial_period_days": trial_period_days},
            success_url=success_url,
            cancel_url=cancel_url,
            api_key=self._api_key,
        )
        return session.url

    async def modify_subscription(
        self, stripe_subscription_id: str, price_id: str
    ) -> dict[str, Any]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Troca o preço de uma assinatura já ativa
        (upgrade/downgrade, build-context-09 §2.5 passo 2) — chamada
        direta à API, sem Checkout Session (a Stripe não tem "modo de
        troca" dentro de uma Checkout Session; o cartão já está salvo,
        não precisa reabrir formulário de pagamento). `proration_behavior
        = "create_prorations"` deixa a Stripe calcular a proration —
        nunca calculada manualmente aqui.
        """
        subscription = await stripe.Subscription.retrieve_async(
            stripe_subscription_id, api_key=self._api_key
        )
        item_id = subscription["items"]["data"][0]["id"]
        updated = await stripe.Subscription.modify_async(
            stripe_subscription_id,
            items=[{"id": item_id, "price": price_id}],
            proration_behavior="create_prorations",
            api_key=self._api_key,
        )
        return dict(updated)

    async def create_billing_portal_session(self, customer_id: str, return_url: str) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Cria uma sessão do Stripe Customer Portal
        (build-context-09 §2.5 passo 3) — cancelamento, troca de
        cartão e histórico de fatura acontecem dentro do Stripe, nunca
        em tela própria do Amezia.
        """
        session = await stripe.billing_portal.Session.create_async(
            customer=customer_id, return_url=return_url, api_key=self._api_key
        )
        return session.url

    def construct_webhook_event(self, payload: bytes, sig_header: str) -> dict[str, Any]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Valida a assinatura `Stripe-Signature` do webhook
        (build-context-09 §2.5 passo 5) e devolve o evento decodificado
        — síncrono (validação criptográfica local, sem chamada de
        rede). Traduz a exceção do SDK numa exceção de domínio, para o
        router/use case nunca importar `stripe` diretamente. `event.
        to_dict()` (não `dict(event)`, achado real em 2026-09-11) —
        a partir do `stripe-python` v15 (instalada: 15.6.1), `Event`
        não implementa mais o protocolo de mapeamento/iterável que
        `dict()` precisa (`TypeError: Event is not iterable or a
        mapping`); `to_dict()` é o jeito suportado de virar dict puro,
        recursivo (aninhados como `data.object` também viram dict).
        """
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, self._webhook_secret)
        except (ValueError, stripe.SignatureVerificationError) as exc:
            raise InvalidStripeWebhookSignatureError(str(exc)) from exc
        return _json_safe(event.to_dict())
