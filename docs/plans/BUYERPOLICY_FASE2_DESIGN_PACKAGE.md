# BuyerPolicy — Fase 2: Design Package (PLAN)

**Data:** 2026-08-19  
**Estado:** AGUARDANDO APROVAÇÃO PARA BUILD  
**Escopo:** desenho técnico da SPEC proposta de BuyerPolicy Fase 2; nenhuma linha de código, migration ou teste é criada por este documento.

**Derivado de:**
- ADR-0065 (proposta) — BuyerPolicy Fase 2: compartilhamento contratual para autoavaliação do fornecedor
- SPEC proposta — BuyerPolicy Fase 2: compartilhamento contratual para autoavaliação do fornecedor  
- ADR-0064 — BuyerPolicy Fase 1 (ACEITA)
- ADR-0018 — compartilhamento por finalidade, escopo e concessões (ACEITA)
- ADR-0049 — políticas regulatórias e perfis de mercado (ACEITA)
- ADR-0050 — execução determinística e isolada de policies e rules (ACEITA)

> Este PLAN existe para transformar a Fase 2 em um recorte executável sem misturar sharing bilateral, consumo do resultado pelo comprador, Decision, bundle ou matriz regulatória. O BUILD só deve começar depois da aprovação explícita deste plano, porque a fase introduz contrato público novo, permission nova e compartilhamento cross-Organization.

---

## 1. Objetivo

Implementar o primeiro corte seguro de BuyerPolicy Fase 2:

- comprador compartilha uma BuyerPolicy contratual com um fornecedor específico;
- fornecedor lê a Policy compartilhada dentro de escopo autorizado;
- fornecedor executa Evaluation sobre seus próprios sujeitos e facts;
- resultado permanece no contexto do fornecedor;
- nenhum dado bruto do fornecedor é exposto ao comprador por efeito colateral;
- nada entra na matriz regulatória;
- nada vira Decision, DecisionProposal, Publication, Assertion ou VerificationBundle.

---

## 2. Caso Real Implementado

**Caso mínimo suportado:**

1. uma Organization compradora publica uma BuyerPolicy homogeneamente CONTRACT;
2. ela concede acesso dessa Policy a uma Organization fornecedora específica;
3. o fornecedor consulta a Policy compartilhada;
4. o fornecedor executa autoavaliação sobre um animal ou lote da sua própria Organization;
5. recebe resultado técnico, razões e facts faltantes;
6. o comprador pode revogar o grant depois.

**Não implementado neste corte:**
- comprador ler o resultado produzido pelo fornecedor;
- fornecedor confirmar formalmente "estou em conformidade";
- composição com elegibilidade regulatória;
- grants para vários fornecedores em uma operação;
- vigência baseada em contrato externo complexo.

---

## 3. Fronteiras Funcionais

### 3.1 Incluído

- BuyerPolicy CONTRACT
- concessão bilateral 1:1 comprador → fornecedor por Policy
- leitura autorizada da Policy compartilhada
- avaliação autorizada pelo fornecedor
- revogação explícita do grant
- validade temporal do grant
- auditoria mínima da concessão e da revogação
- resposta técnica com origem contratual explícita

### 3.2 Excluído

- leitura do resultado pelo comprador
- facts brutos do fornecedor para o comprador
- DecisionProposal / Decision
- qualquer uso em MarketEligibilityPurpose
- nova semântica de recognition_boundary
- bundle contratual
- notificações
- UX final de produto

---

## 4. Ownership Técnico Proposto

### 4.1 Módulos owners

**Core/Application**
- regra de autorização do grant bilateral
- validação de escopo, beneficiário, validade e finalidade
- orquestração da leitura compartilhada e da avaliação bilateral

**Core/Infrastructure**
- persistência do grant
- queries de leitura do grant por owner/beneficiário/policy
- persistência de auditoria correlata

**Apps/API**
- endpoints HTTP de sharing, leitura e avaliação
- resolução do OrganizationContext
- adaptação de erros para contrato público

**Livestock/Application**
- reutilização do FactProvider existente para avaliar animal/lote do fornecedor
- nenhum ownership novo de domínio

### 4.2 Sem entidade nova de vertical

A fase deve ficar em Core/Application + API, usando a vertical Livestock apenas como provedora dos facts para a execução da Policy.

---

## 5. Modelo Técnico Mínimo

### 5.1 Grant Bilateral

O mecanismo mínimo deve representar:

