"""Listagem e detalhe das entidades da vertical (Marco 12).

A API do Marco 10 só criava e lia por identificador: quem cadastrasse um animal e
perdesse o UUID não o alcançava mais. Nenhuma interface funciona assim — a
primeira tela de qualquer aplicação é uma lista.

**Toda listagem é paginada e escopada pela organização do contexto.** O
`organization_id` nunca vem do cliente: vem do contexto já resolvido, e o RLS
confirma no banco. Aceitar organização por parâmetro seria oferecer ao chamador
a chance de pedir dados de outra.
"""

import json
from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from apps.api.geodata_dependencies import car_lookup_opcional
from apps.api.livestock_dependencies import (
    ConnectionDependency,
    require_permission,
    typed_id_or_problem,
)
from apps.api.pagination import Pagina, PaginacaoDependency, montar_pagina
from apps.api.problem import RESPOSTAS_PADRAO, DomainProblem
from packages.core_application.relation_service import RelationService
from packages.core_domain import OrganizationContext
from packages.core_infrastructure.persistence.events import DomainEventRepository
from packages.core_infrastructure.persistence.relations import TransactionalRelationRepository
from packages.livestock_application.authorization import (
    ANIMAL_LER,
    ANIMAL_LER_GENEALOGIA,
    LOT_LER,
    MEDICATION_LER,
    MOVEMENT_LER,
    PROPERTY_LER,
    PROPERTY_LER_GEOMETRIA,
    REPRODUCTION_LER,
    TREATMENT_LER,
    VETERINARIAN_LER,
)
from packages.livestock_application.environmental_embargo_assertion_service import (
    EnvironmentalEmbargoAssertionService,
)
from packages.livestock_application.environmental_embargo_service import (
    EnvironmentalEmbargoAssessment,
    EnvironmentalEmbargoService,
)
from packages.livestock_application.event_recorder import LivestockEventRecorder
from packages.livestock_application.geometry_service import PropertyGeometryService
from packages.livestock_application.parentage_service import (
    GERACOES_MAXIMAS,
    GERACOES_PADRAO,
    ParentageService,
)
from packages.livestock_application.territorial_overlap_service import (
    PropertyTerritorialOverlapAssessment,
    TerritorialOverlapService,
)
from packages.livestock_application.territorial_timeline_service import (
    PropertyTerritorialTimelineAssessment,
    TerritorialTimelineService,
)
from packages.livestock_domain.geometry import CAMADA_PERIMETRO
from packages.livestock_infrastructure.geodata import (
    CarNaoEncontrado,
    GeodataIndisponivel,
    GeodataNaoConfigurado,
)
from packages.livestock_infrastructure.persistence import (
    TransactionalPropertyEnvironmentalEmbargoAssertionRepository,
)
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.livestock_infrastructure.persistence.external_counterparty_repository import (
    TransactionalExternalCounterpartyRepository,
)
from packages.livestock_infrastructure.persistence.geometry_repository import (
    TransactionalPropertyGeometryRepository,
)
from packages.livestock_infrastructure.persistence.imported_fact_repository import (
    TransactionalImportedLivestockFactRepository,
)
from packages.livestock_infrastructure.persistence.lot_repository import (
    TransactionalLivestockLotRepository,
    TransactionalLotMembershipRepository,
)
from packages.livestock_infrastructure.persistence.medication_repository import (
    TransactionalMedicationBatchRepository,
    TransactionalMedicationRepository,
)
from packages.livestock_infrastructure.persistence.movement_repository import (
    TransactionalAnimalMovementRepository,
)
from packages.livestock_infrastructure.persistence.property_repository import (
    TransactionalRuralPropertyRepository,
)
from packages.livestock_infrastructure.persistence.reproduction_repository import (
    TransactionalReproductiveEventRepository,
)
from packages.livestock_infrastructure.persistence.transfer_artifact_repository import (
    TransactionalReceivedTransferArtifactRepository,
)
from packages.livestock_infrastructure.persistence.treatment_repository import (
    TransactionalTreatmentApplicationRepository,
)
from packages.livestock_infrastructure.persistence.veterinarian_repository import (
    TransactionalVeterinarianRepository,
)
from packages.shared_kernel import SystemClock

router = APIRouter(prefix="/v1/livestock", tags=["livestock"])


def _nao_encontrado(o_que: str) -> DomainProblem:
    """Inexistente e de outra organização respondem igual, sempre.

    Distinguir transformaria a resposta em oráculo: bastaria tentar
    identificadores para descobrir o que existe fora do alcance de quem pergunta.
    """
    return DomainProblem(
        status_code=status.HTTP_404_NOT_FOUND,
        reason_code="RECURSO_NAO_ENCONTRADO",
        title="Recurso não encontrado",
        detail=f"{o_que} não encontrado nesta organização.",
    )


# -- Representações ----------------------------------------------------------


class SaidaResumo(BaseModel):
    exit_id: str
    exit_type: str
    occurred_at: datetime
    reason: str | None
    destination: str | None
    destination_counterparty_id: str | None


class ContraparteExternaResumo(BaseModel):
    counterparty_id: str
    name: str
    counterparty_type: str
    identifiers: list[str]
    notes: str | None
    created_at: datetime


class AnimalResumo(BaseModel):
    animal_id: str
    sex: str
    breed: str | None
    birth_date: date | None
    # Nulo quando o parto não teve propriedade determinável (ADR-0040). A
    # procedência ao lado diz se o valor foi derivado, declarado ou é desconhecido.
    birth_property_id: str | None
    birth_property_source: str
    birth_outcome: str
    identifiers: list[dict[str, Any]]
    created_at: datetime
    # Nulo quando o animal está no rebanho. Na listagem padrão é nulo em toda
    # linha por construção, já que só o rebanho ativo é devolvido.
    saida: SaidaResumo | None = None


class PropriedadeResumo(BaseModel):
    property_id: str
    code: str
    name: str
    municipality: str
    state_code: str
    registration_number: str | None
    total_area_hectares: float | None


class MedicamentoResumo(BaseModel):
    medication_id: str
    trade_name: str
    active_ingredient: str
    manufacturer: str
    withdrawal_period_days: int
    product_class: str
    dosage_instruction: str | None


class LoteResumo(BaseModel):
    batch_id: str
    medication_id: str
    batch_number: str
    expiry_date: datetime
    manufacturing_date: datetime | None


class TratamentoResumo(BaseModel):
    application_id: str
    animal_id: str
    medication_batch_id: str
    applied_at: datetime
    dose: str | None
    prescription_id: str | None
    sanitary_campaign_id: str | None
    corrects_application_id: str | None
    evidence_ids: list[str]
    evidence_notes: list[str]


class LoteAnimaisResumo(BaseModel):
    lot_id: str
    property_id: str
    code: str
    name: str
    lot_type: str
    status: str


class VeterinarioResumo(BaseModel):
    veterinarian_id: str
    name: str
    council_number: str
    council_state: str
    verification_status: str


class MovimentacaoResumo(BaseModel):
    movement_id: str
    origin_property_id: str
    destination_property_id: str
    movement_time: datetime
    animal_ids: list[str]
    reason: str | None


class LacunaTransferenciaResumo(BaseModel):
    code: str
    starts_at: datetime | None
    ends_at: datetime | None
    description: str


class CoberturaTransferenciaResumo(BaseModel):
    known_from: datetime | None
    known_until: datetime | None
    gaps: list[LacunaTransferenciaResumo]


class ArtefatoTransferenciaResumo(BaseModel):
    artifact_id: str
    animal_id: str
    source_counterparty_id: str
    bundle_digest: str
    bundle_issued_at: datetime
    transfer_effective_at: datetime
    issuer_name: str | None
    coverage: CoberturaTransferenciaResumo


class FatoImportadoResumo(BaseModel):
    imported_fact_id: str
    animal_id: str
    source_artifact_id: str
    fact_type: str
    occurred_at: datetime
    asserted_by: str
    received_by: str
    origin: str
    confidence_tier: str
    payload: dict[str, Any]
    imported_at: datetime


