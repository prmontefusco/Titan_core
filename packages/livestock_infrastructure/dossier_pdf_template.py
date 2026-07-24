"""Template PDF da vertical Livestock (Passo 10.3).

Descreve **o que mostrar e em que ordem**; não sabe desenhar nada. Quem desenha é
o adaptador do Core. Por isso este módulo não importa biblioteca de PDF e é
testável comparando dados, o que torna a validação do PLANO — "comparar JSON e
PDF campo a campo" — uma comparação de valores em vez de leitura de pixels.

**Fidelidade antes de brevidade.** A linha do tempo é impressa inteira, mesmo
longa. Um PDF que resumisse o histórico deixaria de ser representação fiel do
snapshot, e passaria a ser uma opinião sobre ele.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from packages.core_application.dossier_pdf_template import PdfSection

LIVESTOCK_NAMESPACE = "livestock"
_AUSENTE = "—"


class LivestockPdfTemplate:
    """Apresenta a seção `livestock` do dossiê da decisão farmacológica."""

    @property
    def namespace(self) -> str:
        return LIVESTOCK_NAMESPACE

    def render(self, content: Mapping[str, Any]) -> Sequence[PdfSection]:
        return [
            self._identidade(content.get("subject", {})),
            self._carencia(content.get("withdrawal", {})),
            *self._cadeia(content.get("evidence_chain", [])),
            self._linha_do_tempo(content.get("timeline", {})),
        ]

    def _identidade(self, subject: Mapping[str, Any]) -> PdfSection:
        """Brinco e SISBOV primeiro: é o que um fiscal confere contra o animal."""
        linhas: list[tuple[str, ...]] = []
        for tag in subject.get("identifiers", []):
            linhas.append(
                (
                    _texto(tag.get("type")),
                    _texto(tag.get("value")),
                    _texto(tag.get("state")),
                    _texto(tag.get("verification_status")),
                )
            )
        if not linhas:
            linhas.append((_AUSENTE, "Sem identificador registrado", _AUSENTE, _AUSENTE))

        linhas.append(("Sexo", _texto(subject.get("sex")), "Raça", _texto(subject.get("breed"))))
        linhas.append(
            (
                "Identificação interna",
                _texto(subject.get("animal_id")),
                "Origem da identidade",
                _texto(subject.get("identity_source")),
            )
        )
        return PdfSection(
            title="Identificação do animal",
            columns=("Tipo", "Valor", "Situação", "Verificação"),
            rows=tuple(linhas),
        )

    def _carencia(self, withdrawal: Mapping[str, Any]) -> PdfSection:
        """A conta aparece: aplicação, prazo congelado e data-limite calculada."""
        linhas: list[tuple[str, ...]] = [
            (
                "Situação",
                "EM CARÊNCIA" if withdrawal.get("in_withdrawal") else "FORA DE CARÊNCIA",
                _texto(withdrawal.get("rule_version")),
                _AUSENTE,
            ),
            (
                "Elegível a partir de",
                _texto(withdrawal.get("eligible_from")),
                _AUSENTE,
                _AUSENTE,
            ),
        ]
        for contribuicao in withdrawal.get("contributions", []):
            linhas.append(
                (
                    "Aplicação",
                    _texto(contribuicao.get("applied_at")),
                    f"{contribuicao.get('withdrawal_period_days')} dias",
                    _texto(contribuicao.get("withdrawal_ends_at")),
                )
            )
        return PdfSection(
            title="Carência farmacológica",
            columns=("Item", "Valor", "Prazo aplicado", "Fim da carência"),
            rows=tuple(linhas),
        )

    def _cadeia(self, chain: Sequence[Mapping[str, Any]]) -> list[PdfSection]:
        """Uma seção por aplicação, ligando o cálculo às provas que o sustentam."""
        secoes: list[PdfSection] = []
        for elo in chain:
            linhas: list[tuple[str, ...]] = []
            for evidencia in elo.get("evidences", []):
                conteudo = evidencia.get("content")
                if conteudo is None:
                    linhas.append(
                        (
                            _texto(evidencia.get("id")),
                            "CONTEÚDO NÃO ACOMPANHA",
                            _AUSENTE,
                            _AUSENTE,
                        )
                    )
                    continue
                revogacao = conteudo.get("revocation")
                linhas.append(
                    (
                        _texto(evidencia.get("id")),
                        _texto(conteudo.get("content_hash")),
                        f"{conteudo.get('source', {}).get('source_type')} / "
                        f"{conteudo.get('confidence', {}).get('tier')}",
                        # Revogação em destaque: apresentar evidência revogada como
                        # válida transformaria esta folha em prova falsa.
                        "REVOGADA: " + _texto(revogacao.get("reason")) if revogacao else "Vigente",
                    )
                )
            for nota in elo.get("notes", []):
                linhas.append((_AUSENTE, f"Anotação do operador: {nota}", "NÃO É PROVA", _AUSENTE))
            if not linhas:
                linhas.append((_AUSENTE, "Sem evidência anexada", _AUSENTE, _AUSENTE))

            secoes.append(
                PdfSection(
                    title=f"Evidências da aplicação {_curto(elo.get('application_id'))}",
                    columns=(
                        "Evidência",
                        "Hash do conteúdo (SHA-256)",
                        "Fonte / Confiança",
                        "Situação",
                    ),
                    rows=tuple(linhas),
                )
            )
        return secoes

    def _linha_do_tempo(self, timeline: Mapping[str, Any]) -> PdfSection:
        linhas: list[tuple[str, ...]] = [
            (
                _texto(entrada.get("occurred_at")),
                _texto(entrada.get("entry_type")),
                _texto(entrada.get("aggregate_type")),
                "corrigido por " + _curto(entrada.get("superseded_by"))
                if entrada.get("superseded_by")
                else _AUSENTE,
            )
            for entrada in timeline.get("entries", [])
        ]
        if not linhas:
            linhas.append((_AUSENTE, "Sem histórico até o instante da decisão", _AUSENTE, _AUSENTE))
        return PdfSection(
            title=(
                f"Linha do tempo até {timeline.get('known_until', _AUSENTE)} "
                f"({timeline.get('entry_count', len(linhas))} registros)"
            ),
            columns=("Ocorrido em", "Fato", "Agregado", "Correção"),
            rows=tuple(linhas),
        )


def _texto(value: Any) -> str:
    return _AUSENTE if value is None or value == "" else str(value)


def _curto(value: Any) -> str:
    """Identificador abreviado: a folha precisa caber, o JSON guarda o inteiro."""
    texto = _texto(value)
    return texto if len(texto) <= 12 else f"{texto[:8]}…"
