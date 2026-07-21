"""Principal autenticado normalizado, sem detalhes do token."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class PrincipalType(StrEnum):
    USER = "USER"
    SERVICE_IDENTITY = "SERVICE_IDENTITY"


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    issuer: str
    subject: str
    principal_type: PrincipalType
    authenticated_at: datetime | None
    client_id: str | None
    technical_scopes: frozenset[str]

    def __post_init__(self) -> None:
        if not isinstance(self.issuer, str) or not self.issuer:
            raise ValueError("issuer não pode ser vazio.")
        if not isinstance(self.subject, str) or not self.subject:
            raise ValueError("subject não pode ser vazio.")
        if not isinstance(self.principal_type, PrincipalType):
            raise TypeError("principal_type deve ser PrincipalType.")
        if not isinstance(self.technical_scopes, frozenset):
            raise TypeError("technical_scopes deve ser frozenset.")
