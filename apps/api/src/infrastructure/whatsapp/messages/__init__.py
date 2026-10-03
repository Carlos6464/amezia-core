from src.domain.user.value_objects import Language
from src.infrastructure.whatsapp.messages import en, pt_br

_CATALOGS: dict[Language, dict[str, str]] = {
    Language.PT_BR: pt_br.MESSAGES,
    Language.EN: en.MESSAGES,
}


def get_message(key: str, language: Language, **kwargs: object) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Resolve uma chave do catálogo de mensagens do bot no
    idioma do usuário (RN-10, build-context-07 §2.7) — Transloco é uma
    ferramenta de frontend, este é o catálogo próprio de backend para o
    texto que o bot manda pelo WhatsApp. `**kwargs` preenche placeholders
    (`str.format`) como `expense.confirmation`.
    """
    template = _CATALOGS[language][key]
    return template.format(**kwargs) if kwargs else template


def render_menu(language: Language) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Monta o texto completo do Menu (título + opções) — usado
    por `ResetToMenuUseCase` e por `HandleMenuStateUseCase` (opção
    inválida), para as duas rotas nunca divergirem no texto exibido.
    """
    return f"{get_message('menu.title', language)}\n\n{get_message('menu.options', language)}"


class MessageCatalog:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Implementação de `MessageCatalogPort` (domain/whatsapp_bot/ports.py)
    — wrapper fino sobre `get_message()`/`render_menu()`, injetado nos
    use cases do Bot WhatsApp para a application layer nunca importar
    infrastructure/ diretamente.
    """

    def get_message(self, key: str, language: Language, **kwargs: object) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Delega para `get_message()` — existe só para
        satisfazer `MessageCatalogPort` sem a application layer importar
        este módulo diretamente.
        """
        return get_message(key, language, **kwargs)

    def render_menu(self, language: Language) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Delega para `render_menu()` — mesmo motivo de
        `get_message` acima.
        """
        return render_menu(language)
