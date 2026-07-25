"""Conferência da configuração no arranque da API (Passo 10.4, dívida).

A API subia sem as variáveis de OIDC e só falhava na **primeira requisição
autenticada** — e falhava respondendo sobre o token, que estava correto. Quem
integrava ia conferir a credencial enquanto o defeito era do servidor.

Falhar no arranque troca um erro tardio e enganoso por um imediato e nomeado:
o processo não sobe, e diz exatamente qual variável falta.

Aqui só se confere **presença**. Se a URL do banco aponta para lugar errado, ou
se o emissor não corresponde ao Keycloak que assina os tokens, isso o arranque
não descobre — descobre-se na primeira requisição, e é o limite honesto desta
conferência.
"""

import os
from collections.abc import Mapping

VARIAVEIS_OBRIGATORIAS: dict[str, str] = {
    "TITAN_DATABASE_URL": "conexão com o PostgreSQL",
    "TITAN_OPERATOR_ORGANIZATION_ID": "Organization operadora, dona dos registros de User",
    "TITAN_OIDC_ISSUER": "emissor dos tokens, usado na validação",
    "TITAN_OIDC_AUDIENCE": "público esperado no token (audience)",
}


class ConfiguracaoIncompleta(RuntimeError):
    """Falta configuração para a API operar."""


def variaveis_ausentes(ambiente: Mapping[str, str] | None = None) -> list[str]:
    fonte = os.environ if ambiente is None else ambiente
    return [nome for nome in VARIAVEIS_OBRIGATORIAS if not fonte.get(nome, "").strip()]


def exigir_configuracao(ambiente: Mapping[str, str] | None = None) -> None:
    ausentes = variaveis_ausentes(ambiente)
    if not ausentes:
        return
    detalhe = "\n".join(f"  {nome}: {VARIAVEIS_OBRIGATORIAS[nome]}" for nome in ausentes)
    raise ConfiguracaoIncompleta(
        "A API não pode subir sem estas variáveis de ambiente:\n" + detalhe
    )
