# ADR 0065 — BuyerPolicy Fase 2: Compartilhamento Contratual para Autoavaliação do Fornecedor

**Data:** 2026-08-19  
**Status:** ACEITA  
**Decisores:** responsável pelo produto e arquitetura do Titan  
**Aceita em:** 2026-08-19

---

## Contexto

BuyerPolicy Fase 1 (ADR-0064) implementou autoavaliação privada do comprador (origen INTERNAL_POLICY, reconhecimento INTERNAL_ONLY). Não há ainda compartilhamento bilateral.

No modelo Livestock, comprador (slaughterhouse) e fornecedor (farm) operam em Organizations separadas. Hoje, fornecedor publica animais/facts; comprador avalia elegibilidade regulatória contra matriz de mercado. Falta:

- comprador compartilhar Policy contratual com fornecedor;
- fornecedor autoavaliar conformidade;
- evidência auditável de que fornecedor conhece critério.

Discovery (2026-08-19) validou que o caso real existe e é viável com escopo contido: apenas leitura compartilhada + avaliação isolada do fornecedor, sem Decision/Proposal/Composição.

---

## Problema

1. **Falta contrato público de sharing:** APIs de criar/revogar grant, ler Policy compartilhada, avaliar Policy compartilhada não existem.
2. **Falta autorização nova:** Permission para compartilhar, ler grant, avaliar Policy recebida não está definida.
3. **Falta persistência:** Não há tabela de grants bilaterais; modelo ainda não está decidido.
4. **Semântica não resolvida:** Como grant ancora a Policy? Se comprador atualiza Policy, novo critério se aplica retroativamente?
5. **Limite de escopo não explícito:** Qual é o ponto de parada? Essa fase toca Decision, composição com matriz, ou leitura de resultado pelo comprador?

---

## Alternativas Consideradas

### Alternativa A: Compartilhamento Mínimo (RECOMENDADA)

**Escopo:**
- grant unidirecional comprador → fornecedor, específico por Policy
- fornecedor lê Policy + autoavalia seus próprios dados
- revogação explícita; sem vencimento automático
- nenhuma leitura de resultado pelo comprador
- nenhuma composição com matriz regulatória

**Vantagens:**
- Reutiliza PolicyEvaluationService, PolicyOrigin (Fase 1)
- Escopo contido, auditável
- Risco mitigado via FieldScope minimalista
- Extensível para Decision/Proposal (Fase 3)

**Desvantagens:**
- Não captura "Fornecedor confirmou estar dentro"
- Comprador não consegue negociar critério dinamicamente

**Trade-off:** Velocidade vs. inteligência operacional. Ganho inicial é redução de assimetria e fricção; feedback/negociação é iteração futura.

### Alternativa B: Compartilhamento com Acknowledgment

**Escopo:** Alternativa A + fornecedor pode confirmar conformidade ou escalar não-conformidade.

**Vantagens:** Captura evidência explícita.

**Desvantagens:** Adiciona entidade, workflow, coordenação. Escopo cresce.

**Decisão:** DEFER para Fase 3. Fase 2 valida sharing puro; acknowledgment vira iteração com feedback de uso real.

### Alternativa C: Integração Imediata com Matriz Regulatória

**Escopo:** Alternativa A + Policy contratual aparece lado a lado com regulatória.

**Vantagens:** UI integrado.

**Desvantagens:** Mistura trilhas não relacionadas; toca ADR-0044; risco de Fornecedor confundir resultado contratual com regulatório.

**Decisão:** REJECT. Trilhas permanecem separadas até haver caso real que exija composição.

---

## Decisão

**Adotar Alternativa A (Compartilhamento Mínimo).**

**Decisões RED (Contrato Público + Autorização + Persistência):**

### 1. Permissions Novas

```text
POLICY.COMPARTILHAR
├─ owner da Policy concede/revoga grant bilateral

POLICY.COMPARTILHAMENTO_LER
├─ owner lista grants emitidos
├─ beneficiário lista grants recebidos (opcional, pode separar endpoint)

POLICY.AVALIAR_COMPARTILHADA
└─ beneficiário executa avaliação sobre Policy recebida por grant
```