# -- Conversões --------------------------------------------------------------


def _saida(registro: Any) -> SaidaResumo | None:
    if registro is None:
        return None
    return SaidaResumo(
        exit_id=str(registro.exit_id.value),
        exit_type=registro.exit_type.value,
        occurred_at=registro.occurred_at,
        reason=registro.reason,
        destination=registro.destination,
        destination_counterparty_id=(
            None
            if registro.destination_counterparty_id is None
            else str(registro.destination_counterparty_id.value)
        ),
    )


def _animal(entidade: Any, saida: Any = None) -> AnimalResumo:
    return AnimalResumo(
        animal_id=str(entidade.animal_id.value),
        sex=entidade.sex.value,
        breed=entidade.breed,
        birth_date=entidade.birth_date,
        birth_property_id=(
            None if entidade.birth_property_id is None else str(entidade.birth_property_id.value)
        ),
        birth_property_source=entidade.birth_property_source.value,
        birth_outcome=entidade.birth_outcome.value,
        identifiers=[
            {
                "identifier_id": str(tag.identifier_id.value),
                "type": tag.identifier_type.value,
                "value": tag.identifier_value,
                "state": tag.state.value,
            }
            for tag in entidade.identifiers
        ],
        created_at=entidade.created_at,
        saida=_saida(saida),
    )


def _propriedade(entidade: Any) -> PropriedadeResumo:
    return PropriedadeResumo(
        property_id=str(entidade.property_id.value),
        code=entidade.code,
        name=entidade.name,
        municipality=entidade.municipality,
        state_code=entidade.state_code,
        registration_number=entidade.registration_number,
        total_area_hectares=entidade.total_area_hectares,
    )


def _medicamento(entidade: Any) -> MedicamentoResumo:
    return MedicamentoResumo(
        medication_id=str(entidade.medication_id.value),
        trade_name=entidade.trade_name,
        active_ingredient=entidade.active_ingredient,
        manufacturer=entidade.manufacturer,
        withdrawal_period_days=entidade.withdrawal_period_days,
        product_class=entidade.product_class.value,
        dosage_instruction=entidade.dosage_instruction,
    )


def _lote_medicamento(entidade: Any) -> LoteResumo:
    return LoteResumo(
        batch_id=str(entidade.batch_id.value),
        medication_id=str(entidade.medication_id.value),
        batch_number=entidade.batch_number,
        expiry_date=entidade.expiry_date,
        manufacturing_date=entidade.manufacturing_date,
    )


def _tratamento(entidade: Any) -> TratamentoResumo:
    return TratamentoResumo(
        application_id=str(entidade.application_id.value),
        animal_id=str(entidade.animal_id.value),
        medication_batch_id=str(entidade.medication_batch_id.value),
        applied_at=entidade.applied_at,
        dose=entidade.dose,
        prescription_id=(str(entidade.prescription_id.value) if entidade.prescription_id else None),
        sanitary_campaign_id=(
            str(entidade.sanitary_campaign_id.value) if entidade.sanitary_campaign_id else None
        ),
        corrects_application_id=(
            str(entidade.corrects_application_id.value)
            if entidade.corrects_application_id
            else None
        ),
        evidence_ids=[str(r.target_id.value) for r in entidade.evidence_references],
        evidence_notes=list(entidade.evidence_notes),
    )


def _lote_animais(entidade: Any) -> LoteAnimaisResumo:
    return LoteAnimaisResumo(
        lot_id=str(entidade.lot_id.value),
        property_id=str(entidade.property_id.value),
        code=entidade.code,
        name=entidade.name,
        lot_type=entidade.lot_type.value,
        status=entidade.status.value,
    )


def _veterinario(entidade: Any) -> VeterinarioResumo:
    """O CPF não sai na API: identifica pessoa natural e não é necessário à consulta."""
    return VeterinarioResumo(
        veterinarian_id=str(entidade.veterinarian_id.value),
        name=entidade.name,
        council_number=entidade.council_number,
        council_state=entidade.council_state,
        verification_status=entidade.verification_status.value,
    )


def _movimentacao(entidade: Any) -> MovimentacaoResumo:
    return MovimentacaoResumo(
        movement_id=str(entidade.movement_id.value),
        origin_property_id=str(entidade.origin_property_id.value),
        destination_property_id=str(entidade.destination_property_id.value),
        movement_time=entidade.movement_time,
        animal_ids=[str(a.value) for a in entidade.animal_ids],
        reason=entidade.reason,
    )


def _contraparte_externa(entidade: Any) -> ContraparteExternaResumo:
    return ContraparteExternaResumo(
        counterparty_id=str(entidade.counterparty_id.value),
        name=entidade.name,
        counterparty_type=entidade.counterparty_type.value,
        identifiers=list(entidade.identifiers),
        notes=entidade.notes,
        created_at=entidade.created_at,
    )


def _artefato_transferencia(entidade: Any) -> ArtefatoTransferenciaResumo:
    return ArtefatoTransferenciaResumo(
        artifact_id=str(entidade.artifact_id.value),
        animal_id=str(entidade.animal_id.value),
        source_counterparty_id=str(entidade.source_counterparty_id.value),
        bundle_digest=entidade.bundle_digest,
        bundle_issued_at=entidade.bundle_issued_at,
        transfer_effective_at=entidade.transfer_effective_at,
        issuer_name=entidade.issuer_name,
        coverage=CoberturaTransferenciaResumo(
            known_from=entidade.coverage.known_from,
            known_until=entidade.coverage.known_until,
            gaps=[
                LacunaTransferenciaResumo(
                    code=gap.code.value,
                    starts_at=gap.starts_at,
                    ends_at=gap.ends_at,
                    description=gap.description,
                )
                for gap in entidade.coverage.gaps
            ],
        ),
    )


def _fato_importado(entidade: Any) -> FatoImportadoResumo:
    return FatoImportadoResumo(
        imported_fact_id=str(entidade.imported_fact_id.value),
        animal_id=str(entidade.animal_id.value),
        source_artifact_id=str(entidade.source_artifact_id.value),
        fact_type=entidade.fact_type,
        occurred_at=entidade.occurred_at,
        asserted_by=entidade.asserted_by,
        received_by=str(entidade.received_by.value),
        origin=entidade.origin.value,
        confidence_tier=entidade.confidence_tier.value,
        payload=dict(entidade.payload),
        imported_at=entidade.imported_at,
    )


# -- Contrapartes externas ---------------------------------------------------


@router.get(
    "/external-counterparties",
    response_model=Pagina[ContraparteExternaResumo],
    summary="Listar contrapartes externas locais",
    responses=RESPOSTAS_PADRAO,
)
def listar_contrapartes_externas(
    contexto: Annotated[OrganizationContext, Depends(require_permission(ANIMAL_LER))],
    paginacao: PaginacaoDependency,
    connection: ConnectionDependency,
) -> Any:
    repositorio = TransactionalExternalCounterpartyRepository(connection=connection)
    encontrados = repositorio.list_by_organization(contexto.organization_id)
    janela = encontrados[paginacao.offset : paginacao.offset + paginacao.limite_de_sondagem]
    return montar_pagina([_contraparte_externa(item) for item in janela], paginacao)


@router.get(
    "/animals/{animal_id}/received-transfer-artifacts",
    response_model=Pagina[ArtefatoTransferenciaResumo],
    summary="Listar artefatos recebidos de transferência do animal",
    responses=RESPOSTAS_PADRAO,
)
def listar_artefatos_transferencia(
    animal_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(ANIMAL_LER))],
    paginacao: PaginacaoDependency,
    connection: ConnectionDependency,
) -> Any:
    alvo = typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id")
    animal = TransactionalAnimalRepository(connection=connection).get_by_id(alvo)
    if animal is None or animal.organization_id != contexto.organization_id:
        raise _nao_encontrado("Animal")
    repositorio = TransactionalReceivedTransferArtifactRepository(connection=connection)
    encontrados = repositorio.list_by_animal(alvo)
    janela = encontrados[paginacao.offset : paginacao.offset + paginacao.limite_de_sondagem]
    return montar_pagina([_artefato_transferencia(item) for item in janela], paginacao)


