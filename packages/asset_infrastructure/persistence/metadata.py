"""MetaData à qual as tabelas do Titan Asset & Sustainment se registram.

As tabelas da vertical vivem no schema ``core_audit``, mas possuem chaves
estrangeiras para ``core_identity.organizations``. O SQLAlchemy só resolve uma
FK quando a tabela referenciada está na **mesma** MetaData; uma MetaData própria
da vertical faria o ``alembic check`` falhar de duas formas — primeiro propondo
remover a vertical inteira, depois não resolvendo a FK para ``organizations``.

Por isso a vertical não mantém MetaData própria: reusa a do Core, onde
``organizations`` já está registrada. Cada tabela de Asset continua declarando
``schema=CORE_AUDIT_SCHEMA`` explicitamente, exatamente como
``packages/livestock_infrastructure/persistence/metadata.py`` já faz.
"""

from packages.core_infrastructure.persistence.organizations import organization_metadata

asset_metadata = organization_metadata
