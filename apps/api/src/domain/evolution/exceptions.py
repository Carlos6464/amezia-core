class EvolutionInstanceNotFoundError(Exception):
    pass


class DuplicateEvolutionInstanceNameError(Exception):
    pass


class EvolutionInstanceAlreadyExistsError(Exception):
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: A instância já existe do lado da Evolution API (`403`,
    "already in use"/"already exists") — diferente de
    `DuplicateEvolutionInstanceNameError` (duplicata no banco local do
    Amezia). `CreateEvolutionInstanceUseCase` captura para **vincular**
    à instância remota existente em vez de falhar — cenário comum
    quando a instância já foi criada/conectada direto na Evolution
    (ex.: pelo painel dela) antes de ser registrada aqui. Portado do
    projeto irmão (`/home/adriano/Documentos/projetos/Amezia`), 2026-08-16.
    """



class InvalidWebhookSignatureError(Exception):
    pass
