# SPEC: BuyerPolicy Fase 2 — Compartilhamento Contratual para Autoavaliação do Fornecedor

**Data:** 2026-08-19  
**Estado:** IMPLEMENTADA  
**Nível de Criticidade:** CRÍTICA (novo contrato público, autorização, compartilhamento cross-Organization)  
**Aprovada em:** 2026-08-19

---

## 1. Visão

Um comprador (slaughterhouse) publica uma Policy contratual com critérios de seleção de animais (peso, saúde, repouso). Ele compartilha essa Policy com um fornecedor específico. O fornecedor consulta a Policy e autoavalia seus próprios animais contra o critério do comprador. Recebe resultado técnico (conforme/não-conforme) e razões (peso fora de faixa, tratamento recente, etc.). Ambos têm auditoria completa. Quando a relação comercial termina, comprador revoga o grant.

**Valor:** Reduz assimetria de informação, evita iterações "seu animal não atende"; fornecedor consegue corrigir antes de oferecer.

---

## 2. Caso de Uso Mínimo

### Ator Principal
- **Comprador (Buyer):** Organization que publica critério contratual
- **Fornecedor (Supplier):** Organization que autoavalia conformidade

### Fluxo Principal

#### Passo 1: Comprador Cria Policy Contratual
```
Comprador
├─ acessa UI ou API de governança
├─ cria Policy com origem CONTRACT
│  ├─ código: "criterio-fornecedor-a"
│  ├─ nome: "Critério de Seleção — Fornecedor A"
│  └─ descrição: "Regras que o Fornecedor A deve atender"
├─ publica regra contratual (RuleVersion):
│  ├─ "Peso entre 450–550kg"
│  ├─ "Sem tratamento nos últimos 7 dias"
│  └─ "Repouso mínimo 15 dias"
└─ Policy fica PUBLISHED, homogeneamente CONTRACT
```

**Status esperado:** ✅ Policy criada, homogeneidade validada, Policy pronta para compartilhamento.

---

#### Passo 2: Comprador Concede Grant ao Fornecedor
```
POST /v1/rule-governance/policies/{policy_id}/shares

Request:
{
  "beneficiary_organization_id": "uuid:fornecedor-a",
  "access_purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
  "valid_until": "2026-12-31T23:59:59Z",
  "field_scope_profile": "CONTRATO_MINIMO"
}

Response: 201 Created
{
  "grant_id": "uuid:grant-001",
  "policy_id": "uuid:policy-001",
  "policy_version": 1,
  "owner_organization_id": "uuid:comprador",
  "beneficiary_organization_id": "uuid:fornecedor-a",
  "access_purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
  "field_scope_profile": "CONTRATO_MINIMO",
  "status": "ATIVO",
  "valid_from": "2026-08-19T10:00:00Z",
  "valid_until": "2026-12-31T23:59:59Z",
  "created_at": "2026-08-19T10:00:00Z",
  "created_by": "user:comprador-operador"
}
```

**Precondições:**
- Solicitante atua em OrganizationContext do comprador
- Solicitante possui `POLICY.COMPARTILHAR`
- Policy é homogeneamente CONTRACT
- valid_until > now()

**Status esperado:** ✅ Grant criado, ativo, com validade até 2026-12-31.

---

#### Passo 3: Fornecedor Lê Policy Compartilhada
```
GET /v1/rule-governance/shared-policies/{policy_id}

Response: 200 OK
{
  "policy_id": "uuid:policy-001",
  "code": "criterio-fornecedor-a",
  "name": "Critério de Seleção — Fornecedor A",
  "version": 1,
  "origin": "CONTRACT",
  "owner_organization_id": "uuid:comprador",
  "rules": [
    {
      "rule_id": "uuid:rule-001",
      "code": "peso-450-550kg",
      "name": "Peso entre 450–550kg",
      "conditions": [
        {
          "fact_type": "livestock.weight",
          "operator": "between",
          "value_min": 450,
          "value_max": 550
        }
      ],
      "severity": "blocking",
      "justification": "Critério de comprador para seleção de animal"
    },
    {
      "rule_id": "uuid:rule-002",
      "code": "sem-tratamento-7d",
      "name": "Sem tratamento nos últimos 7 dias",
      "conditions": [
        {
          "fact_type": "livestock.treatment",
          "payload_key": "treatment_applied_date",
          "operator": "older_than_days",
          "expected_value": 7
        }
      ],
      "severity": "blocking"
    },
    {
      "rule_id": "uuid:rule-003",
      "code": "repouso-15d",
      "name": "Repouso mínimo 15 dias",
      "conditions": [...]
    }
  ],
  "grant_id": "uuid:grant-001",
  "valid_from": "2026-08-19T10:00:00Z",
  "valid_until": "2026-12-31T23:59:59Z"
}
```

