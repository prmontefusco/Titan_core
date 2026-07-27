# ADR-0045 — Importação e Reconciliação de Qualificações de Estabelecimento

**Status:** PENDENTE (aceito em conceito, requer revisão arquitetural)  
**Data de criação:** 27 de julho de 2026  
**Revisado:** 27 de julho de 2026  
**Autores:** Claude Code, Paulo Roberto Montefusco  

## Problema

Qualificações de estabelecimento (p. ex., `exportacao-china`, `frigorífico-certificado`) hoje são cadastradas manualmente, sem fonte versionada que permita auditoria, rastreamento de mudança ou reconciliação temporal.

**Cenário crítico:** um frigorífico perde a certificação de exportação para a China. Não há registro de quando foi perdida, quem a revogou ou por qual motivo — impossível distinguir entre auditoria e ocultação.

**Consequência para a elegibilidade:** a matriz mostra `ELEGIVEL` com base numa qualificação que era válida no dia do embarque mas foi revogada meses depois. O dossiê não captura a mudança.

## Restrições

1. **Consistência com ADR-0043**: regra e fato são conceitos distintos
2. **Honestidade temporal**: ausência de conhecimento não vira precisão inventada
3. **Rastreabilidade**: cada importação captura o instante, a fonte e o que ela afirmou
4. **Isolamento RLS**: qualificações pertencem à Organization
5. **Idempotência**: mesma versão de fonte importada 2x não duplica

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
RuleCondition: "estabelecimento.qualification = EXPORT_CN"
```

**FATO (Asserção Temporal — ADR-0045)**
```
EstablishmentQualificationAssertion:
  establishment_id: UUID
  qualification_type: "EXPORT_CN"
  
  asserted_status: QUALIFIED | NOT_QUALIFIED | UNKNOWN
  effective_from?: datetime
  effective_until?: datetime
  
  observed_at: datetime (quando a fonte foi consultada)
  source: "MAPA" | "FRIGORÍFICO" | ...
  source_version: string (identificador único da versão capturada)
  source_artifact_id: UUID (aponta para artefato que trouxe a informação)
  
  confidence: ALTO | MÉDIO | BAIXO
```

**Exemplo Concreto:**

Source (MAPA em 27/07):
```
SIF 1234: EXPORT_CN = ACTIVE (válido até indefinido)
SIF 1235: EXPORT_CN = ACTIVE (válido até indefinido)
SIF 1236: não aparece na lista
```

Registro no Titan:
```
Assertion 1:
  SIF 1234, EXPORT_CN, status=QUALIFIED
  effective_from: ?? (MAPA não informa)
  effective_until: ?? (MAPA não informa)
  observed_at: 27/07/2026
  source: MAPA
  source_version: "2026-07-27T15:30Z"

Assertion 2:
  SIF 1235, EXPORT_CN, status=QUALIFIED
  effective_from: ?? 
  effective_until: ??
  observed_at: 27/07/2026
  source: MAPA
  source_version: "2026-07-27T15:30Z"

Assertion 3 (anterior):
  SIF 1236, EXPORT_CN, status=QUALIFIED
  effective_from: 2024-03-15 (registrada anteriormente)
  effective_until: ?? (MAPA não informa quando revogou)
  observed_at: 15/03/2024
  source: MAPA
  source_version: "2024-03-15T08:00Z"

Assertion 4 (nova):
  SIF 1236, EXPORT_CN, status=UNKNOWN
  effective_from: null
  effective_until: null
  observed_at: 27/07/2026 (capturado como ausente em nova versão)
  source: MAPA
  source_version: "2026-07-27T15:30Z"
  confidence: BAIXO (só sabemos que saiu da lista; não quando nem por quê)
```

**O que isso diz:**

- SIF 1234 e 1235 estão habilitados conforme fonte de 27/07
- SIF 1236 estava habilitado conforme fonte anterior, mas não aparece em 27/07
- Titan sabe que ocorreu mudança entre 15/03/2024 e 27/07/2026
- Titan **não inventa** a data exata da revogação
- Dossiê reproduzível: qual assertion estava vigente no instante de cada decisão

### 2. Fluxo de Reconciliação (sem Invenção de Datas)

```
1. [Entrada]
   list = [SIF 1234, SIF 1235] (versão nova)

2. [Carregamento]
   anterior = [SIF 1234, SIF 1235, SIF 1236] (versão anterior)

3. [Comparação]
   Continua: SIF 1234, SIF 1235
   Saiu: SIF 1236

