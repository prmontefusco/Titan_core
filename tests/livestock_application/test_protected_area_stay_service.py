"""Permanência do animal em imóvel que declara área protegida no CAR (Passo 17.5)."""

from datetime import UTC, datetime

from packages.livestock_application.protected_area_stay_service import (
    POSICAO_INTRA_IMOVEL_DESCONHECIDA,
    ProtectedAreaStayGapCode,
    ProtectedAreaStayService,
    ProtectedAreaStayStatus,
)
from packages.livestock_domain.geometry import GeometrySource, PropertyGeometry, digest_de
from packages.livestock_domain.movement import PropertyStay, StayStatus
from packages.shared_kernel import OrganizationId, TypedId

QUADRADO = (
    '{"coordinates":[[[-54.0,-22.0],[-54.0,-21.0],[-53.0,-21.0],'
    '[-53.0,-22.0],[-54.0,-22.0]]],"type":"Polygon"}'
)

ORG = OrganizationId.new()
OUTRA_ORG = OrganizationId.new()
ANIMAL = TypedId.new("animal")
FAZENDA_A = TypedId.new("rural_property")
FAZENDA_B = TypedId.new("rural_property")


class FakeStayRepo:
    def __init__(self, stays: list[PropertyStay]) -> None:
        self.stays = stays

    def get_timeline(self, animal_id: TypedId) -> list[PropertyStay]:
        return [stay for stay in self.stays if stay.animal_id == animal_id]


class FakeGeometryRepo:
    def __init__(self, layers: dict[TypedId, list[PropertyGeometry]]) -> None:
        self.layers = layers

    def save(self, geometry: PropertyGeometry) -> None: ...

    def current_for(
        self, property_id: TypedId, layer: str = "AREA_IMOVEL"
    ) -> PropertyGeometry | None:
        for geometry in self.layers.get(property_id, []):
            if geometry.layer == layer:
                return geometry
        return None

    def current_layers_for(self, property_id: TypedId) -> list[PropertyGeometry]:
        return list(self.layers.get(property_id, []))

    def history_of(self, property_id: TypedId, layer: str | None = None) -> list[PropertyGeometry]:
        return []

    def next_version_for(self, property_id: TypedId, layer: str = "AREA_IMOVEL") -> int:
        return 1


def _geometria(
    property_id: TypedId,
    layer: str,
    *,
    organization_id: OrganizationId = ORG,
    captured_at: datetime | None = None,
) -> PropertyGeometry:
    return PropertyGeometry(
        geometry_id=TypedId.new("property_geometry"),
        organization_id=organization_id,
        property_id=property_id,
        source=GeometrySource.SICAR_CAR,
        layer=layer,
        srid=4326,
        source_payload=QUADRADO,
        source_digest=digest_de(QUADRADO),
        version=1,
        captured_at=captured_at,
        external_reference="MS-5006606-ABC",
        layer_version="v2026-07",
    )


def _permanencia(
    property_id: TypedId,
    *,
    start: datetime,
    end: datetime | None = None,
    organization_id: OrganizationId = ORG,
) -> PropertyStay:
    return PropertyStay(
        stay_id=TypedId.new("property_stay"),
        organization_id=organization_id,
        animal_id=ANIMAL,
        property_id=property_id,
        start_time=start,
        end_time=end,
        status=StayStatus.ACTIVE if end is None else StayStatus.CLOSED,
    )


def _servico(
    stays: list[PropertyStay],
    layers: dict[TypedId, list[PropertyGeometry]],
) -> ProtectedAreaStayService:
    return ProtectedAreaStayService(
        stay_repository=FakeStayRepo(stays),
        geometry_repository=FakeGeometryRepo(layers),
    )


def test_reserva_legal_declarada_no_imovel_da_permanencia() -> None:
    servico = _servico(
        [_permanencia(FAZENDA_A, start=datetime(2026, 1, 10, tzinfo=UTC))],
        {
            FAZENDA_A: [
                _geometria(FAZENDA_A, "AREA_IMOVEL"),
                _geometria(FAZENDA_A, "RESERVA_LEGAL"),
            ]
        },
    )

    resultado = servico.assess_animal(ORG, ANIMAL)

    assert resultado.status is ProtectedAreaStayStatus.COM_AREA_PROTEGIDA_DECLARADA
    assert [camada.layer for camada in resultado.stays[0].declared_layers] == ["RESERVA_LEGAL"]
    assert resultado.properties_with_declared_area == (FAZENDA_A,)
    assert resultado.gaps == ()


