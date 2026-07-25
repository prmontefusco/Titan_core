"""Genealogia da vertical Titan Livestock (Passo 13.2).

A vertical não guarda parentesco em campo próprio: usa a **Relação Universal e
Temporal** do Core (Passo 7.1), que já é temporal, já carrega confiança e
evidências, e já recusa uma ponta em outra Organization. Parentesco em campo
mataria a pergunta que mais importa no campo — "quais touros podem ser o pai" —
porque um campo só guarda uma resposta.

**Maternidade não é uma, são duas.** Com transferência de embrião, quem forneceu
o óvulo e quem gestou são fêmeas diferentes, e ambas são fato:

- a **doadora** define a linhagem;
- a **receptora** esteve fisicamente com o bezerro, e é dela a rastreabilidade
  sanitária e o histórico reprodutivo.

Colapsá-las num único vínculo produziria um dado que mente numa das duas
leituras. São dois tipos de relação, e não um com anotação, pelo mesmo motivo do
touro do lote: quem é a mãe genética precisa ser consultável sem abrir metadados.

**A linhagem sobe pela genética.** A receptora não é ancestral de ninguém — ela
gestou, o que é outra pergunta e outra consulta.
"""

from enum import StrEnum

from packages.core_domain.evidence import ConfidenceLevel, ConfidenceTier
from packages.livestock_domain.animal import AnimalSex

# Nomes canônicos do Core: minúsculas, namespaced na vertical.
GENETIC_MOTHER_OF = "livestock.genetic_mother_of"
GESTATIONAL_MOTHER_OF = "livestock.gestational_mother_of"
FATHER_OF = "livestock.father_of"


class ParentageRole(StrEnum):
    """O papel que o progenitor exerce sobre a cria."""

    MAE_GENETICA = "MAE_GENETICA"
    MAE_GESTACIONAL = "MAE_GESTACIONAL"
    PAI = "PAI"


RELATION_TYPE_BY_ROLE: dict[ParentageRole, str] = {
    ParentageRole.MAE_GENETICA: GENETIC_MOTHER_OF,
    ParentageRole.MAE_GESTACIONAL: GESTATIONAL_MOTHER_OF,
    ParentageRole.PAI: FATHER_OF,
}

ROLE_BY_RELATION_TYPE: dict[str, ParentageRole] = {
    tipo: papel for papel, tipo in RELATION_TYPE_BY_ROLE.items()
}

# Nomear alguém como mãe é afirmar que é fêmea. `UNKNOWN` não é aceito em papel
# de progenitor: deixar passar criaria um registro que se contradiz.
SEXO_EXIGIDO: dict[ParentageRole, AnimalSex] = {
    ParentageRole.MAE_GENETICA: AnimalSex.FEMALE,
    ParentageRole.MAE_GESTACIONAL: AnimalSex.FEMALE,
    ParentageRole.PAI: AnimalSex.MALE,
}

# Papéis que compõem a árvore genealógica. A maternidade gestacional fica de
# fora de propósito: quem gestou não transmitiu genes.
PAPEIS_DE_LINHAGEM: frozenset[ParentageRole] = frozenset(
    {ParentageRole.MAE_GENETICA, ParentageRole.PAI}
)

# Papéis dos quais um animal só pode ter um vigente por vez. A paternidade fica
# de fora: vários pais possíveis é o caso reconhecido do touro do lote.
PAPEIS_EXCLUSIVOS: frozenset[ParentageRole] = frozenset(
    {ParentageRole.MAE_GENETICA, ParentageRole.MAE_GESTACIONAL}
)


class ParentageConfidence(StrEnum):
    """Quanto se sabe sobre este vínculo, no vocabulário de quem opera.

    Espelha os níveis do Passo 5.2 sem o `INDETERMINADO` que os identificadores
    admitem: afirmar parentesco indeterminado é não afirmar parentesco nenhum, e
    para isso basta não registrar a relação.
    """

    DECLARADO = "DECLARADO"
    DOCUMENTADO = "DOCUMENTADO"
    VERIFICADO_EM_FONTE = "VERIFICADO_EM_FONTE"


_TIER_POR_CONFIANCA: dict[ParentageConfidence, ConfidenceTier] = {
    ParentageConfidence.DECLARADO: ConfidenceTier.INFORMED,
    ParentageConfidence.DOCUMENTADO: ConfidenceTier.DOCUMENTED,
    ParentageConfidence.VERIFICADO_EM_FONTE: ConfidenceTier.VERIFIED_SOURCE,
}

_RAZAO_PADRAO: dict[ParentageConfidence, str] = {
    ParentageConfidence.DECLARADO: "Informado pelo produtor, sem comprovação.",
    ParentageConfidence.DOCUMENTADO: "Registro de cobertura, inseminação ou transferência.",
    ParentageConfidence.VERIFICADO_EM_FONTE: "Exame de DNA arquivado.",
}


def confidence_level(confianca: ParentageConfidence, reason: str | None = None) -> ConfidenceLevel:
    """Traduz o vocabulário da vertical para o tipo do Core.

    O operador nunca vê `INFORMED` ou `VERIFIED_SOURCE`: a tradução acontece
    nesta fronteira, e o Core não ganha enum novo por causa da vertical.
    """
    if not isinstance(confianca, ParentageConfidence):
        raise TypeError("confianca deve ser um ParentageConfidence.")
    declarada = (reason or "").strip()
    return ConfidenceLevel(
        tier=_TIER_POR_CONFIANCA[confianca],
        reason=declarada or _RAZAO_PADRAO[confianca],
    )


def confidence_from_tier(tier: ConfidenceTier) -> ParentageConfidence | None:
    """Caminho de volta, para a leitura devolver o vocabulário da vertical.

    Devolve `None` para os níveis que a vertical não emite (`HARDENED_SYSTEM` e
    `CRYPTOGRAPHICALLY_ATTESTED`), em vez de aproximá-los ao mais próximo:
    inventar equivalência faria a resposta afirmar algo que ninguém registrou.
    """
    for confianca, equivalente in _TIER_POR_CONFIANCA.items():
        if equivalente is tier:
            return confianca
    return None
