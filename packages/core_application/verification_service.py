"""Montagem do VerificationBundle a partir de um Dossier (ADR-0010/Passo 7.6)."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from packages.core_domain.dossier import Dossier
from packages.core_domain.verification import (
    BundleComponent,
    BundleManifest,
    ComponentRequirement,
    SignatureMaterial,
    VerificationBundle,
    build_manifest,
    compute_digest,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

DOSSIER_COMPONENT = "dossier.json"
TRUST_POLICY_COMPONENT = "verification-policy.json"

# Nunca podem viajar dentro do pacote, por mais conveniente que pareça.
_PROIBIDOS = frozenset(
    {"private_key", "secret", "token", "credential", "pin", "password", "organization_context"}
)


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    """Bytes estáveis: mesmo conteúdo produz sempre os mesmos bytes e digest."""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


@dataclass(frozen=True, slots=True)
class VerificationBundleService:
    """Empacota o material necessário ao escopo declarado.

    O pacote é montado para viajar: ele não pode depender de segredo, de rede nem
    do banco do Titan para ser verificado do outro lado.
    """

    def build_from_dossier(
        self,
        dossier: Dossier,
        audience: str,
        created_at: datetime,
        issuer_reference: UniversalReference | None = None,
        signature: SignatureMaterial | None = None,
        verification_policy: Mapping[str, Any] | None = None,
        declared_gaps: Sequence[str] = (),
        profiles: Sequence[str] = (),
    ) -> VerificationBundle:
        if not dossier.verify():
            raise ValueError("Dossiê não confere com seu próprio hash: não pode ser empacotado.")
        self._guard_forbidden_material(signature, verification_policy)

        payloads: dict[str, bytes] = {DOSSIER_COMPONENT: _canonical_bytes(dossier.document)}
        componentes: list[BundleComponent] = [
            BundleComponent(
                logical_name=DOSSIER_COMPONENT,
                media_type="application/json",
                requirement=ComponentRequirement.OBRIGATORIO,
                digest=compute_digest(payloads[DOSSIER_COMPONENT]),
                size_bytes=len(payloads[DOSSIER_COMPONENT]),
                note="Snapshot canônico autocontido da decisão.",
            )
        ]

        if verification_policy is not None:
            conteudo = _canonical_bytes(verification_policy)
            payloads[TRUST_POLICY_COMPONENT] = conteudo
            componentes.append(
                BundleComponent(
                    logical_name=TRUST_POLICY_COMPONENT,
                    media_type="application/json",
                    requirement=ComponentRequirement.OPCIONAL,
                    digest=compute_digest(conteudo),
                    size_bytes=len(conteudo),
                    note="Política de verificação declarada pelo emissor.",
                )
            )
        else:
            # Ausência declarada é honesta; ausência silenciosa não.
            componentes.append(
                BundleComponent(
                    logical_name=TRUST_POLICY_COMPONENT,
                    media_type="application/json",
                    requirement=ComponentRequirement.DELIBERADAMENTE_AUSENTE,
                    note="Política de verificação não acompanha este pacote.",
                )
            )

        escopos = ["integridade", "conteudo_da_decisao"]
        lacunas = list(declared_gaps)
        if signature is None:
            lacunas.append("Sem assinatura: a autenticidade de emissão não é comprovável offline.")
        if verification_policy is None:
            lacunas.append("Sem política de verificação: a confiança depende de perfil externo.")

        manifesto = build_manifest(
            bundle_id=TypedId.new("verification_bundle"),
            organization_id=dossier.organization_id,
            purpose=dossier.purpose,
            audience=audience,
            created_at=created_at,
            components=componentes,
            issuer_reference=issuer_reference,
            declared_scopes=escopos,
            declared_gaps=lacunas,
            profiles=profiles,
        )

        # A assinatura cobre o digest do manifesto, que por sua vez cobre todos os
        # componentes: assinar o manifesto é assinar o conjunto.
        assinatura_final = (
            SignatureMaterial(
                key_id=signature.key_id,
                algorithm=signature.algorithm,
                profile=signature.profile,
                signed_digest=manifesto.manifest_digest,
                signature_value=signature.signature_value,
                signed_at=signature.signed_at,
                certificate_chain=signature.certificate_chain,
                revocation_material=signature.revocation_material,
            )
            if signature is not None
            else None
        )

        return VerificationBundle(manifest=manifesto, payloads=payloads, signature=assinatura_final)

    def export(self, bundle: VerificationBundle) -> dict[str, Any]:
        """Forma transportável do pacote, pronta para sair do Titan."""
        return {
            "manifest": {
                **bundle.manifest.protected_content(),
                "manifest_digest": bundle.manifest.manifest_digest,
            },
            "payloads": {
                nome: conteudo.decode("utf-8") for nome, conteudo in bundle.payloads.items()
            },
            "signature": (
                {
                    "key_id": bundle.signature.key_id,
                    "algorithm": bundle.signature.algorithm,
                    "profile": bundle.signature.profile,
                    "signed_digest": bundle.signature.signed_digest,
                    "signature_value": bundle.signature.signature_value,
                    "signed_at": (
                        bundle.signature.signed_at.isoformat()
                        if bundle.signature.signed_at
                        else None
                    ),
                    "certificate_chain": list(bundle.signature.certificate_chain),
                    "revocation_material": list(bundle.signature.revocation_material),
                }
                if bundle.signature is not None
                else None
            ),
        }

    @staticmethod
    def load(exported: Mapping[str, Any]) -> VerificationBundle:
        """Reconstrói o pacote a partir da forma transportável, sem o Titan."""
        raw_manifest = exported["manifest"]
        manifesto = BundleManifest(
            bundle_id=TypedId.parse("verification_bundle", raw_manifest["bundle_id"]),
            organization_id=OrganizationId(UUID(raw_manifest["organization_id"])),
            purpose=raw_manifest["purpose"],
            audience=raw_manifest["audience"],
            created_at=datetime.fromisoformat(raw_manifest["created_at"]),
            components=tuple(
                BundleComponent(
                    logical_name=c["logical_name"],
                    media_type=c["media_type"],
                    requirement=ComponentRequirement(c["requirement"]),
                    digest=c["digest"],
                    size_bytes=c["size_bytes"],
                    note=c["note"],
                )
                for c in raw_manifest["components"]
            ),
            manifest_digest=raw_manifest["manifest_digest"],
            format_version=raw_manifest["format_version"],
            serialization_version=raw_manifest["serialization_version"],
            declared_scopes=tuple(raw_manifest["declared_scopes"]),
            declared_gaps=tuple(raw_manifest["declared_gaps"]),
            profiles=tuple(raw_manifest["profiles"]),
        )

        raw_signature = exported.get("signature")
        assinatura = (
            SignatureMaterial(
                key_id=raw_signature["key_id"],
                algorithm=raw_signature["algorithm"],
                profile=raw_signature["profile"],
                signed_digest=raw_signature["signed_digest"],
                signature_value=raw_signature["signature_value"],
                signed_at=(
                    datetime.fromisoformat(raw_signature["signed_at"])
                    if raw_signature.get("signed_at")
                    else None
                ),
                certificate_chain=tuple(raw_signature.get("certificate_chain", [])),
                revocation_material=tuple(raw_signature.get("revocation_material", [])),
            )
            if raw_signature
            else None
        )

        return VerificationBundle(
            manifest=manifesto,
            payloads={
                nome: conteudo.encode("utf-8") for nome, conteudo in exported["payloads"].items()
            },
            signature=assinatura,
        )

    @staticmethod
    def _guard_forbidden_material(
        signature: SignatureMaterial | None, verification_policy: Mapping[str, Any] | None
    ) -> None:
        alvos: list[str] = []
        if verification_policy is not None:
            alvos.extend(str(k).lower() for k in verification_policy)
        if signature is not None:
            alvos.append(signature.key_id.lower())
        for alvo in alvos:
            for proibido in _PROIBIDOS:
                if proibido in alvo:
                    raise ValueError(
                        f"Material proibido no pacote de verificação: '{alvo}'. "
                        "Chaves privadas, segredos, tokens e credenciais nunca são "
                        "exportados."
                    )
