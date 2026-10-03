import uuid

from src.domain.conversation.entities import ConversationMessage
from src.domain.conversation.ports import EmbeddingGeneratorPort
from src.domain.embedding.entities import Embedding, EmbeddingSourceType
from src.domain.embedding.repository import EmbeddingRepository


class IndexConversationMessageEmbeddingUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Indexa o embedding do conteúdo de uma ConversationMessage
    — mesma lógica de upsert de `IndexTransactionEmbeddingUseCase`,
    chamada pelo `GenerateAiResponseUseCase` para a mensagem do usuário e
    para a resposta gerada (build-context-04 §2.4, passo 8).
    """

    def __init__(
        self,
        embedding_repository: EmbeddingRepository,
        embedding_generator: EmbeddingGeneratorPort,
    ) -> None:
        self._embedding_repository = embedding_repository
        self._embedding_generator = embedding_generator

    async def execute(self, user_id: uuid.UUID, message: ConversationMessage) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: `message.id` já precisa estar preenchido (mensagem já
        persistida) — `source_id` é o id interno da ConversationMessage.
        """
        vector = await self._embedding_generator.generate(message.content)
        await self._embedding_repository.upsert(
            Embedding(
                user_id=user_id,
                source_type=EmbeddingSourceType.CONVERSATION_MESSAGE,
                source_id=message.id,
                content=message.content,
                embedding=vector,
            )
        )
