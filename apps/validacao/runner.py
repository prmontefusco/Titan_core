"""Execução guiada de um roteiro de validação contra a API real.

Percorrer o roteiro pelo Swagger custa caro: cada passo exige copiar o
identificador que o passo anterior devolveu, colar no corpo seguinte, e conferir
o resultado a olho. O tédio não é o pior — o pior é que um engano de cópia produz
um erro que parece defeito da aplicação, e foi assim que a validação do Passo
13.1 se perdeu duas vezes.

**O que este módulo não faz é decidir se o passo está correto.** Ele executa,
mostra o que pediu, o que esperava e o que veio, e diz se bateu. O julgamento
continua sendo de quem valida — é para isso que cada passo imprime a resposta
inteira quando falha, e um resumo quando acerta.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

_TIMEOUT_SEGUNDOS = 30

VERDE = "\033[32m"
VERMELHO = "\033[31m"
AMARELO = "\033[33m"
CINZA = "\033[90m"
NEGRITO = "\033[1m"
FIM = "\033[0m"


@dataclass(frozen=True, slots=True)
class Resposta:
    status: int
    corpo: Any

    def __getitem__(self, chave: str) -> Any:
        return self.corpo[chave]


@dataclass
class Requisicao:
    """O que foi enviado, guardado para ser mostrado junto com o resultado.

    Ver a requisição ao lado da resposta é o que permite conferir o roteiro sem
    abrir o código dele: sem o corpo à vista, "esperava 201 e veio 409" obriga a
    ir ler o script para saber o que foi pedido.
    """

    metodo: str
    caminho: str
    corpo: Mapping[str, Any] | None
    autor: str


@dataclass
class Cliente:
    """Cliente HTTP mínimo, com o cabeçalho de organização sempre preenchido.

    Esquecer `X-Titan-Organization-Id` é o engano que a API responde com 400, e
    num roteiro automatizado ele nunca deveria acontecer por descuido.
    """

    base_url: str
    token: str
    organization_id: str
    rotulo: str
    # Compartilhado entre os clientes: um passo é de um autor só, e o relato
    # precisa dizer qual — a mesma chamada muda de significado conforme quem a faz.
    diario: list[Requisicao] = field(default_factory=list)

    def requisitar(
        self,
        metodo: str,
        caminho: str,
        corpo: Mapping[str, Any] | None = None,
        *,
        com_organizacao: bool = True,
    ) -> Resposta:
        self.diario.append(Requisicao(metodo, caminho, corpo, self.rotulo))
        url = f"{self.base_url.rstrip('/')}{caminho}"
        dados = None if corpo is None else json.dumps(corpo).encode("utf-8")
        cabecalhos = {"Accept": "application/json", "Authorization": f"Bearer {self.token}"}
        if dados is not None:
            cabecalhos["Content-Type"] = "application/json"
        if com_organizacao:
            cabecalhos["X-Titan-Organization-Id"] = self.organization_id

        requisicao = urllib.request.Request(url, data=dados, headers=cabecalhos, method=metodo)
        try:
            with urllib.request.urlopen(requisicao, timeout=_TIMEOUT_SEGUNDOS) as resposta:
                bruto = resposta.read()
                return Resposta(resposta.status, json.loads(bruto) if bruto else None)
        except urllib.error.HTTPError as erro:
            bruto = erro.read()
            try:
                corpo_erro = json.loads(bruto) if bruto else None
            except json.JSONDecodeError:
                corpo_erro = bruto.decode("utf-8", errors="replace")
            return Resposta(erro.code, corpo_erro)
        except urllib.error.URLError as erro:
            raise SystemExit(
                f"{VERMELHO}A API não respondeu em {url}: {erro.reason}{FIM}\n"
                "Suba a API antes de rodar o roteiro."
            ) from erro

    def post(self, caminho: str, corpo: Mapping[str, Any] | None = None, **kw: Any) -> Resposta:
        return self.requisitar("POST", caminho, corpo, **kw)

    def get(self, caminho: str, **kw: Any) -> Resposta:
        return self.requisitar("GET", caminho, None, **kw)


@dataclass
class Passo:
    numero: str
    titulo: str
    executar: Callable[[], Resposta]
    esperado: int
    conferir: Callable[[Resposta], str | None] = lambda _: None
    porque: str = ""
    guardar: Callable[[Resposta], None] | None = None


@dataclass
class Roteiro:
    """Uma sequência de passos, executada com relato legível."""

    titulo: str
    diario: list[Requisicao] = field(default_factory=list)
    passos: list[Passo] = field(default_factory=list)
    linhas_de_corpo: int = 18

    def passo(self, *args: Any, **kwargs: Any) -> None:
        self.passos.append(Passo(*args, **kwargs))

    def executar(self, pausar: bool = False) -> int:
        print(f"\n{NEGRITO}{self.titulo}{FIM}")
        print("=" * len(self.titulo))
        falhas: list[str] = []

        for passo in self.passos:
            print(f"\n{NEGRITO}[{passo.numero}] {passo.titulo}{FIM}")
            if passo.porque:
                print(f"{CINZA}  {passo.porque}{FIM}")

            marca = len(self.diario)
            try:
                resposta = passo.executar()
            except (KeyError, IndexError, TypeError) as erro:
                self._mostrar_requisicao(marca)
                falhas.append(
                    f"[{passo.numero}] {passo.titulo}: roteiro sem dado esperado "
                    f"para continuar ({erro!r})"
                )
                print(
                    f"  {CINZA}<-{FIM} {NEGRITO}sem resposta{FIM}  "
                    f"{VERMELHO}FALHOU{FIM} — roteiro sem dado esperado"
                )
                break
            self._mostrar_requisicao(marca)
            problema = self._avaliar(passo, resposta)

            veredito = (
                f"{VERDE}OK{FIM}"
                if problema is None
                else f"{VERMELHO}FALHOU{FIM} — esperava {passo.esperado}, {problema}"
            )
            print(f"  {CINZA}<-{FIM} {NEGRITO}{resposta.status}{FIM}  {veredito}")
            print(self._corpo(resposta.corpo))

            if problema is None:
                if passo.guardar is not None:
                    passo.guardar(resposta)
            else:
                falhas.append(f"[{passo.numero}] {passo.titulo}: {problema}")
                if pausar:
                    input(f"{CINZA}  — ENTER para encerrar —{FIM}")
                break

            if pausar:
                input(f"{CINZA}  — ENTER para o próximo —{FIM}")

        return self._fechar(falhas)

    def _mostrar_requisicao(self, marca: int) -> None:
        """Tudo o que o passo enviou, e não apenas a última chamada.

        Um passo pode fazer mais de uma requisição; mostrar só a última esconderia
        metade do que ele fez.
        """
        for pedido in self.diario[marca:]:
            print(
                f"  {CINZA}->{FIM} {NEGRITO}{pedido.metodo}{FIM} {pedido.caminho}"
                f"  {CINZA}({pedido.autor}){FIM}"
            )
            if pedido.corpo is not None:
                print(self._corpo(pedido.corpo))

    def _corpo(self, valor: Any) -> str:
        if valor is None:
            return f"{CINZA}     (sem corpo){FIM}"
        texto = json.dumps(valor, indent=2, ensure_ascii=False, default=str)
        linhas = texto.splitlines()
        if len(linhas) > self.linhas_de_corpo:
            restantes = len(linhas) - self.linhas_de_corpo
            linhas = [*linhas[: self.linhas_de_corpo], f"... (+{restantes} linhas)"]
        return CINZA + "\n".join(f"     {linha}" for linha in linhas) + FIM

    @staticmethod
    def _avaliar(passo: Passo, resposta: Resposta) -> str | None:
        if resposta.status != passo.esperado:
            return f"veio {resposta.status}"
        try:
            return passo.conferir(resposta)
        except (KeyError, IndexError, TypeError) as erro:
            return f"a resposta não tem a forma esperada ({erro!r})"

    def _fechar(self, falhas: list[str]) -> int:
        total = len(self.passos)
        print()
        if not falhas:
            print(f"{VERDE}{NEGRITO}Todos os {total} passos passaram.{FIM}")
            return 0
        print(f"{VERMELHO}{NEGRITO}{len(falhas)} de {total} passos falharam:{FIM}")
        for falha in falhas:
            print(f"  {VERMELHO}—{FIM} {falha}")
        print(
            f"\n{AMARELO}Não conclua que o passo está errado sem ler a resposta acima:{FIM} "
            "ambiente fora do lugar produz o mesmo sintoma que defeito de código."
        )
        return 1