**Precondições:**
- Solicitante atua em OrganizationContext do fornecedor
- Grant ativo e válido existe
- Grant não expirou
- FieldScope cobre a leitura

**Status esperado:** ✅ Fornecedor vê Policy contratual completa, com todas as Rules e condições.

---

#### Passo 4: Fornecedor Avalia Seus Animais
```
POST /v1/rule-governance/shared-policies/{policy_id}/evaluate

Request:
{
  "subject_type": "animal",
  "subject_id": "uuid:animal-123",
  "purpose": "autoavaliacao-contratual",
  "reference_time": "2026-08-19T10:00:00Z"
}

Response: 201 Created
{
  "evaluation_id": "uuid:eval-001",
  "policy_id": "uuid:policy-001",
  "policy_code": "criterio-fornecedor-a",
  "policy_version": 1,
  "origin": "CONTRACT",
  "owner_organization_id": "uuid:comprador",
  "requesting_organization_id": "uuid:fornecedor-a",
  "subject_type": "animal",
  "subject_id": "uuid:animal-123",
  "purpose": "autoavaliacao-contratual",
  "outcome": "CONDICOES_SATISFEITAS",
  "engine_version": "2.1.0",
  "evaluated_at": "2026-08-19T10:00:15Z",
  "snapshot_hash": "sha256:abc123...",
  "context_hash": "sha256:def456...",
  "evaluation_hash": "sha256:ghi789...",
  "rule_results": [
    {
      "rule_id": "uuid:rule-001",
      "rule_code": "peso-450-550kg",
      "rule_version": 1,
      "status": "SATISFEITA",
      "severity": "blocking",
      "reason": "Peso registrado: 520kg, dentro da faixa 450–550kg",
      "corrective_action": null,
      "missing_evidence_types": []
    },
    {
      "rule_id": "uuid:rule-002",
      "rule_code": "sem-tratamento-7d",
      "rule_version": 1,
      "status": "SATISFEITA",
      "severity": "blocking",
      "reason": "Último tratamento registrado há 12 dias, atende critério",
      "corrective_action": null,
      "missing_evidence_types": []
    },
    {
      "rule_id": "uuid:rule-003",
      "rule_code": "repouso-15d",
      "rule_version": 1,
      "status": "SATISFEITA",
      "severity": "blocking",
      "reason": "Animal em repouso há 18 dias, atende critério mínimo",
      "corrective_action": null,
      "missing_evidence_types": []
    }
  ]
}
```

**Precondições:**
- Solicitante atua em OrganizationContext do fornecedor
- Grant ativo e válido existe
- Solicitante possui `POLICY.AVALIAR_COMPARTILHADA`
- Subject (animal) pertence ao fornecedor
- Policy continua homogeneamente CONTRACT

**Status esperado:** ✅ Evaluation executada, resultado conforme, razões claras, animal elegível.

---

#### Passo 5: Fornecedor Avalia Animal Não-Conforme
```
POST /v1/rule-governance/shared-policies/{policy_id}/evaluate

Request:
{
  "subject_type": "animal",
  "subject_id": "uuid:animal-456",
  "purpose": "autoavaliacao-contratual",
  "reference_time": "2026-08-19T10:00:00Z"
}

Response: 201 Created
{
  "evaluation_id": "uuid:eval-002",
  "policy_id": "uuid:policy-001",
  "outcome": "CONDICOES_NAO_SATISFEITAS",
  "rule_results": [
    {
      "rule_id": "uuid:rule-001",
      "rule_code": "peso-450-550kg",
      "status": "NAO_SATISFEITA",
      "reason": "Peso registrado: 420kg, abaixo do mínimo 450kg",
      "corrective_action": "Aguardar ganho de peso ou oferecer animal diferente",
      "missing_evidence_types": []
    },
    {
      "rule_id": "uuid:rule-002",
      "status": "SATISFEITA",
      "reason": "Sem tratamento recente"
    },
    {
      "rule_id": "uuid:rule-003",
      "status": "SATISFEITA",
      "reason": "Repouso adequado"
    }
  ]
}
```

