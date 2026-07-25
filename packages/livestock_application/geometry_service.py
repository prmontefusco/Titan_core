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
from typing import Any, Protocol

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
    CAMADA_PERIMETRO,
    SRID_CANONICO,
    GeometriaInvalida,
    GeometrySource,
    PropertyGeometry,
    digest_de,
    validar_geojson,
)
from packages.livestock_infrastructure.geodata import (
    CarLookupPort,
    CarProperty,
    GeodataNaoConfigurado,
)
from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


@dataclass(frozen=True, slots=True)
class CamadaRecusada:
    """Uma camada que o provider entregou e o Titan não pôde admitir.

    Existe porque **dado oficial real contém geometria inválida**: o SICAR
    entrega camadas com componentes degenerados, e isso é fato do mundo, não
    defeito da integração.
    """

    layer: str
    motivo: str


@dataclass(frozen=True, slots=True)
class ImportacaoDoCar:
    """O que entrou e o que não entrou — as duas coisas declaradas."""

    gravadas: tuple[PropertyGeometry, ...]
    recusadas: tuple[CamadaRecusada, ...]


class PropertyGeometryRepositoryPort(Protocol):
    def save(self, geometry: PropertyGeometry) -> None: ...

    def current_for(
        self, property_id: TypedId, layer: str = CAMADA_PERIMETRO
    ) -> PropertyGeometry | None: ...

    def current_layers_for(self, property_id: TypedId) -> list[PropertyGeometry]: ...

    def history_of(
        self, property_id: TypedId, layer: str | None = None
    ) -> list[PropertyGeometry]: ...

    def next_version_for(self, property_id: TypedId, layer: str = CAMADA_PERIMETRO) -> int: ...