```text
grant_id: UUID
owner_organization_id: OrganizationId
beneficiary_organization_id: OrganizationId
policy_id: TypedId
access_purpose: AccessPurpose (controlado)
field_scope_profile: FieldScopeProfile (controlado)
valid_from: datetime
valid_until: datetime (obrigatório)
status: GrantStatus (ATIVO, REVOGADO, EXPIRADO)
created_at: datetime
revoked_at: datetime | None
revocation_reason: str | None
audit_trail: referência
```

Este PLAN assume grant dedicado a BuyerPolicy Fase 2, mesmo que a modelagem futura possa convergir para um mecanismo mais geral de sharing.

### 5.2 Status Mínimos

- `ATIVO`
- `REVOGADO`
- `EXPIRADO`

Não incluir SUSPENSO, SUBSTITUÍDO ou workflow mais rico neste corte.

---

## 6. AccessPurpose e FieldScope

### 6.1 AccessPurpose Proposto

Valor canônico proposto:

```text
AUTOAVALIACAO_CONTRATUAL_FORNECEDOR
```

Sem cravar ainda em DOMAIN.md; a formalização exata fica para BUILD se a implementação exigir enum/control table local já existente. O importante é a semântica:

- **finalidade:** permitir ao fornecedor executar autoavaliação contratual sobre seus próprios dados;
- **não autoriza:** exportação, redistribuição, composição regulatória ou leitura de dados de terceiros.

### 6.2 FieldScope Mínimo

**Deve permitir leitura apenas de:**
- identificação da Policy
- metadados mínimos da Rule
- condições da Rule necessárias para entendimento do critério
- resultado da própria avaliação
- razões da própria avaliação
- facts faltantes/insuficientes/pendentes da própria avaliação

**Não deve permitir:**
- evidências brutas do comprador
- facts brutos do comprador
- dados de terceiros
- detalhes internos desnecessários de governança
- qualquer campo que permita derivar dataset do fornecedor além do necessário para a própria tela/resposta técnica

---

## 7. Permissions Novas

### 7.1 Propostas

```text
POLICY.COMPARTILHAR
POLICY.COMPARTILHAMENTO_LER
POLICY.AVALIAR_COMPARTILHADA
```

### 7.2 Racional

- **POLICY.COMPARTILHAR:** owner da Policy concede e revoga grant
- **POLICY.COMPARTILHAMENTO_LER:** owner pode listar grants emitidos; beneficiário pode consultar grants recebidos
- **POLICY.AVALIAR_COMPARTILHADA:** beneficiário executa avaliação de Policy que não é owned pela sua Organization, mas foi compartilhada com ela

Não reutilizar `POLICY.AVALIAR` da Fase 1 para evitar confundir:
- avaliação da própria Policy;
- avaliação de Policy recebida por grant bilateral.

---

## 8. Contratos Públicos Propostos

### 8.1 Criar grant

```text
POST /v1/rule-governance/policies/{policy_id}/shares
```

**Request mínimo:**
```json
{
  "beneficiary_organization_id": "uuid",
  "access_purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
  "valid_until": "2026-12-31T23:59:59Z",
  "field_scope_profile": "CONTRATO_MINIMO"
}
```

**Response mínima:**
```json
{
  "grant_id": "uuid",
  "policy_id": "uuid",
  "owner_organization_id": "uuid",
  "beneficiary_organization_id": "uuid",
  "access_purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
  "field_scope_profile": "CONTRATO_MINIMO",
  "status": "ATIVO",
  "valid_from": "2026-08-19T...",
  "valid_until": "2026-12-31T..."
}
```

### 8.2 Revogar grant

```text
POST /v1/rule-governance/policies/{policy_id}/shares/{grant_id}/revoke
```

**Request:**
```json
{
  "revocation_reason": "relacao comercial encerrada"
}
```

### 8.3 Ler Policy Compartilhada

```text
GET /v1/rule-governance/shared-policies/{policy_id}
```

Resolvida pelo contexto do beneficiário + grant válido.

**Response (Policy compartilhada):**
```json
{
  "policy_id": "uuid",
  "code": "politica-comprador-fornecedor",
  "version": 1,
  "origin": "CONTRACT",
  "rules": [
    {
      "rule_id": "uuid",
      "code": "criterio-1",
      "conditions": [...],
      "justification": "..."
    }
  ],
  "grant_id": "uuid",
  "owner_organization_id": "uuid"
}
```

### 8.4 Avaliar Policy Compartilhada

```text
POST /v1/rule-governance/shared-policies/{policy_id}/evaluate
```

**Request mínimo:**
```json
{
  "subject_type": "animal",
  "subject_id": "uuid",
  "purpose": "autoavaliacao-contratual",
  "reference_time": "2026-08-19T..."
}
```

