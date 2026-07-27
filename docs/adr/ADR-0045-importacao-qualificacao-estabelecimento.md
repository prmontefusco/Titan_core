# ADR-0045 — Importação e Reconciliação de Qualificações de Estabelecimento

**Status:** ACEITA (após revisão arquitetural)  
**Data de criação:** 27 de julho de 2026  
**Revisado:** 27 de julho de 2026  
**Autores:** Claude Code, Paulo Roberto Montefusco  

## Problema

Qualificações de estabelecimento (p. ex., `exportacao-china`, `frigorífico-certificado`) hoje são cadastradas manualmente, sem fonte versionada que permita auditoria, rastreamento de mudança ou reconciliação temporal.

**Cenário crítico:** um frigorífico perde a certificação de exportação para a China. Não há registro de quando foi perdida, quem a revogou ou por qual motivo — impossível distinguir entre auditoria e ocultação.

**Consequência para a elegibilidade:** a matriz mostra `ELEGIVEL` com base numa qualificação que era válida no dia do embarque mas foi revogada meses depois. O dossiê não captura a mudança.

## Restrições

1. **Consistência com ADR-0043**: regra (RuleAdoption) e fato (Assertion) são conceitos distintos
2. **Semântica de ausência**: ausência em lista só tem significado se a cobertura for declarada
3. **Honestidade temporal**: não inventar datas que a fonte não forneceu
4. **Rastreabilidade**: cada importação captura o instante, a fonte e o que ela afirmou
5. **Isolamento RLS**: qualificações pertencem à Organization
6. **Idempotência**: mesma versão de fonte importada 2x não duplica
7. **Reprodutibilidade**: decisões podem ser refazidas com conhecimento contemporâneo

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
SourceArtifact
    ↓
EstablishmentQualificationAssertion:
  establishment_id: UUID
  qualification_type: str
  
  asserted_status: QUALIFIED | NOT_QUALIFIED | UNKNOWN
  effective_from?: datetime
  effective_until?: datetime
  
  observed_at: datetime
  source: str
  source_artifact_id: UUID (obrigatório)
  source_snapshot_semantics: COMPLETE_SNAPSHOT | DELTA | PARTIAL | UNKNOWN
  confidence: ConfidenceLevel
  
  recorded_at: datetime
```

### 2. Semântica de AssertionStatus

**QUALIFIED**
- A fonte afirma positivamente a qualificação
- Exemplo: `SIF 1234 consta na lista de habilitados para EXPORT_CN`

**NOT_QUALIFIED**
- A fonte afirma explicitamente que o estabelecimento NÃO possui a qualificação
- Exemplo: `SIF 1236 foi explicitamente revogado do programa em 10/07`
- Nota: ausência em lista NÃO produz NOT_QUALIFIED automaticamente

**UNKNOWN**
- O material disponível não permite afirmar nenhum dos dois
- Exemplo: `SIF 1236 não aparece em versão de 27/07, mas anterior aparecia em 15/03`
- Conhecimento: mudança ocorreu entre os dois pontos; data exata desconhecida

### 3. SourceCoverage: Semântica do Snapshot

Adicionado como campo obrigatório para interpretar corretamente o que ausência significa:

**COMPLETE_SNAPSHOT**
- A fonte representa estado completo e exaustivo de todo o universo consultado
- Ausência tem significado: o estabelecimento não está habilitado
- Exemplo: MAPA publica lista oficial completa de todos os SIFs habilitados

**DELTA**
- A fonte representa apenas mudanças desde versão anterior
- Ausência não informa nada sobre o estado anterior
- Exemplo: "Estes 5 SIFs foram adicionados hoje"

**PARTIAL**
- A fonte representa apenas um subconjunto (região, programa, página)
- Ausência não significa ausência no universo completo
- Exemplo: "Lista de habilitados na região São Paulo, página 3 de 10"

**UNKNOWN**
- Semântica da cobertura é desconhecida
- Ausência não pode ser interpretada
- Falha segura: nenhuma Assertion derivada pode ser feita

### 4. Invariante: Ausência só Significa Algo com Cobertura

```python
# CORRETO
if snapshot.source_snapshot_semantics == COMPLETE_SNAPSHOT:
    if sif not in current_list and sif in previous_list:
        # Mudança ocorreu; cria Assertion UNKNOWN
        assertion.status = UNKNOWN
        assertion.confidence = VERIFIED_SOURCE  # confiamos na captura
        assertion.observed_at = "27/07/2026"

# INCORRETO
if sif not in current_list:
    # Nunca!
    assertion.status = NOT_QUALIFIED
