from dataclasses import dataclass

from ulid import ULID


@dataclass(frozen=True)
class PublicId:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Value object de identificador público (ULID, 26 caracteres)
    usado por entidades expostas externamente via listagem/URL — a
    identidade interna (`id` sequencial) nunca sai do domínio/infra. Nasce
    aqui, no build-context-02 (Category), para ser reaproveitado por
    módulos futuros (ex.: Transaction).
    """

    value: str

    def __post_init__(self) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Valida o formato ULID no momento da construção — tanto
        para IDs gerados (generate()) quanto para valores vindos de fora
        (ex.: path param de uma rota), que podem estar malformados.
        """
        try:
            ULID.from_str(self.value)
        except ValueError as exc:
            raise ValueError(f"Invalid public id: {self.value}") from exc

    def __str__(self) -> str:
        return self.value

    @classmethod
    def generate(cls) -> "PublicId":
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Gera um novo PublicId (novo ULID) — usado ao construir
        uma entidade nova, antes de persistir.
        """
        return cls(str(ULID()))
