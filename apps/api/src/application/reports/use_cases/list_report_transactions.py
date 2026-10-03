import uuid
from dataclasses import dataclass

from src.domain.category.exceptions import CategoryNotFoundError
from src.domain.category.repository import CategoryRepository
from src.domain.reports.repository import ReportsRepository
from src.domain.reports.value_objects import Page, PeriodRange, TransactionSummary
from src.domain.shared.value_objects import PublicId


@dataclass
class ListReportTransactionsInput:
    user_id: uuid.UUID
    period: PeriodRange
    category_public_id: PublicId | None
    page: int
    page_size: int
    payment_method: str | None = None


class ListReportTransactionsUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Tabela paginada de transações do intervalo — usada pela
    tela de Reports, pelo preview de 5 mais recentes do Dashboard
    (build-context-05 §2.4) e pelo modal "despesas por tipo de
    pagamento" do Dashboard (`payment_method`, 2026-09-15, fora de
    qualquer build-context — mesmo modal que já existia pra categoria,
    agora também filtrável por tipo de pagamento).
    """

    def __init__(
        self, reports_repository: ReportsRepository, category_repository: CategoryRepository
    ) -> None:
        self._reports_repository = reports_repository
        self._category_repository = category_repository

    async def execute(self, input_data: ListReportTransactionsInput) -> Page[TransactionSummary]:
        category_id = await self._resolve_category_id(
            input_data.user_id, input_data.category_public_id
        )
        return await self._reports_repository.get_transactions_page(
            input_data.user_id,
            input_data.period,
            category_id,
            input_data.page,
            input_data.page_size,
            payment_method=input_data.payment_method,
        )

    async def _resolve_category_id(
        self, user_id: uuid.UUID, category_public_id: PublicId | None
    ) -> int | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Resolve o `public_id` de categoria opcional recebido
        do cliente para o id interno — global ou pertencente ao usuário
        autenticado, mesmo padrão de
        `CreateTransactionUseCase._resolve_category` (RN-01:
        `CategoryNotFoundError` tanto para inexistente quanto para
        categoria privada de outro usuário, sem distinção).
        """
        if category_public_id is None:
            return None
        category = await self._category_repository.get_by_public_id(category_public_id)
        if category is None or (not category.is_global and category.user_id != user_id):
            raise CategoryNotFoundError(str(category_public_id))
        return category.id
