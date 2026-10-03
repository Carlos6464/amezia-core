from dataclasses import dataclass
from datetime import date

from src.domain.reports.exceptions import InvalidPeriodRangeError
from src.domain.transaction.value_objects import Money, Period


@dataclass(frozen=True)
class PeriodRange:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Intervalo de meses usado pelos agregados de Relatórios —
    reaproveita o VO `Period` (mês/ano) de `domain/transaction/value_objects.py`
    (Shared Kernel entre os bounded contexts Transações e Relatórios,
    build-context-05 §2.2) em vez de guardar datas soltas. `start`/`end`
    são sempre meses cheios: o range de dias efetivo é do 1º dia do mês
    de `start` ao último dia do mês de `end`.
    """

    start: Period
    end: Period

    def __post_init__(self) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Valida que `start` não é posterior a `end` — comparado
        pelo início de cada mês, já que `Period` não define ordenação
        própria.
        """
        if self.start.date_range()[0] > self.end.date_range()[0]:
            raise InvalidPeriodRangeError(f"start {self.start} is after end {self.end}")

    def date_range(self) -> tuple[date, date]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Intervalo [primeiro_dia_de_start, último_dia_de_end] —
        usado por `SqlAlchemyReportsRepository` para filtrar
        `transactions.date BETWEEN ...`.
        """
        return self.start.date_range()[0], self.end.date_range()[1]


@dataclass(frozen=True)
class CategorySummary:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Categoria com maior gasto de um período — usado como
    `FinancialSummary.top_category`. `total` é centavos (`int`), não
    `Money`: `Money.__post_init__` (domain/transaction/value_objects.py)
    rejeita valores <= 0, correto para o valor de uma transação real mas
    incompatível com um agregado que pode ser zero — mesma razão pela
    qual `monthly_budget_cents`/`_to_cents` (build-context-03,
    `transactions/router.py`) já contornam `Money` para o teto mensal.
    """

    category_id: str
    category_name: str
    total: int
    percentage: float


@dataclass(frozen=True)
class TransactionSummary:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Projeção de leitura de uma transação para os relatórios
    (tabela paginada, export CSV, "maior despesa" do resumo). `amount` é
    `Money` de verdade aqui — ao contrário dos agregados desta VO, este
    valor sempre espelha uma transação real já persistida (`amount_cents
    > 0`, invariante garantida na criação, build-context-03). `description`
    já vem descriptografada pelo repositório (RN-05, `EncryptedString` é
    transparente no ORM).
    """

    public_id: str
    occurred_at: date
    description: str
    category_id: str
    category_name: str
    amount: Money


@dataclass(frozen=True)
class FinancialSummary:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Resumo financeiro de um período — total em centavos
    (`int`, mesma razão de `CategorySummary.total` acima: incompatível
    com o VO `Money`, que rejeita zero). Só despesa: o produto é
    expense-only (pedido do usuário, 2026-08-14) — sem `total_income`/
    `balance`, que só faziam sentido com receita.
    """

    period: PeriodRange
    total_expense: int
    transaction_count: int
    top_category: CategorySummary | None
    biggest_transaction: TransactionSummary | None


@dataclass(frozen=True)
class MonthlyEvolutionPoint:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Um ponto do gráfico de linha (evolução mensal) — um mês,
    total de despesas em centavos.
    """

    period: Period
    total_expense: int


@dataclass(frozen=True)
class CategoryDistributionItem:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Uma fatia da distribuição por categoria (donut do
    Dashboard, ranking completo do Reports) — `color` reaproveita a cor
    já cadastrada na categoria (build-context-02).
    """

    category_id: str
    category_name: str
    color: str
    total: int
    percentage: float


@dataclass(frozen=True)
class PaymentMethodDistributionItem:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: Uma fatia da distribuição por tipo de pagamento (lista
    lateral com % no Dashboard/Reports, pedido direto do usuário, fora
    de qualquer build-context) — `payment_method` é o valor bruto salvo
    em `Transaction.payment_method` (`str | None`, texto livre, sem
    enum no domínio — só o frontend usa um catálogo fixo de sugestões,
    `payment-method-select.component.ts`). `None` vira `"not_informed"`
    aqui (nunca chega `None` de verdade até o schema HTTP) — transações
    sem tipo de pagamento preenchido ainda contam pro total do período,
    agrupadas numa fatia própria, em vez de desaparecerem da soma.
    """

    payment_method: str
    total: int
    percentage: float


@dataclass(frozen=True)
class MonthlyPaidPendingPoint:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: Um ponto do gráfico de barra dupla "Pago x Pendente" por
    mês (pedido direto do usuário, fora de qualquer build-context) —
    mesmo recorte de `MonthlyEvolutionPoint` (mês corrido, ordem
    cronológica), mas com a soma quebrada por `PaymentStatus` em vez de
    um total único. `status` é enum de verdade, não criptografado
    (diferente de `payment_method`), então a soma continua inteiramente
    em SQL.
    """

    period: Period
    total_paid: int
    total_pending: int


@dataclass(frozen=True)
class Page[T]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: VO genérico de página — usado por
    `ReportsRepository.get_transactions_page` (build-context-05 §2.3).
    """

    items: list[T]
    page: int
    page_size: int
    total: int
    total_pages: int