def test_perimetro_sozinho_nao_e_area_protegida() -> None:
    servico = _servico(
        [_permanencia(FAZENDA_A, start=datetime(2026, 1, 10, tzinfo=UTC))],
        {FAZENDA_A: [_geometria(FAZENDA_A, "AREA_IMOVEL")]},
    )

    resultado = servico.assess_animal(ORG, ANIMAL)

    assert resultado.status is ProtectedAreaStayStatus.SEM_AREA_PROTEGIDA_DECLARADA
    assert resultado.stays[0].declared_layers == ()


def test_apps_e_uso_restrito_entram_ordenados() -> None:
    servico = _servico(
        [_permanencia(FAZENDA_A, start=datetime(2026, 1, 10, tzinfo=UTC))],
        {
            FAZENDA_A: [
                _geometria(FAZENDA_A, "USO_RESTRITO"),
                _geometria(FAZENDA_A, "AREA_IMOVEL"),
                _geometria(FAZENDA_A, "APPS"),
            ]
        },
    )

    resultado = servico.assess_animal(ORG, ANIMAL)

    assert [camada.layer for camada in resultado.stays[0].declared_layers] == [
        "APPS",
        "USO_RESTRITO",
    ]


def test_hidrografia_e_area_consolidada_nao_sao_area_protegida() -> None:
    """Camada do imóvel não é, por si, restrição legal de atividade."""
    servico = _servico(
        [_permanencia(FAZENDA_A, start=datetime(2026, 1, 10, tzinfo=UTC))],
        {
            FAZENDA_A: [
                _geometria(FAZENDA_A, "AREA_IMOVEL"),
                _geometria(FAZENDA_A, "HIDROGRAFIA"),
                _geometria(FAZENDA_A, "AREA_CONSOLIDADA"),
            ]
        },
    )

    resultado = servico.assess_animal(ORG, ANIMAL)

    assert resultado.status is ProtectedAreaStayStatus.SEM_AREA_PROTEGIDA_DECLARADA


def test_imovel_sem_geometria_importada_fica_indeterminado() -> None:
    """Ausência de CAR importado não é prova de ausência de área protegida."""
    servico = _servico(
        [_permanencia(FAZENDA_A, start=datetime(2026, 1, 10, tzinfo=UTC))],
        {},
    )

    resultado = servico.assess_animal(ORG, ANIMAL)

    assert resultado.status is ProtectedAreaStayStatus.INDETERMINADA
    assert resultado.gaps[0].code is ProtectedAreaStayGapCode.GEOMETRIA_AUSENTE
    assert resultado.gaps[0].property_id == FAZENDA_A


def test_animal_sem_permanencia_fica_indeterminado() -> None:
    resultado = _servico([], {}).assess_animal(ORG, ANIMAL)

    assert resultado.status is ProtectedAreaStayStatus.INDETERMINADA
    assert resultado.gaps[0].code is ProtectedAreaStayGapCode.PERMANENCIA_AUSENTE
    assert resultado.stays == ()


def test_declaracao_positiva_vence_lacuna_de_outro_imovel() -> None:
    """Reserva legal declarada em A continua valendo com B sem CAR importado."""
    servico = _servico(
        [
            _permanencia(
                FAZENDA_A,
                start=datetime(2026, 1, 10, tzinfo=UTC),
                end=datetime(2026, 3, 1, tzinfo=UTC),
            ),
            _permanencia(FAZENDA_B, start=datetime(2026, 3, 1, tzinfo=UTC)),
        ],
        {
            FAZENDA_A: [
                _geometria(FAZENDA_A, "AREA_IMOVEL"),
                _geometria(FAZENDA_A, "RESERVA_LEGAL"),
            ]
        },
    )

    resultado = servico.assess_animal(ORG, ANIMAL)

    assert resultado.status is ProtectedAreaStayStatus.COM_AREA_PROTEGIDA_DECLARADA
    assert resultado.properties_with_declared_area == (FAZENDA_A,)
    assert [gap.code for gap in resultado.gaps] == [ProtectedAreaStayGapCode.GEOMETRIA_AUSENTE]