@router.get(
    "/animals/{animal_id}/imported-facts",
    response_model=Pagina[FatoImportadoResumo],
    summary="Listar fatos importados do animal",
    responses=RESPOSTAS_PADRAO,
)
def listar_fatos_importados(
    animal_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(ANIMAL_LER))],
    paginacao: PaginacaoDependency,
    connection: ConnectionDependency,
) -> Any:
    alvo = typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id")
    animal = TransactionalAnimalRepository(connection=connection).get_by_id(alvo)
    if animal is None or animal.organization_id != contexto.organization_id:
        raise _nao_encontrado("Animal")
    repositorio = TransactionalImportedLivestockFactRepository(connection=connection)
    encontrados = repositorio.list_by_animal(contexto.organization_id, alvo)
    janela = encontrados[paginacao.offset : paginacao.offset + paginacao.limite_de_sondagem]
    return montar_pagina([_fato_importado(item) for item in janela], paginacao)


# -- Animais -----------------------------------------------------------------


@router.get(
    "/animals",
    response_model=Pagina[AnimalResumo],
    summary="Listar animais",
    description=(
        "Devolve o **rebanho ativo**. Quem lista animais quer o rebanho, e não o "
        "histórico inteiro: incluir por padrão quem já morreu, foi abatido ou "
        "vendido enviesaria toda tela e todo relatório. Use "
        "`incluir_saidos=true` para o levantamento histórico — aí cada linha traz "
        "o objeto `saida` preenchido para quem já deixou o rebanho."
    ),
    responses=RESPOSTAS_PADRAO,
)
def listar_animais(
    contexto: Annotated[OrganizationContext, Depends(require_permission(ANIMAL_LER))],
    paginacao: PaginacaoDependency,
    connection: ConnectionDependency,
    incluir_saidos: bool = False,
) -> Any:
    repositorio = TransactionalAnimalRepository(connection=connection)
    encontrados = repositorio.list_by_organization(
        contexto.organization_id,
        limit=paginacao.limite_de_sondagem,
        offset=paginacao.offset,
        include_exited=incluir_saidos,
    )
    # A consulta por animal só acontece quando os saídos foram pedidos, e no
    # máximo uma vez por linha da página. Na listagem padrão não há o que buscar:
    # todo animal devolvido está no rebanho.
    return montar_pagina(
        [
            _animal(item, repositorio.get_exit(item.animal_id) if incluir_saidos else None)
            for item in encontrados
        ],
        paginacao,
    )


@router.get(
    "/animals/{animal_id}",
    response_model=AnimalResumo,
    summary="Detalhar um animal",
    responses=RESPOSTAS_PADRAO,
)
def detalhar_animal(
    animal_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(ANIMAL_LER))],
    connection: ConnectionDependency,
) -> AnimalResumo:
    alvo = typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id")
    repositorio = TransactionalAnimalRepository(connection=connection)
    encontrado = repositorio.get_by_id(alvo)
    if encontrado is None or encontrado.organization_id != contexto.organization_id:
        raise _nao_encontrado("Animal")
    # O detalhe sempre diz se o animal saiu: quem pergunta por um animal
    # específico precisa saber se ele ainda existe no rebanho.
    return _animal(encontrado, repositorio.get_exit(alvo))


# -- Genealogia --------------------------------------------------------------


class VinculoResumo(BaseModel):
    relation_id: str
    parent_id: str
    offspring_id: str
    role: str
    confidence: str | None
    confidence_reason: str
    occurred_at: datetime | None


class AscendenciaResumo(BaseModel):
    animal_id: str
    parents: list["RamoResumo"]


class RamoResumo(BaseModel):
    link: VinculoResumo
    ancestry: AscendenciaResumo


def _vinculo_resumo(link: Any) -> VinculoResumo:
    return VinculoResumo(
        relation_id=str(link.relation_id.value),
        parent_id=str(link.parent_id.value),
        offspring_id=str(link.offspring_id.value),
        role=link.role.value,
        confidence=None if link.confidence is None else link.confidence.value,
        confidence_reason=link.confidence_reason,
        occurred_at=link.occurred_at,
    )


def _ascendencia(no: Any) -> AscendenciaResumo:
    return AscendenciaResumo(
        animal_id=str(no.animal_id.value),
        parents=[
            RamoResumo(link=_vinculo_resumo(ramo.link), ancestry=_ascendencia(ramo.ancestry))
            for ramo in no.parents
        ],
    )


def _genealogia(connection: Any) -> ParentageService:
    """O serviço é um só, e a leitura o monta inteiro.

    Um segundo serviço só de leitura duplicaria a travessia e as regras de qual
    papel compõe a linhagem — e as duas cópias divergiriam na primeira mudança.
    O gravador de eventos entra pronto e simplesmente não é acionado aqui.
    """
    return ParentageService(
        relation_service=RelationService(
            repository=TransactionalRelationRepository(connection=connection)
        ),
        animal_repository=TransactionalAnimalRepository(connection=connection),
        recorder=LivestockEventRecorder(
            event_log=DomainEventRepository(connection=connection), clock=SystemClock()
        ),
    )


@router.get(
    "/animals/{animal_id}/ancestry",
    response_model=AscendenciaResumo,
    summary="Consultar a ascendência de um animal",
    description=(
        "Sobe pela **linhagem genética** — mãe doadora e pai. A mãe gestacional "
        "fica de fora: quem gestou não transmitiu genes, e incluí-la daria à árvore "
        "ancestrais que não são. Use `/reproduction` para o histórico da receptora."
    ),
    responses=RESPOSTAS_PADRAO,
)
def consultar_ascendencia(
    animal_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(ANIMAL_LER_GENEALOGIA))],
    connection: ConnectionDependency,
    geracoes: int = Query(default=GERACOES_PADRAO, ge=1, le=GERACOES_MAXIMAS),
) -> AscendenciaResumo:
    alvo = typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id")
    arvore = _genealogia(connection).ancestry(
        organization_id=contexto.organization_id, animal_id=alvo, generations=geracoes
    )
    return _ascendencia(arvore)


@router.get(
    "/animals/{animal_id}/descendants",
    response_model=list[VinculoResumo],
    summary="Consultar as crias diretas de um animal",
    responses=RESPOSTAS_PADRAO,
)
def consultar_descendencia(
    animal_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(ANIMAL_LER_GENEALOGIA))],
    connection: ConnectionDependency,
) -> list[VinculoResumo]:
    alvo = typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id")
    return [
        _vinculo_resumo(link)
        for link in _genealogia(connection).descendants(contexto.organization_id, alvo)
    ]


@router.get(
    "/animals/{animal_id}/reproduction",
    response_model=list[VinculoResumo],
    summary="Consultar as crias que esta fêmea gestou",
    description=(
        "Pergunta distinta da descendência: uma receptora gestou bezerros que não descendem dela."
    ),
    responses=RESPOSTAS_PADRAO,
)
def consultar_historico_reprodutivo(
    animal_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(ANIMAL_LER_GENEALOGIA))],
    connection: ConnectionDependency,
) -> list[VinculoResumo]:
    alvo = typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id")
    return [
        _vinculo_resumo(link)
        for link in _genealogia(connection).gestational_history(contexto.organization_id, alvo)
    ]


# -- Reprodução --------------------------------------------------------------


class CriaResumo(BaseModel):
    animal_id: str
    outcome: str


class EventoReprodutivoResumo(BaseModel):
    event_id: str
    dam_id: str
    sire_id: str | None
    event_type: str
    occurred_at: datetime
    gestational_age_days: int | None
    gestational_age_basis: str
    notes: str | None
    offspring: list[CriaResumo]


