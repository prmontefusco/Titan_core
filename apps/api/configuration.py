"""Conferência da configuração no arranque da API (Passo 10.4, dívida).

A API subia sem as variáveis de OIDC e só falhava na **primeira requisição
autenticada** — e falhava respondendo sobre o token, que estava correto. Quem
integrava ia conferir a credencial enquanto o defeito era do servidor.

Falhar no arranque troca um erro tardio e enganoso por um imediato e nomeado:
o processo não sobe, e diz exatamente qual variável falta.

**Presença não bastou.** Conferir apenas se a variável está definida deixa passar
o engano mais caro: a variável definida com o valor errado. Um
`TITAN_OPERATOR_ORGANIZATION_ID` que não é UUID deixou o `uvicorn` anunciar
"Application startup complete" e estourou na primeira requisição como **500
sanitizado**, cuja causa real só existia no log do servidor — pelo Swagger, o
sintoma era indistinguível de erro nos dados enviados. Por isso o arranque
também confere a **forma** do que foi definido.

O limite continua honesto, e é a distinção que importa: conferimos forma, nunca
alcançabilidade. Que a URL seja de PostgreSQL, o arranque garante; que o banco
exista, responda e tenha as tabelas, não — isso é I/O, e descobre-se usando.
Mesmo para o emissor: que seja uma URL http, sim; que seja o Keycloak que assina
os tokens, não.
"""

import os
from collections.abc import Callable, Mapping
from urllib.parse import urlsplit
from uuid import UUID

VARIAVEIS_OBRIGATORIAS: dict[str, str] = {
    "TITAN_DATABASE_URL": "conexão com o PostgreSQL",
    "TITAN_OPERATOR_ORGANIZATION_ID": "Organization operadora, dona dos registros de User",
    "TITAN_OIDC_ISSUER": "emissor dos tokens, usado na validação",
    "TITAN_OIDC_AUDIENCE": "público esperado no token (audience)",
}


class ConfiguracaoIncompleta(RuntimeError):
    """Falta configuração para a API operar."""


class ConfiguracaoInvalida(RuntimeError):
    """A configuração está definida, mas não tem a forma que a API exige."""


def _uuid(valor: str) -> str | None:
    try:
        UUID(valor)
    except ValueError:
        return "um UUID"
    return None


def _url_http(valor: str) -> str | None:
    partes = urlsplit(valor)
    if partes.scheme in {"http", "https"} and partes.netloc:
        return None
    return "uma URL absoluta começando por http:// ou https://"


def _url_postgresql(valor: str) -> str | None:
    partes = urlsplit(valor)
    # O driver vem depois de `+` (`postgresql+psycopg`), e qual driver é fica a
    # cargo do SQLAlchemy: aqui só importa que o banco seja PostgreSQL.
    if partes.scheme.split("+")[0] == "postgresql" and partes.netloc:
        return None
    return "uma URL postgresql://... (o Titan usa postgresql+psycopg)"


# `TITAN_OIDC_AUDIENCE` fica deliberadamente fora: audience é uma cadeia livre
# acordada com o emissor, e inventar uma forma para ela recusaria configuração
# legítima — que é pior do que não conferir.
FORMA_EXIGIDA: dict[str, Callable[[str], str | None]] = {
    "TITAN_DATABASE_URL": _url_postgresql,
    "TITAN_OPERATOR_ORGANIZATION_ID": _uuid,
    "TITAN_OIDC_ISSUER": _url_http,
}

# O valor recebido viaja na mensagem, porque é ele que torna o diagnóstico
# imediato — exceto onde carrega credencial. A URL do banco traz a senha, e
# mensagem de arranque acaba em log, em ticket e em captura de tela.
NAO_ECOAR: frozenset[str] = frozenset({"TITAN_DATABASE_URL"})


def variaveis_ausentes(ambiente: Mapping[str, str] | None = None) -> list[str]:
    fonte = os.environ if ambiente is None else ambiente
    return [nome for nome in VARIAVEIS_OBRIGATORIAS if not fonte.get(nome, "").strip()]


def variaveis_malformadas(ambiente: Mapping[str, str] | None = None) -> dict[str, str]:
    """Nome da variável definida com valor de forma errada, e o que se esperava.

    Só examina o que está presente: variável ausente é assunto de
    `variaveis_ausentes`, e acusá-la duas vezes só faria a mensagem confundir.
    """
    fonte = os.environ if ambiente is None else ambiente
    encontrados: dict[str, str] = {}
    for nome, confere in FORMA_EXIGIDA.items():
        valor = fonte.get(nome, "").strip()
        if not valor:
            continue
        esperado = confere(valor)
        if esperado is not None:
            encontrados[nome] = esperado
    return encontrados


def exigir_configuracao(ambiente: Mapping[str, str] | None = None) -> None:
    ausentes = variaveis_ausentes(ambiente)
    if ausentes:
        detalhe = "\n".join(f"  {nome}: {VARIAVEIS_OBRIGATORIAS[nome]}" for nome in ausentes)
        raise ConfiguracaoIncompleta(
            "A API não pode subir sem estas variáveis de ambiente:\n" + detalhe
        )

    fonte = os.environ if ambiente is None else ambiente
    malformadas = variaveis_malformadas(ambiente)
    if malformadas:
        linhas = []
        for nome, esperado in malformadas.items():
            linha = f"  {nome}: esperava {esperado}"
            if nome not in NAO_ECOAR:
                linha += f", e recebeu '{fonte.get(nome, '').strip()}'"
            linhas.append(linha)
        raise ConfiguracaoInvalida(
            "A API não pode subir com estas variáveis de ambiente malformadas:\n"
            + "\n".join(linhas)
        )