def test_captura_posterior_ao_fim_da_permanencia_vira_lacuna() -> None:
    """CAR atualizado depois da saída descreve o imóvel de hoje, não o período."""
    servico = _servico(
        [
            _permanencia(
                FAZENDA_A,
                start=datetime(2026, 1, 10, tzinfo=UTC),
                end=datetime(2026, 3, 1, tzinfo=UTC),
            )
        ],
        {
            FAZENDA_A: [
                _geometria(
                    FAZENDA_A,
                    "AREA_IMOVEL",
                    captured_at=datetime(2026, 7, 1, tzinfo=UTC),
                ),
                _geometria(
                    FAZENDA_A,
                    "RESERVA_LEGAL",
                    captured_at=datetime(2026, 7, 1, tzinfo=UTC),
                ),
            ]
        },
    )

    resultado = servico.assess_animal(ORG, ANIMAL)

    assert resultado.status is ProtectedAreaStayStatus.COM_AREA_PROTEGIDA_DECLARADA
    gap = resultado.gaps[0]
    assert gap.code is ProtectedAreaStayGapCode.CAPTURA_POSTERIOR_A_PERMANENCIA
    assert "AREA_IMOVEL, RESERVA_LEGAL" in gap.message


def test_captura_anterior_a_permanencia_nao_gera_lacuna() -> None:
    servico = _servico(
        [
            _permanencia(
                FAZENDA_A,
                start=datetime(2026, 1, 10, tzinfo=UTC),
                end=datetime(2026, 3, 1, tzinfo=UTC),
            )
        ],
        {
            FAZENDA_A: [
                _geometria(
                    FAZENDA_A,
                    "RESERVA_LEGAL",
                    captured_at=datetime(2025, 11, 1, tzinfo=UTC),
                )
            ]
        },
    )

    resultado = servico.assess_animal(ORG, ANIMAL)

    assert resultado.gaps == ()


def test_permanencia_de_outra_organizacao_e_ignorada() -> None:
    servico = _servico(
        [
            _permanencia(
                FAZENDA_A,
                start=datetime(2026, 1, 10, tzinfo=UTC),
                organization_id=OUTRA_ORG,
            )
        ],
        {
            FAZENDA_A: [
                _geometria(FAZENDA_A, "RESERVA_LEGAL"),
            ]
        },
    )

    resultado = servico.assess_animal(ORG, ANIMAL)

    assert resultado.status is ProtectedAreaStayStatus.INDETERMINADA
    assert resultado.gaps[0].code is ProtectedAreaStayGapCode.PERMANENCIA_AUSENTE


def test_geometria_de_outra_organizacao_nao_afirma_area_protegida() -> None:
    servico = _servico(
        [_permanencia(FAZENDA_A, start=datetime(2026, 1, 10, tzinfo=UTC))],
        {
            FAZENDA_A: [
                _geometria(FAZENDA_A, "RESERVA_LEGAL", organization_id=OUTRA_ORG),
            ]
        },
    )

    resultado = servico.assess_animal(ORG, ANIMAL)

    assert resultado.status is ProtectedAreaStayStatus.INDETERMINADA
    assert resultado.gaps[0].code is ProtectedAreaStayGapCode.GEOMETRIA_AUSENTE


def test_limitacao_de_posicao_intra_imovel_sempre_declarada() -> None:
    """O resultado positivo nunca afirma que o animal esteve dentro do polígono."""
    servico = _servico(
        [_permanencia(FAZENDA_A, start=datetime(2026, 1, 10, tzinfo=UTC))],
        {FAZENDA_A: [_geometria(FAZENDA_A, "RESERVA_LEGAL")]},
    )

    resultado = servico.assess_animal(ORG, ANIMAL)

    assert POSICAO_INTRA_IMOVEL_DESCONHECIDA in resultado.limitations


def test_alvo_precisa_ser_animal() -> None:
    servico = _servico([], {})

    try:
        servico.assess_animal(ORG, TypedId.new("rural_property"))
    except ValueError as erro:
        assert "entity_type 'animal'" in str(erro)
    else:  # pragma: no cover - o teste falha antes de chegar aqui
        raise AssertionError("Um alvo que não é animal deveria ser recusado.")