**Racional:** Não reutilizar `POLICY.AVALIAR` (Fase 1) para evitar confundir avaliação da própria Policy com avaliação de Policy bilateral.

**Restrição:** Nenhum usuário recebe `POLICY.COMPARTILHAR` por padrão. Deve ser concedido explicitamente por organização (ex.: operador, compliance officer).

---

### 2. Contratos Públicos (Endpoints HTTP)

```text
POST /v1/rule-governance/policies/{policy_id}/shares
├─ criar grant (owner da Policy)
│
├─ request: beneficiary_organization_id, access_purpose, valid_until, field_scope_profile
└─ response: grant_id, policy_id, owner_organization_id, beneficiary_organization_id, 
             access_purpose, field_scope_profile, status, valid_from, valid_until

POST /v1/rule-governance/policies/{policy_id}/shares/{grant_id}/revoke
├─ revogar grant (owner da Policy)
│
├─ request: revocation_reason (opcional)
└─ response: grant_id, status=REVOGADO, revoked_at, revocation_reason

GET /v1/rule-governance/shared-policies/{policy_id}
├─ ler Policy compartilhada (beneficiário com grant ativo)
│
├─ autorizado se: grant válido, não expirado, FieldScope cobre leitura
└─ response: policy_id, code, version, origin="CONTRACT", rules[], grant_id, owner_organization_id

POST /v1/rule-governance/shared-policies/{policy_id}/evaluate
├─ avaliar Policy compartilhada (beneficiário com grant ativo + POLICY.AVALIAR_COMPARTILHADA)
│
├─ request: subject_type, subject_id, purpose, reference_time
├─ autorizado se: grant válido, sujeito pertence ao beneficiário, Policy homogeneamente CONTRACT
└─ response: evaluation_id, policy_id, origin="CONTRACT", owner_organization_id, 
             requesting_organization_id, outcome, rule_results, missing_facts, hashes
```

**Nota:** Resultado da avaliação compartilhada **não é** retornado ao comprador por esses endpoints. Comprador não ganha acesso indireto aos facts do fornecedor.

---

### 3. Grant Anchor: Policy + Versão

**Decisão:** Grant ancora `(policy_id, policy_version_published_at_grant_time)`.

**Semântica:**
- Grant concedido em 2026-08-19 para Policy v1 (publicada em 2026-08-15);
- Se comprador publica Policy v2 em 2026-08-25, grant continua servindo v1;
- Fornecedor vê v1 e avalia contra v1;
- Se comprador quer que fornecedor use v2, deve revogar grant v1 e conceder grant novo para v2.

**Racional:**
- Impede mudança silenciosa de critério em grants já ativos;
- Garante auditoria clara do que cada avaliação foi contra;
- Força decisão explícita do comprador quando critério muda.

**Alternativa rejeitada:** Grant ancora Policy lógica (sem versão); atualizar Policy afeta grants ativos retroativamente. Risco de comprador não saber que critério mudou e Fornecedor avaliar contra critério novo sem consentimento.

---

### 4. Persistência: Tabela Própria

**Decisão:** Criar tabela `core_identity.authorization_grants` (ou nomeação equivalente) com schema do PLAN item 5.1.

**Colunas obrigatórias:**
```sql
grant_id UUID PRIMARY KEY
owner_organization_id UUID NOT NULL (foreign key → organizations)
beneficiary_organization_id UUID NOT NULL (foreign key → organizations)
policy_id UUID NOT NULL (foreign key → policies)
policy_version_id UUID NOT NULL (foreign key → policy_versions)
access_purpose VARCHAR(100) NOT NULL (controlled value)
field_scope_profile VARCHAR(100) NOT NULL (controlled value)
valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP
valid_until TIMESTAMP NOT NULL (CHECK valid_until > CURRENT_TIMESTAMP at insert)
status VARCHAR(20) NOT NULL (ATIVO, REVOGADO, EXPIRADO) DEFAULT 'ATIVO'
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
created_by VARCHAR(255) NOT NULL (audit trail: User/Subject)
revoked_at TIMESTAMP NULL
revoked_by VARCHAR(255) NULL
revocation_reason TEXT NULL
record_owner_organization_id UUID NOT NULL (= owner_organization_id for RLS)
```

