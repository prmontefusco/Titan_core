"""Roteiro de fumaça: roda todos os roteiros de `apps/validacao` em sequência.

Não substitui a leitura de um roteiro individual quando algo falha — só dá
uma primeira leitura de saúde do sistema em minutos, para quem não sabe qual
dos roteiros escolher às cegas. Cada roteiro roda como processo separado, do
jeito que já roda hoje (`python -m apps.validacao.<nome>`), e nenhum deles
precisou mudar para isso funcionar.

Pressupõe API e Keycloak no ar e a semeadura já executada (ver
`apps/validacao/README.md`). Falha de um roteiro nunca impede os demais: o
objetivo é o resumo do conjunto, não um veredito sobre qualquer um deles.

    python -m uv run --locked python -m apps.validacao.fumaca
"""

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass

from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, VERDE, VERMELHO

_TIMEOUT_SEGUNDOS = 180
_LINHAS_DE_CAUDA = 12

# Rótulo e argumentos de `python -m <argumentos>`. O primeiro é o roteiro do
# Passo 13.2, invocado por `python -m apps.validacao` (sem submódulo) porque
# vive em `__main__.py` — cresceu para incluir também reprodução (13.3) e
# geometria (17.1/17.2), mas o comando de invocação ficou o histórico.
ROTEIROS: tuple[tuple[str, list[str]], ...] = (
    ("Passo 13.2 — genealogia, reprodução e geometria", ["apps.validacao"]),
    ("ADR-0042 — contraparte externa", ["apps.validacao.contraparte_externa"]),
    ("ADR-0042 — aquisição documental", ["apps.validacao.aquisicao_documental"]),
    ("ADR-0042 — artefato de transferência", ["apps.validacao.artefato_transferencia"]),
    ("ADR-0042 — fato importado", ["apps.validacao.fato_importado"]),
    ("Corte 2B — captura SISBOV simulada", ["apps.validacao.captura_externa_sisbov_simulada"]),
    ("NR-4 — prescrição veterinária", ["apps.validacao.prescricao_veterinaria"]),
    (
        "Passo 14.3 — exigibilidade sanitária mínima",
        ["apps.validacao.exigibilidade_sanitaria_minima"],
    ),
    (
        "ADR-0056 — classificação sanitária de medicamento",
        ["apps.validacao.classificacao_sanitaria_medicamento"],
    ),
    ("NEXT-01 — coverage dimensional", ["apps.validacao.coverage_dimensional"]),
    (
        "ADR-0045 — qualificação de estabelecimento",
        ["apps.validacao.importacao_qualificacao_estabelecimento"],
    ),
    ("Perfis de mercado", ["apps.validacao.perfis_mercado"]),
    ("Endpoint orientado a mercado (animal)", ["apps.validacao.mercados_orientados"]),
    ("Endpoint orientado a mercado (lote)", ["apps.validacao.mercados_orientados_lote"]),
    (
        "ADR-0044 — matriz de elegibilidade por mercado",
        ["apps.validacao.matriz_elegibilidade_mercados"],
    ),
    ("Explicação comercial", ["apps.validacao.explicacao_comercial"]),
    ("Simulação comercial até o frigorífico", ["apps.validacao.simulacao_comercial"]),
    ("Lote comercial heterogêneo", ["apps.validacao.lote_comercial"]),
    ("ADR-0046 — transformação industrial (abate)", ["apps.validacao.transformacao_industrial"]),
    ("ADR-0043 — governança de regras", ["apps.validacao.governanca_regras"]),
    ("EntityTypeRequest", ["apps.validacao.entity_type_request"]),
    ("LIV-C06 — revisão humana de decisão", ["apps.validacao.revisao_humana_decisao"]),
    (
        "LIV-C09 — integração operacional (outbox/inbox)",
        ["apps.validacao.liv_c09_integracao_operacional"],
    ),
    (
        "POST-LIV-01 — suporte operacional derivado",
        ["apps.validacao.post_liv_01_operational_summary"],
    ),
    ("POST-LIV-02A — contrato outbound neutro", ["apps.validacao.post_liv_02a_neutral_contract"]),
    ("IBAMA — embargo ambiental (HTTP real)", ["apps.validacao.embargo_ibama"]),
    ("FUNAI — terra indígena (HTTP real)", ["apps.validacao.funai"]),
    (
        "PRODES/DETER — timelines territoriais (HTTP real)",
        ["apps.validacao.timelines_territoriais"],
    ),
)


