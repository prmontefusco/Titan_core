"""Adapter HTTP local: autentica sem persistir token e mapeia falhas explicitamente."""

from dataclasses import dataclass, field

from packages.livestock_application.sisbov_simulator import SisbovSimulatorRequest
from packages.livestock_infrastructure.sisbov_simulator_http import SisbovSimulatorHttpTransport


@dataclass
class Client:
    calls: list[tuple[str, str, dict[str, str]]] = field(default_factory=list)

    def request(self, method: str, path: str, headers: dict[str, str]) -> tuple[int, bytes]:
        self.calls.append((method, path, headers))
        if path == "/auth/system":
            return 200, b'{"access_token":"ephemeral"}'
        return 200, b'{"id":"a","numero":"BR1"}'


def test_adapter_autentica_e_consulta_path_allowlisted() -> None:
    client = Client()
    result = SisbovSimulatorHttpTransport(client, "test-key", "test-secret").get(
        SisbovSimulatorRequest.animal("BR1")
    )

    assert result.status_code == 200
    assert [item[:2] for item in client.calls] == [
        ("POST", "/auth/system"),
        ("GET", "/animal/BR1/getAnimalPorNumero"),
    ]
    assert client.calls[1][2] == {"Authorization": "Bearer ephemeral"}


def test_adapter_nao_consulta_recurso_quando_autenticacao_falha() -> None:
    class UnauthorizedClient:
        def request(self, method: str, path: str, headers: dict[str, str]) -> tuple[int, bytes]:
            return 401, b'{"error":"invalid"}'

    result = SisbovSimulatorHttpTransport(UnauthorizedClient(), "key", "secret").get(
        SisbovSimulatorRequest.gta("GTA1")
    )

    assert result.status_code == 401
