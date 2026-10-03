import uuid
from dataclasses import dataclass

from src.application.shared.ports import JobEnqueuer
from src.domain.user.entities import User
from src.domain.user.exceptions import UserNotFoundError
from src.domain.user.ports import PhoneHasherPort
from src.domain.user.repository import UserRepository
from src.domain.user.value_objects import Language


@dataclass
class UpdateProfileInput:
    user_id: uuid.UUID
    name: str | None = None
    phone: str | None = None
    language: str | None = None


class UpdateProfileUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Atualiza campos parciais do próprio perfil (name/phone/
    language). `phone` é criptografado automaticamente na persistência
    pelo `EncryptedString` do model — o use case só lida com texto puro
    (RN-05). Sempre que `phone` é definido/alterado, calcula também
    `phone_hash` (build-context-07 §2.2) via `PhoneHasherPort`, para o
    Bot WhatsApp conseguir localizar o usuário pelo número recebido no
    webhook sem decifrar `phone`. Quando `phone` muda de valor (vínculo
    novo ou troca de número), enfileira o envio de uma mensagem de
    boas-vindas pelo WhatsApp (`send_whatsapp_welcome_message`, pedido
    do usuário em 2026-08-16) — nunca de forma síncrona, para o
    salvamento do perfil não depender da Evolution API responder.
    """

    def __init__(
        self, user_repository: UserRepository, phone_hasher: PhoneHasherPort, job_enqueuer: JobEnqueuer
    ) -> None:
        self._user_repository = user_repository
        self._phone_hasher = phone_hasher
        self._job_enqueuer = job_enqueuer

    async def execute(self, data: UpdateProfileInput) -> User:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Aplica só os campos informados (None = "não alterar")
        e persiste — atualização parcial, não substitui o perfil inteiro.
        `phone_changed` é calculado antes de sobrescrever `user.phone`,
        comparando o valor novo com o que já estava salvo — troca por um
        número diferente ou vínculo pela 1ª vez (de `None`) contam como
        mudança; salvar o mesmo número de novo não reenvia a mensagem.
        """
        user = await self._user_repository.get_by_id(data.user_id)
        if user is None:
            raise UserNotFoundError()

        phone_changed = data.phone is not None and data.phone != user.phone

        if data.name is not None:
            user.name = data.name
        if data.phone is not None:
            user.phone = data.phone
            user.phone_hash = self._phone_hasher.hash(data.phone)
        if data.language is not None:
            user.language = Language(data.language)

        updated_user = await self._user_repository.update(user)

        if phone_changed:
            await self._job_enqueuer.enqueue_job(
                "send_whatsapp_welcome_message", str(updated_user.id)
            )

        return updated_user