**Status esperado:** ✅ Evaluation executada, resultado não-conforme, razão clara (peso insuficiente), Fornecedor sabe o que corrigir.

---

#### Passo 6: Fornecedor Avalia Sem Dados Suficientes
```
POST /v1/rule-governance/shared-policies/{policy_id}/evaluate

Request:
{
  "subject_type": "animal",
  "subject_id": "uuid:animal-789",
  ...
}

Response: 201 Created
{
  "evaluation_id": "uuid:eval-003",
  "outcome": "INDETERMINADO",
  "rule_results": [
    {
      "rule_id": "uuid:rule-001",
      "status": "PENDENTE",
      "reason": "Não há registro de peso para este animal",
      "missing_evidence_types": ["livestock.weight"]
    },
    {
      "rule_id": "uuid:rule-002",
      "status": "SATISFEITA"
    }
  ]
}
```

**Status esperado:** ✅ Evaluation parcial, identifica exatamente qual dado falta (peso).

---

#### Passo 7: Comprador Revoga Grant
```
POST /v1/rule-governance/policies/{policy_id}/shares/{grant_id}/revoke

Request:
{
  "revocation_reason": "fim de contrato comercial"
}

Response: 200 OK
{
  "grant_id": "uuid:grant-001",
  "policy_id": "uuid:policy-001",
  "status": "REVOGADO",
  "revoked_at": "2026-08-25T09:00:00Z",
  "revoked_by": "user:comprador-operador",
  "revocation_reason": "fim de contrato comercial"
}
```

**Precondições:**
- Solicitante atua em OrganizationContext do comprador
- Solicitante possui `POLICY.COMPARTILHAR`
- Grant existe

**Status esperado:** ✅ Grant revogado, Fornecedor perde acesso.

---

#### Passo 8: Fornecedor Tenta Reavaliações Após Revogação
```
POST /v1/rule-governance/shared-policies/{policy_id}/evaluate

Response: 403 Forbidden
{
  "reason_code": "PERMISSAO_AUSENTE",
  "message": "Você não possui acesso a esta Policy compartilhada"
}
```

**Status esperado:** ✅ Fornecedor recebe negação segura, sem revelar se grant foi revogado ou nunca existiu.

---

## 3. Cenários de Erro

### Cenário A: Criar Grant para Policy Não-Contratual
```
POST /v1/rule-governance/policies/{policy_id_internal}/shares

Response: 422 Unprocessable Entity
{
  "reason_code": "POLICY_NAO_RECONHECIDA_COMO_CONTRATUAL",
  "message": "A Policy não é homogeneamente CONTRACT; compartilhamento recusado",
  "details": "Policy contém Rules de origem INTERNAL_POLICY, não contratual"
}
```

**Precondição:** Policy é homogeneamente INTERNAL_POLICY (Fase 1).

---

### Cenário B: Terceira Organization Tenta Acessar Grant
```
GET /v1/rule-governance/shared-policies/{policy_id}

[Contexto: Organization não-autorizada]

Response: 404 Not Found
{
  "reason_code": "RECURSO_NAO_ENCONTRADO",
  "message": "Policy não encontrada ou não acessível"
}
```

**Precondição:** Terceira Organization não é owner nem beneficiary do grant.

**Garantia:** Negação uniforme (não diferencia "existe mas não é seu" de "não existe").

---

### Cenário C: Avaliar Subject de Outra Organization
```
POST /v1/rule-governance/shared-policies/{policy_id}/evaluate

Request:
{
  "subject_type": "animal",
  "subject_id": "uuid:animal-de-outra-org"
}

Response: 404 Not Found
{
  "reason_code": "RECURSO_NAO_ENCONTRADO",
  "message": "Animal não encontrado ou não acessível"
}
```

**Garantia:** P-198 compliance — sem revelar que animal existe em outra Organization.

---