@dataclass(frozen=True, slots=True)
class PropertyGeometryService:
    """Registra e consulta o limite declarado de uma propriedade."""

    geometry_repository: PropertyGeometryRepositoryPort
    property_repository: RuralPropertyRepositoryPort
    recorder: LivestockEventRecorder
    # Ausente quando o provider não está configurado: a API sobe e opera sem ele,
    # e só a importação do CAR fica indisponível — com mensagem que diz por quê.
    car_lookup: CarLookupPort | None = None

    def register_geometry(
        self,
        context: LivestockOperationContext,
        property_id: TypedId,
        source: GeometrySource,
        source_payload: str,
        srid: int,
        layer: str = CAMADA_PERIMETRO,
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
            layer=layer,
            srid=srid,
            source_payload=source_payload,
            source_digest=digest_de(source_payload),
            external_reference=external_reference,
            version=self.geometry_repository.next_version_for(property_id, layer),
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

    def import_from_car(
        self,
        context: LivestockOperationContext,
        property_id: TypedId,
        cod_imovel: str,
        state: str,
        notes: str | None = None,
        incluir_camadas: bool = True,
    ) -> ImportacaoDoCar:
        """Traz o imovel do CAR — o perimetro e as camadas dele.

        O provider é a autoridade da camada; o Titan **guarda o que usou**, para
        que a reprodutibilidade seja sua e não dependa de o provider manter a
        consulta histórica disponível.

        `captured_at` vem de `dat_atuali` — quando o CAR foi atualizado, e não
        quando foi importado. Há cadastro em uso com dado de cinco anos atrás, e
        confundir os dois instantes faria a avaliação parecer mais fresca do que é.

        **Nenhum atributo recebido é interpretado.** `des_condic` diz onde o
        cadastro está na fila do SICAR, e não se a fazenda está regular.

        Reserva legal, APP e uso restrito vem do proprio CAR e entram como
        camadas do imovel — cada uma com versao propria, porque sao naturezas
        diferentes e nao versoes umas das outras.

        **Camada invalida nao derruba a importacao inteira.** Dado oficial real
        contem geometria degenerada, e recusar tudo por causa de uma camada
        acessoria perderia o perimetro, que e o que importa. O que nao entrou fica
        declarado em `recusadas`. Se o **perimetro** for invalido, a importacao
        falha: sem ele nao ha o que importar.
        """
        if self.car_lookup is None:
            raise GeodataNaoConfigurado(
                "Importação do CAR exige TITAN_GEODATA_URL e TITAN_GEODATA_API_KEY."
            )
        organization_id = context.organization_id
        propriedade = self.property_repository.get_by_id(property_id)
        if propriedade is None or propriedade.organization_id != organization_id:
            raise KeyError(f"Propriedade '{property_id.value}' não encontrada.")

        imovel = self.car_lookup.fetch(cod_imovel, state)
        referencia = imovel.cod_imovel or cod_imovel

        camadas: list[tuple[str, str, str, dict[str, Any]]] = [
            (
                CAMADA_PERIMETRO,
                imovel.polygon_payload,
                imovel.polygon_digest,
                dict(imovel.attributes),
            )
        ]
        if incluir_camadas:
            camadas.extend(
                (
                    camada.layer,
                    camada.polygon_payload,
                    camada.polygon_digest,
                    {
                        "label": camada.label,
                        "area_hectares": camada.area_hectares,
                        "feature_count": camada.feature_count,
                    },
                )
                for camada in self.car_lookup.fetch_layers(cod_imovel, state)
                if camada.layer and camada.layer != CAMADA_PERIMETRO
            )

        gravadas: list[PropertyGeometry] = []
        recusadas: list[CamadaRecusada] = []
        for nome, payload, digest, atributos in camadas:
            try:
                self._gravar_camada(
                    context=context,
                    organization_id=organization_id,
                    property_id=property_id,
                    layer=nome,
                    payload=payload,
                    digest=digest,
                    atributos=atributos,
                    referencia=referencia,
                    captured_at=imovel.captured_at,
                    response_digest=imovel.response_digest,
                    notes=notes,
                    destino=gravadas,
                )
            except GeometriaInvalida as erro:
                # **Uma camada ruim não derruba as boas.** O perímetro é o que
                # responde onde fica a fazenda, e perdê-lo porque a hidrografia
                # do SICAR tem um componente degenerado seria trocar o essencial
                # pelo acessório. A falha fica declarada, nunca silenciada.
                if nome == CAMADA_PERIMETRO:
                    raise
                recusadas.append(CamadaRecusada(layer=nome, motivo=str(erro)))
        return ImportacaoDoCar(gravadas=tuple(gravadas), recusadas=tuple(recusadas))

    def _gravar_camada(
        self,
        *,
        context: LivestockOperationContext,
        organization_id: OrganizationId,
        property_id: TypedId,
        layer: str,
        payload: str,
        digest: str,
        atributos: dict[str, Any],
        referencia: str,
        captured_at: datetime | None,
        response_digest: str,
        notes: str | None,
        destino: list[PropertyGeometry],
    ) -> None:
        validar_geojson(payload)
        geometria = PropertyGeometry(
            geometry_id=TypedId.new("property_geometry"),
            organization_id=organization_id,
            property_id=property_id,
            source=GeometrySource.SICAR_CAR,
            layer=layer,
            srid=SRID_CANONICO,
            source_payload=payload,
            source_digest=digest,
            external_reference=referencia,
            version=self.geometry_repository.next_version_for(property_id, layer),
            captured_at=captured_at,
            imported_at=datetime.now(UTC),
            notes=notes,
            source_attributes=atributos,
            response_digest=response_digest,
        )
        self.geometry_repository.save(geometria)
        self.recorder.record(
            context=context,
            aggregate_id=geometria.geometry_id,
            event_type=PROPERTY_GEOMETRY_RECORDED,
            payload=property_geometry_recorded_payload(
                geometry_id=geometria.geometry_id,
                property_id=property_id,
                source=GeometrySource.SICAR_CAR.value,
                srid=SRID_CANONICO,
                source_digest=geometria.source_digest,
                external_reference=geometria.external_reference,
                version=geometria.version,
                captured_at=geometria.captured_at,
            ),
            occurred_at=geometria.captured_at or geometria.imported_at,
        )
        destino.append(geometria)

    def preview_car(self, cod_imovel: str, state: str) -> CarProperty:
        """Consulta o CAR **sem gravar nada**, para ajudar o cadastro.

        Município, área e UF vindos da fonte evitam erro de digitação — mas quem
        confirma é o operador, e o que ele confirmar entra como declaração dele.
        Preencher sozinho faria um dado externo entrar no cadastro sem que
        ninguém o tivesse assumido.

        **Isto não afirma titularidade.** O código informado pode ser de outro
        imóvel, e o Titan não infere propriedade jurídica a partir de coordenadas
        (ADR-0026). A verificação de titularidade é afirmação à parte.
        """
        if self.car_lookup is None:
            raise GeodataNaoConfigurado(
                "Consulta ao CAR exige TITAN_GEODATA_URL e TITAN_GEODATA_API_KEY."
            )
        return self.car_lookup.fetch(cod_imovel, state)

    def current_for(
        self,
        organization_id: OrganizationId,
        property_id: TypedId,
        layer: str = CAMADA_PERIMETRO,
    ) -> PropertyGeometry | None:
        """A geometria vigente, ou `None` quando a propriedade não tem limite.

        `None` é resposta honesta e não impeditiva: propriedade sem geometria
        continua operando, e a lacuna aparece declarada em vez de bloquear o
        cadastro — o mesmo tratamento que a propriedade de nascimento
        desconhecida recebe na ADR-0040.
        """
        encontrada = self.geometry_repository.current_for(property_id, layer)
        if encontrada is None or encontrada.organization_id != organization_id:
            return None
        return encontrada

    def layers_of(
        self, organization_id: OrganizationId, property_id: TypedId
    ) -> tuple[PropertyGeometry, ...]:
        """A versao vigente de cada camada que a propriedade tem."""
        return tuple(
            geometria
            for geometria in self.geometry_repository.current_layers_for(property_id)
            if geometria.organization_id == organization_id
        )

    def history_of(
        self,
        organization_id: OrganizationId,
        property_id: TypedId,
        layer: str | None = None,
    ) -> tuple[PropertyGeometry, ...]:
        """Todas as versões, da mais antiga à mais recente.

        É por aqui que se responde "qual polígono a avaliação de junho usou",
        pergunta que uma tabela sobrescrita não teria como responder.
        """
        return tuple(
            geometria
            for geometria in self.geometry_repository.history_of(property_id, layer)
            if geometria.organization_id == organization_id
        )
