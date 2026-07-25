"""Cliente mínimo da API de administração do Keycloak (Passo 10.6, antecipado).

Usa apenas a biblioteca padrão: acrescentar dependência HTTP de produção por
causa de uma ferramenta de desenvolvimento seria caro pelo motivo errado.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

_TIMEOUT_SEGUNDOS = 15


class KeycloakError(RuntimeError):
    pass


def _requisicao(
    metodo: str,
    url: str,
    *,
    token: str | None = None,
    json_body: dict[str, Any] | None = None,
    form: dict[str, str] | None = None,
) -> tuple[int, Any]:
    dados: bytes | None = None
    cabecalhos: dict[str, str] = {"Accept": "application/json"}
    if json_body is not None:
        dados = json.dumps(json_body).encode("utf-8")
        cabecalhos["Content-Type"] = "application/json"
    elif form is not None:
        dados = urllib.parse.urlencode(form).encode("utf-8")
        cabecalhos["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"

    requisicao = urllib.request.Request(url, data=dados, headers=cabecalhos, method=metodo)
    try:
        with urllib.request.urlopen(requisicao, timeout=_TIMEOUT_SEGUNDOS) as resposta:
            bruto = resposta.read()
            return resposta.status, (json.loads(bruto) if bruto else None)
    except urllib.error.HTTPError as erro:
        corpo = erro.read().decode("utf-8", errors="replace")
        raise KeycloakError(f"{metodo} {url} devolveu {erro.code}: {corpo}") from erro
    except urllib.error.URLError as erro:
        raise KeycloakError(f"Keycloak inacessível em {url}: {erro.reason}") from erro


@dataclass(frozen=True, slots=True)
class AdminKeycloak:
    base_url: str
    realm: str
    token: str

    @classmethod
    def autenticar(cls, *, base_url: str, realm: str, usuario: str, senha: str) -> "AdminKeycloak":
        _, corpo = _requisicao(
            "POST",
            f"{base_url}/realms/master/protocol/openid-connect/token",
            form={
                "client_id": "admin-cli",
                "grant_type": "password",
                "username": usuario,
                "password": senha,
            },
        )
        return cls(base_url=base_url, realm=realm, token=corpo["access_token"])

    def garantir_duracao_de_token(self, segundos: int) -> int:
        """Amplia a validade do access token **no realm local de demonstração**.

        O padrão do Keycloak é de cinco minutos, o que é correto em produção e
        inviável numa validação manual: o token expira no meio do roteiro e a
        resposta 401 parece defeito da API quando é só a credencial vencendo.

        Só faz sentido aqui. Ampliar validade de token em ambiente real amplia a
        janela em que uma credencial vazada continua servindo.
        """
        _, realm = _requisicao(
            "GET", f"{self.base_url}/admin/realms/{self.realm}", token=self.token
        )
        atual = int(realm.get("accessTokenLifespan") or 0)
        if atual >= segundos:
            return atual
        realm["accessTokenLifespan"] = segundos
        _requisicao(
            "PUT",
            f"{self.base_url}/admin/realms/{self.realm}",
            token=self.token,
            json_body=realm,
        )
        return segundos

    def garantir_usuario(self, *, username: str, senha: str) -> str:
        """Cria o usuário se faltar, e devolve o `sub` — que é o id dele no Keycloak.

        Reusar quando já existe é o que permite rodar a semeadura várias vezes: o
        vínculo externo do Titan é único por (emissor, subject), e criar um
        usuário novo a cada execução deixaria identidades órfãs para trás.
        """
        existente = self._procurar(username)
        if existente is not None:
            self._definir_senha(existente, senha)
            return existente

        _requisicao(
            "POST",
            f"{self.base_url}/admin/realms/{self.realm}/users",
            token=self.token,
            json_body={
                "username": username,
                "enabled": True,
                "emailVerified": True,
                "firstName": username,
                "lastName": "Demonstracao",
                "credentials": [{"type": "password", "value": senha, "temporary": False}],
            },
        )
        criado = self._procurar(username)
        if criado is None:
            raise KeycloakError(f"Usuário '{username}' não apareceu após a criação.")
        return criado

    def _procurar(self, username: str) -> str | None:
        consulta = urllib.parse.urlencode({"username": username, "exact": "true"})
        _, corpo = _requisicao(
            "GET",
            f"{self.base_url}/admin/realms/{self.realm}/users?{consulta}",
            token=self.token,
        )
        if not corpo:
            return None
        return str(corpo[0]["id"])

    def _definir_senha(self, user_id: str, senha: str) -> None:
        _requisicao(
            "PUT",
            f"{self.base_url}/admin/realms/{self.realm}/users/{user_id}/reset-password",
            token=self.token,
            json_body={"type": "password", "value": senha, "temporary": False},
        )
