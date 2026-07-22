"""Conexão e migrations do PostgreSQL autoritativo."""

from packages.core_infrastructure.persistence.authorization import AuthorizationRepository
from packages.core_infrastructure.persistence.checkpoints import IntegrityCheckpointRepository
from packages.core_infrastructure.persistence.database import (
    DatabaseConfigurationError,
    DatabaseSettings,
    check_database_connection,
    create_database_engine,
)
from packages.core_infrastructure.persistence.events import (
    DomainEventRepository,
    EventAppendConflict,
    EventIntegrityUnavailable,
    StoredDomainEvent,
)
from packages.core_infrastructure.persistence.external_identities import (
    ExternalIdentityRepository,
)
from packages.core_infrastructure.persistence.idempotency import IdempotencyRepository
from packages.core_infrastructure.persistence.memberships import MembershipRepository
from packages.core_infrastructure.persistence.organizations import (
    OrganizationRepository,
    set_local_organization_context,
)
from packages.core_infrastructure.persistence.outbox import (
    OutboxPublicationStateRepository,
    TransactionalEventOutboxRepository,
)
from packages.core_infrastructure.persistence.timestamping import TimestampAuditRepository
from packages.core_infrastructure.persistence.users import UserRepository

__all__ = [
    "DatabaseConfigurationError",
    "AuthorizationRepository",
    "DatabaseSettings",
    "ExternalIdentityRepository",
    "IntegrityCheckpointRepository",
    "IdempotencyRepository",
    "DomainEventRepository",
    "EventAppendConflict",
    "EventIntegrityUnavailable",
    "MembershipRepository",
    "OrganizationRepository",
    "OutboxPublicationStateRepository",
    "StoredDomainEvent",
    "TimestampAuditRepository",
    "TransactionalEventOutboxRepository",
    "UserRepository",
    "check_database_connection",
    "create_database_engine",
    "set_local_organization_context",
]
