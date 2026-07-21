# Plano de Implementação — Titan Greenfield

**Versão:** 3.0  
**Estratégia:** reconstrução iniciada do zero  
**Arquitetura:** Titan Core + verticais independentes  
**Primeira vertical:** Titan Livestock

## 1. Objetivo

Construir o Titan desde o primeiro commit como uma plataforma de decisões auditáveis, sem carregar acoplamentos, estruturas ou limitações da implementação anterior.

O projeto anterior será usado somente como:

- catálogo de requisitos;
- referência de casos de uso;
- fonte de cenários de teste;
- fonte de regras de negócio;
- base para fixtures e dados de demonstração.

Não haverá obrigação de reaproveitar código, banco, contratos ou estrutura interna.

---

## 2. Arquitetura-alvo

```text
Titan Platform
│
├── Titan Core
│   ├── Identity & Access
│   ├── Audit
│   ├── Integrity
│   ├── Evidence
│   ├── Provenance
│   ├── Policies
│   ├── Rules
│   ├── Evaluations
│   ├── Decisions
│   ├── Dossiers
│   ├── Recall
│   ├── Outbox
│   └── Synchronization
│
├── Titan Livestock
│   ├── Properties
│   ├── Animals
│   ├── Lots
│   ├── Movements
│   ├── Veterinary
│   ├── Pharmaceuticals
│   ├── GTA
│   ├── SISBOV
│   ├── RFID
│   └── Livestock Compliance
│
└── Futuras verticais
    ├── Titan Parts
    ├── Titan Food
    ├── Titan Defense
    └── Titan Aviation
```

O Core nunca conhecerá termos como animal, GTA, peça, viatura ou alimento.

---

## 3. Princípios

1. **Greenfield real:** nenhum compromisso com estruturas antigas.
2. **Monólito modular:** sem microserviços no início.
3. **Dependência unidirecional:** verticais dependem do Core; o Core nunca depende das verticais.
4. **Ownership de dados:** cada módulo controla suas próprias tabelas ou coleções.
5. **Eventos imutáveis:** correção gera novo evento; não altera o anterior.
6. **Reprodutibilidade:** toda decisão registra regras, versões, fatos, evidências e hash.
7. **Integridade ≠ veracidade:** o sistema diferencia dado declarado, documentado, verificado e oficial.
8. **Offline by design:** operação desconectada será considerada desde a arquitetura.
9. **Contratos estáveis:** integração entre módulos somente por interfaces públicas.
10. **Segunda vertical como prova:** Titan Parts validará a generalização do Core.

---

## 4. Estrutura inicial do repositório

```text
titan/
├── apps/
│   ├── api/
│   ├── web/
│   └── worker/
├── packages/
│   ├── shared-kernel/
│   ├── core-contracts/
│   ├── core-domain/
│   ├── core-application/
│   ├── core-infrastructure/
│   ├── livestock-domain/
│   ├── livestock-application/
│   ├── livestock-infrastructure/
│   ├── ui-components/
│   └── testing/
├── docs/
│   ├── architecture/
│   ├── adr/
│   ├── domain/
│   ├── api/
│   └── operations/
├── infra/
└── tests/
```

---

# 5. Fases

## Fase 0 — Fundação técnica

**Duração:** 1 semana

### Tarefas

- escolher stack;
- escolher banco;
- definir estratégia de IDs;
- definir datas e timezone;
- criar monorepo;
- configurar lint, formatter e typecheck;
- configurar testes;
- configurar CI;
- configurar Docker;
- criar ambientes;
- definir migrations;
- definir observabilidade;
- definir secrets;
- escrever ADRs.

### ADRs mínimos

- monólito modular;
- escolha do banco;
- modelo de eventos;
- isolamento multi-tenant;
- versionamento de regras;
- estratégia de integridade;
- estratégia offline;
- contratos públicos.

### Aceite

- projeto sobe por comando documentado;
- CI executa testes, lint e typecheck;
- ambiente local reproduzível;
- health check funcional;
- decisões arquiteturais registradas.

---

## Fase 1 — Shared Kernel e contratos

**Duração:** 1 semana

### Criar

- IDs tipados;
- objetos de valor;
- erros padronizados;
- paginação;
- relógio injetável;
- gerador de IDs;
- serialização canônica;
- referências genéricas.

### Contratos principais

```ts
interface SubjectReference {
  tenantId: string;
  type: string;
  id: string;
  label?: string;
}

interface ActorReference {
  type: "USER" | "SYSTEM" | "INTEGRATION";
  id: string;
  displayName?: string;
}

interface DomainEvent<T = unknown> {
  id: string;
  tenantId: string;
  aggregateType: string;
  aggregateId: string;
  eventType: string;
  eventVersion: number;
  occurredAt: string;
  recordedAt: string;
  actor: ActorReference;
  payload: T;
  correlationId?: string;
  causationId?: string;
}
```