**Racional:**
- Tabela própria evita contaminação de Policy com sharing concerns;
- RLS por `record_owner_organization_id` = `owner_organization_id` garante apenas owner consegue revogar;
- Audit trail completo para compliance.

**Alternativa rejeitada:** Usar JSON em Policy, coluna em Evaluation, ou cache em Valkey. Inseguro, não-auditável, risco de garbage.

---

### 5. valid_until Obrigatório

**Decisão:** Todo grant deve ter `valid_until` preenchido no momento da criação. Sem vencimento automático, revogação é explícita.

**Validação na API:**
- `valid_until > CURRENT_TIMESTAMP` (deve ser futuro)
- `valid_until - CURRENT_TIMESTAMP` máximo recomendado 1 ano (sugerência, não bloqueio)

**Status EXPIRADO:**
- Grant muda para status EXPIRADO automaticamente após `valid_until` (via job/trigger ou lazy-check na query);
- Acesso é bloqueado mesmo que status ainda seja fisicamente ATIVO (query valida `status='ATIVO' AND valid_until > NOW()`).

**Racional:**
- Impede grants "para sempre" e esquecimento de revogação;
- Força comprador a renovar explicitamente se relacionamento continua;
- Auditável (renewal = novo grant).

---

### 6. AccessPurpose Local Controlado

**Decisão:** Fase 2 usa valor local controlado `AUTOAVALIACAO_CONTRATUAL_FORNECEDOR` **sem promover ainda ao DOMAIN.md**.

**Implementação:**
- Defina enum ou control table local em `packages/core_application/policy_authorization.py` (ou local equivalente);
- Valor é validado antes de criar grant (não aceita string arbitrária);
- Documentação clara: "Permite Fornecedor autoavaliar conformidade contra Policy compartilhada do Comprador".

**Promoção futura (Fase 3+):**
- Se há segundo domínio que reutiliza AccessPurpose (ex.: auditoria de terceiro, inspeção regulatória);
- Então formaliza `AccessPurpose` enum em DOMAIN.md com `AUTOAVALIACAO_CONTRATUAL_FORNECEDOR` entre outros valores canônicos.

**Racional:**
- Não contamina DOMAIN.md enquanto há incerteza de reutilização;
- Evita formalização prematura que depois precisaria ser revisada;
- DOMAIN.md fica congelado (ADR-0001); promoção exige decisão explícita.

---

### 7. FieldScope Mínimo

**Decisão (confirmada do PLAN):** FieldScope autoriza leitura apenas de:
- Identificação da Policy (policy_id, code, version)
- Metadados mínimos da Rule (rule_id, code)
- Condições da Rule (para entendimento do critério)
- Resultado da própria avaliação (outcome, rule_results)
- Razões da própria avaliação (reason per rule_result)
- Facts faltantes/pendentes (missing_evidence_types)

**Bloqueia:**
- Evidências brutas do comprador
- Facts brutos do comprador
- Dados de terceiros
- Payload bruto de VerificationBundle
- Detalhes internos de governança não necessários

**Validação:** Cada campo no response de `GET shared-policies/{policy_id}` e `POST shared-policies/{policy_id}/evaluate` é explicitamente listado no PLAN seção 8. Testes negativos cobrem tentativa de ler campos bloqueados.

---

## Consequências

### Implementação

1. **Core/Application** (`packages/core_application/`):
   - `policy_sharing_service.py` (novo): orquestração de grant create/revoke/validate
   - `policy_authorization.py`: adiciona `POLICY.COMPARTILHAR`, `POLICY.COMPARTILHAMENTO_LER`, `POLICY.AVALIAR_COMPARTILHADA`