def _evento_reprodutivo_resumo(evento: Any) -> EventoReprodutivoResumo:
    return EventoReprodutivoResumo(
        event_id=str(evento.event_id.value),
        dam_id=str(evento.dam_id.value),
        sire_id=None if evento.sire_id is None else str(evento.sire_id.value),
        event_type=evento.event_type.value,
        occurred_at=evento.occurred_at,
        gestational_age_days=evento.gestational_age_days,
        gestational_age_basis=evento.gestational_age_basis.value,
        notes=evento.notes,
        offspring=[
            CriaResumo(animal_id=str(cria.animal_id.value), outcome=cria.outcome.value)
            for cria in evento.offspring
        ],
    )


@router.get(
    "/animals/{animal_id}/reproductive-events",
    response_model=list[EventoReprodutivoResumo],
    summary="Consultar os eventos reprodutivos de uma matriz",
    description=(
        "Partos e perdas gestacionais em ordem cronológica. É a base do índice "
        "reprodutivo: cem gestações que se resolvem em nascidos vivos, natimortos "
        "e abortos, cada um contado pelo que foi."
    ),
    responses=RESPOSTAS_PADRAO,
)
def consultar_eventos_reprodutivos(
    animal_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(REPRODUCTION_LER))],
    connection: ConnectionDependency,
) -> list[EventoReprodutivoResumo]:
    alvo = typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id")
    encontrados = TransactionalReproductiveEventRepository(connection=connection).list_by_dam(
        contexto.organization_id, alvo
    )
    return [_evento_reprodutivo_resumo(evento) for evento in encontrados]


@router.get(
    "/animals/{animal_id}/origin",
    response_model=EventoReprodutivoResumo | None,
    summary="Consultar o parto de onde este animal veio",
    description=(
        "A origem comprovável da identidade do animal. Devolve `null` para o "
        "rebanho legado, cadastrado sem parto registrado — o que é uma resposta "
        "honesta, e não uma falha."
    ),
    responses=RESPOSTAS_PADRAO,
)
def consultar_origem(
    animal_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(REPRODUCTION_LER))],
    connection: ConnectionDependency,
) -> EventoReprodutivoResumo | None:
    alvo = typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id")
    encontrado = TransactionalReproductiveEventRepository(connection=connection).get_by_offspring(
        alvo
    )
    if encontrado is None or encontrado.organization_id != contexto.organization_id:
        return None
    return _evento_reprodutivo_resumo(encontrado)


# -- Geometria da propriedade ------------------------------------------------


class GeometriaResumo(BaseModel):
    geometry_id: str
    property_id: str
    source: str
    layer: str
    srid: int
    source_digest: str
    external_reference: str | None
    version: int
    captured_at: datetime | None
    imported_at: datetime
    geojson: dict[str, Any]


def _geometria_resumo(registro: Any) -> GeometriaResumo:
    return GeometriaResumo(
        geometry_id=str(registro.geometry_id.value),
        property_id=str(registro.property_id.value),
        source=registro.source.value,
        layer=registro.layer,
        srid=registro.srid,
        source_digest=registro.source_digest,
        external_reference=registro.external_reference,
        version=registro.version,
        captured_at=registro.captured_at,
        imported_at=registro.imported_at,
        # O material como foi recebido, e não uma reserialização: é sobre ele que
        # o digest foi calculado, e devolver outra coisa quebraria a conferência.
        geojson=json.loads(registro.source_payload),
    )


def _geometria_servico(connection: Any) -> PropertyGeometryService:
    return PropertyGeometryService(
        geometry_repository=TransactionalPropertyGeometryRepository(connection=connection),
        property_repository=TransactionalRuralPropertyRepository(connection=connection),
        recorder=LivestockEventRecorder(
            event_log=DomainEventRepository(connection=connection), clock=SystemClock()
        ),
        car_lookup=car_lookup_opcional(),
    )


def _embargo_ambiental_servico(connection: Any) -> EnvironmentalEmbargoService:
    cliente = car_lookup_opcional()
    if cliente is None:
        raise GeodataNaoConfigurado(
            "Avaliacao espacial exige TITAN_GEODATA_URL e TITAN_GEODATA_API_KEY."
        )
    return EnvironmentalEmbargoService(
        property_repository=TransactionalRuralPropertyRepository(connection=connection),
        geometry_repository=TransactionalPropertyGeometryRepository(connection=connection),
        geodata_lookup=cliente,
    )


def _embargo_assertion_servico(connection: Any) -> EnvironmentalEmbargoAssertionService:
    return EnvironmentalEmbargoAssertionService(
        assessment_service=_embargo_ambiental_servico(connection),
        repository=TransactionalPropertyEnvironmentalEmbargoAssertionRepository(
            connection=connection
        ),
        recorder=LivestockEventRecorder(
            event_log=DomainEventRepository(connection=connection),
            clock=SystemClock(),
        ),
    )


def _timeline_territorial_servico(connection: Any) -> TerritorialTimelineService:
    cliente = car_lookup_opcional()
    if cliente is None:
        raise GeodataNaoConfigurado(
            "Consulta territorial exige TITAN_GEODATA_URL e TITAN_GEODATA_API_KEY."
        )
    return TerritorialTimelineService(
        property_repository=TransactionalRuralPropertyRepository(connection=connection),
        geometry_repository=TransactionalPropertyGeometryRepository(connection=connection),
        geodata_lookup=cliente,
    )


def _sobreposicao_territorial_servico(connection: Any) -> TerritorialOverlapService:
    cliente = car_lookup_opcional()
    if cliente is None:
        raise GeodataNaoConfigurado(
            "Consulta territorial exige TITAN_GEODATA_URL e TITAN_GEODATA_API_KEY."
        )
    return TerritorialOverlapService(
        property_repository=TransactionalRuralPropertyRepository(connection=connection),
        geometry_repository=TransactionalPropertyGeometryRepository(connection=connection),
        geodata_lookup=cliente,
    )


def _resumo_embargo_ambiental(
    assessment: EnvironmentalEmbargoAssessment,
) -> "AvaliacaoEmbargoAmbientalResponse":
    return AvaliacaoEmbargoAmbientalResponse(
        property_id=str(assessment.property_id.value),
        geometry_id=(None if assessment.geometry_id is None else str(assessment.geometry_id.value)),
        geometry_version=assessment.geometry_version,
        status=assessment.status.value,
        source=assessment.source,
        layer=assessment.layer,
        operation=assessment.operation,
        source_digest=assessment.source_digest,
        response_digest=assessment.response_digest,
        version_ids=list(assessment.version_ids),
        restriction_count=assessment.restriction_count,
        restrictions=[
            RestricaoEspacialResumo(
                source=item.source,
                layer=item.layer,
                feature_id=item.feature_id,
                version_id=item.version_id,
                polygon_digest=item.polygon_digest,
                geojson=json.loads(item.polygon_payload),
                attributes=item.attributes,
            )
            for item in assessment.restrictions
        ],
        gaps=[gap.to_dict() for gap in assessment.gaps],
    )


def _resumo_embargo_assertion(registro: Any) -> "EmbargoAmbientalAssertionResumo":
    return EmbargoAmbientalAssertionResumo(
        assertion_id=str(registro.assertion_id.value),
        property_id=str(registro.property_id.value),
        geometry_id=(None if registro.geometry_id is None else str(registro.geometry_id.value)),
        geometry_version=registro.geometry_version,
        source_name=registro.source_name,
        source_layer=registro.source_layer,
        operation=registro.operation,
        status=registro.status.value,
        source_digest=registro.source_digest,
        response_digest=registro.response_digest,
        version_ids=list(registro.version_ids),
        restriction_count=registro.restriction_count,
        restrictions=[
            RestricaoEspacialGravadaResumo(
                source=str(item.get("source", "")),
                layer=str(item.get("layer", "")),
                feature_id=(
                    int(item["feature_id"]) if isinstance(item.get("feature_id"), int) else None
                ),
                version_id=(
                    str(item["version_id"]) if item.get("version_id") is not None else None
                ),
                polygon_digest=str(item.get("polygon_digest", "")),
                attributes=dict(item.get("attributes") or {}),
            )
            for item in registro.restrictions_payload
        ],
        observed_at=registro.observed_at,
        recorded_at=registro.recorded_at,
    )