### Aceite

- nenhum termo pecuário;
- serialização determinística;
- contratos validados;
- testes de compatibilidade.

---

## Fase 2 — Identity & Access

**Duração:** 1 a 2 semanas

### Entidades

- User;
- Organization;
- Membership;
- Role;
- Permission;
- Session;
- ApiCredential.

### Tarefas

- autenticação;
- recuperação de acesso;
- organização ativa;
- RBAC;
- isolamento por tenant;
- logs de segurança;
- proteção de rotas.

### Aceite

- nenhum usuário acessa outro tenant;
- toda operação possui organização;
- permissões são verificadas na aplicação;
- tentativas de violação são testadas.

---

## Fase 3 — Audit & Integrity Core

**Duração:** 1 a 2 semanas

### Componentes

- AuditEvent;
- AggregateSequence;
- CanonicalSerializer;
- HashChain;
- IntegrityVerifier;
- CorrectionReference.

### Tarefas

- append-only;
- sequência por agregado;
- hash anterior e atual;
- algoritmo versionado;
- verificação de cadeia;
- correção sem edição;
- consulta por agregado e correlação.

### Aceite

- adulteração é detectada;
- cadeia pode ser recalculada;
- evento antigo não é alterado;
- correção referencia o original.

---

## Fase 4 — Idempotência, concorrência e outbox

**Duração:** 1 semana

### Componentes

- IdempotencyKey;
- OperationRecord;
- AggregateVersion;
- ConflictResult;
- OutboxMessage;
- RetryPolicy;
- DeadLetter.

### Aceite

- replay não duplica;
- versão desatualizada gera conflito;
- outbox não perde eventos;
- retries são idempotentes;
- falhas permanentes são isoladas.

---

## Fase 5 — Evidence & Provenance Core

**Duração:** 2 semanas

### Entidades

- Evidence;
- EvidenceSource;
- Provenance;
- Verification;
- Revocation;
- ValidityPeriod;
- AttachmentReference.

### Níveis de confiança

```text
INFORMED
DECLARED
DOCUMENTED
SIGNED
VERIFIED
CORROBORATED
OFFICIAL
```

### Aceite

- evidência pode expirar;
- pode ser revogada;
- histórico é preservado;
- anexo pode ser verificado;
- confiança é separada de integridade.

---

## Fase 6 — Policies & Rules Core

**Duração:** 2 semanas

### Entidades

- Policy;
- PolicyVersion;
- RuleDefinition;
- RuleVersion;
- RuleApplicability;
- RuleResult;
- NormativeSource.

### Estados

```text
DRAFT
PUBLISHED
SUPERSEDED
REVOKED
```

### Contrato de resultado

```ts
interface RuleResult {
  ruleId: string;
  ruleVersion: string;
  status: "PASS" | "FAIL" | "PENDING" | "NOT_APPLICABLE";
  severity: "INFO" | "WARNING" | "BLOCKING";
  reason: string;
  affectedSubjects: SubjectReference[];
  evidence: EvidenceReference[];
  correctiveAction?: string;
  evaluatedAt: string;
}
```

### Aceite

- versão publicada é imutável;
- regra histórica permanece disponível;
- política seleciona regras por vigência;
- resultado é explicável;
- Core não acessa dados de vertical diretamente.

---

## Fase 7 — Evaluation & Decision Core

**Duração:** 2 semanas

### Fluxo

```text
Evaluation Request
        ↓
Subject Provider
        ↓
Fact Collection
        ↓
Evidence Resolution
        ↓
Policy Selection
        ↓
Rule Execution
        ↓
Aggregation
        ↓
Decision
        ↓
Immutable Snapshot
```

### Entidades

- EvaluationRequest;
- Evaluation;
- EvaluationSnapshot;
- Decision;
- CorrectiveAction;
- DecisionLifecycle.

### Aceite

- mesma entrada gera mesmo hash;
- fatos futuros não alteram avaliação passada;
- decisão possui justificativas;
- ações corretivas são identificadas;
- decisão pode ser reproduzida.

---

## Fase 8 — Dossier Core

**Duração:** 1 a 2 semanas

### Conteúdo

- sujeito;
- finalidade;
- política;
- regras;
- resultados;
- fatos;
- evidências;
- pendências;
- decisão;
- ações corretivas;
- versão do motor;
- versão do template;
- emissor;
- timestamps;
- hash;
- histórico.

