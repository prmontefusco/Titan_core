import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

POSTGIS_IMAGE = (
    "postgis/postgis:18-3.6@sha256:b410052c6f0d7d37b83cac1369df144e1c843971155dea3317961001704d0a9d"
)
MONGO_IMAGE = (
    "mongo:8.0.26-noble@sha256:b49841837cd7688885d7479d14a71733bacae4c99faaae615622384eaee045a0"
)
KEYCLOAK_IMAGE = (
    "quay.io/keycloak/keycloak:26.7.0@sha256:"
    "2eb3cd316835c990e69e26ade292ffa78f6fb0db7d5fc6377463c162e1979ac0"
)
KEYCLOAK_POSTGRES_IMAGE = (
    "postgres:18.4@sha256:3a82e1f56c8f0f5616a11103ac3d47e632c3938698946a7ad26da0df1334744a"
)
RABBITMQ_IMAGE = (
    "rabbitmq:4.3.3-management@sha256:"
    "2ddd1887437c46349a2f4830fff217a069ad4e462d99313afeac076f407258fa"
)
VALKEY_IMAGE = (
    "valkey/valkey:9.1.0@sha256:8e8d64b405ce18f41b8e5ee20aa4687a8ed0022d1298f2ce31cdcf3a76e09411"
)


def load_compose_config() -> dict[str, Any]:
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI não está disponível neste ambiente.")

    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return cast(dict[str, Any], json.loads(result.stdout))


def test_postgis_service_is_pinned_and_locally_scoped() -> None:
    config = load_compose_config()
    postgres = config["services"]["postgres"]

    assert postgres["image"] == POSTGIS_IMAGE
    assert postgres["ports"] == [
        {
            "mode": "ingress",
            "target": 5432,
            "published": "5432",
            "protocol": "tcp",
            "host_ip": "127.0.0.1",
        }
    ]
    assert postgres["volumes"] == [
        {
            "type": "volume",
            "source": "postgres_data",
            "target": "/var/lib/postgresql",
            "volume": {},
        }
    ]


def test_postgis_service_has_a_healthcheck() -> None:
    config = load_compose_config()
    healthcheck = config["services"]["postgres"]["healthcheck"]

    assert healthcheck["test"] == [
        "CMD-SHELL",
        "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB",
    ]
    assert healthcheck["retries"] == 10


def test_mongo_service_is_pinned_and_locally_scoped() -> None:
    config = load_compose_config()
    mongo = config["services"]["mongo"]

    assert mongo["image"] == MONGO_IMAGE
    assert mongo["ports"] == [
        {
            "mode": "ingress",
            "target": 27017,
            "published": "27017",
            "protocol": "tcp",
            "host_ip": "127.0.0.1",
        }
    ]
    assert mongo["volumes"] == [
        {
            "type": "volume",
            "source": "mongo_data",
            "target": "/data/db",
            "volume": {},
        }
    ]


def test_mongo_service_has_an_authenticated_healthcheck() -> None:
    config = load_compose_config()
    healthcheck = config["services"]["mongo"]["healthcheck"]
    health_command = healthcheck["test"][1]

    assert healthcheck["test"][0] == "CMD-SHELL"
    assert "$$MONGO_INITDB_ROOT_USERNAME" in health_command
    assert "$$MONGO_INITDB_ROOT_PASSWORD" in health_command
    assert "db.adminCommand('ping')" in health_command
    assert healthcheck["retries"] == 10


def test_keycloak_is_pinned_and_locally_scoped() -> None:
    config = load_compose_config()
    keycloak = config["services"]["keycloak"]

    assert keycloak["image"] == KEYCLOAK_IMAGE
    assert keycloak["command"] == ["start-dev", "--import-realm"]
    assert keycloak["ports"] == [
        {
            "mode": "ingress",
            "target": 8080,
            "published": "8080",
            "protocol": "tcp",
            "host_ip": "127.0.0.1",
        }
    ]
    assert keycloak["environment"]["KC_DB"] == "postgres"
    assert "keycloak-postgres:5432" in keycloak["environment"]["KC_DB_URL"]
    # A chave "bind" carrega normalizações que variam com a versão do Docker Compose
    # (ex.: create_host_path). Afirmar o dicionário inteiro tornaria o teste refém da
    # versão instalada, então verificamos o que de fato importa: o realm é montado
    # somente leitura, a partir do arquivo correto, no caminho esperado.
    assert len(keycloak["volumes"]) == 1
    realm_volume = keycloak["volumes"][0]
    assert realm_volume["type"] == "bind"
    assert realm_volume["source"] == str(Path("config/keycloak/titan-realm.json").resolve())
    assert realm_volume["target"] == "/opt/keycloak/data/import/titan-realm.json"
    assert realm_volume["read_only"] is True