def _ano_resumo_territorial(item: dict[str, Any]) -> "TimelineTerritorialAnoResumo":
    ano = item.get("year")
    quantidade = item.get("feature_count", 0)
    area_sobreposta = item.get("overlap_area_hectares")
    area_fonte = item.get("source_area_hectares")
    versoes = item.get("version_ids", [])
    return TimelineTerritorialAnoResumo(
        year=(ano if isinstance(ano, int) else None),
        feature_count=(int(quantidade) if isinstance(quantidade, int | float | str) else 0),
        overlap_area_hectares=(
            float(area_sobreposta) if isinstance(area_sobreposta, int | float) else None
        ),
        source_area_hectares=(float(area_fonte) if isinstance(area_fonte, int | float) else None),
        version_ids=[
            str(version_id)
            for version_id in (versoes if isinstance(versoes, list) else [])
            if version_id
        ],
    )


def _resumo_timeline_territorial(
    assessment: PropertyTerritorialTimelineAssessment,
) -> "TimelineTerritorialResponse":
    return TimelineTerritorialResponse(
        property_id=str(assessment.property_id.value),
        geometry_id=(None if assessment.geometry_id is None else str(assessment.geometry_id.value)),
        geometry_version=assessment.geometry_version,
        external_reference=assessment.external_reference,
        status=assessment.status.value,
        source=assessment.source,
        layer=assessment.layer,
        property_area_hectares=assessment.property_area_hectares,
        year_from=assessment.year_from,
        year_to=assessment.year_to,
        years=[_ano_resumo_territorial(item) for item in assessment.years],
        response_digest=assessment.response_digest,
        gaps=[gap.to_dict() for gap in assessment.gaps],
    )


def _resumo_sobreposicao_territorial(
    assessment: PropertyTerritorialOverlapAssessment,
) -> "SobreposicaoTerritorialResponse":
    return SobreposicaoTerritorialResponse(
        property_id=str(assessment.property_id.value),
        geometry_id=(None if assessment.geometry_id is None else str(assessment.geometry_id.value)),
        geometry_version=assessment.geometry_version,
        external_reference=assessment.external_reference,
        status=assessment.status.value,
        source=assessment.source,
        layer=assessment.layer,
        label=assessment.label,
        feature_count=assessment.feature_count,
        area_hectares=assessment.area_hectares,
        source_area_hectares=assessment.source_area_hectares,
        version_ids=list(assessment.version_ids),
        response_digest=assessment.response_digest,
        gaps=[gap.to_dict() for gap in assessment.gaps],
    )


@router.get(
    "/properties/{property_id}/geometry",
    response_model=GeometriaResumo | None,
    summary="Consultar a geometria vigente de uma propriedade",
    description=(
        "Devolve `null` quando a propriedade não tem limite registrado — resposta "
        "honesta e não impeditiva: propriedade sem geometria continua operando, e "
        "a lacuna aparece declarada em vez de bloquear.\n\n"
        "Exige permissão própria: o polígono revela onde a operação fica, e ler o "
        "cadastro da propriedade não implica ler o limite dela."
    ),
    responses=RESPOSTAS_PADRAO,
)
def consultar_geometria(
    property_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(PROPERTY_LER_GEOMETRIA))],
    connection: ConnectionDependency,
    layer: str = Query(default=CAMADA_PERIMETRO, max_length=60),
) -> GeometriaResumo | None:
    alvo = typed_id_or_problem(property_id, entity_type="rural_property", campo="property_id")
    encontrada = _geometria_servico(connection).current_for(contexto.organization_id, alvo, layer)
    return None if encontrada is None else _geometria_resumo(encontrada)


@router.get(
    "/properties/{property_id}/geometry/layers",
    response_model=list[GeometriaResumo],
    summary="Consultar a versao vigente de cada camada do imovel",
    description=(
        "Perimetro, reserva legal, APP, hidrografia — o que o CAR declarar sobre "
        "aquele imovel.\n\n"
        "**Sao camadas DO IMOVEL.** Embargo, terra indigena e alerta de "
        "desmatamento existem independentemente de qualquer propriedade e nao "
        "vivem aqui: a pergunta que elas respondem e se a fazenda intersecta "
        "aquela area, e nao qual e a area da fazenda."
    ),
    responses=RESPOSTAS_PADRAO,
)
def consultar_camadas(
    property_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(PROPERTY_LER_GEOMETRIA))],
    connection: ConnectionDependency,
) -> list[GeometriaResumo]:
    alvo = typed_id_or_problem(property_id, entity_type="rural_property", campo="property_id")
    return [
        _geometria_resumo(geometria)
        for geometria in _geometria_servico(connection).layers_of(contexto.organization_id, alvo)
    ]


@router.get(
    "/properties/{property_id}/geometry/history",
    response_model=list[GeometriaResumo],
    summary="Consultar todas as versões da geometria",
    description=(
        "Da mais antiga à mais recente. É por aqui que se responde qual polígono "
        "uma avaliação passada usou — pergunta que uma tabela sobrescrita não "
        "teria como responder."
    ),
    responses=RESPOSTAS_PADRAO,
)
def consultar_historico_de_geometria(
    property_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(PROPERTY_LER_GEOMETRIA))],
    connection: ConnectionDependency,
    layer: str | None = Query(default=None, max_length=60),
) -> list[GeometriaResumo]:
    alvo = typed_id_or_problem(property_id, entity_type="rural_property", campo="property_id")
    return [
        _geometria_resumo(geometria)
        for geometria in _geometria_servico(connection).history_of(
            contexto.organization_id, alvo, layer
        )
    ]


class CarPreviewResumo(BaseModel):
    """O que o CAR diz, para ajudar o cadastro. Nada aqui foi gravado."""

    cod_imovel: str
    state: str
    layer: str
    municipality: str | None
    state_code: str | None
    area_hectares: float | None
    registry_condition: str | None
    captured_at: datetime | None
    polygon_digest: str
    geojson: dict[str, Any]
    attributes: dict[str, Any]


class RestricaoEspacialResumo(BaseModel):
    source: str
    layer: str
    feature_id: int | None
    version_id: str | None
    polygon_digest: str
    geojson: dict[str, Any]
    attributes: dict[str, Any]


class AvaliacaoEmbargoAmbientalResponse(BaseModel):
    property_id: str
    geometry_id: str | None
    geometry_version: int | None
    status: str
    source: str
    layer: str
    operation: str
    source_digest: str | None
    response_digest: str | None
    version_ids: list[str]
    restriction_count: int
    restrictions: list[RestricaoEspacialResumo]
    gaps: list[dict[str, str]]


class RestricaoEspacialGravadaResumo(BaseModel):
    source: str
    layer: str
    feature_id: int | None
    version_id: str | None
    polygon_digest: str
    attributes: dict[str, Any]


class EmbargoAmbientalAssertionResumo(BaseModel):
    assertion_id: str
    property_id: str
    geometry_id: str | None
    geometry_version: int | None
    source_name: str
    source_layer: str
    operation: str
    status: str
    source_digest: str | None
    response_digest: str | None
    version_ids: list[str]
    restriction_count: int
    restrictions: list[RestricaoEspacialGravadaResumo]
    observed_at: datetime
    recorded_at: datetime


class TimelineTerritorialAnoResumo(BaseModel):
    year: int | None
    feature_count: int
    overlap_area_hectares: float | None
    source_area_hectares: float | None
    version_ids: list[str]


class TimelineTerritorialResponse(BaseModel):
    property_id: str
    geometry_id: str | None
    geometry_version: int | None
    external_reference: str | None
    status: str
    source: str
    layer: str
    property_area_hectares: float | None
    year_from: int | None
    year_to: int | None
    years: list[TimelineTerritorialAnoResumo]
    response_digest: str | None
    gaps: list[dict[str, str]]


