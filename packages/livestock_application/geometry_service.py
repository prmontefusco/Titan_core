"""Registro da geometria da propriedade (Passo 17.1 - Titan Livestock, ADR-0026).

**A geometria nunca é substituída.** Cada registro cria uma versão nova, e a
anterior permanece — é ela que faz uma avaliação de 2025 continuar reproduzível
depois que o CAR for retificado em 2027.

O serviço não transforma sistema de referência nem confere topologia: as duas
coisas exigem PROJ e GEOS, que são do PostGIS, e a ADR-0026 as mantém na
Infrastructure. Aqui se confere o que é do domínio — forma do GeoJSON, faixa das
coordenadas, coerência do digest — e se decide **admissibilidade**.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_domain.events import (
    PROPERTY_GEOMETRY_RECORDED,
    property_geometry_recorded_payload,
)
from packages.livestock_domain.geometry import (
    GeometrySource,
    PropertyGeometry,
    digest_de,
    validar_geojson,
)
from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class PropertyGeometryRepositoryPort(Protocol):
    def save(self, geometry: PropertyGeometry) -> None: ...

    def current_for(self, property_id: TypedId) -> PropertyGeometry | None: ...

    def history_of(self, property_id: TypedId) -> list[PropertyGeometry]: ...

    def next_version_for(self, property_id: TypedId) -> int: ...


@dataclass(frozen=True, slots=True)
class PropertyGeometryService:
    """Registra e consulta o limite declarado de uma propriedade."""

    geometry_repository: PropertyGeometryRepositoryPort
    property_repository: RuralPropertyRepositoryPort
    recorder: LivestockEventRecorder

    def register_geometry(
        self,
        context: LivestockOperationContext,
        property_id: TypedId,
        source: GeometrySource,
        source_payload: str,
        srid: int,
        external_reference: str | None = None,
        captured_at: datetime | None = None,
        notes: str | None = None,
    ) -> PropertyGeometry:
        organization_id = context.organization_id
        propriedade = self.property_repository.get_by_id(property_id)
        if propriedade is None or propriedade.organization_id != organization_id:
            raise KeyError(f"Propriedade '{property_id.value}' não encontrada.")

        if captured_at is not None:
            require_utc(captured_at, field_name="captured_at")
            if captured_at > datetime.now(UTC):
                raise ValueError("captured_at não pode ser no futuro.")

        # Recusa o malformado antes de o banco ser acionado. A validade
        # topológica é conferida na gravação, por quem tem GEOS.
        validar_geojson(source_payload)

        geometria = PropertyGeometry(
            geometry_id=TypedId.new("property_geometry"),
            organization_id=organization_id,
            property_id=property_id,
            source=source,
            srid=srid,
            source_payload=source_payload,
            source_digest=digest_de(source_payload),
            external_reference=external_reference,
            version=self.geometry_repository.next_version_for(property_id),
            captured_at=captured_at,
            imported_at=datetime.now(UTC),
            notes=notes,
        )
        self.geometry_repository.save(geometria)

        # O agregado é a geometria: é a entidade criada aqui, e a propriedade a
        # cita — mesmo padrão da relação no 13.2 e do evento reprodutivo no 13.3.
        self.recorder.record(
            context=context,
            aggregate_id=geometria.geometry_id,
            event_type=PROPERTY_GEOMETRY_RECORDED,
            payload=property_geometry_recorded_payload(
                geometry_id=geometria.geometry_id,
                property_id=property_id,
                source=source.value,
                srid=srid,
                source_digest=geometria.source_digest,
                external_reference=external_reference,
                version=geometria.version,
                captured_at=captured_at,
            ),
            occurred_at=captured_at or geometria.imported_at,
        )
        return geometria

    def current_for(
        self, organization_id: OrganizationId, property_id: TypedId
    ) -> PropertyGeometry | None:
        """A geometria vigente, ou `None` quando a propriedade não tem limite.

        `None` é resposta honesta e não impeditiva: propriedade sem geometria
        continua operando, e a lacuna aparece declarada em vez de bloquear o
        cadastro — o mesmo tratamento que a propriedade de nascimento
        desconhecida recebe na ADR-0040.
        """
        encontrada = self.geometry_repository.current_for(property_id)
        if encontrada is None or encontrada.organization_id != organization_id:
            return None
        return encontrada

    def history_of(
        self, organization_id: OrganizationId, property_id: TypedId
    ) -> tuple[PropertyGeometry, ...]:
        """Todas as versões, da mais antiga à mais recente.

        É por aqui que se responde "qual polígono a avaliação de junho usou",
        pergunta que uma tabela sobrescrita não teria como responder.
        """
        return tuple(
            geometria
            for geometria in self.geometry_repository.history_of(property_id)
            if geometria.organization_id == organization_id
        )
