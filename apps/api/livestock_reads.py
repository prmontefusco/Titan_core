"""Listagem e detalhe das entidades da vertical (Marco 12).

A API do Marco 10 só criava e lia por identificador: quem cadastrasse um animal e
perdesse o UUID não o alcançava mais. Nenhuma interface funciona assim — a
primeira tela de qualquer aplicação é uma lista.

**Toda listagem é paginada e escopada pela organização do contexto.** O
`organization_id` nunca vem do cliente: vem do contexto já resolvido, e o RLS
confirma no banco. Aceitar organização por parâmetro seria oferecer ao chamador
a chance de pedir dados de outra.
"""

from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from apps.api.livestock_dependencies import (
    ConnectionDependency,
    require_permission,
    typed_id_or_problem,
)
from apps.api.pagination import Pagina, PaginacaoDependency, montar_pagina
from apps.api.problem import RESPOSTAS_PADRAO, DomainProblem
from packages.core_domain import OrganizationContext
from packages.livestock_application.authorization import (
    ANIMAL_LER,
    LOT_LER,
    MEDICATION_LER,
    MOVEMENT_LER,
    PROPERTY_LER,
    TREATMENT_LER,
    VETERINARIAN_LER,
)
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
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
from packages.livestock_infrastructure.persistence.treatment_repository import (
    TransactionalTreatmentApplicationRepository,
)
from packages.livestock_infrastructure.persistence.veterinarian_repository import (
    TransactionalVeterinarianRepository,
)

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


class AnimalResumo(BaseModel):
    animal_id: str
    sex: str
    breed: str | None
    birth_date: date | None
    birth_property_id: str
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
    )


def _animal(entidade: Any, saida: Any = None) -> AnimalResumo:
    return AnimalResumo(
        animal_id=str(entidade.animal_id.value),
        sex=entidade.sex.value,
        breed=entidade.breed,
        birth_date=entidade.birth_date,
        birth_property_id=str(entidade.birth_property_id.value),
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
    connection: ConnectionDependency,
    paginacao: PaginacaoDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(ANIMAL_LER))],
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
    connection: ConnectionDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(ANIMAL_LER))],
) -> AnimalResumo:
    alvo = typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id")
    repositorio = TransactionalAnimalRepository(connection=connection)
    encontrado = repositorio.get_by_id(alvo)
    if encontrado is None or encontrado.organization_id != contexto.organization_id:
        raise _nao_encontrado("Animal")
    # O detalhe sempre diz se o animal saiu: quem pergunta por um animal
    # específico precisa saber se ele ainda existe no rebanho.
    return _animal(encontrado, repositorio.get_exit(alvo))


# -- Propriedades ------------------------------------------------------------


@router.get(
    "/properties",
    response_model=Pagina[PropriedadeResumo],
    summary="Listar propriedades rurais",
    responses=RESPOSTAS_PADRAO,
)
def listar_propriedades(
    connection: ConnectionDependency,
    paginacao: PaginacaoDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(PROPERTY_LER))],
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
    connection: ConnectionDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(PROPERTY_LER))],
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
    connection: ConnectionDependency,
    paginacao: PaginacaoDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(MEDICATION_LER))],
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
    connection: ConnectionDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(MEDICATION_LER))],
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
    connection: ConnectionDependency,
    paginacao: PaginacaoDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(MEDICATION_LER))],
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
    connection: ConnectionDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(MEDICATION_LER))],
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
    connection: ConnectionDependency,
    paginacao: PaginacaoDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(TREATMENT_LER))],
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
    connection: ConnectionDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(TREATMENT_LER))],
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
    connection: ConnectionDependency,
    paginacao: PaginacaoDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(LOT_LER))],
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
    connection: ConnectionDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(LOT_LER))],
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
    connection: ConnectionDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(LOT_LER))],
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
    connection: ConnectionDependency,
    paginacao: PaginacaoDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(VETERINARIAN_LER))],
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
    connection: ConnectionDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(VETERINARIAN_LER))],
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
    connection: ConnectionDependency,
    paginacao: PaginacaoDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(MOVEMENT_LER))],
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
    connection: ConnectionDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(MOVEMENT_LER))],
) -> MovimentacaoResumo:
    alvo = typed_id_or_problem(movement_id, entity_type="animal_movement", campo="movement_id")
    encontrado = TransactionalAnimalMovementRepository(connection=connection).get_by_id(alvo)
    if encontrado is None or encontrado.organization_id != contexto.organization_id:
        raise _nao_encontrado("Movimentação")
    return _movimentacao(encontrado)