class SobreposicaoTerritorialResponse(BaseModel):
    property_id: str
    geometry_id: str | None
    geometry_version: int | None
    external_reference: str | None
    status: str
    source: str
    layer: str
    label: str
    feature_count: int
    area_hectares: float | None
    source_area_hectares: float | None
    version_ids: list[str]
    response_digest: str | None
    gaps: list[dict[str, str]]


@router.get(
    "/properties/car-preview",
    response_model=CarPreviewResumo,
    summary="Consultar o CAR sem gravar nada",
    description=(
        "Serve para **pre-preencher o cadastro**: municipio, UF e area vindos da "
        "fonte evitam erro de digitacao. Nada e gravado, e o que o operador "
        "confirmar entra como declaracao dele. "
        "**Nao afirma titularidade.** O codigo informado pode ser de outro imovel, "
        "e o Titan nao infere propriedade juridica a partir de coordenadas. A "
        "condicao do cadastro diz onde ele esta na fila do SICAR, e nao se a "
        "propriedade esta regular."
    ),
    responses=RESPOSTAS_PADRAO,
)
def consultar_car(
    contexto: Annotated[OrganizationContext, Depends(require_permission(PROPERTY_LER_GEOMETRIA))],
    connection: ConnectionDependency,
    cod_imovel: str = Query(min_length=1, max_length=120),
    state: str = Query(min_length=2, max_length=2),
) -> CarPreviewResumo:
    try:
        imovel = _geometria_servico(connection).preview_car(cod_imovel, state)
    except CarNaoEncontrado as error:
        raise _nao_encontrado("Imovel no CAR") from error
    except GeodataNaoConfigurado as error:
        raise DomainProblem(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            reason_code="PROVIDER_NAO_CONFIGURADO",
            title="Consulta ao CAR indisponivel",
            detail=str(error),
        ) from error
    except GeodataIndisponivel as error:
        raise DomainProblem(
            status_code=status.HTTP_502_BAD_GATEWAY,
            reason_code="PROVIDER_INDISPONIVEL",
            title="O provider de geodados nao respondeu",
            detail=str(error),
        ) from error

    return CarPreviewResumo(
        cod_imovel=imovel.cod_imovel,
        state=imovel.state,
        layer=imovel.layer,
        municipality=imovel.municipality,
        state_code=imovel.state_code,
        area_hectares=imovel.area_hectares,
        registry_condition=imovel.registry_condition,
        captured_at=imovel.captured_at,
        polygon_digest=imovel.polygon_digest,
        geojson=json.loads(imovel.polygon_payload),
        attributes=imovel.attributes,
    )


@router.get(
    "/properties/{property_id}/environmental-embargoes/ibama",
    response_model=AvaliacaoEmbargoAmbientalResponse,
    summary="Avaliar embargos ambientais do IBAMA sobre a geometria vigente",
    description=(
        "Consulta o provider geoespacial configurado usando o poligono vigente da "
        "propriedade e devolve as feicoes do IBAMA que intersectam essa geometria.\n\n"
        "Isto ainda nao decide conformidade nem elegibilidade de mercado: declara o "
        "que o provider respondeu, com a versao da geometria e da base consultada."
    ),
    responses=RESPOSTAS_PADRAO,
)
def avaliar_embargos_ambientais_ibama(
    property_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(PROPERTY_LER_GEOMETRIA))],
    connection: ConnectionDependency,
) -> AvaliacaoEmbargoAmbientalResponse:
    alvo = typed_id_or_problem(property_id, entity_type="rural_property", campo="property_id")
    try:
        assessment = _embargo_ambiental_servico(connection).assess_ibama_embargoes(
            contexto.organization_id,
            alvo,
        )
    except KeyError as error:
        raise _nao_encontrado("Propriedade") from error
    except GeodataNaoConfigurado as error:
        raise DomainProblem(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            reason_code="PROVIDER_NAO_CONFIGURADO",
            title="Avaliacao espacial indisponivel",
            detail=str(error),
        ) from error
    except GeodataIndisponivel as error:
        raise DomainProblem(
            status_code=status.HTTP_502_BAD_GATEWAY,
            reason_code="PROVIDER_INDISPONIVEL",
            title="O provider de geodados nao respondeu",
            detail=str(error),
        ) from error
    return _resumo_embargo_ambiental(assessment)


@router.get(
    "/properties/{property_id}/environmental-embargoes/ibama/assertions",
    response_model=Pagina[EmbargoAmbientalAssertionResumo],
    summary="Listar assercoes gravadas de embargo ambiental do IBAMA",
    description=(
        "Devolve o historico auditavel das observacoes espaciais ja congeladas para "
        "a propriedade, da mais recente para a mais antiga. Aqui a pergunta nao e "
        "o que o provider responderia agora, e sim o que o Titan registrou em cada momento."
    ),
    responses=RESPOSTAS_PADRAO,
)
def listar_assertions_embargo_ambiental_ibama(
    property_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(PROPERTY_LER_GEOMETRIA))],
    paginacao: PaginacaoDependency,
    connection: ConnectionDependency,
) -> Any:
    alvo = typed_id_or_problem(property_id, entity_type="rural_property", campo="property_id")
    propriedade = TransactionalRuralPropertyRepository(connection=connection).get_by_id(alvo)
    if propriedade is None or propriedade.organization_id != contexto.organization_id:
        raise _nao_encontrado("Propriedade")
    encontrados = _embargo_assertion_servico(connection).list_for_property(
        contexto.organization_id,
        alvo,
    )
    janela = encontrados[paginacao.offset : paginacao.offset + paginacao.limite_de_sondagem]
    return montar_pagina([_resumo_embargo_assertion(item) for item in janela], paginacao)


@router.get(
    "/properties/{property_id}/territorial-overlaps/funai",
    response_model=SobreposicaoTerritorialResponse,
    summary="Consultar a sobreposicao territorial da FUNAI para a propriedade",
    description=(
        "Usa a geometria vigente da propriedade e a referencia externa do CAR para "
        "consultar a sobreposicao territorial atual declarada pelo provider para a "
        "camada FUNAI_TI.\n\n"
        "Isto ainda nao decide conformidade nem elegibilidade de mercado: devolve "
        "a leitura territorial crua, com lacunas declaradas quando a consulta nao "
        "for reproduzivel."
    ),
    responses=RESPOSTAS_PADRAO,
)
def consultar_sobreposicao_territorial_funai(
    property_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(PROPERTY_LER_GEOMETRIA))],
    connection: ConnectionDependency,
) -> SobreposicaoTerritorialResponse:
    alvo = typed_id_or_problem(property_id, entity_type="rural_property", campo="property_id")
    try:
        assessment = _sobreposicao_territorial_servico(connection).assess_funai_overlap(
            contexto.organization_id,
            alvo,
        )
    except KeyError as error:
        raise _nao_encontrado("Propriedade") from error
    except GeodataNaoConfigurado as error:
        raise DomainProblem(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            reason_code="PROVIDER_NAO_CONFIGURADO",
            title="Consulta territorial indisponivel",
            detail=str(error),
        ) from error
    except GeodataIndisponivel as error:
        raise DomainProblem(
            status_code=status.HTTP_502_BAD_GATEWAY,
            reason_code="PROVIDER_INDISPONIVEL",
            title="O provider de geodados nao respondeu",
            detail=str(error),
        ) from error
    return _resumo_sobreposicao_territorial(assessment)


