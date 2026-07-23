"""Contrato público da API de verificação externa (ADR-0039/Passo 7.7).

Endpoint hermético: não consulta rede, sistema de arquivos, banco de domínio nem
resolve referências declaradas pelo pacote. Verifica somente o material enviado
no corpo da requisição.
"""

import json
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from packages.core_application.verification_service import VerificationBundleService
from packages.core_domain.verification import (
    MANDATORY_DIMENSIONS,
    NORMATIVE_DIMENSION_ORDER,
    BundleVerifier,
    ValidationReport,
    VerificationBundle,
    VerificationStatus,
    compute_digest,
)
from packages.shared_kernel.serialization import CanonicalSerializer

CONTRACT_VERSION = "1.0"
VERIFICATION_PROFILE = "titan-bundle-verification-v1"
ENGINE_NAME = "titan-bundle-verifier"
ENGINE_VERSION = "1.0.0"

# Limites operacionais da ADR-0039. Ausência de autenticação de usuário não
# implica disponibilidade ilimitada.
MAX_BODY_BYTES = 1024 * 1024
MAX_COMPONENTS = 32
MAX_COMPONENT_BYTES = 512 * 1024
MAX_JSON_DEPTH = 32
MAX_ANCHORS = 8
MAX_ANCHOR_BYTES = 8 * 1024

ALLOWED_ANCHOR_TYPES = frozenset({"PUBLIC_KEY"})
ALLOWED_ANCHOR_PURPOSES = frozenset({"BUNDLE_SIGNATURE"})

router = APIRouter()


class TrustAnchorInput(BaseModel):
    anchor_id: str
    anchor_type: Literal["PUBLIC_KEY"]
    algorithm: str
    encoding: Literal["BASE64URL", "HEX", "RAW"] = "BASE64URL"
    value: str
    purpose: Literal["BUNDLE_SIGNATURE"] = "BUNDLE_SIGNATURE"


class VerificationRequest(BaseModel):
    model_config = {"extra": "forbid"}

    bundle: dict[str, Any]
    trust_anchors: list[TrustAnchorInput] = Field(default_factory=list)