**Response mínima:**
```json
{
  "evaluation_id": "uuid",
  "policy_id": "uuid",
  "policy_version": 1,
  "origin": "CONTRACT",
  "owner_organization_id": "uuid",
  "requesting_organization_id": "uuid",
  "outcome": "CONDICOES_SATISFEITAS",
  "rule_results": [...],
  "missing_facts": ["livestock.weight"],
  "snapshot_hash": "sha256:...",
  "context_hash": "sha256:...",
  "evaluation_hash": "sha256:...",
  "evaluated_at": "2026-08-19T..."
}
```

### 8.5 Fora do Contrato desta Fase

- endpoint para comprador ler as avaliações do fornecedor
- endpoint de acknowledgment
- endpoint de composição com matriz regulatória

---

## 9. Regras de Autorização

### 9.1 Criação de Grant

Permitida somente quando:

- o solicitante atua no OrganizationContext owner da Policy;
- possui `POLICY.COMPARTILHAR`;
- a Policy existe no escopo do owner;
- a Policy é homogeneamente CONTRACT;
- beneficiário é uma Organization explícita (não wildcard);
- `valid_until` é futuro em relação ao momento da concessão.

Rejeita com `422 / POLICY_NAO_RECONHECIDA_COMO_CONTRATUAL` se Policy não for homogeneamente CONTRACT.

### 9.2 Leitura da Policy Compartilhada

Permitida somente quando:

- existe grant ativo;
- grant não expirou;
- o solicitante atua no OrganizationContext beneficiário;
- o FieldScope do grant cobre a leitura solicitada.

### 9.3 Avaliação da Policy Compartilhada

Permitida somente quando:

- existe grant ativo e válido;
- o solicitante atua no OrganizationContext beneficiário;
- possui `POLICY.AVALIAR_COMPARTILHADA`;
- o sujeito avaliado pertence ao beneficiário;
- a Policy continua homogeneamente CONTRACT.

Revalida homogeneidade antes de executar (defesa em profundidade, como Fase 1).

### 9.4 Revogação

Permitida somente ao owner da Policy com `POLICY.COMPARTILHAR`.

---

## 10. Negação Segura e Erros

Seguir DOMAIN.md P-198 e ARCHITECTURE.md.

### 10.1 Casos Mínimos

| Situação | Resposta Esperada | Notas |
|----------|------------------|-------|
| permission ausente no próprio contexto | 403 PERMISSAO_AUSENTE | uniforme |
| policy_id inexistente | 404 RECURSO_NAO_ENCONTRADO | uniforme |
| policy_id de outra Organization sem grant válido | 404 RECURSO_NAO_ENCONTRADO | uniforme, não revela propriedade |
| grant_id inexistente ou fora do escopo | 404 RECURSO_NAO_ENCONTRADO | uniforme |
| grant expirado/revogado | 403 ou 422, conforme contrato escolhido | sem revelar existência extra |
| Policy não homogênea CONTRACT | 409 CONFLITO_DE_DOMINIO ou 422 POLICY_NAO_RECONHECIDA_COMO_CONTRATUAL | estruturado |
| subject de outra Organization | 404 RECURSO_NAO_ENCONTRADO | uniforme |
| FieldScope insuficiente | 403 PERMISSAO_AUSENTE | ou 422 com detalhe mínimo |

O BUILD deve escolher um mapeamento consistente sem criar um terceiro sinal que revele "existe mas não é seu".

---

## 11. Verificação de Homogeneidade

### 11.1 Requisito

A BuyerPolicy compartilhável nesta fase deve ser homogeneamente CONTRACT.

### 11.2 Pontos de Defesa

- **na publicação/vinculação de Rule a Policy:** impedir mistura quando CONTRACT estiver envolvido;
- **na criação do grant:** recusar Policy não classificável como BuyerPolicy contratual;
- **na avaliação compartilhada:** revalidar a classificação antes de executar.

Isso evita:
- compartilhar Policy mista por engano;
- avaliar Policy contratual corrompida;
- depender de um único gate.

**Nota:** O gate de homogeneidade publicado em Fase 1 (`rule_governance_service.py:publish_rule_version`) já rejeita mistura quando `INTERNAL_POLICY` está envolvido. Fase 2 estende o mesmo padrão para `CONTRACT`.

---

## 12. Persistência e Migration

### 12.1 Expectativa

Esta fase provavelmente exige migration, porque Fase 1 não criou estrutura persistida para grants bilaterais.

### 12.2 Decisão a Confirmar no BUILD

Criar tabela owner do módulo de sharing BuyerPolicy com colunas do item 5.1.

