from dataclasses import dataclass

from src.domain.category.entities import Category
from src.domain.transaction.entities import RecurrenceRule, Transaction


@dataclass
class CategorySummary:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Resumo de categoria embutido na resposta de uma transação
    — só os campos que o cliente HTTP precisa (public_id/name/color),
    nunca o id interno (RN-01, não vaza identificador interno).
    """

    public_id: str
    name: str
    color: str

    @classmethod
    def from_entity(cls, category: Category) -> "CategorySummary":
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Constrói o resumo a partir da entidade de domínio
        Category (build-context-02).
        """
        return cls(public_id=str(category.public_id), name=category.name, color=category.color)


@dataclass
class TransactionWithCategory:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: DTO de saída dos use cases de transação — combina a
    entidade de domínio Transaction (que só guarda `category_id: int`)
    com o resumo da categoria associada, resolvido na application layer
    via CategoryRepository. Evita que o domínio de Transaction precise
    conhecer nome/cor de Category.
    """

    transaction: Transaction
    category: CategorySummary


@dataclass
class RecurrenceWithCategory:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: DTO de saída dos use cases de RecurrenceRule — mesmo
    padrão de TransactionWithCategory.
    """

    rule: RecurrenceRule
    category: CategorySummary
