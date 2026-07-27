"""Copia os arquivos essenciais do Titan para uma pasta de backup versionada.

O critério do que é essencial é o próprio git: entra no backup tudo que está
versionado (`git ls-files`) mais o que ainda não foi commitado mas subiria no
próximo `git add` (novos arquivos não ignorados). Ou seja, exatamente o mesmo
conjunto que vai para o GitHub — nada de `.venv`, caches, bytecode ou build.

Por padrão o diretório `.git` também é copiado, para que o snapshot carregue o
histórico completo e não só a foto da árvore de trabalho.

Cada execução cria um snapshot novo em `<destino>/<AAAAMMDD-HHMMSS>/`, com um
`MANIFESTO.json` contendo o commit de origem, o estado da árvore de trabalho e o
SHA-256 de cada arquivo copiado. A cópia é conferida relendo o destino.

Uso típico:

    python scripts/backup_titan.py
    python scripts/backup_titan.py --manter 20
    python scripts/backup_titan.py --dry-run
    python scripts/backup_titan.py --verificar-apenas "D:/backup_titan/snapshots/20260727-140000"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
DESTINO_PADRAO = Path(r"D:\backup_titan\snapshots")

NOME_MANIFESTO = "MANIFESTO.json"
NOME_LEIAME = "LEIAME.txt"
NOME_ULTIMO = "ULTIMO.txt"
VERSAO_FORMATO = 1

# Um snapshot criado por este script sempre tem este formato de nome. A poda
# exige o padrão *e* a presença do manifesto, para nunca apagar pasta de terceiro.
PADRAO_SNAPSHOT = re.compile(r"^\d{8}-\d{6}(_[\w.-]+)?$")

TAMANHO_BLOCO = 1024 * 1024


class ErroDeBackup(RuntimeError):
    """Falha que impede a criação do snapshot."""


def caminho_estendido(caminho: Path) -> Path:
    """Prefixo `\\\\?\\` do Windows, que libera o limite de 260 caracteres.

    O destino é mais fundo que a origem, então caminhos que cabem no repositório
    podem estourar o MAX_PATH dentro do snapshot — em especial os de `.git`.
    """
    if sys.platform != "win32":
        return caminho
    texto = str(caminho)
    if texto.startswith("\\\\?\\"):
        return caminho
    if texto.startswith("\\\\"):
        return Path("\\\\?\\UNC" + texto[1:])
    return Path("\\\\?\\" + texto)


@dataclass(frozen=True)
class ArquivoCopiado:
    caminho: str
    bytes_: int
    sha256: str

    def como_dicionario(self) -> dict[str, object]:
        return {"caminho": self.caminho, "bytes": self.bytes_, "sha256": self.sha256}


@dataclass(frozen=True)
class EstadoGit:
    commit: str | None
    ramo: str | None
    arvore_suja: bool
    alteracoes_pendentes: tuple[str, ...]

    def como_dicionario(self) -> dict[str, object]:
        return {
            "commit": self.commit,
            "ramo": self.ramo,
            "arvore_suja": self.arvore_suja,
            "alteracoes_pendentes": list(self.alteracoes_pendentes),
        }


def formatar_bytes(quantidade: int) -> str:
    valor = float(quantidade)
    for unidade in ("B", "KB", "MB", "GB"):
        if valor < 1024 or unidade == "GB":
            return f"{valor:.1f} {unidade}"
        valor /= 1024
    return f"{valor:.1f} GB"


def executar_git(origem: Path, *argumentos: str) -> str | None:
    """Roda um comando git na origem; devolve None se o git falhar ou não existir."""
    try:
        resultado = subprocess.run(
            ["git", "-C", str(origem), *argumentos],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return None
    if resultado.returncode != 0:
        return None
    return resultado.stdout


def ler_estado_git(origem: Path) -> EstadoGit:
    commit = executar_git(origem, "rev-parse", "HEAD")
    ramo = executar_git(origem, "rev-parse", "--abbrev-ref", "HEAD")
    situacao = executar_git(origem, "status", "--porcelain") or ""
    pendentes = tuple(linha for linha in situacao.splitlines() if linha.strip())
    return EstadoGit(
        commit=commit.strip() if commit else None,
        ramo=ramo.strip() if ramo else None,
        arvore_suja=bool(pendentes),
        alteracoes_pendentes=pendentes,
    )


def listar_arquivos_do_git(origem: Path) -> list[Path]:
    """Lista o que está versionado mais o que subiria no próximo `git add`.

    `-c` traz os arquivos já rastreados, `-o --exclude-standard` traz os novos
    que o `.gitignore` não exclui, e `--deduplicate` evita repetição. É
    exatamente o conjunto que vive (ou viverá) no GitHub.
    """
    saida = executar_git(
        origem,
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "--deduplicate",
        "-z",
    )
    if saida is None:
        raise ErroDeBackup(
            f"Não consegui listar os arquivos versionados em {origem}. "
            "O git está instalado e a pasta é um repositório?"
        )
    relativos = [Path(item) for item in saida.split("\0") if item]
    # `ls-files` também lista arquivos apagados na árvore de trabalho e
    # submódulos (que aparecem como diretório): fica só o que existe como arquivo.
    origem_io = caminho_estendido(origem)
    return [relativo for relativo in relativos if (origem_io / relativo).is_file()]


def listar_arquivos_do_diretorio_git(origem: Path) -> list[Path]:
    """Lista o conteúdo de `.git`, o histórico completo do repositório."""
    pasta_git = origem / ".git"
    if not pasta_git.is_dir():
        return []
    return [
        caminho.relative_to(origem)
        for caminho in sorted(pasta_git.rglob("*"))
        if caminho.is_file() and not caminho.is_symlink()
    ]


def calcular_sha256(caminho: Path) -> str:
    digestor = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(TAMANHO_BLOCO), b""):
            digestor.update(bloco)
    return digestor.hexdigest()


def copiar_arquivos(origem: Path, destino: Path, relativos: list[Path]) -> list[ArquivoCopiado]:
    copiados: list[ArquivoCopiado] = []
    for indice, relativo in enumerate(relativos, start=1):
        arquivo_destino = destino / relativo
        arquivo_destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem / relativo, arquivo_destino)
        copiados.append(
            ArquivoCopiado(
                caminho=relativo.as_posix(),
                bytes_=arquivo_destino.stat().st_size,
                sha256=calcular_sha256(arquivo_destino),
            )
        )
        if indice % 500 == 0:
            print(f"  ... {indice}/{len(relativos)} arquivos")
    return copiados


def verificar_snapshot(raiz_snapshot: Path, copiados: list[ArquivoCopiado]) -> list[str]:
    """Relê o destino e devolve as divergências encontradas."""
    divergencias: list[str] = []
    for arquivo in copiados:
        caminho = raiz_snapshot / arquivo.caminho
        if not caminho.is_file():
            divergencias.append(f"ausente no destino: {arquivo.caminho}")
        elif caminho.stat().st_size != arquivo.bytes_:
            divergencias.append(f"tamanho diferente: {arquivo.caminho}")
        elif calcular_sha256(caminho) != arquivo.sha256:
            divergencias.append(f"conteúdo diferente: {arquivo.caminho}")
    return divergencias


def relatar_divergencias(divergencias: list[str]) -> None:
    for divergencia in divergencias[:20]:
        print(f"  - {divergencia}")
    if len(divergencias) > 20:
        print(f"  ... e mais {len(divergencias) - 20}")


def escrever_manifesto(
    raiz_snapshot: Path,
    origem: Path,
    estado_git: EstadoGit,
    copiados: list[ArquivoCopiado],
    incluir_git: bool,
    criado_em: datetime,
) -> None:
    manifesto = {
        "versao_formato": VERSAO_FORMATO,
        "criado_em": criado_em.astimezone().isoformat(timespec="seconds"),
        "origem": str(origem),
        "maquina": os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME"),
        "inclui_historico_git": incluir_git,
        "git": estado_git.como_dicionario(),
        "totais": {
            "arquivos": len(copiados),
            "bytes": sum(arquivo.bytes_ for arquivo in copiados),
        },
        "arquivos": [arquivo.como_dicionario() for arquivo in copiados],
    }
    (raiz_snapshot / NOME_MANIFESTO).write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def escrever_leiame(raiz_snapshot: Path, estado_git: EstadoGit, incluir_git: bool) -> None:
    linhas = [
        "Snapshot do repositório Titan gerado por scripts/backup_titan.py.",
        "",
        f"Commit de origem: {estado_git.commit or 'desconhecido'}",
        f"Ramo: {estado_git.ramo or 'desconhecido'}",
        f"Árvore suja no momento da cópia: {'sim' if estado_git.arvore_suja else 'não'}",
        "",
        "Conteúdo: os mesmos arquivos que vão para o GitHub (versionados mais os",
        "novos ainda não commitados)"
        + (" e o histórico completo em .git." if incluir_git else "."),
        "",
        "Como restaurar:",
        "  1. Copie esta pasta para o destino, menos MANIFESTO.json e LEIAME.txt.",
        "  2. Recrie o ambiente: python -m uv sync --locked",
        "  3. Suba a infraestrutura: docker compose up -d",
        "  4. Aplique as migrations: python -m uv run --locked alembic upgrade head",
        "",
        "Como conferir a integridade:",
        '  python scripts/backup_titan.py --verificar-apenas "<caminho desta pasta>"',
    ]
    if not incluir_git:
        linhas += ["", "ATENÇÃO: feito com --sem-git; este snapshot não contém o histórico."]
    (raiz_snapshot / NOME_LEIAME).write_text("\n".join(linhas) + "\n", encoding="utf-8")


def snapshots_existentes(destino: Path) -> list[Path]:
    if not destino.is_dir():
        return []
    return sorted(
        (
            pasta
            for pasta in destino.iterdir()
            if pasta.is_dir()
            and PADRAO_SNAPSHOT.match(pasta.name)
            and (pasta / NOME_MANIFESTO).is_file()
        ),
        key=lambda pasta: pasta.name,
    )


def podar_snapshots(destino: Path, manter: int, dry_run: bool) -> list[Path]:
    """Remove snapshots antigos. Só toca em pastas criadas por este script."""
    if manter <= 0:
        return []
    existentes = snapshots_existentes(destino)
    excedentes = existentes[: max(0, len(existentes) - manter)]
    for pasta in excedentes:
        print(f"{'[dry-run] ' if dry_run else ''}Removendo snapshot antigo: {pasta.name}")
        if not dry_run:
            shutil.rmtree(pasta)
    return excedentes


def comando_verificar(caminho: Path) -> int:
    caminho = caminho_estendido(caminho)
    manifesto_caminho = caminho / NOME_MANIFESTO
    if not manifesto_caminho.is_file():
        print(f"ERRO: {manifesto_caminho} não existe; não é um snapshot deste script.")
        return 2
    dados = json.loads(manifesto_caminho.read_text(encoding="utf-8"))
    copiados = [
        ArquivoCopiado(caminho=item["caminho"], bytes_=item["bytes"], sha256=item["sha256"])
        for item in dados["arquivos"]
    ]
    print(f"Verificando {len(copiados)} arquivos em {caminho} ...")
    divergencias = verificar_snapshot(caminho, copiados)
    if divergencias:
        print(f"FALHA: {len(divergencias)} divergência(s):")
        relatar_divergencias(divergencias)
        return 1
    print("OK: snapshot íntegro.")
    return 0


def montar_analisador() -> argparse.ArgumentParser:
    analisador = argparse.ArgumentParser(
        description="Backup versionado dos arquivos essenciais do Titan.",
    )
    analisador.add_argument(
        "--origem",
        type=Path,
        default=RAIZ_PROJETO,
        help=f"Raiz do repositório a copiar (padrão: {RAIZ_PROJETO}).",
    )
    analisador.add_argument(
        "--destino",
        type=Path,
        default=DESTINO_PADRAO,
        help=f"Pasta que guarda os snapshots (padrão: {DESTINO_PADRAO}).",
    )
    analisador.add_argument(
        "--rotulo",
        default=None,
        help="Sufixo opcional no nome do snapshot, ex: --rotulo antes-do-passo-9-4.",
    )
    analisador.add_argument(
        "--manter",
        type=int,
        default=10,
        help="Quantos snapshots manter; 0 desliga a poda (padrão: 10).",
    )
    analisador.add_argument(
        "--sem-git",
        action="store_true",
        help="Não copiar o diretório .git; o snapshot fica sem o histórico.",
    )
    analisador.add_argument(
        "--sem-verificacao",
        action="store_true",
        help="Não reler o destino para conferir os hashes.",
    )
    analisador.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar o que seria copiado e removido, sem escrever nada.",
    )
    analisador.add_argument(
        "--verificar-apenas",
        type=Path,
        default=None,
        metavar="SNAPSHOT",
        help="Só conferir a integridade de um snapshot existente e sair.",
    )
    return analisador


def montar_nome_snapshot(criado_em: datetime, rotulo: str | None) -> str:
    nome = criado_em.strftime("%Y%m%d-%H%M%S")
    if rotulo:
        nome = f"{nome}_{re.sub(r'[^\w.-]+', '-', rotulo).strip('-')}"
    return nome


def executar(opcoes: argparse.Namespace) -> int:
    origem: Path = opcoes.origem.resolve()
    destino: Path = opcoes.destino.resolve()
    incluir_git = not opcoes.sem_git

    if not origem.is_dir():
        raise ErroDeBackup(f"origem não existe: {origem}")
    if destino == origem or origem in destino.parents:
        raise ErroDeBackup(f"o destino {destino} está dentro da origem {origem}.")
    if destino.anchor and not Path(destino.anchor).exists():
        raise ErroDeBackup(f"a unidade {destino.anchor} não está disponível.")

    estado_git = ler_estado_git(origem)
    criado_em = datetime.now()
    raiz_snapshot = destino / montar_nome_snapshot(criado_em, opcoes.rotulo)

    print(f"Origem : {origem}")
    print(f"Destino: {raiz_snapshot}")
    print(f"Commit : {estado_git.commit or 'desconhecido'} ({estado_git.ramo or '?'})")
    if estado_git.arvore_suja:
        print(
            f"Aviso  : {len(estado_git.alteracoes_pendentes)} alteração(ões) não commitadas "
            "— elas entram no backup."
        )
    if not incluir_git:
        print("Aviso  : --sem-git; o histórico do repositório NÃO será copiado.")

    origem_io = caminho_estendido(origem)

    print("Levantando arquivos ...")
    relativos = listar_arquivos_do_git(origem)
    bytes_projeto = sum((origem_io / relativo).stat().st_size for relativo in relativos)
    print(f"  projeto: {len(relativos)} arquivos, {formatar_bytes(bytes_projeto)}")
    if incluir_git:
        arquivos_git = listar_arquivos_do_diretorio_git(origem)
        bytes_git = sum((origem_io / relativo).stat().st_size for relativo in arquivos_git)
        print(f"  .git   : {len(arquivos_git)} arquivos, {formatar_bytes(bytes_git)}")
        relativos += arquivos_git

    if opcoes.dry_run:
        print("[dry-run] Nada foi escrito.")
        podar_snapshots(destino, opcoes.manter, dry_run=True)
        return 0

    if raiz_snapshot.exists():
        raise ErroDeBackup(f"{raiz_snapshot} já existe.")

    raiz_io = caminho_estendido(raiz_snapshot)
    raiz_io.mkdir(parents=True)
    print("Copiando ...")
    try:
        copiados = copiar_arquivos(origem_io, raiz_io, relativos)
    except OSError as erro:
        shutil.rmtree(raiz_io, ignore_errors=True)
        raise ErroDeBackup(f"falha ao copiar: {erro}") from erro

    if not opcoes.sem_verificacao:
        print("Conferindo a cópia ...")
        divergencias = verificar_snapshot(raiz_io, copiados)
        if divergencias:
            print(f"FALHA: {len(divergencias)} divergência(s); snapshot mantido para exame:")
            relatar_divergencias(divergencias)
            return 1

    escrever_manifesto(raiz_io, origem, estado_git, copiados, incluir_git, criado_em)
    escrever_leiame(raiz_io, estado_git, incluir_git)
    (destino / NOME_ULTIMO).write_text(raiz_snapshot.name + "\n", encoding="utf-8")
    podar_snapshots(destino, opcoes.manter, dry_run=False)

    total = sum(arquivo.bytes_ for arquivo in copiados)
    print(f"OK: {len(copiados)} arquivos, {formatar_bytes(total)} em {raiz_snapshot}")
    return 0


def main(argumentos: list[str] | None = None) -> int:
    opcoes = montar_analisador().parse_args(argumentos)
    try:
        if opcoes.verificar_apenas is not None:
            return comando_verificar(opcoes.verificar_apenas.resolve())
        return executar(opcoes)
    except ErroDeBackup as erro:
        print(f"ERRO: {erro}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
