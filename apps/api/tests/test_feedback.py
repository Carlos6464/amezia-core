import uuid
from collections.abc import Callable
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.feedback.use_cases.submit_feedback import (
    SubmitFeedbackInput,
    SubmitFeedbackUseCase,
)
from src.domain.feedback.exceptions import (
    EmptyFeedbackMessageError,
    FeedbackMessageTooLongError,
    InvalidNpsScoreError,
)
from src.domain.feedback.value_objects import FeedbackChannel, FeedbackType
from src.infrastructure.database.models.feedback import Feedback as FeedbackModel
from src.infrastructure.database.models.user import User as UserModel
from src.infrastructure.database.repositories.feedback_repository import (
    SqlAlchemyFeedbackRepository,
)
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def test_create_feedback_via_web_persists_with_web_channel(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """POST /feedback força channel=web e user_id do JWT, nunca do corpo."""
    _, token = await make_user()

    response = await client.post(
        "/api/v1/feedback",
        headers=auth_headers(token),
        json={
            "message": "Adorei o bot no WhatsApp!",
            "type": "praise",
            "nps_score": 9,
            "subject": "Bot excelente",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["channel"] == "web"
    assert body["type"] == "praise"
    assert body["nps_score"] == 9
    assert body["subject"] == "Bot excelente"
    assert body["message"] == "Adorei o bot no WhatsApp!"


async def test_create_feedback_via_web_defaults_type_to_other(
    client: AsyncClient, make_user: Callable[..., Any]
) -> None:
    """Sem `type` no payload, o use case aplica o default `other`."""
    _, token = await make_user()

    response = await client.post(
        "/api/v1/feedback", headers=auth_headers(token), json={"message": "Só isso mesmo"}
    )

    assert response.status_code == 201
    assert response.json()["type"] == "other"


async def test_submit_feedback_use_case_directly_persists_with_whatsapp_channel(
    db_session: AsyncSession, make_user: Callable[..., Any]
) -> None:
    """Simula o handler do modo Feedback do Bot WhatsApp — mesmo use case do canal web."""
    user, _ = await make_user()
    use_case = SubmitFeedbackUseCase(SqlAlchemyFeedbackRepository(db_session))

    feedback = await use_case.execute(
        SubmitFeedbackInput(
            user_id=user.id, channel=FeedbackChannel.WHATSAPP, message="Gostei muito do bot"
        )
    )

    assert feedback.channel == FeedbackChannel.WHATSAPP
    assert feedback.type == FeedbackType.OTHER
    assert feedback.nps_score is None
    assert feedback.subject is None


async def test_empty_message_raises_domain_exception() -> None:
    from src.domain.feedback.entities import Feedback

    with pytest.raises(EmptyFeedbackMessageError):
        Feedback(user_id=uuid.uuid4(), message="   ", channel=FeedbackChannel.WEB)


async def test_message_over_1000_chars_raises_domain_exception() -> None:
    from src.domain.feedback.entities import Feedback

    with pytest.raises(FeedbackMessageTooLongError):
        Feedback(user_id=uuid.uuid4(), message="x" * 1001, channel=FeedbackChannel.WEB)


async def test_nps_score_out_of_range_raises_domain_exception() -> None:
    from src.domain.feedback.entities import Feedback

    with pytest.raises(InvalidNpsScoreError):
        Feedback(user_id=uuid.uuid4(), message="ok", channel=FeedbackChannel.WEB, nps_score=11)


async def test_get_my_feedback_only_returns_own_feedback(
    client: AsyncClient, make_user: Callable[..., Any], db_session: AsyncSession
) -> None:
    """RN-01: GET /feedback/me nunca retorna feedback de outro usuário."""
    owner, owner_token = await make_user()
    other, _ = await make_user()

    db_session.add_all(
        [
            FeedbackModel(user_id=owner.id, message="Meu feedback", channel="web"),
            FeedbackModel(user_id=other.id, message="Feedback de outro usuário", channel="web"),
        ]
    )
    await db_session.flush()

    response = await client.get("/api/v1/feedback/me", headers=auth_headers(owner_token))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["message"] == "Meu feedback"


async def test_deleting_user_cascades_feedback(
    db_session: AsyncSession, make_user: Callable[..., Any]
) -> None:
    """RN-03: ON DELETE CASCADE em feedback.user_id."""
    user, _ = await make_user()

    feedback = FeedbackModel(user_id=user.id, message="Vai sumir", channel="web")
    db_session.add(feedback)
    await db_session.flush()

    await db_session.execute(delete(UserModel).where(UserModel.id == user.id))
    await db_session.flush()

    remaining = await db_session.execute(
        select(FeedbackModel).where(FeedbackModel.user_id == user.id)
    )
    assert remaining.scalar_one_or_none() is None
