"""VerificationBundle e verificação offline (ADR-0010/Passo 7.6).

Pacote autossuficiente para o escopo declarado, verificável **sem rede, sem
segredo e sem acesso ao banco do Titan**.

Duas regras governam o resultado:

1. Material ausente produz `INDETERMINADA` para a dimensão afetada, nunca uma
   consulta silenciosa de rede e nunca uma conversão permissiva em válida.
2. Violação determinística produz `INVALIDA` apontando o componente exato.

O resultado nunca é um booleano: cada dimensão responde por si, e o agregado
declara escopo e instante de referência.
"""

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.serialization import CanonicalSerializer

BUNDLE_FORMAT_VERSION = 1

_SERIALIZER = CanonicalSerializer()


class VerificationStatus(Enum):
    VALIDA = "valida"
    INVALIDA = "invalida"
    INDETERMINADA = "indeterminada"


class VerificationDimension(Enum):
    """Cada dimensão responde por si; não existe veredito único e opaco."""

    ESTRUTURA = "estrutura"
    SERIALIZACAO = "serializacao"
    INTEGRIDADE = "integridade"
    ASSINATURA = "assinatura"
    TEMPORAL = "temporal"
    CADEIA = "cadeia"
    REVOGACAO = "revogacao"
    COBERTURA = "cobertura"


class ComponentRequirement(Enum):
    OBRIGATORIO = "obrigatorio"
    OPCIONAL = "opcional"
    DELIBERADAMENTE_AUSENTE = "deliberadamente_ausente"
    EXTERNO = "externo"


class VerificationReasonCode(Enum):
    """Código estável de razão. Contrato; a mensagem pode ser traduzida."""

    TUDO_CONFERE = "tudo_confere"
    COMPONENTE_OBRIGATORIO_AUSENTE = "componente_obrigatorio_ausente"
    COMPONENTE_NAO_DECLARADO = "componente_nao_declarado"
    DIGEST_DIVERGENTE = "digest_divergente"
    MANIFESTO_ADULTERADO = "manifesto_adulterado"
    SERIALIZACAO_DESCONHECIDA = "serializacao_desconhecida"
    MATERIAL_DE_CONFIANCA_AUSENTE = "material_de_confianca_ausente"
    ASSINATURA_NAO_CONFERE = "assinatura_nao_confere"
    MATERIAL_AUSENTE = "material_ausente"
    ESCOPO_NAO_COMPROVADO = "escopo_nao_comprovado"


def compute_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


