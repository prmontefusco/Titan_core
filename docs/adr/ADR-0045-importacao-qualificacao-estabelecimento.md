# ADR-0045 — Importação e Reconciliação de Qualificações de Estabelecimento

**Status:** ACEITA  
**Data de criação:** 27 de julho de 2026  
**Revisado:** 27 de julho de 2026 (duas rodadas de revisão arquitetural)  
**Autores:** Claude Code, Paulo Roberto Montefusco  

## Problema

Qualificações de estabelecimento (p. ex., `exportacao-china`, `frigorífico-certificado`) hoje são cadastradas manualmente, sem fonte versionada que permita auditoria, rastreamento de mudança ou reconciliação temporal.

**Cenário crítico:** um frigorífico perde a certificação de exportação para a China. Não há registro de quando foi perdida, quem a revogou ou por qual motivo — impossível distinguir entre auditoria e ocultação.

**Consequência para a elegibilidade:** a matriz mostra `ELEGIVEL` com base numa qualificação que era válida no dia do embarque mas foi revogada meses depois. O dossiê não captura a mudança.

## Restrições

1. **Consistência com ADR-0043**: regra (`RuleAdoption`) e fato (`Assertion`) são conceitos distintos
2. **Fato não carrega decisão escondida**: ausência em lista é observação; seu significado normativo pertence à Policy
3. **Honestidade temporal**: não inventar datas que a fonte não forneceu
4. **Bitemporalidade**: distinguir quando o fato ocorreu (valid time) de quando o Titan soube (transaction/knowledge time)
5. **Rastreabilidade**: cada importação captura o instante, a fonte e o que ela afirmou, com identidade própria para idempotência
6. **Confiança é resultado, não entrada**: `ConfidenceLevel` é computado pelo Titan a partir do caminho de proveniência, nunca declarado livremente pelo cliente
7. **Isolamento RLS**: qualificações pertencem à Organization
8. **Idempotência**: mesma versão de fonte importada 2x não duplica
9. **Reprodutibilidade**: decisões podem ser refeitas com o conhecimento contemporâneo a elas, sem serem reescritas por conhecimento posterior

## Solução

### 1. Separação Conceitual: Regra vs Fato

**REGRA (Governança — ADR-0043)**
```
RuleIdentity: "Habilitação para exportação China"
    ↓
RuleVersion: "CN-v7, vigente desde 01/2026"
    ↓
RuleAdoption: "Organization XYZ adota CN-v7 para validação"
    ↓
RuleCondition: "estabelecimento.qualificacao = EXPORT_CN"
```

**FATO (Asserção Temporal — ADR-0045)**
```
SourceArtifact (identidade da importação)
    ↓
EstablishmentQualificationAssertion (fato individual)
```

### 2. `SourceArtifact` — Identidade da Importação

A versão da fonte, o hash de conteúdo e a semântica de cobertura são propriedades **da importação como um todo**, não de cada Assertion individual. Persistir isso repetido em toda Assertion duplicaria informação e obscureceria onde vive a chave de idempotência.

```python
@dataclass(frozen=True)
class SourceArtifact:
    artifact_id: TypedId
    organization_id: OrganizationId
    source: str
    source_version: str              # parte da chave de idempotência
    content_hash: str                # SHA-256 do conteúdo bruto recebido
    snapshot_semantics: SourceCoverage
    observed_at: datetime
    recorded_at: datetime
```

**Idempotência:** `(organization_id, source, source_version)` é único. Reimportar a mesma versão localiza o `SourceArtifact` existente e não cria um novo — nem novas Assertions.

```
SourceArtifact
 ├── source = MAPA
 ├── source_version = 2026-07-27T15:30Z
 ├── content_hash = sha256:abc...
 ├── snapshot_semantics = COMPLETE_SNAPSHOT
 ├── observed_at = 2026-07-27T15:30:00Z
          │
          ├── Assertion (SIF 1234, QUALIFIED)
          ├── Assertion (SIF 1235, QUALIFIED)
          └── Assertion (SIF 1236, UNKNOWN)
```

