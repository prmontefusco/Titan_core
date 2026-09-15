import pytest

from packages.livestock_application.gta_declaration import (
    GtaPayloadInvalido,
    validar_payload_gta,
)


def _payload_valido(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "gta_number": "MS-000123456",
        "issuing_state": "MS",
        "issuing_agency": "IAGRO",
        "issued_at": "2026-09-10",
        "origin_description": "Fazenda Santa Rita, Ribas do Rio Pardo/MS",
        "destination_description": "Fazenda Boa Vista, Campo Grande/MS",
        "purpose": "recria",
        "animal_count": 40,
    }
    base.update(overrides)
    return base


def test_payload_completo_e_valido() -> None:
    validar_payload_gta(_payload_valido())


def test_campos_opcionais_ausentes_nao_disparam_erro() -> None:
    payload = _payload_valido()
    assert "sanitary_conditions" not in payload
    assert "veterinarian_name" not in payload
    validar_payload_gta(payload)


@pytest.mark.parametrize(
    "campo",
    ["gta_number", "issuing_agency", "origin_description", "destination_description", "purpose"],
)
def test_campo_string_obrigatorio_ausente_e_recusado(campo: str) -> None:
    payload = _payload_valido()
    del payload[campo]
    with pytest.raises(GtaPayloadInvalido) as excinfo:
        validar_payload_gta(payload)
    assert excinfo.value.campo == campo


@pytest.mark.parametrize(
    "campo",
    ["gta_number", "issuing_agency", "origin_description", "destination_description", "purpose"],
)
def test_campo_string_obrigatorio_vazio_e_recusado(campo: str) -> None:
    payload = _payload_valido(**{campo: "   "})
    with pytest.raises(GtaPayloadInvalido) as excinfo:
        validar_payload_gta(payload)
    assert excinfo.value.campo == campo


@pytest.mark.parametrize("valor", [None, "m", "MSS", "ms"])
def test_issuing_state_invalido_e_recusado(valor: object) -> None:
    payload = _payload_valido(issuing_state=valor) if valor is not None else _payload_valido()
    if valor is None:
        del payload["issuing_state"]
    with pytest.raises(GtaPayloadInvalido) as excinfo:
        validar_payload_gta(payload)
    assert excinfo.value.campo == "issuing_state"


def test_issued_at_ausente_e_recusado() -> None:
    payload = _payload_valido()
    del payload["issued_at"]
    with pytest.raises(GtaPayloadInvalido) as excinfo:
        validar_payload_gta(payload)
    assert excinfo.value.campo == "issued_at"


@pytest.mark.parametrize("valor", ["10/09/2026", "2026-09-32", "nao e uma data", ""])
def test_issued_at_nao_iso_e_recusado(valor: str) -> None:
    payload = _payload_valido(issued_at=valor)
    with pytest.raises(GtaPayloadInvalido) as excinfo:
        validar_payload_gta(payload)
    assert excinfo.value.campo == "issued_at"


def test_animal_count_ausente_e_recusado() -> None:
    payload = _payload_valido()
    del payload["animal_count"]
    with pytest.raises(GtaPayloadInvalido) as excinfo:
        validar_payload_gta(payload)
    assert excinfo.value.campo == "animal_count"


@pytest.mark.parametrize("valor", ["40", 0, -1, True, False, 1.5])
def test_animal_count_invalido_e_recusado(valor: object) -> None:
    payload = _payload_valido(animal_count=valor)
    with pytest.raises(GtaPayloadInvalido) as excinfo:
        validar_payload_gta(payload)
    assert excinfo.value.campo == "animal_count"