def test_keycloak_waits_for_its_dedicated_database_and_has_readiness() -> None:
    config = load_compose_config()
    keycloak = config["services"]["keycloak"]
    healthcheck = keycloak["healthcheck"]

    assert keycloak["depends_on"]["keycloak-postgres"]["condition"] == "service_healthy"
    assert healthcheck["test"][0] == "CMD-SHELL"
    assert "/health/ready" in healthcheck["test"][1]
    assert "/dev/tcp/127.0.0.1/9000" in healthcheck["test"][1]


def test_keycloak_database_is_private_persistent_and_pinned() -> None:
    config = load_compose_config()
    database = config["services"]["keycloak-postgres"]

    assert database["image"] == KEYCLOAK_POSTGRES_IMAGE
    assert "ports" not in database
    assert database["volumes"] == [
        {
            "type": "volume",
            "source": "keycloak_postgres_data",
            "target": "/var/lib/postgresql",
            "volume": {},
        }
    ]
    assert database["healthcheck"]["test"] == [
        "CMD-SHELL",
        "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB",
    ]


def test_keycloak_local_realm_separates_api_and_swagger_with_pkce() -> None:
    realm = json.loads(Path("config/keycloak/titan-realm.json").read_text(encoding="utf-8"))
    clients = {client["clientId"]: client for client in realm["clients"]}
    api = clients["titan-api"]
    swagger = clients["titan-swagger"]
    assert api["bearerOnly"] is True
    assert swagger["publicClient"] is True
    assert swagger["standardFlowEnabled"] is True
    assert swagger["implicitFlowEnabled"] is False
    assert swagger["directAccessGrantsEnabled"] is False
    assert swagger["attributes"]["pkce.code.challenge.method"] == "S256"
    mappers = {mapper["name"]: mapper for mapper in swagger["protocolMappers"]}
    assert mappers["titan-api-audience"]["config"]["id.token.claim"] == "false"
    purpose = mappers["titan-access-token-purpose"]["config"]
    assert purpose["claim.value"] == "access"
    assert purpose["id.token.claim"] == "false"
    assert purpose["access.token.claim"] == "true"


def test_rabbitmq_is_pinned_persistent_and_locally_scoped() -> None:
    config = load_compose_config()
    rabbitmq = config["services"]["rabbitmq"]

    assert rabbitmq["image"] == RABBITMQ_IMAGE
    assert rabbitmq["hostname"] == "titan-rabbitmq"
    assert rabbitmq["ports"] == [
        {
            "mode": "ingress",
            "target": 5672,
            "published": "5672",
            "protocol": "tcp",
            "host_ip": "127.0.0.1",
        },
        {
            "mode": "ingress",
            "target": 15672,
            "published": "15672",
            "protocol": "tcp",
            "host_ip": "127.0.0.1",
        },
    ]
    assert rabbitmq["volumes"] == [
        {
            "type": "volume",
            "source": "rabbitmq_data",
            "target": "/var/lib/rabbitmq",
            "volume": {},
        }
    ]


def test_rabbitmq_has_authenticated_defaults_and_healthcheck() -> None:
    config = load_compose_config()
    rabbitmq = config["services"]["rabbitmq"]
    healthcheck = rabbitmq["healthcheck"]

    assert rabbitmq["environment"]["RABBITMQ_DEFAULT_USER"] == "titan"
    assert rabbitmq["environment"]["RABBITMQ_DEFAULT_VHOST"] == "titan"
    assert rabbitmq["environment"]["RABBITMQ_DEFAULT_PASS"]
    assert healthcheck["test"][0] == "CMD-SHELL"
    assert "rabbitmq-diagnostics -q check_running" in healthcheck["test"][1]
    assert "rabbitmq-diagnostics -q check_local_alarms" in healthcheck["test"][1]


def test_valkey_is_pinned_ephemeral_and_locally_scoped() -> None:
    config = load_compose_config()
    valkey = config["services"]["valkey"]

    assert valkey["image"] == VALKEY_IMAGE
    assert valkey["ports"] == [
        {
            "mode": "ingress",
            "target": 6379,
            "published": "6379",
            "protocol": "tcp",
            "host_ip": "127.0.0.1",
        }
    ]
    assert "volumes" not in valkey
    assert valkey["command"][-4:] == ["--save", "", "--appendonly", "no"]


def test_valkey_has_authentication_memory_limit_eviction_and_healthcheck() -> None:
    config = load_compose_config()
    valkey = config["services"]["valkey"]
    command = valkey["command"]
    healthcheck = valkey["healthcheck"]

    assert command[command.index("--requirepass") + 1]
    assert command[command.index("--maxmemory") + 1] == "128mb"
    assert command[command.index("--maxmemory-policy") + 1] == "allkeys-lfu"
    assert healthcheck["test"][0] == "CMD-SHELL"
    assert 'VALKEYCLI_AUTH="$$VALKEY_PASSWORD"' in healthcheck["test"][1]
    assert "valkey-cli ping" in healthcheck["test"][1]
