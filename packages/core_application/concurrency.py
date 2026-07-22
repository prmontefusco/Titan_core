"""Contrato de conflito para concorrência otimista de agregados."""


class OptimisticConcurrencyConflict(RuntimeError):
    """A versão observada pelo comando deixou de ser a versão corrente."""

    code = "VERSAO_DE_AGREGADO_CONFLITANTE"

    def __init__(self) -> None:
        super().__init__(self.code)