@dataclass(frozen=True, slots=True)
class BundleComponent:
    """Item declarado no manifesto. Presença não implica validade nem confiança."""

    logical_name: str
    media_type: str
    requirement: ComponentRequirement
    digest: str = ""
    size_bytes: int = 0
    note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.logical_name, str) or not self.logical_name.strip():
            raise ValueError("logical_name do componente deve ser não vazio.")
        if not isinstance(self.requirement, ComponentRequirement):
            raise TypeError("requirement deve ser um ComponentRequirement válido.")
        # Componente que deveria estar presente precisa declarar seu digest, senão
        # o manifesto não protegeria contra substituição.
        if (
            self.requirement in (ComponentRequirement.OBRIGATORIO, ComponentRequirement.OPCIONAL)
            and not self.digest.strip()
        ):
            raise ValueError(
                f"Componente '{self.logical_name}' exige digest declarado no manifesto."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "logical_name": self.logical_name,
            "media_type": self.media_type,
            "requirement": self.requirement.value,
            "digest": self.digest,
            "size_bytes": self.size_bytes,
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class BundleManifest:
    """Manifesto canônico e imutável.

    Impede adição, remoção, substituição ou mistura silenciosa de componentes:
    o que não está listado não integra o escopo.
    """

    bundle_id: TypedId
    organization_id: OrganizationId
    purpose: str
    audience: str
    created_at: datetime
    components: tuple[BundleComponent, ...]
    manifest_digest: str
    issuer_reference: UniversalReference | None = None
    format_version: int = BUNDLE_FORMAT_VERSION
    serialization_version: str = CanonicalSerializer.version
    declared_scopes: tuple[str, ...] = field(default_factory=tuple)
    declared_gaps: tuple[str, ...] = field(default_factory=tuple)
    profiles: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.bundle_id.entity_type != "verification_bundle":
            raise ValueError("bundle_id deve ser do tipo 'verification_bundle'.")
        if not isinstance(self.purpose, str) or not self.purpose.strip():
            raise ValueError("O manifesto exige finalidade não vazia.")
        if not isinstance(self.components, tuple) or not self.components:
            raise ValueError("O manifesto exige ao menos um componente declarado.")
        nomes = [c.logical_name for c in self.components]
        if len(nomes) != len(set(nomes)):
            raise ValueError("Nomes lógicos de componentes não podem se repetir.")

    def component(self, logical_name: str) -> BundleComponent | None:
        return next((c for c in self.components if c.logical_name == logical_name), None)

    def protected_content(self) -> dict[str, Any]:
        """O que o digest do manifesto protege — tudo, menos o próprio digest."""
        return {
            "bundle_id": str(self.bundle_id.value),
            "organization_id": str(self.organization_id.value),
            "purpose": self.purpose,
            "audience": self.audience,
            "created_at": self.created_at.isoformat(),
            "format_version": self.format_version,
            "serialization_version": self.serialization_version,
            "declared_scopes": list(self.declared_scopes),
            "declared_gaps": list(self.declared_gaps),
            "profiles": list(self.profiles),
            "components": [c.to_dict() for c in self.components],
        }

    def recompute_digest(self) -> str:
        return compute_digest(_SERIALIZER.serialize(self.protected_content()))


@dataclass(frozen=True, slots=True)
class SignatureMaterial:
    """Material de assinatura transportado no pacote.

    Chave privada, segredo, token ou credencial nunca entram aqui.
    """

    key_id: str
    algorithm: str
    profile: str
    signed_digest: str
    signature_value: str
    signed_at: datetime | None = None
    certificate_chain: tuple[str, ...] = field(default_factory=tuple)
    revocation_material: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class VerificationBundle:
    """Manifesto mais os bytes dos componentes efetivamente presentes."""

    manifest: BundleManifest
    payloads: dict[str, bytes]
    signature: SignatureMaterial | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, BundleManifest):
            raise TypeError("manifest deve ser um BundleManifest.")
        if not isinstance(self.payloads, dict):
            raise TypeError("payloads deve ser um dicionário.")


