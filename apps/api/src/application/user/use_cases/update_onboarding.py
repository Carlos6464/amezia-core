import uuid
from dataclasses import dataclass

from src.domain.user.entities import User
from src.domain.user.exceptions import UserNotFoundError
from src.domain.user.repository import UserRepository


@dataclass
class UpdateOnboardingInput:
    user_id: uuid.UUID
    onboarding_completed: bool


class UpdateOnboardingUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: Marca (ou desmarca, via "reiniciar tour") o onboarding do
    usuário como concluído — separado de `UpdateProfileUseCase` porque é
    um estado de produto (progresso do tour guiado), não um dado de
    perfil editável pelo usuário num formulário.
    """

    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def execute(self, input_data: UpdateOnboardingInput) -> User:
        """
        Autor: Carlos Adriano
        Data: 2026-08-16
        Descrição: Busca o usuário, atualiza a flag e persiste.
        """
        user = await self._user_repository.get_by_id(input_data.user_id)
        if user is None:
            raise UserNotFoundError("User not found")

        user.onboarding_completed = input_data.onboarding_completed
        return await self._user_repository.update(user)