@dataclass(frozen=True, slots=True)
class Resultado:
    rotulo: str
    modulo: str
    codigo: int | None
    duracao_segundos: float
    cauda: str
    motivo: str | None


def _rodar(rotulo: str, modulo_args: list[str]) -> Resultado:
    """Roda um roteiro como processo separado e captura o essencial do resultado."""
    modulo = " ".join(modulo_args)
    comando = [sys.executable, "-m", *modulo_args]
    inicio = time.monotonic()
    try:
        processo = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT_SEGUNDOS,
        )
        duracao = time.monotonic() - inicio
        saida = (processo.stdout or "") + (processo.stderr or "")
        cauda = "\n".join(saida.splitlines()[-_LINHAS_DE_CAUDA:])
        return Resultado(rotulo, modulo, processo.returncode, duracao, cauda, None)
    except subprocess.TimeoutExpired as erro:
        duracao = time.monotonic() - inicio
        saida = _como_texto(erro.stdout) + _como_texto(erro.stderr)
        cauda = "\n".join(saida.splitlines()[-_LINHAS_DE_CAUDA:])
        motivo = f"tempo esgotado apos {_TIMEOUT_SEGUNDOS}s"
        return Resultado(rotulo, modulo, None, duracao, cauda, motivo)


def _como_texto(valor: bytes | str | None) -> str:
    """`TimeoutExpired.stdout`/`.stderr` ficam tipados como `bytes | str | None`
    no typeshed independentemente de `text=True` em tempo de execução."""
    if valor is None:
        return ""
    if isinstance(valor, bytes):
        return valor.decode("utf-8", errors="replace")
    return valor


def main() -> int:
    argparse.ArgumentParser(
        description="Roda todos os roteiros de apps/validacao em sequência e resume o resultado."
    ).parse_args()

    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")

    total = len(ROTEIROS)
    print(f"{NEGRITO}Roteiro de fumaça — {total} roteiros{FIM}")
    print(
        f"{CINZA}Pressupõe API e Keycloak no ar e semeadura já executada. Cada roteiro "
        f"roda como processo separado; falha de um não impede os demais.{FIM}\n"
    )

    resultados: list[Resultado] = []
    for indice, (rotulo, modulo_args) in enumerate(ROTEIROS, start=1):
        print(
            f"{CINZA}[{indice}/{total}]{FIM} {rotulo} {CINZA}({' '.join(modulo_args)}){FIM} ...",
            end=" ",
            flush=True,
        )
        resultado = _rodar(rotulo, modulo_args)
        resultados.append(resultado)
        if resultado.codigo == 0:
            print(f"{VERDE}OK{FIM} ({resultado.duracao_segundos:.1f}s)")
        elif resultado.motivo is not None:
            print(f"{VERMELHO}FALHOU{FIM} — {resultado.motivo}")
        else:
            duracao = f"{resultado.duracao_segundos:.1f}s"
            print(f"{VERMELHO}FALHOU{FIM} — código {resultado.codigo} ({duracao})")

    falhas = [r for r in resultados if r.codigo != 0]
    print()
    if not falhas:
        print(f"{VERDE}{NEGRITO}Todos os {len(resultados)} roteiros passaram.{FIM}")
        return 0

    print(f"{VERMELHO}{NEGRITO}{len(falhas)} de {len(resultados)} roteiros falharam:{FIM}\n")
    for resultado in falhas:
        print(f"{VERMELHO}—{FIM} {resultado.rotulo} {CINZA}({resultado.modulo}){FIM}")
        if resultado.motivo is not None:
            print(f"  {resultado.motivo}")
        print(f"{CINZA}  últimas linhas:{FIM}")
        for linha in resultado.cauda.splitlines():
            print(f"    {CINZA}{linha}{FIM}")
        print()

    print(
        f"{AMARELO}Isto é leitura de fumaça, não veredito.{FIM} Abra o roteiro individual para "
        "entender o motivo antes de concluir que algo está quebrado — a falha pode ser "
        "ambiente fora do lugar (provider não configurado, semeadura desatualizada), e não "
        "defeito de código."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
