"""Permissoes do Core para gestao de Policies versionadas (ADR-0038/Passo 6.1)."""

from typing import Final

POLICY_CRIAR: Final = "POLICY.CRIAR"
POLICY_PUBLICAR: Final = "POLICY.PUBLICAR"
POLICY_LER: Final = "POLICY.LER"

POLICY_PERMISSIONS: Final = frozenset(
    {
        POLICY_CRIAR,
        POLICY_PUBLICAR,
        POLICY_LER,
    }
)