### Cenário D: Grant Expirado
```
GET /v1/rule-governance/shared-policies/{policy_id}

[Grant expirou em 2026-12-31]

Response: 403 Forbidden
{
  "reason_code": "PERMISSAO_AUSENTE",
  "message": "Acesso negado: concessão expirada ou revogada"
}
```

---

### Cenário E: Sem Permission POLICY.AVALIAR_COMPARTILHADA
```
POST /v1/rule-governance/shared-policies/{policy_id}/evaluate

Response: 403 Forbidden
{
  "reason_code": "PERMISSAO_AUSENTE",
  "message": "Permission POLICY.AVALIAR_COMPARTILHADA necessária para avaliar Policy compartilhada"
}
```

---

## 4. Critérios de Aceite

| # | Critério | Validação |
|---|----------|-----------|
| 1 | Comprador cria Policy homogeneamente CONTRACT | Policy publica com origem CONTRACT sem erros |
| 2 | Comprador concede grant válido a Fornecedor | Grant criado, ATIVO, com validade clara |
| 3 | Fornecedor lê Policy compartilhada completa | Todas as Rules, condições e metadados acessíveis |
| 4 | Fornecedor autoavalia animal conforme | Evaluation retorna CONDICOES_SATISFEITAS com razões |
| 5 | Fornecedor autoavalia animal não-conforme | Evaluation retorna CONDICOES_NAO_SATISFEITAS com razões claras |
| 6 | Fornecedor identifica dados faltantes | Evaluation retorna INDETERMINADO com missing_evidence_types |
| 7 | Comprador revoga grant | Grant muda para REVOGADO, revoked_at preenchido |
| 8 | Fornecedor perde acesso após revogação | GET/POST recebem 403/404, sem revelar grant anterior |
| 9 | Grant expirado bloqueia acesso | Após valid_until, acesso negado |
| 10 | Terceira Organization recebe 404 uniforme | Sem sinal de "existe mas não é seu" |
| 11 | Evaluation compartilhada não entra em matriz | MarketEligibilityPurpose continua inafetada |
| 12 | Fase 1 (POLICY.AVALIAR) continua funcionando | Policy INTERNAL_POLICY avaliada sem grant |
| 13 | Auditoria registra todas as operações | Grant create/revoke/eval estão em trilha |
| 14 | Homogeneidade é rechecada na avaliação | Evaluation rejeita se Policy virou heterogênea |

---

## 5. Fora de Escopo (Fase 2)

- ❌ Comprador ler resultado produzido pelo Fornecedor
- ❌ Comprador consumir facts brutos do Fornecedor por essa trilha
- ❌ Fornecedor confirmar formalmente "estou em conformidade" (DecisionProposal)
- ❌ Comprador aceitar/rejeitar proposta do Fornecedor (Decision)
- ❌ Integração visual de trilha contratual com matriz regulatória
- ❌ Broadcast de grant para múltiplos Fornecedores em um comando
- ❌ Vigência baseada em contrato externo complexo (Fase 3)
- ❌ Feedback (comprador comunica se comprou ou rejeitou o Lote)
- ❌ Versionamento automático de grant quando Policy muda

---

## 6. Definições

- **Grant:** Concessão bilateral e auditável de acesso a Policy para um propósito e período definido
- **AccessPurpose:** Finalidade controlada da concessão (ex.: AUTOAVALIACAO_CONTRATUAL_FORNECEDOR)
- **FieldScope:** Conjunto de campos que o beneficiário pode ler (ex.: Policy, Rule, resultado, razões)
- **Origin CONTRACT:** Tipo de Policy compartilhável, homogeneamente contratual
- **Homogeneidade:** Garantia de que todas as Rules publicadas sob uma Policy têm o mesmo RuleSourceType

---

## 7. Aceitação

Esta SPEC foi implementada na Fase 2 conforme ADR-0065 (ACEITA) e registrada no checklist como NEXT-10.

**Decisões já fechadas em ADR-0065:**
- ✅ Permissions novas
- ✅ Endpoints HTTP
- ✅ Grant anchor
- ✅ Persistência
- ✅ valid_until
- ✅ AccessPurpose
- ✅ FieldScope

**Esta SPEC detalha entrega, cenários e critérios de aceite.**
