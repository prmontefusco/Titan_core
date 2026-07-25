"""Fiação do provider de geodados (Passo 17.2, ADR-0026).

**A configuração é opcional, e de propósito.** A API sobe e opera inteira sem o
Titan_geodata; só a consulta e a importação do CAR ficam indisponíveis, e
respondem dizendo exatamente o que falta.

Tratá-la como obrigatória — junto das quatro variáveis que o arranque exige —
impediria subir o Titan para quem não usa o provider, e a dependência de uma
integração externa passaria a bloquear o produto inteiro.

A chave **nunca vive no repositório**: entra por ambiente, como as demais
credenciais.
"""

import os
from functools import lru_cache

from packages.livestock_infrastructure.geodata import CarLookupPort, GeodataCarClient

URL_VARIAVEL = "TITAN_GEODATA_URL"
CHAVE_VARIAVEL = "TITAN_GEODATA_API_KEY"  # noqa: S105 — nome da variável, não o segredo


@lru_cache(maxsize=1)
def car_lookup_opcional() -> CarLookupPort | None:
    """O cliente do CAR, ou `None` quando o provider não está configurado.

    Devolver `None` em vez de levantar erro é o que mantém a integração opcional:
    quem chamar a rota recebe uma recusa que nomeia as variáveis ausentes, e quem
    não a chamar nem percebe que ela existe.
    """
    base_url = os.environ.get(URL_VARIAVEL, "").strip()
    api_key = os.environ.get(CHAVE_VARIAVEL, "").strip()
    if not base_url or not api_key:
        return None
    return GeodataCarClient(base_url=base_url, api_key=api_key)