### Aceite

- dossiê é congelado;
- JSON é estável;
- PDF representa o snapshot;
- hash é recalculável;
- template é fornecido pela vertical.

---

## Fase 9 — Titan Livestock básico

**Duração:** 2 a 3 semanas

### Módulos

- properties;
- animals;
- livestock-lots;
- movements;
- stays;
- veterinarians.

### Entidades

- RuralProperty;
- Animal;
- LivestockLot;
- LotMembership;
- AnimalMovement;
- PropertyStay;
- Veterinarian.

### Aceite

- animal possui identidade estável;
- histórico não é sobrescrito;
- movimentações geram permanências;
- composição do lote é temporal;
- tudo gera auditoria pelo Core.

---

## Fase 10 — Titan Livestock farmacológico

**Duração:** 2 semanas

### Entidades

- VeterinaryPrescription;
- Medication;
- MedicationBatch;
- TreatmentApplication;
- WithdrawalPeriod.

### Cenário obrigatório

```text
Animal tratado
    ↓
Carência ativa
    ↓
Animal entra em lote
    ↓
Lote avaliado
    ↓
REJECTED
    ↓
Animal removido
    ↓
Nova avaliação
    ↓
APPROVED
```

### Aceite

- cálculo determinístico;
- regra versionada;
- decisão identifica o animal causador;
- ação corretiva é sugerida;
- avaliações antiga e nova coexistem.

---

## Fase 11 — Titan Livestock documental

**Duração:** 2 semanas

### Escopo

- GTA;
- SISBOV sandbox;
- evidência documental;
- regras documentais;
- pendências.

### Aceite

- GTA cancelada não é apagada;
- documento expirado afeta avaliação;
- protocolo externo é idempotente;
- indisponibilidade externa gera pendência;
- documento aparece no dossiê.

---

## Fase 12 — RFID e operação offline

**Duração:** 2 a 3 semanas

### Componentes

- RFIDRead;
- Device;
- FieldOperation;
- OfflineOperation;
- SyncSession;
- ConflictResolution.

### Aceite

- leitura repetida não duplica;
- fila offline preserva ordem;
- conflitos são apresentados;
- sincronização é retomável;
- evento registra dispositivo e origem.

---

## Fase 13 — Dossiê Livestock v1

**Duração:** 1 semana

### Seções

- identificação;
- propriedade;
- composição;
- movimentações;
- permanências;
- farmacológico;
- GTA;
- SISBOV;
- evidências;
- regras;
- decisão;
- ações corretivas;
- integridade.

### Aceite

- PDF validado;
- JSON validado por schema;
- QR Code ou código de verificação;
- hash público recalculável;
- auditor entende a decisão sem acessar o banco.

---

## Fase 14 — Recall Core + Livestock

**Duração:** 2 semanas

### Core

- grafo de relações;
- propagação;
- janela temporal;
- caminhos;
- profundidade;
- decisões afetadas.

### Livestock

- animal;
- lote;
- propriedade;
- GTA;
- medicamento;
- lote de medicamento;
- destino.

### Aceite

- recall parte de medicamento ou animal;
- sujeitos afetados são identificados;
- caminho é explicável;
- decisões comprometidas são localizadas;
- exercício fica auditado.

---

## Fase 15 — Titan Parts POC

**Duração:** 2 semanas

### Escopo

- Part;
- ManufacturingBatch;
- Supplier;
- Certificate;
- Inspection;
- Equipment;
- Installation.

### Cenário

```text
Peça
    ↓
Certificado
    ↓
Inspeção
    ↓
Instalação
    ↓
Política
    ↓
LIBERADA / BLOQUEADA
    ↓
Dossiê
```

### Regra de validação

A vertical pode criar:

- entidades;
- providers;
- adaptadores;
- regras;
- templates;
- integrações.

Não pode exigir:

- campos específicos no Core;
- lógica industrial no Core;
- dependência do Core para a vertical;
- mudanças destrutivas nos contratos universais.

---

# 6. Sprints recomendadas

| Sprint | Entrega |
|---|---|
| 1 | Fundação, monorepo, CI, Docker e ADRs |
| 2 | Identity & Access |
| 3 | Audit & Integrity |
| 4 | Idempotência, concorrência e outbox |
| 5 | Evidence & Provenance |
| 6 | Policies & Rules |
| 7 | Evaluation & Decision |
| 8 | Dossier Core |
| 9 | Livestock básico |
| 10 | Farmacológico |
| 11 | Documental |
| 12 | Offline e RFID |
| 13 | Dossiê Livestock e cenário completo |
| 14 | Recall |
| 15 | Titan Parts POC |

