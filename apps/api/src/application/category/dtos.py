from dataclasses import dataclass

from src.domain.category.entities import Category


@dataclass
class CategoryWithUsage:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Categoria + agregação de uso (quantidade de transações e
    total movimentado, em centavos) do usuário autenticado — "uso" não é
    propriedade da entidade Category em si (é derivado de `transactions`,
    outro bounded context), então fica numa DTO de aplicação, mesmo
    padrão de `TransactionWithCategory` (application/transaction/dtos.py).
    Categoria sem nenhuma transação tem `transaction_count=0`/
    `total_amount_cents=0`, não é omitida.
    """

    category: Category
    transaction_count: int
    total_amount_cents: int
