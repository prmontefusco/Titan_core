"""Caso de uso para Recall — navegação na genealogia (Passo 7.4)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from packages.core_application.relation_service import RelationRepositoryPort
from packages.core_domain.recall import (
    RecallDirection,
    RecallGap,
    RecallLimitReason,
    RecallMode,
    RecallPath,
    RecallRequest,
    RecallResult,
    RecallStep,
)
from packages.core_domain.relations import UniversalRelation
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


class RecallResultRepositoryPort(Protocol):
    def save(self, result: RecallResult) -> None: ...

    def get_by_id(self, recall_id: TypedId) -> RecallResult | None: ...


class AffectedDecisionLookupPort(Protocol):
    """Localiza decisões emitidas sobre um sujeito alcançado pela travessia."""

    def list_decision_ids_for_subject(
        self, organization_id: OrganizationId, subject_id: TypedId
    ) -> list[TypedId]: ...


@dataclass(frozen=True, slots=True)
class RecallService:
    """Percorre a genealogia em largura, com limites explícitos e lacunas declaradas.

    A travessia é em largura de propósito: o caminho mais curto até um sujeito é o
    mais fácil de explicar, e explicar cada caminho é requisito do passo.
    """

    relations: RelationRepositoryPort
    decisions: AffectedDecisionLookupPort | None = None
    result_repository: RecallResultRepositoryPort | None = None

    def execute(self, request: RecallRequest, executed_at: datetime | None = None) -> RecallResult:
        # Incidente é ato auditável: sem onde registrar, não se executa. Simulação
        # é hipótese e não precisa deixar rastro.
        if request.mode is RecallMode.INCIDENTE and self.result_repository is None:
            raise RuntimeError(
                "Recall em modo incidente exige repositório para registro auditável."
            )

        paths, gaps, visitados = self._traverse(request)
        resultado = RecallResult(
            recall_id=TypedId.new("recall"),
            request=request,
            executed_at=executed_at or datetime.now(UTC),
            paths=paths,
            gaps=gaps,
            affected_decision_ids=self._locate_decisions(request, paths),
            visited_nodes=visitados,
        )

        if request.mode is RecallMode.INCIDENTE and self.result_repository is not None:
            self.result_repository.save(resultado)
        return resultado

    # -- Travessia ---------------------------------------------------------

    def _traverse(
        self, request: RecallRequest
    ) -> tuple[tuple[RecallPath, ...], tuple[RecallGap, ...], int]:
        origem = request.subject_reference
        visitados: set[TypedId] = {origem.target_id}
        fila: list[tuple[UniversalReference, tuple[RecallStep, ...]]] = [(origem, ())]
        caminhos: list[RecallPath] = []
        lacunas: list[RecallGap] = []

        while fila:
            atual, trilha = fila.pop(0)
            profundidade = len(trilha)

            if profundidade >= request.max_depth:
                # Havia por onde continuar, mas o limite pediu parada: isso é lacuna,
                # não conclusão de que nada mais existe.
                if self._has_more(request, atual):
                    lacunas.append(
                        RecallGap(
                            reason=RecallLimitReason.PROFUNDIDADE_MAXIMA,
                            at_reference=atual,
                            depth=profundidade,
                            description=(
                                f"Profundidade máxima ({request.max_depth}) atingida com "
                                "relações ainda por percorrer."
                            ),
                        )
                    )
                continue

            for relacao, vizinho, direcao in self._neighbours(request, atual):
                passo = RecallStep(
                    relation_id=relacao.relation_id,
                    relation_type=relacao.relation_type,
                    from_reference=atual,
                    to_reference=vizinho,
                    direction=direcao,
                )
                nova_trilha = (*trilha, passo)

                if vizinho.target_id in visitados:
                    # Ciclo ou reencontro: o caminho existe, mas não é reexpandido.
                    lacunas.append(
                        RecallGap(
                            reason=RecallLimitReason.CICLO_DETECTADO,
                            at_reference=vizinho,
                            depth=len(nova_trilha),
                            description=(
                                "Sujeito já visitado nesta travessia; expansão "
                                "interrompida para evitar ciclo."
                            ),
                        )
                    )
                    continue

                if len(visitados) >= request.max_nodes:
                    lacunas.append(
                        RecallGap(
                            reason=RecallLimitReason.LIMITE_DE_NOS,
                            at_reference=vizinho,
                            depth=len(nova_trilha),
                            description=(
                                f"Limite de {request.max_nodes} nós atingido; grafo "
                                "não foi percorrido por completo."
                            ),
                        )
                    )
                    return tuple(caminhos), tuple(lacunas), len(visitados)

                visitados.add(vizinho.target_id)
                caminhos.append(RecallPath(steps=nova_trilha))
                fila.append((vizinho, nova_trilha))

        return tuple(caminhos), tuple(lacunas), len(visitados)

    def _neighbours(
        self, request: RecallRequest, atual: UniversalReference
    ) -> list[tuple[UniversalRelation, UniversalReference, RecallDirection]]:
        encontrados: list[tuple[UniversalRelation, UniversalReference, RecallDirection]] = []

        if request.direction in (RecallDirection.PROSPECTIVA, RecallDirection.AMBAS):
            for relacao in self._filtered(
                request,
                self.relations.list_outgoing(
                    organization_id=request.organization_id,
                    source_id=atual.target_id,
                    at_time=request.at_time,
                ),
            ):
                encontrados.append((relacao, relacao.target_reference, RecallDirection.PROSPECTIVA))

        if request.direction in (RecallDirection.RETROSPECTIVA, RecallDirection.AMBAS):
            for relacao in self._filtered(
                request,
                self.relations.list_incoming(
                    organization_id=request.organization_id,
                    target_id=atual.target_id,
                    at_time=request.at_time,
                ),
            ):
                encontrados.append(
                    (relacao, relacao.source_reference, RecallDirection.RETROSPECTIVA)
                )

        # Ordem determinística: o mesmo grafo produz sempre os mesmos caminhos.
        encontrados.sort(key=lambda item: str(item[0].relation_id.value))
        return encontrados

    def _filtered(
        self, request: RecallRequest, relacoes: list[UniversalRelation]
    ) -> list[UniversalRelation]:
        if not request.relation_types:
            return relacoes
        permitidos = {t.strip().lower() for t in request.relation_types}
        return [r for r in relacoes if r.relation_type in permitidos]

    def _has_more(self, request: RecallRequest, atual: UniversalReference) -> bool:
        return bool(self._neighbours(request, atual))

    # -- Decisões afetadas -------------------------------------------------

    def _locate_decisions(
        self, request: RecallRequest, paths: tuple[RecallPath, ...]
    ) -> tuple[TypedId, ...]:
        if self.decisions is None:
            return ()

        alvos = [request.subject_reference.target_id]
        for path in paths:
            alvo = path.reached.target_id
            if alvo not in alvos:
                alvos.append(alvo)

        encontradas: list[TypedId] = []
        for alvo in alvos:
            for decision_id in self.decisions.list_decision_ids_for_subject(
                request.organization_id, alvo
            ):
                if decision_id not in encontradas:
                    encontradas.append(decision_id)
        return tuple(encontradas)
