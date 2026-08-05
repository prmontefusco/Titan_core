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
    SignaturePurpose,
    SignatureTarget,
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


def _livestock_declared_scopes_and_gaps(dossier: Dossier) -> tuple[list[str], list[str]]:
    vertical = dossier.document.get("vertical")
    if not isinstance(vertical, Mapping):
        return [], []
    if vertical.get("namespace") != "livestock":
        return [], []
    content = vertical.get("content")
    if not isinstance(content, Mapping):
        return [], []

    scopes = ["integridade", "conteudo_da_decisao"]
    gaps: list[str] = []

    coverage = content.get("coverage")
    if isinstance(coverage, Mapping):
        scopes.append("prova_sanitaria_vitalicia")
        declared_scope = coverage.get("declared_scope")
        if isinstance(declared_scope, str) and declared_scope:
            scopes.append(f"coverage:{declared_scope}")
        if coverage.get("status") == "NAO_DECLARADA":
            gaps.append(
                "Cobertura sanitaria vitalicia nao declarada; "
                "o pacote nao prova historico completo."
            )
        if coverage.get("has_declared_gaps"):
            gaps.append(
                "Cobertura sanitaria parcial declarada no dossie; "
                "existem lacunas historicas abertas."
            )

    imported = content.get("imported_material")
    if isinstance(imported, Mapping):
        declared_scope = imported.get("declared_scope")
        if isinstance(declared_scope, str) and declared_scope:
            scopes.append(f"material:{declared_scope}")
        if imported.get("has_imported_facts"):
            scopes.append("historico_importado_declarado")
            gaps.append(
                "Material importado acompanha o pacote como afirmacao importada; "
                "nao substitui observacao local."
            )

    limitations = content.get("declared_limitations")
    if isinstance(limitations, Sequence) and not isinstance(limitations, (str, bytes)):
        for limitation in limitations:
            if isinstance(limitation, str) and limitation not in gaps:
                gaps.append(limitation)

    return sorted(set(scopes)), gaps


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
        auto_scopes, auto_gaps = _livestock_declared_scopes_and_gaps(dossier)
        escopos.extend(auto_scopes)
        lacunas.extend(auto_gaps)
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
            declared_scopes=tuple(sorted(set(escopos))),
            declared_gaps=tuple(dict.fromkeys(lacunas)),
            profiles=profiles,
        )

        # A assinatura cobre o digest do manifesto, que por sua vez cobre todos os
        # componentes: assinar o manifesto é assinar o conjunto. O alvo é
        # rebindado para o manifesto real -- que só existe a partir daqui --
        # preservando a finalidade (`purpose`) que o chamador declarou.
        assinatura_final = (
            SignatureMaterial(
                key_id=signature.key_id,
                algorithm=signature.algorithm,
                profile=signature.profile,
                signature_target=SignatureTarget(
                    target_type="bundle_manifest",
                    target_identifier=manifesto.manifest_digest,
                    domain="titan.verification_bundle",
                    contract_version=manifesto.format_version,
                    purpose=signature.signature_target.purpose,
                ),
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
                    "signature_target": {
                        "target_type": bundle.signature.signature_target.target_type,
                        "target_identifier": bundle.signature.signature_target.target_identifier,
                        "domain": bundle.signature.signature_target.domain,
                        "contract_version": bundle.signature.signature_target.contract_version,
                        "purpose": bundle.signature.signature_target.purpose.value,
                    },
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
                signature_target=SignatureTarget(
                    target_type=raw_signature["signature_target"]["target_type"],
                    target_identifier=raw_signature["signature_target"]["target_identifier"],
                    domain=raw_signature["signature_target"]["domain"],
                    contract_version=raw_signature["signature_target"]["contract_version"],
                    purpose=SignaturePurpose(raw_signature["signature_target"]["purpose"]),
                ),
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
