"""Interpreta a seÃ§Ã£o Livestock de um Dossier para o VerificationBundle."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from packages.core_domain.dossier import Dossier


@dataclass(frozen=True, slots=True)
class LivestockVerificationBundleInterpreter:
    """Declara escopo e limites Livestock sem alterar o Dossier canÃ´nico."""

    def declared_scopes_and_gaps(self, dossier: Dossier) -> tuple[Sequence[str], Sequence[str]]:
        vertical = dossier.document.get("vertical")
        if not isinstance(vertical, Mapping) or vertical.get("namespace") != "livestock":
            return (), ()
        content = vertical.get("content")
        if not isinstance(content, Mapping):
            return (), ()
        scopes = ["integridade", "conteudo_da_decisao"]
        gaps: list[str] = []
        coverage = content.get("coverage")
        if isinstance(coverage, Mapping):
            scopes.append("prova_sanitaria_vitalicia")
            declared_scope = coverage.get("declared_scope")
            if isinstance(declared_scope, str) and declared_scope:
                scopes.append(f"coverage:{declared_scope}")
            if coverage.get("status") == "NAO_DECLARADA":
                gaps.append(
                    "Cobertura sanitaria vitalicia nao declarada; "
                    "o pacote nao prova historico completo."
                )
            if coverage.get("has_declared_gaps"):
                gaps.append(
                    "Cobertura sanitaria parcial declarada no dossie; "
                    "existem lacunas historicas abertas."
                )
        imported = content.get("imported_material")
        if isinstance(imported, Mapping):
            declared_scope = imported.get("declared_scope")
            if isinstance(declared_scope, str) and declared_scope:
                scopes.append(f"material:{declared_scope}")
            if imported.get("has_imported_facts"):
                scopes.append("historico_importado_declarado")
                gaps.append(
                    "Material importado acompanha o pacote como afirmacao importada; "
                    "nao substitui observacao local."
                )
        limitations = content.get("declared_limitations")
        if isinstance(limitations, Sequence) and not isinstance(limitations, (str, bytes)):
            gaps.extend(item for item in limitations if isinstance(item, str))
        return tuple(sorted(set(scopes))), tuple(dict.fromkeys(gaps))