@router.get(
    "/properties/{property_id}/territorial-timelines/prodes",
    response_model=TimelineTerritorialResponse,
    summary="Consultar a timeline territorial do PRODES para a propriedade",
    description=(
        "Usa a geometria vigente da propriedade e a referencia externa do CAR para "
        "consultar a serie temporal declarada pelo provider para a camada TB_PRODES.\n\n"
        "Isto ainda nao decide conformidade nem elegibilidade de mercado: devolve "
        "a leitura temporal crua, com lacunas declaradas quando a consulta nao for "
        "reproduzivel."
    ),
    responses=RESPOSTAS_PADRAO,
)
def consultar_timeline_territorial_prodes(
    property_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(PROPERTY_LER_GEOMETRIA))],
    connection: ConnectionDependency,
    year_from: int | None = Query(default=None, ge=1900, le=2100),
    year_to: int | None = Query(default=None, ge=1900, le=2100),
) -> TimelineTerritorialResponse:
    alvo = typed_id_or_problem(property_id, entity_type="rural_property", campo="property_id")
    try:
        assessment = _timeline_territorial_servico(connection).assess_prodes_timeline(
            contexto.organization_id,
            alvo,
            year_from=year_from,
            year_to=year_to,
        )
    except KeyError as error:
        raise _nao_encontrado("Propriedade") from error
    except GeodataNaoConfigurado as error:
        raise DomainProblem(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            reason_code="PROVIDER_NAO_CONFIGURADO",
            title="Consulta territorial indisponivel",
            detail=str(error),
        ) from error
    except GeodataIndisponivel as error:
        raise DomainProblem(
            status_code=status.HTTP_502_BAD_GATEWAY,
            reason_code="PROVIDER_INDISPONIVEL",
            title="O provider de geodados nao respondeu",
            detail=str(error),
        ) from error
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="PARAMETRO_INVALIDO",
            title="Parâmetro inválido",
            detail=str(error),
        ) from error
    return _resumo_timeline_territorial(assessment)


@router.get(
    "/properties/{property_id}/territorial-timelines/deter",
    response_model=TimelineTerritorialResponse,
    summary="Consultar a timeline territorial do DETER para a propriedade",
    description=(
        "Usa a geometria vigente da propriedade e a referencia externa do CAR para "
        "consultar a serie temporal declarada pelo provider para a camada TB_DETER.\n\n"
        "Isto ainda nao decide conformidade nem elegibilidade de mercado: devolve "
        "a leitura temporal crua, com lacunas declaradas quando a consulta nao for "
        "reproduzivel."
    ),
    responses=RESPOSTAS_PADRAO,
)
def consultar_timeline_territorial_deter(
    property_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(PROPERTY_LER_GEOMETRIA))],
    connection: ConnectionDependency,
    year_from: int | None = Query(default=None, ge=1900, le=2100),
    year_to: int | None = Query(default=None, ge=1900, le=2100),
) -> TimelineTerritorialResponse:
    alvo = typed_id_or_problem(property_id, entity_type="rural_property", campo="property_id")
    try:
        assessment = _timeline_territorial_servico(connection).assess_deter_timeline(
            contexto.organization_id,
            alvo,
            year_from=year_from,
            year_to=year_to,
        )
    except KeyError as error:
        raise _nao_encontrado("Propriedade") from error
    except GeodataNaoConfigurado as error:
        raise DomainProblem(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            reason_code="PROVIDER_NAO_CONFIGURADO",
            title="Consulta territorial indisponivel",
            detail=str(error),
        ) from error
    except GeodataIndisponivel as error:
        raise DomainProblem(
            status_code=status.HTTP_502_BAD_GATEWAY,
            reason_code="PROVIDER_INDISPONIVEL",
            title="O provider de geodados nao respondeu",
            detail=str(error),
        ) from error
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="PARAMETRO_INVALIDO",
            title="Parâmetro inválido",
            detail=str(error),
        ) from error
    return _resumo_timeline_territorial(assessment)


# -- Propriedades ------------------------------------------------------------


@router.get(
    "/properties",
    response_model=Pagina[PropriedadeResumo],
    summary="Listar propriedades rurais",
    responses=RESPOSTAS_PADRAO,
)
def listar_propriedades(
    contexto: Annotated[OrganizationContext, Depends(require_permission(PROPERTY_LER))],
    paginacao: PaginacaoDependency,
    connection: ConnectionDependency,
) -> Any:
    encontrados = TransactionalRuralPropertyRepository(connection=connection).list_by_organization(
        contexto.organization_id, limit=paginacao.limite_de_sondagem, offset=paginacao.offset
    )
    return montar_pagina([_propriedade(item) for item in encontrados], paginacao)


@router.get(
    "/properties/{property_id}",
    response_model=PropriedadeResumo,
    summary="Detalhar uma propriedade rural",
    responses=RESPOSTAS_PADRAO,
)
def detalhar_propriedade(
    property_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(PROPERTY_LER))],
    connection: ConnectionDependency,
) -> PropriedadeResumo:
    alvo = typed_id_or_problem(property_id, entity_type="rural_property", campo="property_id")
    encontrado = TransactionalRuralPropertyRepository(connection=connection).get_by_id(alvo)
    if encontrado is None or encontrado.organization_id != contexto.organization_id:
        raise _nao_encontrado("Propriedade")
    return _propriedade(encontrado)


# -- Medicamentos e lotes ----------------------------------------------------


@router.get(
    "/medications",
    response_model=Pagina[MedicamentoResumo],
    summary="Listar medicamentos",
    responses=RESPOSTAS_PADRAO,
)
def listar_medicamentos(
    contexto: Annotated[OrganizationContext, Depends(require_permission(MEDICATION_LER))],
    paginacao: PaginacaoDependency,
    connection: ConnectionDependency,
) -> Any:
    encontrados = TransactionalMedicationRepository(connection=connection).list_by_organization(
        contexto.organization_id, limit=paginacao.limite_de_sondagem, offset=paginacao.offset
    )
    return montar_pagina([_medicamento(item) for item in encontrados], paginacao)


@router.get(
    "/medications/{medication_id}",
    response_model=MedicamentoResumo,
    summary="Detalhar um medicamento",
    responses=RESPOSTAS_PADRAO,
)
def detalhar_medicamento(
    medication_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(MEDICATION_LER))],
    connection: ConnectionDependency,
) -> MedicamentoResumo:
    alvo = typed_id_or_problem(medication_id, entity_type="medication", campo="medication_id")
    encontrado = TransactionalMedicationRepository(connection=connection).get_by_id(alvo)
    if encontrado is None or encontrado.organization_id != contexto.organization_id:
        raise _nao_encontrado("Medicamento")
    return _medicamento(encontrado)


@router.get(
    "/medication-batches",
    response_model=Pagina[LoteResumo],
    summary="Listar lotes de medicamento",
    description=(
        "Sem `medication_id`, lista os lotes da organização do mais recente ao mais "
        "antigo. Com ele, lista os do medicamento ordenados pelo que vence primeiro."
    ),
    responses=RESPOSTAS_PADRAO,
)
def listar_lotes_de_medicamento(
    contexto: Annotated[OrganizationContext, Depends(require_permission(MEDICATION_LER))],
    paginacao: PaginacaoDependency,
    connection: ConnectionDependency,
    medication_id: str | None = None,
) -> Any:
    repositorio = TransactionalMedicationBatchRepository(connection=connection)
    if medication_id:
        alvo = typed_id_or_problem(medication_id, entity_type="medication", campo="medication_id")
        encontrados = repositorio.list_by_medication(contexto.organization_id, alvo)
        recorte = encontrados[paginacao.offset : paginacao.offset + paginacao.limite_de_sondagem]
    else:
        recorte = repositorio.list_by_organization(
            contexto.organization_id,
            limit=paginacao.limite_de_sondagem,
            offset=paginacao.offset,
        )
    return montar_pagina([_lote_medicamento(item) for item in recorte], paginacao)


@router.get(
    "/medication-batches/{batch_id}",
    response_model=LoteResumo,
    summary="Detalhar um lote de medicamento",
    responses=RESPOSTAS_PADRAO,
)
def detalhar_lote_de_medicamento(
    batch_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(MEDICATION_LER))],
    connection: ConnectionDependency,
) -> LoteResumo:
    alvo = typed_id_or_problem(batch_id, entity_type="medication_batch", campo="batch_id")
    encontrado = TransactionalMedicationBatchRepository(connection=connection).get_by_id(alvo)
    if encontrado is None or encontrado.organization_id != contexto.organization_id:
        raise _nao_encontrado("Lote de medicamento")
    return _lote_medicamento(encontrado)