### 3. `EstablishmentQualificationAssertion` — Fato Individual

```python
@dataclass(frozen=True)
class EstablishmentQualificationAssertion:
    assertion_id: TypedId
    organization_id: OrganizationId
    establishment_id: TypedId
    qualification_type: str

    asserted_status: AssertionStatus  # QUALIFIED, NOT_QUALIFIED, UNKNOWN
    effective_from: datetime | None
    effective_until: datetime | None

    observed_at: datetime
    source_artifact_id: TypedId       # OBRIGATÓRIO — referencia o SourceArtifact
    confidence: ConfidenceLevel       # computado pelo Titan, nunca recebido do cliente

    recorded_at: datetime
```

### 4. Semântica de `AssertionStatus`

**QUALIFIED**
- A fonte afirma positivamente a qualificação.

**NOT_QUALIFIED**
- A fonte afirma **explicitamente** que o estabelecimento não possui a qualificação (p. ex., um código de status "REVOGADO" no próprio registro).
- Ausência em uma lista **nunca**, por si, produz `NOT_QUALIFIED`.

**UNKNOWN**
- O material disponível não permite afirmar nenhum dos dois.
- Cobre tanto "desapareceu de um snapshot completo, sem explicação" quanto "recebemos boato sem fonte documental forte".

### 5. `SourceCoverage` — Semântica do Snapshot (definição corrigida)

O ponto de atenção da rodada anterior: `COMPLETE_SNAPSHOT` **não** converte ausência em `NOT_QUALIFIED`. Ele apenas habilita a observação de ausência a **significar algo** — o significado normativo dessa observação continua sendo decisão da Policy, nunca do fato.

**COMPLETE_SNAPSHOT**
> A fonte declara representar integralmente o universo consultado. A ausência de um elemento é, portanto, uma observação significativa de não-presença naquele snapshot — mas essa observação não se converte automaticamente em `NOT_QUALIFIED`. Ela produz uma `Assertion` com `status=UNKNOWN` (a menos que a fonte também afirme negação explícita). O que essa ausência implica para a elegibilidade é decisão da Policy, não do fato.

**DELTA**
- A fonte representa apenas mudanças desde a versão anterior. Ausência não informa nada sobre o estado anterior.

**PARTIAL**
- A fonte representa apenas um subconjunto (região, programa, página). Ausência não significa ausência no universo completo. **Nenhuma Assertion derivada de ausência é criada.**

**UNKNOWN**
- Semântica da cobertura é desconhecida. Falha segura: nenhuma Assertion derivada de ausência é criada.

```python
# Fato: apenas registra a observação, nunca decide
if snapshot.snapshot_semantics == SourceCoverage.COMPLETE_SNAPSHOT:
    if sif not in current_list and sif in previous_list:
        assertion.status = AssertionStatus.UNKNOWN
        assertion.confidence = titan_computes_confidence(source_artifact)
        assertion.observed_at = snapshot.observed_at

elif snapshot.snapshot_semantics in (SourceCoverage.PARTIAL, SourceCoverage.UNKNOWN):
    # Nenhuma inferência de ausência é feita
    pass

# Regra: decide o que a ausência significa para a finalidade
# (isto vive em RuleCondition/Policy, não no serviço de importação)
```

### 6. `ConfidenceLevel` — Computado pelo Titan, Nunca pelo Cliente

O ponto mais importante desta rodada. `confidence` **não** é um campo do payload HTTP. Um cliente que pudesse declarar `CRYPTOGRAPHICALLY_ATTESTED` estaria escolhendo o próprio grau de confiança — o que a ADR-0042 já proíbe ao tratar confiança como resultado da qualidade e verificação da proveniência, não como afirmação livre.

**O que o HTTP envia:**
```json
{
  "source": "MAPA",
  "source_version": "2026-07-27T15:30Z",
  "snapshot_semantics": "COMPLETE_SNAPSHOT",
  "assertions": [
    {"establishment_id": "...", "qualification_type": "EXPORT_CN", "asserted_status": "QUALIFIED"}
  ]
}
```