def _problem(
    request: Request,
    http_status: int,
    reason_code: str,
    title: str,
    detail: str,
) -> JSONResponse:
    """Erro de contrato nunca se parece com resultado de verificação."""
    return JSONResponse(
        content={
            "type": f"urn:titan:problema:{reason_code.lower().replace('_', '-')}",
            "title": title,
            "status": http_status,
            "detail": detail,
            "instance": request.url.path,
            "reason_code": reason_code,
        },
        media_type="application/problem+json",
        status_code=http_status,
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


def _json_depth(value: Any, current: int = 0) -> int:
    if current > MAX_JSON_DEPTH:
        return current
    if isinstance(value, dict):
        return max((_json_depth(v, current + 1) for v in value.values()), default=current)
    if isinstance(value, list):
        return max((_json_depth(v, current + 1) for v in value), default=current)
    return current


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    vistos: set[str] = set()
    for chave, _ in pairs:
        if chave in vistos:
            raise ValueError(f"Propriedade duplicada no JSON: '{chave}'.")
        vistos.add(chave)
    return dict(pairs)


def _bundle_digest(bundle_payload: dict[str, Any]) -> str:
    """Digest da representação canônica do pacote.

    Exclui as âncoras da requisição e metadados HTTP, de modo que o mesmo pacote
    produza a mesma referência independentemente das âncoras usadas.
    """
    return compute_digest(CanonicalSerializer().serialize(bundle_payload))


def _limitations(report: ValidationReport) -> list[dict[str, str]]:
    codigos = [
        "CONTENT_TRUTH_NOT_ASSERTED",
        "CURRENT_REVOCATION_NOT_CHECKED",
        "RESULT_DEPENDS_ON_VERIFIER_INSTANCE",
    ]
    # Só faz sentido declarar a limitação da âncora quando houve âncora avaliada.
    if any(
        r.status is VerificationStatus.VALIDA and r.dimension.value == "ASSINATURA"
        for r in report.results
    ):
        codigos.append("SIGNATURE_VALID_ONLY_AGAINST_CALLER_SUPPLIED_ANCHOR")
    return [{"code": c} for c in codigos]


@router.post(
    "/v1/verification/bundles",
    summary="Verificar um pacote de verificação submetido",
    tags=["verificação"],
    responses={
        400: {"description": "JSON sintaticamente inválido"},
        413: {"description": "Corpo acima do limite"},
        422: {"description": "Estrutura inválida"},
    },
)
async def verify_bundle(request: Request) -> Response:
    corpo = await request.body()

    if len(corpo) > MAX_BODY_BYTES:
        return _problem(
            request,
            status.HTTP_413_CONTENT_TOO_LARGE,
            "PAYLOAD_TOO_LARGE",
            "Corpo acima do limite",
            f"O corpo excede o limite de {MAX_BODY_BYTES} bytes.",
        )

    try:
        bruto = json.loads(corpo.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as erro:
        return _problem(
            request,
            status.HTTP_400_BAD_REQUEST,
            "MALFORMED_JSON",
            "JSON inválido",
            str(erro),
        )

    if _json_depth(bruto) > MAX_JSON_DEPTH:
        return _problem(
            request,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "MALFORMED_REQUEST",
            "Estrutura demasiado profunda",
            f"A profundidade do JSON excede {MAX_JSON_DEPTH}.",
        )

    try:
        pedido = VerificationRequest.model_validate(bruto)
    except Exception as erro:  # noqa: BLE001 — qualquer violação de schema é 422
        return _problem(
            request,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "MALFORMED_REQUEST",
            "Requisição fora do schema",
            _sanitize(str(erro)),
        )

    identificadores = [a.anchor_id for a in pedido.trust_anchors]
    if len(identificadores) != len(set(identificadores)):
        return _problem(
            request,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "DUPLICATE_ANCHOR_ID",
            "Âncora duplicada",
            "Âncoras com o mesmo anchor_id não são resolvidas silenciosamente.",
        )

    if len(pedido.trust_anchors) > MAX_ANCHORS:
        return _problem(
            request,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "MALFORMED_REQUEST",
            "Âncoras em excesso",
            f"No máximo {MAX_ANCHORS} âncoras por requisição.",
        )

    if any(len(a.value.encode("utf-8")) > MAX_ANCHOR_BYTES for a in pedido.trust_anchors):
        return _problem(
            request,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "MALFORMED_REQUEST",
            "Âncora acima do limite",
            f"Cada âncora deve caber em {MAX_ANCHOR_BYTES} bytes.",
        )

    payloads = pedido.bundle.get("payloads", {})
    if isinstance(payloads, dict):
        if len(payloads) > MAX_COMPONENTS:
            return _problem(
                request,
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "MALFORMED_BUNDLE",
                "Componentes em excesso",
                f"No máximo {MAX_COMPONENTS} componentes por pacote.",
            )
        for nome, conteudo in payloads.items():
            if isinstance(conteudo, str) and len(conteudo.encode("utf-8")) > MAX_COMPONENT_BYTES:
                return _problem(
                    request,
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "MALFORMED_BUNDLE",
                    "Componente acima do limite",
                    f"O componente '{nome}' excede {MAX_COMPONENT_BYTES} bytes.",
                )

    try:
        pacote: VerificationBundle = VerificationBundleService.load(pedido.bundle)
    except Exception as erro:  # noqa: BLE001 — material irrepresentável é 422
        return _problem(
            request,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "MALFORMED_BUNDLE",
            "Pacote não interpretável",
            _sanitize(str(erro)),
        )

    if pacote.manifest.format_version != 1:
        return _problem(
            request,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "UNSUPPORTED_BUNDLE_VERSION",
            "Versão de pacote não suportada",
            f"Versão de formato {pacote.manifest.format_version} não é suportada.",
        )

    ancoras = {a.anchor_id: a.value for a in pedido.trust_anchors}
    verificado_em = datetime.now(UTC)
    relatorio = BundleVerifier().verify(
        pacote, verified_at=verificado_em, trust_anchors=ancoras or None
    )

    return JSONResponse(
        content=_render(relatorio, pedido, pacote, verificado_em),
        status_code=status.HTTP_200_OK,
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


def _sanitize(mensagem: str) -> str:
    """Detalhe é explicativo e não pode vazar caminho interno nem stack trace."""
    primeira = mensagem.splitlines()[0] if mensagem else "Estrutura inválida."
    if "\\" in primeira or "/" in primeira or "Traceback" in primeira:
        return "Estrutura inválida para este contrato."
    return primeira[:200]


def _render(
    relatorio: ValidationReport,
    pedido: VerificationRequest,
    pacote: VerificationBundle,
    verificado_em: datetime,
) -> dict[str, Any]:
    por_dimensao = {r.dimension: r for r in relatorio.results}
    dimensoes = [
        {
            "dimension": d.value,
            "status": por_dimensao[d].status.value,
            "reason_code": por_dimensao[d].reason_code.value.upper(),
            "failure_point": por_dimensao[d].failure_point or None,
            "mandatory": d in MANDATORY_DIMENSIONS,
            "detail": por_dimensao[d].detail,
        }
        for d in NORMATIVE_DIMENSION_ORDER
        if d in por_dimensao
    ]

    return {
        "contract_version": CONTRACT_VERSION,
        "verification_profile": VERIFICATION_PROFILE,
        "engine": {"name": ENGINE_NAME, "version": ENGINE_VERSION},
        "bundle_reference": {
            "bundle_id": str(pacote.manifest.bundle_id.value),
            "bundle_digest": f"sha256:{_bundle_digest(pedido.bundle)}",
        },
        "aggregate_status": relatorio.status.value,
        "verified_at": verificado_em.isoformat(),
        "reference_instant": pacote.manifest.created_at.isoformat(),
        "trust_anchors_used": [
            {
                "origin": "CALLER_SUPPLIED",
                "anchor_id": a.anchor_id,
                "algorithm": a.algorithm.upper(),
                "fingerprint": f"sha256:{compute_digest(a.value.encode('utf-8'))}",
            }
            for a in pedido.trust_anchors
        ],
        "declared_scopes": list(pacote.manifest.declared_scopes),
        "examined_components": sorted(pacote.payloads),
        "dimensions": dimensoes,
        "failures": [
            {
                "dimension": f.dimension.value,
                "reason_code": f.reason_code.value.upper(),
                "failure_point": f.failure_point or None,
            }
            for f in relatorio.failures
        ],
        "first_failure": (
            {
                "dimension": relatorio.first_failure.dimension.value,
                "reason_code": relatorio.first_failure.reason_code.value.upper(),
                "failure_point": relatorio.first_failure.failure_point or None,
            }
            if relatorio.first_failure is not None
            else None
        ),
        "gaps": list(pacote.manifest.declared_gaps),
        "warnings": [],
        "limitations": _limitations(relatorio),
    }
