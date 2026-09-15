"""Validacao do payload de fato importado do tipo GTA.

SPEC: docs/specs/approved/2026-09-15-declaracao-gta-documental.md
PLAN: docs/plans/GTA_DECLARACAO_BUILD_PLAN.md

O mecanismo generico de fato importado (ADR-0042, ``ImportedLivestockFact``) aceita
qualquer ``fact_type``/``payload`` sem nenhuma validacao de conteudo. Este modulo
acrescenta um contrato validado apenas para o caso especifico de GTA (Guia de
Transito Animal), sem tocar o dominio generico nem os servicos existentes.
"""

from datetime import date
from typing import Any

GTA_DECLARED_FACT_TYPE = "livestock.gta_declared"

REQUIRED_STRING_FIELDS = (
    "gta_number",
    "issuing_agency",
    "origin_description",
    "destination_description",
    "purpose",
)


class GtaPayloadInvalido(ValueError):
    """Payload de fato importado tipo GTA nao atende ao contrato minimo da SPEC."""

    def __init__(self, campo: str, motivo: str) -> None:
        self.campo = campo
        self.motivo = motivo
        super().__init__(f"{campo}: {motivo}")


def validar_payload_gta(payload: dict[str, Any]) -> None:
    """Levanta GtaPayloadInvalido no primeiro campo invalido encontrado."""
    for campo in REQUIRED_STRING_FIELDS:
        valor = payload.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            raise GtaPayloadInvalido(campo, "obrigatorio e nao pode ser vazio.")

    estado = payload.get("issuing_state")
    if not isinstance(estado, str) or len(estado.strip()) != 2 or not estado.strip().isupper():
        raise GtaPayloadInvalido(
            "issuing_state", "deve conter exatamente 2 letras maiusculas (ex: 'MS')."
        )

    emitida_em = payload.get("issued_at")
    if not isinstance(emitida_em, str):
        raise GtaPayloadInvalido("issued_at", "obrigatorio, formato de data ISO 8601.")
    try:
        date.fromisoformat(emitida_em)
    except ValueError as error:
        raise GtaPayloadInvalido(
            "issued_at", "nao e uma data ISO 8601 valida (ex: '2026-09-10')."
        ) from error

    quantidade = payload.get("animal_count")
    if not isinstance(quantidade, int) or isinstance(quantidade, bool) or quantidade <= 0:
        raise GtaPayloadInvalido("animal_count", "deve ser um inteiro positivo.")