**O que o Titan computa** (a partir do caminho de proveniência da conexão, autenticação da fonte, e políticas de importação registradas):

```python
def compute_confidence(source_artifact: SourceArtifact, importer_context: ...) -> ConfidenceLevel:
    """Confiança nasce da proveniência, não é declarada."""
    if importer_context.is_manual_upload_without_verification():
        return ConfidenceLevel.DOCUMENTED
    if importer_context.is_authenticated_external_source():
        return ConfidenceLevel.VERIFIED_SOURCE
    if importer_context.has_valid_signature_per_profile():
        return ConfidenceLevel.CRYPTOGRAPHICALLY_ATTESTED
    return ConfidenceLevel.INFORMED
```

Se um caso de uso legítimo precisar que o remetente **declare** uma confiança pretendida (p. ex., um frigorífico dizendo "isto vem de auditoria própria, trato como verificado"), esse valor entra como `claimed_confidence` — um dado observacional a mais — e nunca sobrescreve o `confidence` efetivo computado pelo Titan.

### 7. Exemplo Corrigido: `UNKNOWN` + `INFORMED`

O exemplo da rodada anterior violava a própria invariante de `source_artifact_id` obrigatório ("não temos artefato que comprove"). Correção: o artefato **sempre existe** — o que pode faltar é força probatória do conteúdo dele, não o artefato em si.

```
SourceArtifact:
    source = "relato informal recebido por e-mail do responsável técnico"
    content_hash = sha256:...(do e-mail arquivado)
    snapshot_semantics = UNKNOWN

Assertion:
    status = UNKNOWN
    confidence = INFORMED

Significado: existe um artefato que documenta a declaração recebida —
o e-mail foi arquivado e tem hash. O que falta é uma fonte documental
independente que comprove o conteúdo da alegação. O artefato prova que
alguém declarou aquilo; não prova que a declaração é verdadeira.
```

### 8. Bitemporalidade: Valid Time × Knowledge Time

```
VALID TIME                          KNOWLEDGE / TRANSACTION TIME
Quando aquilo era válido no mundo?  Quando o Titan soube disso?

effective_from                      observed_at
effective_until                     recorded_at
```

**Duas perguntas distintas, duas respostas distintas:**

**Reprodução histórica** — "por que o Titan decidiu assim naquele dia?"
```
knowledge cutoff = 20/07
→ usa apenas Assertions com observed_at <= 20/07
```

**Auditoria retrospectiva** — "com o que sabemos hoje, o que podemos afirmar sobre 15/07?"
```
knowledge cutoff = hoje
effective time em análise = 15/07
→ usa Assertions cujo effective_from/until cobre 15/07,
  independentemente de quando foram observadas
```

**Exemplo:**
```
15/07 → embarque
20/07 → Titan decide elegibilidade (Decision D1)
27/07 → MAPA publica: habilitação foi revogada em 10/07

Reprodução de D1 (cutoff = 20/07):
  Nenhuma Assertion com observed_at <= 20/07 informa revogação.
  D1 permanece reproduzível como APROVADA — o conhecimento
  disponível naquele instante sustentava a decisão.

Auditoria hoje (01/08):
  Nova Assertion: effective_until = 10/07, observed_at = 27/07.
  Conclusão: a habilitação já não era válida em 15/07, embora o
  Titan não pudesse saber disso em 20/07.
  D1 NÃO é reescrita. Um coverage gap retrospectivo é registrado,
  e uma nova Evaluation pode ser solicitada se a Policy exigir.
```

Isso é consistente com a ADR-0043: conhecimento novo produz reavaliação, nunca reescreve a decisão histórica.

### 9. Arquitetura Unificada

```
             GOVERNANÇA
                 │
          RuleIdentity → RuleVersion → RuleAdoption
                 │
                 ▼
              Policy
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
   Animal Facts    Establishment Facts
        │                 │
        │           SourceArtifact
        │                 │
        │     EstablishmentQualificationAssertion
        │        (status, effective_*, observed_at,
        │         confidence computado)
        │                 │
        └────────┬────────┘
                 ▼
             Evaluation
                 │
             Decision
                 │
        Market Eligibility
                 │
          Dossier (com coverage gaps)
```

