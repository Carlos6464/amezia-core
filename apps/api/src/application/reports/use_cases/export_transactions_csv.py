import csv
import io
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from src.domain.category.exceptions import CategoryNotFoundError
from src.domain.category.repository import CategoryRepository
from src.domain.reports.repository import ReportsRepository
from src.domain.reports.value_objects import PeriodRange, TransactionSummary
from src.domain.shared.value_objects import PublicId
from src.domain.user.value_objects import Language

_HEADERS = {
    Language.PT_BR: ["Data", "Descrição", "Categoria", "Valor"],
    Language.EN: ["Date", "Description", "Category", "Amount"],
}


def _format_date_pt_br(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _format_amount_pt_br(amount: Decimal) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Formata um valor monetário no padrão numérico pt-BR
    (decimal com vírgula, milhar com ponto) — fixo independente do
    idioma da UI, decisão deliberada do build-context-05 §2.6 (CSV é
    pensado para abrir no Excel PT-BR, convenção de planilha, não de
    produto — RN-10 não se aplica aqui).
    """
    sign = "-" if amount < 0 else ""
    integer_part, decimal_part = f"{abs(amount):.2f}".split(".")
    reversed_digits = integer_part[::-1]
    grouped = ".".join(reversed_digits[i : i + 3] for i in range(0, len(reversed_digits), 3))
    return f"{sign}{grouped[::-1]},{decimal_part}"


@dataclass
class ExportTransactionsCsvInput:
    user_id: uuid.UUID
    period: PeriodRange
    category_public_id: PublicId | None
    language: Language


class ExportTransactionsCsvUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Gera o CSV de exportação (build-context-05 §2.6) —
    separador `;`, formato numérico/data fixo em pt-BR, cabeçalho
    traduzido por `language`, BOM UTF-8. Síncrono: volume de dados é
    limitado (transações de um usuário, sem paginação no arquivo). Sem
    coluna "Tipo": produto é expense-only (2026-08-14), toda linha já é
    despesa.
    """

    def __init__(
        self, reports_repository: ReportsRepository, category_repository: CategoryRepository
    ) -> None:
        self._reports_repository = reports_repository
        self._category_repository = category_repository

    async def execute(self, input_data: ExportTransactionsCsvInput) -> bytes:
        category_id = await self._resolve_category_id(
            input_data.user_id, input_data.category_public_id
        )
        transactions = await self._reports_repository.get_transactions_for_export(
            input_data.user_id, input_data.period, category_id
        )
        return self._build_csv(transactions, input_data.language)

    def _build_csv(self, transactions: list[TransactionSummary], language: Language) -> bytes:
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Monta o conteúdo do CSV em memória — `csv.writer` com
        `delimiter=";"` já cuida do escape de campos com `;`/aspas/
        quebra de linha (RFC 4180). BOM UTF-8 prefixado para o Excel
        PT-BR reconhecer acentuação corretamente.
        """
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";")
        writer.writerow(_HEADERS[language])
        for transaction in transactions:
            writer.writerow(
                [
                    _format_date_pt_br(transaction.occurred_at),
                    transaction.description,
                    transaction.category_name,
                    _format_amount_pt_br(transaction.amount.to_decimal()),
                ]
            )
        return ("﻿" + buffer.getvalue()).encode("utf-8")

    async def _resolve_category_id(
        self, user_id: uuid.UUID, category_public_id: PublicId | None
    ) -> int | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Mesmo padrão de
        `ListReportTransactionsUseCase._resolve_category_id`.
        """
        if category_public_id is None:
            return None
        category = await self._category_repository.get_by_public_id(category_public_id)
        if category is None or (not category.is_global and category.user_id != user_id):
            raise CategoryNotFoundError(str(category_public_id))
        return category.id
