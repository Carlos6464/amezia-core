from dataclasses import dataclass

from src.domain.feedback.entities import Feedback
from src.domain.subscription.entities import Plan
from src.domain.user.entities import User


@dataclass
class FeedbackWithUser:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Feedback + resumo do usuário que o enviou (nome/email,
    exibidos na tela de Feedback do Admin) — `user` só é None se o
    usuário já não existir mais (não deveria acontecer em uso normal,
    já que a exclusão de conta faz cascade sobre `feedback`, RN-03).
    """

    feedback: Feedback
    user: User | None


@dataclass
class AdminUserRow:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: User + o plano efetivo (`Subscription.resolve_effective_plan()`)
    e se é uma conta de teste concedida pelo admin — usado pelas 3
    telas/ações de Usuários do Admin (listagem, detalhe, troca de papel,
    concessão/revogação de acesso de teste) pra sempre devolver o mesmo
    formato de resposta. `effective_plan`/`is_admin_test_access` ficam
    `None`/`False` só no caso (não deveria acontecer em uso normal) de
    o usuário não ter `Subscription` — toda conta ganha uma no cadastro.
    """

    user: User
    effective_plan: Plan | None
    is_admin_test_access: bool
