import re
from dataclasses import dataclass
from enum import Enum

import phonenumbers

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class Email:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Value object de email — valida o formato no construtor,
    garantindo que nenhuma entidade User exista com email malformado.
    """

    value: str

    def __post_init__(self) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Valida o formato do email no momento da construção —
        qualquer código que tente criar um Email inválido falha na hora,
        não silenciosamente mais adiante.
        """
        if not _EMAIL_PATTERN.match(self.value):
            raise ValueError(f"Invalid email format: {self.value}")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Phone:
    """
    Autor: Carlos Adriano
    Data: 2026-08-19
    Descrição: Value object de telefone — exige código do país (`+`) e
    valida o número inteiro via `phonenumbers` (biblioteca da libphonenumber
    do Google) no construtor, garantindo que nenhum `User.phone` seja salvo
    incompleto (ex.: só o DDI, sem DDD/assinante) ou com um DDD/quantidade
    de dígitos incompatível com o país informado. `value` normaliza sempre
    para E.164 (`+5511999990001`), formato exigido pelo `phone_hash`
    (`infrastructure/security/phone_hasher.py`) para casar com o
    `remoteJid` recebido do webhook Evolution (build-context-07 §2.2).
    """

    value: str

    def __post_init__(self) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-19
        Descrição: Faz o parse do número exigindo o prefixo `+` (região
        `None` — não assume país default) e confere `is_valid_number`, que
        checa tamanho e faixa de DDD/assinante reais por país, não só
        contagem de dígitos. Normaliza `value` para E.164 já validado.
        """
        try:
            parsed = phonenumbers.parse(self.value, None)
        except phonenumbers.NumberParseException as exc:
            raise ValueError(f"Invalid phone number: {self.value}") from exc
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError(f"Invalid phone number: {self.value}")
        object.__setattr__(
            self, "value", phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        )

    def __str__(self) -> str:
        return self.value


class Language(str, Enum):
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Idioma de preferência do usuário (RN-10) — rege UI, bot
    WhatsApp e respostas de IA. Default do perfil é PT_BR.
    """

    PT_BR = "pt-BR"
    EN = "en"


class DashboardCard(str, Enum):
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: Conjunto fechado dos cards do Dashboard que o usuário
    pode mostrar/esconder e reordenar (pedido direto do usuário, fora de
    qualquer build-context) — Hero (Planejado vs Realizado) e os 4 cards
    de métrica pequenos ficam sempre fixos, de propósito, só os
    blocos de gráfico/lista maiores entram na personalização.
    """

    MONTHLY_TREND = "monthly_trend"
    CATEGORY_COMPOSITION = "category_composition"
    CATEGORY_DISTRIBUTION = "category_distribution"
    RECENT_TRANSACTIONS = "recent_transactions"
    PAYMENT_METHOD_DISTRIBUTION = "payment_method_distribution"
    PAID_PENDING = "paid_pending"


@dataclass(frozen=True)
class DashboardCardPreference:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: Um item do layout personalizado do Dashboard
    (`User.dashboard_layout`) — `visible` controla se o card aparece;
    a posição do item na lista é a ordem de exibição (não há campo de
    posição explícito, a ordem da própria lista já carrega essa
    informação, mesmo espírito de `CategoryDistributionItem` que já vem
    ordenado do backend em vez de carregar um índice).
    """

    card: DashboardCard
    visible: bool