Não improvisar usando:
- colunas em Policy;
- JSON solto;
- reaproveitamento informal de estrutura de auditoria;
- cache/Valkey como autoridade.

---

## 13. Auditoria Mínima Obrigatória

Registrar, no mínimo:

- quem concedeu o grant (User/Subject)
- em nome de qual Organization (owner)
- para qual Organization (beneficiary)
- qual Policy foi compartilhada
- qual AccessPurpose
- qual FieldScope
- validade (valid_from, valid_until)
- criação (created_at, created_by)
- revogação (revoked_at, revoked_by, revocation_reason)
- tentativa de avaliação relevante (beneficiary, subject_type, subject_id, outcome)
- negação relevante (beneficiary, motivo, 403/404/422)

Sem copiar payload bruto de facts ou evidências.

---

## 14. Testes Mínimos para BUILD

1. Criar grant válido para Policy CONTRACT homogênea → sucesso.
2. Tentar criar grant para Policy INTERNAL_POLICY → rejeitado com 422.
3. Tentar criar grant para Policy heterogênea → rejeitado com 422.
4. Beneficiário lê Policy compartilhada com grant válido → sucesso.
5. Terceiro sem grant tenta ler → 404 uniforme.
6. Beneficiário com grant expirado tenta ler → negação segura (403 ou 404).
7. Beneficiário avalia Policy compartilhada sobre subject próprio → sucesso.
8. Beneficiário tenta avaliar subject de outra Organization → 404 uniforme.
9. Buyer não ganha leitura de facts brutos do fornecedor por essa trilha.
10. Revogar grant impede nova leitura e nova avaliação.
11. Avaliação compartilhada não aparece na matriz regulatória.
12. Fase 1 continua intacta: `POLICY.AVALIAR` para própria Policy segue funcionando sem grant.

---

## 15. Validação Manual

Criar roteiro em `apps/validacao` cobrindo:

1. comprador cria Policy CONTRACT;
2. comprador concede grant a fornecedor A;
3. fornecedor A consulta Policy compartilhada;
4. fornecedor A avalia animal/lote próprio;
5. fornecedor B tenta acessar e recebe negação segura;
6. comprador revoga grant;
7. fornecedor A perde acesso e não consegue reavaliar;
8. trilha regulatória permanece separada.

O roteiro deve mostrar request e response de cada passo e não depender de copiar IDs manualmente.

---

## 16. Riscos Principais

| Risco | Mitigação |
|-------|-----------|
| grant amplo demais expor informação desnecessária | FieldScope mínimo e testes negativos |
| confusão entre fase contratual e regulatória | origem CONTRACT explícita + não-interferência com matriz |
| buyer ganhar acesso indireto a dados do fornecedor | contrato sem leitura de resultado/facts pelo buyer nesta fase |
| grants residuais sem expiração clara | valid_until obrigatório |
| Policy atualizada alterar silenciosamente grant ativo | BUILD deve decidir se grant ancora Policy/version ou Policy corrente |

---

## 17. Decisões Necessárias Antes do BUILD

Confirmar:

1. **Permissions novas:**
   - `POLICY.COMPARTILHAR`
   - `POLICY.COMPARTILHAMENTO_LER`
   - `POLICY.AVALIAR_COMPARTILHADA`

2. **Endpoints:**
   - `POST /v1/rule-governance/policies/{policy_id}/shares`
   - `POST /v1/rule-governance/policies/{policy_id}/shares/{grant_id}/revoke`
   - `GET /v1/rule-governance/shared-policies/{policy_id}`
   - `POST /v1/rule-governance/shared-policies/{policy_id}/evaluate`

3. **Grant anchor:**
   - grant ancora Policy como recurso lógico + versão publicada vigente no momento da concessão;
   - mudança de Policy não afeta grants já emitidos (novo grant necessário se critério mudar).

4. **valid_until obrigatório** para todos os grants.

5. **Resultado não será lido pelo comprador** nesta fase (Fase 3).

---

## 18. Portão para Autorizar BUILD

Este PLAN só deve liberar BUILD quando houver decisão explícita sobre:

- ✓ permissions novas;
- ✓ contratos HTTP novos;
- ✓ migration do grant bilateral;
- ✓ anchor do grant em Policy vs. Policy+versão;
- ✓ AccessPurpose canônico;
- ✓ FieldScope mínimo;
- ✓ valid_until obrigatório.

Sem essas decisões, o BUILD ficaria adivinhando justamente as partes RED da fase.

---

## 19. Não-Implementação

Este documento não cria API, migration, permission, tabela, teste ou UI. Ele apenas define o desenho técnico mínimo da Fase 2 para que a implementação futura fique disciplinada, auditável e contida.