```

### 5. Tempo Efetivo vs Tempo do Conhecimento

Ambos são necessários para dois tipos de pergunta:

**Tempo Efetivo** (`effective_from`, `effective_until`)
- Quando a afirmação se refere ao mundo
- Preenchido apenas se a fonte declara explicitamente
- Exemplo: "habilitação revogada em 10/07" → `effective_until = 10/07`

**Tempo do Conhecimento** (`observed_at`, `recorded_at`)
- Quando o Titan passou a conhecer a afirmação
- Sempre preenchido
- `observed_at`: quando consultamos a fonte (27/07/2026)
- `recorded_at`: quando gravamos na transação

**Pergunta 1: Reproduzir decisão de 20/07**
```
Qual era o conhecimento em 20/07?
Resposta: consulte Assertions com observed_at <= 20/07
```

**Pergunta 2: Auditoria retrospectiva hoje**
```
O que sabemos hoje sobre a habilitação em 15/07?
Resposta: consulte Assertions com effective_from/until que cobrem 15/07
        (independentemente de quando foram observadas)
```

Exemplo concreto:
```
15/07 → embarque (decisão feita com conhecimento de 15/07)
20/07 → Titan toma decisão sobre elegibilidade
27/07 → MAPA publica que habilitação havia sido revogada em 10/07

Reproduzir 20/07:
  Assertions com observed_at <= 20/07
  → não havia informação de revogação
  → status era QUALIFIED (ou UNKNOWN se versão anterior)
  
Auditoria hoje (01/08):
  Novo conhecimento: effective_until = 10/07
  → habilitação não era válida em 15/07
  → decisão de 20/07 foi tomada com informação incompleta
  → Dossier registra: "conhecimento posterior revelou lacuna temporal"
```

### 6. ConfidenceLevel Canônico

Usar exclusivamente o `ConfidenceLevel` definido na ADR-0042:

```python
class ConfidenceLevel(StrEnum):
    INFORMED = "INFORMED"                       # Recebimento declarado
    DOCUMENTED = "DOCUMENTED"                   # Documentação interna
    VERIFIED_SOURCE = "VERIFIED_SOURCE"         # Fonte externa verificada
    HARDENED_SYSTEM = "HARDENED_SYSTEM"         # Sistema crítico auditado
    CRYPTOGRAPHICALLY_ATTESTED = "CRYPTOGRAPHICALLY_ATTESTED"
```

**Nota importante:** `UNKNOWN` (status) ≠ baixa confiança

```python
# Ambas as afirmações são possíveis:

Assertion(
    status=UNKNOWN,
    confidence=VERIFIED_SOURCE
)
# Significado: confiamos que SIF 1236 não consta em snapshot
# oficial de 27/07, MAS não sabemos quando deixou de constar.

Assertion(
    status=UNKNOWN,
    confidence=INFORMED
)
# Significado: ouvimos dizer que SIF mudou de status, mas
# fonte é incerta e não temos artefato que comprove.
```

### 7. Fluxo de Reconciliação (com Cobertura)

```
1. [Entrada]
   list = [SIF 1234, SIF 1235]
   snapshot_semantics = COMPLETE_SNAPSHOT
   source_version = "2026-07-27T15:30Z"

2. [Carregamento]
   anterior = [SIF 1234, SIF 1235, SIF 1236]
   semantica_anterior = COMPLETE_SNAPSHOT

3. [Comparação]
   continua: SIF 1234, SIF 1235
   saiu: SIF 1236

4. [Ação - SIF 1236]
   NÃO marca effective_until = 26/07 (inventar)
   
   Cria Assertion:
     status = UNKNOWN
     effective_from = null
     effective_until = null
     observed_at = 27/07 (captura atual)
     source = MAPA
     source_snapshot_semantics = COMPLETE_SNAPSHOT
     confidence = VERIFIED_SOURCE (confiamos na fonte)
     
   Significado: "Observado ausente em snapshot completo oficial
                de 27/07, após estar presente em 15/03.
                Mudança ocorreu em algum ponto do intervalo,
                data exata desconhecida."
```

### 8. Impacto na Elegibilidade (Exemplo Corrigido)

**Policy CN:**
```
"Para exportar para China:
 estabelecimento deve ter habilitação EXPORT_CN vigente"
```

**Evaluation com dados:**
```
SIF 1236, China, 27/07/2026

Assertions disponíveis:
- 15/03/2024: QUALIFIED (observed_at=15/03/2024)
- 27/07/2026: UNKNOWN (observed_at=27/07/2026)

Conhecimento em 27/07:
- Não existe Assertion positiva vigente
- Última informação: UNKNOWN com confiança VERIFIED_SOURCE

Decision:
  Requisito: habilitação EXPORT_CN vigente
  Status: INDETERMINADO
  Razão: última afirmação positiva de 15/03/2024;
         ausência observada em 27/07/2026 (snapshot completo);
         mudança de status ocorreu entre os dois instantes,
         data exata desconhecida.
  Confiança: VERIFICADA (confiamos na fonte, não na data)