2. **Core/Infrastructure** (`packages/core_infrastructure/persistence/`):
   - migration: tabela `authorization_grants`
   - `authorization_grant.py` (novo): TransactionalAuthorizationGrantRepository

3. **Apps/API** (`apps/api/`):
   - `policy_governance.py`: adiciona 4 endpoints
   - `livestock_dependencies.py`: atualiza `require_permission` para novas Permissions
   - `problem.py`: mapeia erros de sharing para contratos HTTP

4. **Tests**:
   - `tests/application/test_policy_sharing_service.py` (novo)
   - `tests/integration/test_policy_sharing_api.py` (novo): 14 testes mínimos do PLAN
   - `tests/livestock_api_support.py`: adiciona novas Permissions ao operador de teste

5. **Validação Manual**:
   - `apps/validacao/policy_sharing_bilateral.py` (novo): roteiro comprador-fornecedor

### Verificações de Segurança

- **P-198 (negação uniforme):** 404 para policy/subject/grant não acessíveis; sem terceiro sinal
- **Homogeneidade:** Grant rejeita Policy não homogeneamente CONTRACT (3 pontos de defesa: publicação, criação grant, avaliação)
- **RLS:** `record_owner_organization_id = owner_organization_id` em grants
- **Auditoria:** Todas as operações de grant registradas com User, Organization, timestamp
- **Isolamento:** Resultado de avaliação compartilhada permanece isolado; não entra na matriz regulatória

### Não-Mudança

- Fase 1 (ADR-0064) fica intacta; INTERNAL_POLICY e POLICY.AVALIAR continuam funcionando
- Matriz regulatória (ADR-0044) sem mudança
- DOMAIN.md sem mudança (AccessPurpose fica local por enquanto)

---

## Relacionadas

- ADR-0064 — BuyerPolicy Fase 1: autoavaliação privada (origem INTERNAL_POLICY)
- ADR-0018 — Compartilhamento por finalidade, escopo e concessões (candidatos arquiteturais: Sharing, Grant, AccessPurpose, FieldScope)
- ADR-0044 — Matriz de elegibilidade por mercado com regras governadas
- ADR-0050 — Execução determinística e isolada de policies e rules
- ADR-0003 — PostgreSQL, RLS e defesa em profundidade
- ADR-0002 — Isolamento e propriedade por Organization

---

## Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Grant amplo demais expor dados desnecessários | MÉDIA | ALTO | FieldScope mínimo + testes negativos |
| Confusão entre trilha contratual e regulatória | BAIXA | MÉDIO | origen CONTRACT explícita + não-interferência com matriz |
| Buyer ganhar acesso indireto aos dados do Fornecedor | BAIXA | ALTO | Contrato não permite leitura de resultado/facts pelo buyer; Fase 3 se exigido |
| Grant expirado mas avaliação histórica fica "órfã" | MUITO BAIXA | BAIXO | Evaluation é imutável; expiração só bloqueia novos acessos |
| Policy atualizada alterar silenciosamente grant ativo | BAIXA | MÉDIO | Grant ancora Policy + versão; mudança de critério exige novo grant |
| Fornecedor consegue derivar dataset do comprador por força bruta | BAIXA | MÉDIO | FieldScope + rate-limiting (Fase 3) + auditoria de acesso |

---

## Decisão Final

**ESTA ADR PROPÕE ACEITAR A ALTERNATIVA A (Compartilhamento Mínimo) COM AS 7 DECISÕES RED ACIMA EXPLICITADAS.**

Os seguintes passos dependem desta ADR:

1. **SPEC proposta** (entra após esta ADR ACEITA): descreve contratos HTTP, exemplos de request/response, cenários, fluxos
2. **BUILD authorization** (após SPEC aprovada): implementação segue design congelado
3. **Fase 3** (quando há demanda): Decision, Proposal, Composição com matriz, acknowledgment, feedback