4. [Ação]
   Para SIF 1236:
   - NÃO marca effective_until = 26/07 (inventar)
   - Cria nova Assertion com status=UNKNOWN
   - observed_at = 27/07 (quando descobrimos a ausência)
   - confidence = BAIXO
```

### 3. Arquitetura Unificada (Regra → Fato → Decisão)

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
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
   Animal Facts              Establishment Facts
        │                               │
        │                   QualificationAssertion
        │                               │
        │                         SourceArtifact
        │                               │
        └───────────┬───────────────────┘
                    ▼
                Evaluation
                    │
                 Decision
                    │
                    ▼
            Market Eligibility
                    │
                    ▼
                  Dossier
```

**Exemplo de Resposta (Dossiê de Elegibilidade):**

```
Animal A, Frigorífico F, Data 27/07/2026

CHINA:
  Policy: CN-v7 (RuleAdoption vigente)
  Requisitos:
    1. Animal sem medicamento residual (prazo carência)
       Status: APROVADO
       Evidência: TreatmentApplication de 05/07, fim de carência 24/07
    
    2. Estabelecimento habilitado (EXPORT_CN)
       Status: REJEITADO
       Razão: Qualificação não encontrada em versão de 27/07/2026
       Última informação: SIF 1236 estava QUALIFIED em 15/03/2024
                         Ausente em versão posterior
                         Mudança ocorreu entre 15/03 e 27/07
       Confiança: BAIXA (data exata desconhecida)
       
  Decisão: NÃO ELEGÍVEL (requisito 2 falhou)
```

### 4. Implementação

**Domínio (`packages/livestock_domain/establishment_qualification_assertion.py`):**

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
    
    observed_at: datetime  # quando a fonte foi consultada
    source: str
    source_version: str
    source_artifact_id: TypedId | None
    confidence: ConfidenceLevel
    
    recorded_at: datetime
```

**Serviço (`packages/livestock_application/...`):**

- `EstablishmentQualificationImportService.import_assertions()`
- Não inventa `effective_until`
- Cria Assertion com `status=UNKNOWN` quando item sai da lista
- Mantém histórico completo de versões

**API (`apps/api/livestock_writes.py`):**

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
      "confidence": "HIGH"
    }
  ],
  "source_version": "2026-07-27T15:30Z"
}
```

### 5. Integração com Dossiê

Quando `EligibilityService` avalia um animal para um destino:

```python
assertions = repository.find_assertions_at(
    organization=org,
    establishment=frigorífico,
    observed_at_or_before=evaluation_time
)

for assertion in assertions:
    if assertion.asserted_status == QUALIFIED:
        if assertion.effective_until is None or assertion.effective_until >= evaluation_time:
            # Qualificação está vigente (ou vigência desconhecida)
            result = APROVADO
        else:
            # Qualificação expirou
            result = REJEITADO
    elif assertion.asserted_status == NOT_QUALIFIED:
        result = REJEITADO
    else:  # UNKNOWN
        result = INDETERMINADO
        # Dossiê registra que houve mudança, mas data desconhecida
        gap = CoverageGap(
            type="QUALIFICATION_TEMPORAL_BOUNDARY",
            last_known_status=anterior.status,
            last_known_observed_at=anterior.observed_at,
            current_observed_at=assertion.observed_at,
            message="Qualificação não encontrada em versão posterior. "
                    "Mudança ocorreu entre ... e ..., data exata desconhecida."
        )
```

---

## Por que essa estrutura é melhor

1. **Honestidade temporal**: não inventa dados que a fonte não forneceu
2. **Rastreabilidade**: cada asserção cita a versão exata da fonte
3. **Auditoria**: é possível reconstruir por que uma decisão foi tomada
4. **Consistência**: regra e fato mantêm papéis distintos (ADR-0043)
5. **Escalabilidade**: padrão é reutilizável para outras asserções (NR-7)

## Próximos Passos

1. Implementar `EstablishmentQualificationAssertion` no domínio
2. Estender `EligibilityService` para consultar assertions
3. Atualizar dossiê para registrar coverage gaps temporais
4. Testes de reconciliação com histórico de versões

## Referências

- **ADR-0041**: Elegibilidade por finalidade (requisitos sobre estabelecimento)
- **ADR-0042**: Proveniência e artefato recebido (reutilizar modelo)
- **ADR-0043**: Governança de regras (RuleAdoption separado de fato)
- **ADR-0044**: Matriz de elegibilidade por mercado (consome assertions)
- **NR-7**: Assertion como conceito emergente (esta ADR especializa)
- **Passo 7.5**: Dossiê e reprodutibilidade (assertions no snapshot)