---

# 7. Uso do projeto anterior

O sistema anterior será tratado como referência, não como base técnica.

## Aproveitar

- requisitos;
- casos de uso;
- regras;
- estados;
- permissões;
- cenários offline;
- integrações;
- exemplos de dossiê.

## Não reaproveitar automaticamente

- estrutura de banco;
- nomes internos;
- acoplamentos;
- contratos;
- arquitetura;
- migrations;
- hashes históricos;
- APIs internas.

## Dados antigos

Como não há usuários ativos dependentes, os dados podem ser:

- descartados;
- usados apenas em desenvolvimento;
- convertidos por script opcional;
- preservados como histórico.

Não criar migração de produção sem necessidade real.

---

# 8. Requisitos não funcionais

## Segurança

- isolamento multi-tenant;
- menor privilégio;
- criptografia em trânsito;
- secrets externos;
- logs de segurança;
- rate limiting;
- validação de entrada.

## Confiabilidade

- idempotência;
- retries;
- transações;
- concorrência otimista;
- backup;
- recuperação;
- health checks.

## Auditabilidade

- append-only;
- hash;
- autoria;
- correlação;
- versionamento;
- timestamp;
- histórico.

## Observabilidade

- logs estruturados;
- métricas;
- tracing;
- alertas;
- dashboard operacional.

## Metas iniciais

- avaliação unitária abaixo de 1 segundo;
- avaliação de lote abaixo de 5 segundos;
- dossiê abaixo de 10 segundos;
- paginação obrigatória;
- sincronização retomável.

---

# 9. Testes obrigatórios

## Unitários

- objetos de valor;
- serialização;
- regras;
- agregação;
- cálculos farmacológicos.

## Contrato

- schemas;
- providers;
- adaptadores;
- compatibilidade.

## Integração

- banco;
- transações;
- outbox;
- anexos;
- autenticação.

## Arquitetura

- Core não depende de verticais;
- módulo não acessa dados de outro módulo;
- dependências são acíclicas;
- infraestrutura não contém regra de negócio.

## Segurança

- isolamento por tenant;
- escalada de privilégio;
- acesso sem organização;
- adulteração de token;
- enumeração de IDs.

## Integridade

- alteração de evento;
- quebra de cadeia;
- snapshot divergente;
- anexo adulterado.

## Concorrência

- atualizações simultâneas;
- replay;
- emissão simultânea;
- duplicação de outbox.

## E2E

- cenário farmacológico;
- GTA cancelada;
- operação offline;
- reavaliação;
- dossiê;
- recall.

---

# 10. Definição de pronto

Uma funcionalidade só está pronta quando:

- possui modelo de domínio;
- possui contrato;
- possui validação;
- possui testes;
- respeita tenant;
- respeita permissões;
- gera auditoria;
- trata concorrência;
- trata idempotência quando aplicável;
- possui documentação;
- possui observabilidade;
- não viola fronteiras;
- aparece no dossiê quando relevante.

Uma regra só está pronta quando:

- possui código;
- possui versão;
- possui vigência;
- possui fonte;
- possui severidade;
- possui justificativa;
- declara evidências requeridas;
- declara ação corretiva;
- possui testes de borda.

---

# 11. Fora do escopo inicial

Antes do Titan Livestock v1, não implementar:

- microserviços;
- blockchain;
- IA decisória;
- marketplace;
- múltiplas verticais completas;
- aplicativo nativo;
- hardware proprietário;
- assinatura ICP-Brasil;
- integrações oficiais sem sandbox;
- internacionalização completa.

---

# 12. Marcos

## Marco 1 — Core operacional

Fases 0 a 8 concluídas.

## Marco 2 — Titan Livestock v1

Fases 9 a 13 concluídas.

## Marco 3 — Recall

Fase 14 concluída.

## Marco 4 — Plataforma comprovada

Fase 15 concluída com segunda vertical funcionando sem contaminar o Core.

---

# 13. Critério final de sucesso

```text
Fato operacional
    ↓
Evento auditável
    ↓
Evidência e proveniência
    ↓
Política versionada
    ↓
Regra versionada
    ↓
Avaliação reproduzível
    ↓
Decisão explicável
    ↓
Ação corretiva
    ↓
Reavaliação
    ↓
Dossiê verificável
```

A reconstrução estará validada quando esse fluxo funcionar no Titan Livestock e puder ser reutilizado no Titan Parts sem alteração indevida do Titan Core.

> **Titan Core transforma fatos, evidências e políticas em decisões auditáveis.**

> **Titan Livestock aplica esse núcleo à cadeia pecuária.**