@dataclass(frozen=True, slots=True)
class DimensionResult:
    dimension: VerificationDimension
    status: VerificationStatus
    reason_code: VerificationReasonCode
    detail: str
    failure_point: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ValueError("Todo resultado de dimensão exige detalhe explicativo.")


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Relatório imutável. Descreve o estado segundo o material incluído.

    Não afirma revogação atual, publicação atual nem ausência de evento posterior:
    a verificação offline enxerga apenas o que veio dentro do pacote.
    """

    bundle_id: TypedId
    verified_at: datetime
    results: tuple[DimensionResult, ...]
    trust_anchor_origin: str = "nenhuma âncora de confiança fornecida"

    @property
    def status(self) -> VerificationStatus:
        """Violação determinística prevalece; na dúvida, indeterminada."""
        estados = {r.status for r in self.results}
        if VerificationStatus.INVALIDA in estados:
            return VerificationStatus.INVALIDA
        if VerificationStatus.INDETERMINADA in estados:
            return VerificationStatus.INDETERMINADA
        return VerificationStatus.VALIDA

    @property
    def first_failure(self) -> DimensionResult | None:
        """Primeira falha determinística, com o ponto exato."""
        return next((r for r in self.results if r.status is VerificationStatus.INVALIDA), None)

    def result_for(self, dimension: VerificationDimension) -> DimensionResult | None:
        return next((r for r in self.results if r.dimension is dimension), None)

    def explain(self) -> tuple[str, ...]:
        return tuple(
            f"{r.dimension.value}: {r.status.value} ({r.reason_code.value}) — {r.detail}"
            + (f" [ponto: {r.failure_point}]" if r.failure_point else "")
            for r in self.results
        )


class BundleVerifier:
    """Verificador offline e independente do Titan.

    Não consulta rede, não usa segredo e não conhece o banco: recebe o pacote e,
    opcionalmente, âncoras de confiança externas.
    """

    known_serializations = frozenset({CanonicalSerializer.version})

    def verify(
        self,
        bundle: VerificationBundle,
        verified_at: datetime,
        trust_anchors: Mapping[str, str] | None = None,
    ) -> ValidationReport:
        resultados: list[DimensionResult] = [
            self._check_structure(bundle),
            self._check_serialization(bundle),
            self._check_integrity(bundle),
            self._check_signature(bundle, trust_anchors),
            self._check_temporal(bundle),
            self._check_revocation(bundle),
            self._check_coverage(bundle),
        ]
        return ValidationReport(
            bundle_id=bundle.manifest.bundle_id,
            verified_at=verified_at,
            results=tuple(resultados),
            trust_anchor_origin=(
                "âncoras fornecidas pelo verificador"
                if trust_anchors
                else "nenhuma âncora de confiança fornecida"
            ),
        )

    # -- Dimensões ---------------------------------------------------------

    def _check_structure(self, bundle: VerificationBundle) -> DimensionResult:
        manifesto = bundle.manifest

        # Arquivo não declarado é mistura silenciosa: falha determinística.
        for nome in sorted(bundle.payloads):
            if manifesto.component(nome) is None:
                return DimensionResult(
                    dimension=VerificationDimension.ESTRUTURA,
                    status=VerificationStatus.INVALIDA,
                    reason_code=VerificationReasonCode.COMPONENTE_NAO_DECLARADO,
                    detail=(
                        f"O componente '{nome}' está presente mas não consta do "
                        "manifesto; o que não está listado não integra o escopo."
                    ),
                    failure_point=nome,
                )

        ausentes = [
            c.logical_name
            for c in manifesto.components
            if c.requirement is ComponentRequirement.OBRIGATORIO
            and c.logical_name not in bundle.payloads
        ]
        if ausentes:
            return DimensionResult(
                dimension=VerificationDimension.ESTRUTURA,
                status=VerificationStatus.INDETERMINADA,
                reason_code=VerificationReasonCode.COMPONENTE_OBRIGATORIO_AUSENTE,
                detail=(
                    "Componentes obrigatórios ausentes: "
                    f"{', '.join(sorted(ausentes))}. Sem eles não é possível concluir."
                ),
                failure_point=sorted(ausentes)[0],
            )

        return DimensionResult(
            dimension=VerificationDimension.ESTRUTURA,
            status=VerificationStatus.VALIDA,
            reason_code=VerificationReasonCode.TUDO_CONFERE,
            detail="Manifesto e inventário são consistentes entre si.",
        )

    def _check_serialization(self, bundle: VerificationBundle) -> DimensionResult:
        versao = bundle.manifest.serialization_version
        if versao not in self.known_serializations:
            return DimensionResult(
                dimension=VerificationDimension.SERIALIZACAO,
                status=VerificationStatus.INDETERMINADA,
                reason_code=VerificationReasonCode.SERIALIZACAO_DESCONHECIDA,
                detail=(
                    f"Serialização '{versao}' desconhecida por este verificador; "
                    "digests não podem ser reproduzidos com segurança."
                ),
                failure_point=versao,
            )
        return DimensionResult(
            dimension=VerificationDimension.SERIALIZACAO,
            status=VerificationStatus.VALIDA,
            reason_code=VerificationReasonCode.TUDO_CONFERE,
            detail=f"Serialização '{versao}' é conhecida e reproduzível.",
        )

    def _check_integrity(self, bundle: VerificationBundle) -> DimensionResult:
        manifesto = bundle.manifest

        if manifesto.recompute_digest() != manifesto.manifest_digest:
            return DimensionResult(
                dimension=VerificationDimension.INTEGRIDADE,
                status=VerificationStatus.INVALIDA,
                reason_code=VerificationReasonCode.MANIFESTO_ADULTERADO,
                detail=(
                    "O digest recalculado do manifesto não confere com o declarado: "
                    "o próprio manifesto foi alterado."
                ),
                failure_point="manifest",
            )

        for nome in sorted(bundle.payloads):
            componente = manifesto.component(nome)
            if componente is None:
                # Componente não declarado já é reprovado pela dimensão de estrutura.
                # Aqui ele é ignorado de propósito: cada dimensão precisa concluir por
                # si, porque um verificador que estoura não produz relatório algum.
                continue
            calculado = compute_digest(bundle.payloads[nome])
            if calculado != componente.digest:
                return DimensionResult(
                    dimension=VerificationDimension.INTEGRIDADE,
                    status=VerificationStatus.INVALIDA,
                    reason_code=VerificationReasonCode.DIGEST_DIVERGENTE,
                    detail=(
                        f"O componente '{nome}' não confere com o digest declarado. "
                        f"Esperado {componente.digest[:16]}…, obtido {calculado[:16]}…"
                    ),
                    failure_point=nome,
                )

        return DimensionResult(
            dimension=VerificationDimension.INTEGRIDADE,
            status=VerificationStatus.VALIDA,
            reason_code=VerificationReasonCode.TUDO_CONFERE,
            detail="Manifesto e todos os componentes presentes conferem com seus digests.",
        )

    def _check_signature(
        self, bundle: VerificationBundle, trust_anchors: Mapping[str, str] | None
    ) -> DimensionResult:
        assinatura = bundle.signature
        if assinatura is None:
            return DimensionResult(
                dimension=VerificationDimension.ASSINATURA,
                status=VerificationStatus.INDETERMINADA,
                reason_code=VerificationReasonCode.MATERIAL_AUSENTE,
                detail=(
                    "O pacote não transporta assinatura; a autenticidade de emissão "
                    "não pode ser afirmada nem negada."
                ),
            )

        # Âncora incluída no pacote não é confiável por estar no pacote: a confiança
        # vem de fora, do verificador.
        if not trust_anchors or assinatura.key_id not in trust_anchors:
            return DimensionResult(
                dimension=VerificationDimension.ASSINATURA,
                status=VerificationStatus.INDETERMINADA,
                reason_code=VerificationReasonCode.MATERIAL_DE_CONFIANCA_AUSENTE,
                detail=(
                    f"Não há âncora de confiança externa para a chave "
                    f"'{assinatura.key_id}'; a assinatura não é avaliável."
                ),
                failure_point=assinatura.key_id,
            )

        if assinatura.signed_digest != bundle.manifest.manifest_digest:
            return DimensionResult(
                dimension=VerificationDimension.ASSINATURA,
                status=VerificationStatus.INVALIDA,
                reason_code=VerificationReasonCode.ASSINATURA_NAO_CONFERE,
                detail=(
                    "A assinatura cobre um digest de manifesto diferente do presente no pacote."
                ),
                failure_point="signature.signed_digest",
            )

        esperado = trust_anchors[assinatura.key_id]
        if assinatura.signature_value != esperado:
            return DimensionResult(
                dimension=VerificationDimension.ASSINATURA,
                status=VerificationStatus.INVALIDA,
                reason_code=VerificationReasonCode.ASSINATURA_NAO_CONFERE,
                detail="A assinatura não confere com a âncora de confiança informada.",
                failure_point="signature.signature_value",
            )

        return DimensionResult(
            dimension=VerificationDimension.ASSINATURA,
            status=VerificationStatus.VALIDA,
            reason_code=VerificationReasonCode.TUDO_CONFERE,
            detail=(
                f"Assinatura confere para o perfil '{assinatura.profile}' segundo a "
                "âncora fornecida ao verificador."
            ),
        )

    def _check_temporal(self, bundle: VerificationBundle) -> DimensionResult:
        assinatura = bundle.signature
        if assinatura is None or assinatura.signed_at is None:
            return DimensionResult(
                dimension=VerificationDimension.TEMPORAL,
                status=VerificationStatus.INDETERMINADA,
                reason_code=VerificationReasonCode.MATERIAL_AUSENTE,
                detail=(
                    "Sem âncora temporal no pacote: o instante de assinatura não pode "
                    "ser comprovado."
                ),
            )
        return DimensionResult(
            dimension=VerificationDimension.TEMPORAL,
            status=VerificationStatus.VALIDA,
            reason_code=VerificationReasonCode.TUDO_CONFERE,
            detail=f"Âncora temporal declarada em {assinatura.signed_at.isoformat()}.",
        )

    def _check_revocation(self, bundle: VerificationBundle) -> DimensionResult:
        assinatura = bundle.signature
        if assinatura is None or not assinatura.revocation_material:
            return DimensionResult(
                dimension=VerificationDimension.REVOGACAO,
                status=VerificationStatus.INDETERMINADA,
                reason_code=VerificationReasonCode.MATERIAL_AUSENTE,
                detail=(
                    "Sem material de revogação no pacote. A verificação offline não "
                    "consulta rede e não afirma o estado de revogação atual."
                ),
            )
        return DimensionResult(
            dimension=VerificationDimension.REVOGACAO,
            status=VerificationStatus.VALIDA,
            reason_code=VerificationReasonCode.TUDO_CONFERE,
            detail=(
                "Material de revogação presente; o resultado vale para o instante de "
                "referência incluído no pacote."
            ),
        )

    def _check_coverage(self, bundle: VerificationBundle) -> DimensionResult:
        manifesto = bundle.manifest
        if not manifesto.declared_scopes:
            return DimensionResult(
                dimension=VerificationDimension.COBERTURA,
                status=VerificationStatus.INDETERMINADA,
                reason_code=VerificationReasonCode.ESCOPO_NAO_COMPROVADO,
                detail=(
                    "O manifesto não declara escopo: componentes presentes podem estar "
                    "íntegros, mas a completude permanece indeterminada."
                ),
            )
        if manifesto.declared_gaps:
            return DimensionResult(
                dimension=VerificationDimension.COBERTURA,
                status=VerificationStatus.INDETERMINADA,
                reason_code=VerificationReasonCode.ESCOPO_NAO_COMPROVADO,
                detail=(
                    "O manifesto declara lacunas: "
                    f"{'; '.join(manifesto.declared_gaps)}. A cobertura é parcial por "
                    "declaração do próprio emissor."
                ),
            )
        return DimensionResult(
            dimension=VerificationDimension.COBERTURA,
            status=VerificationStatus.VALIDA,
            reason_code=VerificationReasonCode.TUDO_CONFERE,
            detail=(f"Escopo declarado sem lacunas: {', '.join(manifesto.declared_scopes)}."),
        )


def build_manifest(
    bundle_id: TypedId,
    organization_id: OrganizationId,
    purpose: str,
    audience: str,
    created_at: datetime,
    components: Sequence[BundleComponent],
    issuer_reference: UniversalReference | None = None,
    declared_scopes: Sequence[str] = (),
    declared_gaps: Sequence[str] = (),
    profiles: Sequence[str] = (),
) -> BundleManifest:
    """Monta o manifesto já com o digest que protege seu próprio conteúdo."""
    parcial = BundleManifest(
        bundle_id=bundle_id,
        organization_id=organization_id,
        purpose=purpose,
        audience=audience,
        created_at=created_at,
        components=tuple(components),
        manifest_digest="pendente",
        issuer_reference=issuer_reference,
        declared_scopes=tuple(declared_scopes),
        declared_gaps=tuple(declared_gaps),
        profiles=tuple(profiles),
    )
    return BundleManifest(
        bundle_id=parcial.bundle_id,
        organization_id=parcial.organization_id,
        purpose=parcial.purpose,
        audience=parcial.audience,
        created_at=parcial.created_at,
        components=parcial.components,
        manifest_digest=parcial.recompute_digest(),
        issuer_reference=parcial.issuer_reference,
        declared_scopes=parcial.declared_scopes,
        declared_gaps=parcial.declared_gaps,
        profiles=parcial.profiles,
    )
