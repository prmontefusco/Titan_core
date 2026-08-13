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

    def garantir_cliente_de_validacao(self, client_id: str) -> None:
        """Cliente público com *direct access grant*, para o roteiro automatizado.

        O `titan-swagger` tem `directAccessGrantsEnabled: false`, e está certo: ele
        existe para o fluxo de navegador com PKCE. Um script de validação não tem
        navegador, e habilitar o grant nele afrouxaria o cliente que a demonstração
        usa de verdade. Um cliente à parte mantém essa separação.

        **Só faz sentido no realm local descartável**, pelo mesmo motivo que
        ampliar a validade do token: trocar senha por token sem interação é
        exatamente o que não se quer em produção.

        Os mapeadores não são detalhe: ver `_mapeadores_de_validacao`.
        """
        mapeadores = self._mapeadores_de_validacao()
        _, existentes = _requisicao(
            "GET",
            f"{self.base_url}/admin/realms/{self.realm}/clients"
            f"?{urllib.parse.urlencode({'clientId': client_id})}",
            token=self.token,
        )
        if existentes:
            # Idempotente de verdade: um cliente criado por uma versão anterior,
            # sem algum mapeador, precisa ser completado. Sair cedo aqui deixaria
            # o token quebrado para sempre, e o sintoma seria um 401 que fala do
            # token quando o defeito está na configuração do cliente.
            self._completar_mapeadores(str(existentes[0]["id"]), mapeadores)
            return

        _requisicao(
            "POST",
            f"{self.base_url}/admin/realms/{self.realm}/clients",
            token=self.token,
            json_body={
                "clientId": client_id,
                "name": "Titan — validação automatizada (local)",
                "enabled": True,
                "publicClient": True,
                "standardFlowEnabled": False,
                "directAccessGrantsEnabled": True,
                "protocol": "openid-connect",
                "protocolMappers": mapeadores,
            },
        )

    def _completar_mapeadores(self, id_interno: str, desejados: list[dict[str, Any]]) -> None:
        caminho = (
            f"{self.base_url}/admin/realms/{self.realm}/clients/{id_interno}"
            "/protocol-mappers/models"
        )
        _, atuais = _requisicao("GET", caminho, token=self.token)
        presentes = {mapeador["name"] for mapeador in (atuais or [])}
        for mapeador in desejados:
            if mapeador["name"] not in presentes:
                _requisicao("POST", caminho, token=self.token, json_body=mapeador)

    @staticmethod
    def _mapeadores_de_validacao() -> list[dict[str, Any]]:
        """Os dois claims sem os quais a API recusa o token.

        `aud: titan-api` diz para quem o token vale; `token_use: access` distingue
        credencial de acesso de ID token. Faltando qualquer um, a resposta é 401 —
        e o 401 fala do token, quando o defeito está na configuração do cliente.
        """
        return [
            {
                "name": "titan-api-audience",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-audience-mapper",
                "consentRequired": False,
                "config": {
                    "included.client.audience": "titan-api",
                    "id.token.claim": "false",
                    "access.token.claim": "true",
                },
            },
            {
                "name": "titan-access-token-purpose",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-hardcoded-claim-mapper",
                "consentRequired": False,
                "config": {
                    "claim.name": "token_use",
                    "claim.value": "access",
                    "jsonType.label": "String",
                    "id.token.claim": "false",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "false",
                    "access.tokenResponse.claim": "false",
                },
            },
        ]

    def garantir_atributo_de_perfil_select(
        self,
        *,
        nome: str,
        rotulo: str,
        opcoes: list[str],
        rotulos_das_opcoes: dict[str, str],
    ) -> None:
        """Acrescenta um atributo de escolha única ao perfil declarativo do realm.

        O valor escolhido não concede nada por si só (ADR-0031: sem
        autoatribuição) — é só uma conveniência de UX que o frontend lê como
        sugestão para pré-preencher o pedido real de tipo de entidade, que
        continua exigindo aprovação. Por isso fica de fora do Access Token e só
        entra no ID Token: nenhuma rota da API precisa confiar nele.

        Reaproveita o perfil (username/email/nome) em vez de substituí-lo — o
        endpoint de perfil é *set*, não *patch*: mandar só o atributo novo
        apagaria os demais.
        """
        _, perfil = _requisicao(
            "GET", f"{self.base_url}/admin/realms/{self.realm}/users/profile", token=self.token
        )
        atributos = [attr for attr in perfil.get("attributes", []) if attr.get("name") != nome]
        atributos.append(
            {
                "name": nome,
                "displayName": rotulo,
                "validations": {"options": {"options": opcoes}},
                "annotations": {
                    "inputType": "select",
                    "inputOptionLabels": rotulos_das_opcoes,
                },
                "permissions": {"view": ["admin", "user"], "edit": ["admin", "user"]},
                "multivalued": False,
            }
        )
        perfil["attributes"] = atributos
        _requisicao(
            "PUT",
            f"{self.base_url}/admin/realms/{self.realm}/users/profile",
            token=self.token,
            json_body=perfil,
        )

    def garantir_mapeador_de_atributo_no_id_token(
        self, client_id: str, *, nome_atributo: str, nome_claim: str
    ) -> None:
        _, existentes = _requisicao(
            "GET",
            f"{self.base_url}/admin/realms/{self.realm}/clients"
            f"?{urllib.parse.urlencode({'clientId': client_id})}",
            token=self.token,
        )
        if not existentes:
            raise KeycloakError(f"Client '{client_id}' não existe neste realm.")
        id_interno = str(existentes[0]["id"])

        caminho = (
            f"{self.base_url}/admin/realms/{self.realm}/clients/{id_interno}"
            "/protocol-mappers/models"
        )
        _, atuais = _requisicao("GET", caminho, token=self.token)
        nome_mapeador = f"titan-{nome_claim}"
        if any(mapeador["name"] == nome_mapeador for mapeador in (atuais or [])):
            return

        _requisicao(
            "POST",
            caminho,
            token=self.token,
            json_body={
                "name": nome_mapeador,
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-attribute-mapper",
                "consentRequired": False,
                "config": {
                    "user.attribute": nome_atributo,
                    "claim.name": nome_claim,
                    "jsonType.label": "String",
                    "id.token.claim": "true",
                    "access.token.claim": "false",
                    "userinfo.token.claim": "true",
                },
            },
        )

    def token_de_usuario(self, *, client_id: str, username: str, senha: str) -> str:
        _, corpo = _requisicao(
            "POST",
            f"{self.base_url}/realms/{self.realm}/protocol/openid-connect/token",
            form={
                "client_id": client_id,
                "grant_type": "password",
                "scope": "openid",
                "username": username,
                "password": senha,
            },
        )
        return str(corpo["access_token"])

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
                "email": f"{username}@titan-validacao.invalid",
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