### 10. Impacto na Elegibilidade — Exemplo Final

```
SIF 1236, China, 27/07/2026

Assertions:
- 15/03/2024: QUALIFIED (observed_at=15/03/2024, source_artifact=SA-1)
- 27/07/2026: UNKNOWN (observed_at=27/07/2026, source_artifact=SA-2,
              snapshot_semantics=COMPLETE_SNAPSHOT, confidence=VERIFIED_SOURCE)

Policy CN padrão ("habilitação positiva vigente deve estar demonstrada"):
  Decision: INDETERMINADO
  Razão: última afirmação positiva de 15/03/2024; ausência observada
         em snapshot completo de 27/07/2026; mudança de status ocorreu
         em algum ponto do intervalo, data exata desconhecida.

Policy X alternativa ("ausência em snapshot completo vigente implica
não habilitação"):
  Decision: REJEITADO
  Razão: ausência confirmada em snapshot completo oficial vigente.

Mesmo fato, mesma fonte, decisões diferentes — porque a decisão vem
da regra, nunca do fato isolado.
```

### 11. Plano de Testes (inclui os dois testes recomendados na revisão)

1. Importação básica cria Assertions corretas
2. Reimportação da mesma `source_version` é idempotente (localiza `SourceArtifact` existente, não duplica)
3. Ausência em `COMPLETE_SNAPSHOT` produz `UNKNOWN`, nunca `NOT_QUALIFIED`
4. Ausência em `PARTIAL` ou `UNKNOWN` não produz nenhuma Assertion derivada
5. **Conhecimento posterior não altera decisão histórica**: uma Decision tomada com cutoff `T1` permanece reproduzível com Assertions de `observed_at <= T1`, mesmo após nova Assertion com `observed_at > T1` revelar `effective_until` anterior a `T1`
6. `confidence` nunca é aceito do payload HTTP; é sempre computado a partir da proveniência
7. `source_artifact_id` é obrigatório em toda Assertion; a tentativa de criar uma sem artefato é rejeitada no domínio

## Por que essa estrutura é sólida

1. **Fato não carrega decisão escondida**: `COMPLETE_SNAPSHOT` habilita significado, não o decide
2. **Idempotência com identidade própria**: `SourceArtifact` concentra `source_version`/hash, não replicado em cada Assertion
3. **Confiança é resultado da proveniência**: nunca um campo livre do cliente
4. **Bitemporalidade explícita**: reprodução histórica e auditoria retrospectiva respondem perguntas diferentes, sem reescrever decisões
5. **Consistência com o Core**: regra, fato, evidência, proveniência e decisão continuam distintos
6. **Escalabilidade**: padrão bitemporal + Assertion é generalizável (NR-7), mas permanece na vertical até segunda ou terceira ocorrência comprovada em domínio distinto

## Próximos Passos

1. Implementar `SourceArtifact` e `EstablishmentQualificationAssertion` no domínio
2. Implementar `compute_confidence()` a partir do contexto de importação
3. Estender `EligibilityService` para consultar Assertions por cutoff temporal
4. Atualizar dossiê para registrar coverage gaps (incluindo o retrospectivo)
5. Testes conforme seção 11

## Referências

- **ADR-0041**: Elegibilidade por finalidade (requisitos sobre estabelecimento)
- **ADR-0042**: Proveniência, artefato recebido, `ConfidenceLevel` canônico
- **ADR-0043**: Governança de regras (`RuleAdoption` separado de fato; reavaliação sem reescrita)
- **ADR-0044**: Matriz de elegibilidade por mercado (consome Assertions)
- **NR-7**: `Assertion` como conceito emergente (esta ADR especializa; bitemporalidade é candidata a novo padrão observado)
- **Passo 7.5**: Dossiê e reprodutibilidade (Assertions no snapshot, coverage gaps)