Dossiê registra:
  type: COVERAGE_GAP_TEMPORAL
  message: "Mudança de status não datada. Última confirmação 
            positiva anterior a atual ausência. Intervalo: 
            15/03/2024 a 27/07/2026."
```

**Alternativa: se Policy fosse diferente**

Policy X:
```
"Estabelecimentos presentes na lista oficial vigente
 estão habilitados. Ausência em snapshot completo implica
 não habilitação."
```

Neste caso:
```
Decision:
  Requisito atende à Policy X
  Status: REJEITADO
  Razão: ausência confirmada em snapshot completo oficial vigente
  Confiança: VERIFICADA
```

Observe: mesmo dado (ausência) + mesma fonte (MAPA snapshot completo)
→ decisões DIFERENTES conforme a regra.

### 9. Arquitetura Unificada

```
             GOVERNANÇA
                 │
          RuleIdentity
                 │
          RuleVersion
                 │
          RuleAdoption
                 │
                 ▼
              Policy
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
   Animal Facts    Establishment Facts
        │                 │
        │      SourceArtifact
        │                 │
        │      QualificationAssertion
        │                 │
        │       (asserted_status
        │        effective_time
        │        knowledge_time
        │        confidence)
        │                 │
        └────────┬────────┘
                 ▼
             Evaluation
                 │
             Decision
                 │
        Market Eligibility
                 │
             Dossier
            (com gaps)
```

### 10. Implementação

**Domínio** (`packages/livestock_domain/establishment_qualification_assertion.py`):
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
    source: str
    source_artifact_id: TypedId  # OBRIGATÓRIO
    source_snapshot_semantics: SourceCoverage  # OBRIGATÓRIO
    
    confidence: ConfidenceLevel  # Canônico de ADR-0042
    
    recorded_at: datetime

class SourceCoverage(StrEnum):
    COMPLETE_SNAPSHOT = "COMPLETE_SNAPSHOT"
    DELTA = "DELTA"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"

class AssertionStatus(StrEnum):
    QUALIFIED = "QUALIFIED"
    NOT_QUALIFIED = "NOT_QUALIFIED"
    UNKNOWN = "UNKNOWN"
```

**Serviço** (`packages/livestock_application/...`):
- `EstablishmentQualificationImportService.import_assertions()`
- Valida `source_snapshot_semantics`
- Não inventa `effective_until`
- Cria Assertion com `status=UNKNOWN` quando apropriado
- Mantém histórico completo de versões

**API** (`apps/api/livestock_writes.py`):
```python
POST /v1/livestock/establishments/qualifications/import
Body: {
  "assertions": [
    {
      "establishment_id": "...",
      "qualification_type": "EXPORT_CN",
      "asserted_status": "QUALIFIED",
      "effective_from": null,
      "effective_until": null,
      "source": "MAPA",
      "source_snapshot_semantics": "COMPLETE_SNAPSHOT",
      "confidence": "VERIFIED_SOURCE"
    }
  ],
  "source_version": "2026-07-27T15:30Z"
}
```

---

## Por que essa estrutura é mais sólida

1. **Sem invenção de dados**: não cria datas que a fonte não forneceu
2. **Interpretação honesta**: ausência só significa algo com cobertura declarada
3. **Rastreabilidade temporal dupla**: sabe-se quando ocorreu (effective) e quando soube (observed)
4. **Auditoria retrospectiva**: conhecimento posterior sobre fatos anteriores é capturado
5. **Consistência com Core**: regra, fato, evidência, proveniência e decisão continuam distintos
6. **Confiança semântica**: UNKNOWN com VERIFIED_SOURCE é válido e diferente de baixa confiança
7. **Escalabilidade**: padrão é generalizável (NR-7: Assertion como conceito)

## Próximos Passos

1. ✅ Implementar `EstablishmentQualificationAssertion` no domínio
2. ✅ Estender `EligibilityService` para consultar assertions
3. ✅ Atualizar dossiê para registrar coverage gaps temporais
4. ✅ Testes: unitários + integração PostgreSQL + E2E com dossiê

## Referências

- **ADR-0041**: Elegibilidade por finalidade (requisitos sobre estabelecimento)
- **ADR-0042**: Proveniência, artefato recebido, confidence level
- **ADR-0043**: Governança de regras (RuleAdoption separado de fato)
- **ADR-0044**: Matriz de elegibilidade por mercado (consome assertions)
- **NR-7**: Assertion como conceito emergente (esta ADR especializa)
- **Passo 7.5**: Dossiê e reprodutibilidade (assertions no snapshot)