# -- Tratamentos -------------------------------------------------------------


@router.get(
    "/treatments",
    response_model=Pagina[TratamentoResumo],
    summary="Listar aplicações de tratamento",
    description=(
        "Inclui as aplicações corrigidas: elas continuam sendo registros válidos do "
        "que foi lançado. `corrects_application_id` identifica cada correção."
    ),
    responses=RESPOSTAS_PADRAO,
)
def listar_tratamentos(
    contexto: Annotated[OrganizationContext, Depends(require_permission(TREATMENT_LER))],
    paginacao: PaginacaoDependency,
    connection: ConnectionDependency,
    animal_id: str | None = None,
) -> Any:
    repositorio = TransactionalTreatmentApplicationRepository(connection=connection)
    if animal_id:
        alvo = typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id")
        encontrados = repositorio.list_by_animal(contexto.organization_id, alvo)
        recorte = encontrados[paginacao.offset : paginacao.offset + paginacao.limite_de_sondagem]
    else:
        recorte = repositorio.list_by_organization(
            contexto.organization_id,
            limit=paginacao.limite_de_sondagem,
            offset=paginacao.offset,
        )
    return montar_pagina([_tratamento(item) for item in recorte], paginacao)


@router.get(
    "/treatments/{application_id}",
    response_model=TratamentoResumo,
    summary="Detalhar uma aplicação de tratamento",
    responses=RESPOSTAS_PADRAO,
)
def detalhar_tratamento(
    application_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(TREATMENT_LER))],
    connection: ConnectionDependency,
) -> TratamentoResumo:
    alvo = typed_id_or_problem(
        application_id, entity_type="treatment_application", campo="application_id"
    )
    encontrado = TransactionalTreatmentApplicationRepository(connection=connection).get_by_id(alvo)
    if encontrado is None or encontrado.organization_id != contexto.organization_id:
        raise _nao_encontrado("Aplicação de tratamento")
    return _tratamento(encontrado)


# -- Lotes pecuários ---------------------------------------------------------


@router.get(
    "/lots",
    response_model=Pagina[LoteAnimaisResumo],
    summary="Listar lotes de animais",
    responses=RESPOSTAS_PADRAO,
)
def listar_lotes(
    contexto: Annotated[OrganizationContext, Depends(require_permission(LOT_LER))],
    paginacao: PaginacaoDependency,
    connection: ConnectionDependency,
) -> Any:
    encontrados = TransactionalLivestockLotRepository(connection=connection).list_by_organization(
        contexto.organization_id, limit=paginacao.limite_de_sondagem, offset=paginacao.offset
    )
    return montar_pagina([_lote_animais(item) for item in encontrados], paginacao)


@router.get(
    "/lots/{lot_id}",
    response_model=LoteAnimaisResumo,
    summary="Detalhar um lote de animais",
    responses=RESPOSTAS_PADRAO,
)
def detalhar_lote(
    lot_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(LOT_LER))],
    connection: ConnectionDependency,
) -> LoteAnimaisResumo:
    alvo = typed_id_or_problem(lot_id, entity_type="livestock_lot", campo="lot_id")
    encontrado = TransactionalLivestockLotRepository(connection=connection).get_by_id(alvo)
    if encontrado is None or encontrado.organization_id != contexto.organization_id:
        raise _nao_encontrado("Lote")
    return _lote_animais(encontrado)


@router.get(
    "/lots/{lot_id}/members",
    summary="Composição de um lote",
    description=(
        "Sem `at_time`, devolve a composição vigente. Com ele, a que valia naquele "
        "instante — a composição é temporal, e um lote não é o que ele é hoje."
    ),
    responses=RESPOSTAS_PADRAO,
)
def composicao_do_lote(
    lot_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(LOT_LER))],
    connection: ConnectionDependency,
    at_time: datetime | None = None,
) -> dict[str, Any]:
    alvo = typed_id_or_problem(lot_id, entity_type="livestock_lot", campo="lot_id")
    lote = TransactionalLivestockLotRepository(connection=connection).get_by_id(alvo)
    if lote is None or lote.organization_id != contexto.organization_id:
        raise _nao_encontrado("Lote")

    vinculos = TransactionalLotMembershipRepository(connection=connection).get_memberships_for_lot(
        alvo, at_time=at_time
    )
    return {
        "lot_id": str(alvo.value),
        "at_time": at_time.isoformat() if at_time else None,
        "members": [
            {
                "membership_id": str(vinculo.membership_id.value),
                "animal_id": str(vinculo.animal_id.value),
                "valid_from": vinculo.valid_from.isoformat(),
                "valid_until": (vinculo.valid_until.isoformat() if vinculo.valid_until else None),
                "reason": vinculo.reason,
            }
            for vinculo in vinculos
        ],
    }


# -- Veterinários ------------------------------------------------------------


@router.get(
    "/veterinarians",
    response_model=Pagina[VeterinarioResumo],
    summary="Listar veterinários",
    responses=RESPOSTAS_PADRAO,
)
def listar_veterinarios(
    contexto: Annotated[OrganizationContext, Depends(require_permission(VETERINARIAN_LER))],
    paginacao: PaginacaoDependency,
    connection: ConnectionDependency,
) -> Any:
    encontrados = TransactionalVeterinarianRepository(connection=connection).list_by_organization(
        contexto.organization_id, limit=paginacao.limite_de_sondagem, offset=paginacao.offset
    )
    return montar_pagina([_veterinario(item) for item in encontrados], paginacao)


@router.get(
    "/veterinarians/{veterinarian_id}",
    response_model=VeterinarioResumo,
    summary="Detalhar um veterinário",
    responses=RESPOSTAS_PADRAO,
)
def detalhar_veterinario(
    veterinarian_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(VETERINARIAN_LER))],
    connection: ConnectionDependency,
) -> VeterinarioResumo:
    alvo = typed_id_or_problem(veterinarian_id, entity_type="veterinarian", campo="veterinarian_id")
    encontrado = TransactionalVeterinarianRepository(connection=connection).get_by_id(alvo)
    if encontrado is None or encontrado.organization_id != contexto.organization_id:
        raise _nao_encontrado("Veterinário")
    return _veterinario(encontrado)


# -- Movimentações -----------------------------------------------------------


@router.get(
    "/movements",
    response_model=Pagina[MovimentacaoResumo],
    summary="Listar movimentações",
    responses=RESPOSTAS_PADRAO,
)
def listar_movimentacoes(
    contexto: Annotated[OrganizationContext, Depends(require_permission(MOVEMENT_LER))],
    paginacao: PaginacaoDependency,
    connection: ConnectionDependency,
    animal_id: str | None = None,
) -> Any:
    repositorio = TransactionalAnimalMovementRepository(connection=connection)
    if animal_id:
        alvo = typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id")
        encontrados = repositorio.list_by_animal(alvo)
        recorte = encontrados[paginacao.offset : paginacao.offset + paginacao.limite_de_sondagem]
    else:
        recorte = repositorio.list_by_organization(
            contexto.organization_id,
            limit=paginacao.limite_de_sondagem,
            offset=paginacao.offset,
        )
    return montar_pagina([_movimentacao(item) for item in recorte], paginacao)


@router.get(
    "/movements/{movement_id}",
    response_model=MovimentacaoResumo,
    summary="Detalhar uma movimentação",
    responses=RESPOSTAS_PADRAO,
)
def detalhar_movimentacao(
    movement_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(MOVEMENT_LER))],
    connection: ConnectionDependency,
) -> MovimentacaoResumo:
    alvo = typed_id_or_problem(movement_id, entity_type="animal_movement", campo="movement_id")
    encontrado = TransactionalAnimalMovementRepository(connection=connection).get_by_id(alvo)
    if encontrado is None or encontrado.organization_id != contexto.organization_id:
        raise _nao_encontrado("Movimentação")
    return _movimentacao(encontrado)
