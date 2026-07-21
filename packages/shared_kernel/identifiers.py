"""Identificadores internos opacos e tipados."""

import re
from dataclasses import dataclass
from typing import Self
from uuid import UUID, uuid4

_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")


def _validated_uuid(value: UUID) -> UUID:
    if not isinstance(value, UUID):
        raise TypeError("O valor do identificador deve ser UUID.")
    if value.int == 0:
        raise ValueError("O UUID nulo não é um identificador válido.")
    return value


@dataclass(frozen=True, slots=True)
class TypedId:
    """Identificador opaco que preserva o tipo lógico da entidade."""

    entity_type: str
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.entity_type, str):
            raise TypeError("O tipo lógico do identificador deve ser texto.")
        if not _TYPE_PATTERN.fullmatch(self.entity_type):
            raise ValueError("O tipo lógico deve usar nomes canônicos em minúsculas.")
        _validated_uuid(self.value)

    @classmethod
    def new(cls, entity_type: str) -> Self:
        return cls(entity_type=entity_type, value=uuid4())

    @classmethod
    def parse(cls, entity_type: str, value: str) -> Self:
        if not isinstance(value, str):
            raise TypeError("O identificador serializado deve ser texto.")
        try:
            parsed = UUID(value)
        except (ValueError, AttributeError) as error:
            raise ValueError("O identificador serializado não é um UUID válido.") from error
        return cls(entity_type=entity_type, value=parsed)

    def __str__(self) -> str:
        return f"{self.entity_type}:{self.value}"


@dataclass(frozen=True, slots=True)
class OrganizationId:
    """Identificador interno específico de uma Organization."""

    value: UUID

    def __post_init__(self) -> None:
        _validated_uuid(self.value)

    @classmethod
    def new(cls) -> Self:
        return cls(value=uuid4())

    @classmethod
    def parse(cls, value: str) -> Self:
        if not isinstance(value, str):
            raise TypeError("O identificador serializado deve ser texto.")
        try:
            parsed = UUID(value)
        except (ValueError, AttributeError) as error:
            raise ValueError("O identificador de Organization não é um UUID válido.") from error
        return cls(value=parsed)

    def __str__(self) -> str:
        return str(self.value)
