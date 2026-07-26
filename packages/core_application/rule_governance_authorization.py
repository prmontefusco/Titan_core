"""Permissoes do Core para governanca auditavel de regras."""

from typing import Final

RULE_GOVERNANCE_CRIAR: Final = "RULE_GOVERNANCE.CRIAR"
RULE_GOVERNANCE_PUBLICAR: Final = "RULE_GOVERNANCE.PUBLICAR"
RULE_GOVERNANCE_LER: Final = "RULE_GOVERNANCE.LER"

RULE_GOVERNANCE_PERMISSIONS: Final = frozenset(
    {
        RULE_GOVERNANCE_CRIAR,
        RULE_GOVERNANCE_PUBLICAR,
        RULE_GOVERNANCE_LER,
    }
)
