class UnlinkedPhoneNumberError(Exception):
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Levantada pelo orquestrador (build-context-07 §2.6, passo
    3) quando o número que mandou a mensagem não corresponde a nenhum
    usuário cadastrado (`UserRepository.get_by_phone_hash` devolve
    None). Nenhuma `WhatsappSession` é criada nesse caso (RN-06).
    """
