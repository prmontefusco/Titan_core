# CORE_REUSE_ASSESSMENT — Reutilização do Titan Core pela vertical Titan Asset & Sustainment

**Versão:** 1.0
**Status:** Proposta para revisão (nenhum código movido)
**Data:** 10 de setembro de 2026
**Escopo:** Auditoria do Titan Core existente e avaliação de sua reutilização por uma segunda vertical, sem fork e sem contaminação de conceitos de Asset no Core.

> Este documento é a Fase 1 (auditoria) e alimenta os demais artefatos em
> `docs/asset/`. Ele **não autoriza** mover pacotes, criar migrations
> ou implementar Titan Asset. Ver `STOP CONDITION` no final.

---

## 1. Estado atual encontrado

### 1.1 Forma do repositório

| Fato | Evidência |
|---|---|
| Monorepo, monólito modular, Python 3.12, `uv` (`package = false`), sem workspace de subpacotes | `pyproject.toml`, `uv.lock` |
| Executáveis isolados em `apps/` (`api`, `worker`, `web`, `bootstrap`, `seed`, `demo`, `validacao`) | `apps/` |
| Capacidades reutilizáveis em `packages/` | `packages/` |
| Direção de dependência já decidida e documentada: Domain ← Application ← Infrastructure/Presentation; vertical → Core; Core nunca → vertical | `ARCHITECTURE.md` §"Direção das dependências", ADR-0001 |
| Fronteiras já protegidas por teste arquitetural executável | `tests/architecture/test_dependency_boundaries.py` |

### 1.2 Pacotes do Titan Core

| Package | Arquivos `.py` | LOC aprox. | Papel |
|---|---:|---:|---|
| `packages/shared_kernel` | 5 | 321 | Identificadores opacos tipados, `UniversalReference`, primitivas temporais, serialização canônica `titan-json-v1` |
| `packages/core_domain` | 32 | 6 739 | Invariantes e contratos universais: identidade, autorização, política, regra, avaliação, decisão, evidência, fato, proveniência, verificação, dossiê, correção, normativo, relações, projeções, sincronização, eventos, crypto |
| `packages/core_application` | 37 | 6 066 | Casos de uso e portas: outbox, inbox, idempotência, concorrência otimista, timestamping, checkpoint de integridade, `event_log`, `document_service`, serviços de policy/rule/evaluation/decision/dossier/evidence/fact/relation/correction/synchronization |
| `packages/core_infrastructure` | 131 | 21 109 | Adapters: persistência PostgreSQL/PostGIS, migrations Alembic, RabbitMQ, storage, rate limiter, crypto, redação de log, PDF, autenticação |
| `packages/core_integrity` | 3 | 628 | Cadeia de hash de eventos e checkpoints de integridade |

`core_domain/__init__.py` (282 linhas) e `core_application/__init__.py` (238 linhas) reexportam
uma **superfície pública curada** (contratos + portas). Essa é hoje a fronteira de
reutilização que uma vertical consome. Os pacotes `core_contracts/` e `testing/`
aparecem na árvore aspiracional de `ARCHITECTURE.md` mas **não existem**.

### 1.3 Vertical existente (Livestock)

| Package | Arquivos `.py` | LOC aprox. |
|---|---:|---:|
| `packages/livestock_domain` | 28 | 4 093 |
| `packages/livestock_application` | 66 | 20 467 |
| `packages/livestock_infrastructure` | 38 | 7 912 |

### 1.4 Superfície real de reutilização Livestock → Core

Contagem de `import` de `livestock_*` para `packages.core_*` / `packages.shared_kernel`
(agrupado por módulo de origem):

```
115  from packages.shared_kernel            (+ 49 temporal, + 2 serialization)
 26  from packages.core_infrastructure.persistence.events
 16  from packages.core_domain.evidence
 10  from packages.core_domain.facts
  7  from packages.core_domain.evaluation
  7  from packages.core_domain.decision
  6  from packages.core_domain.rule
  6  from packages.core_application.event_log
  5  from packages.core_domain.policy
  4  from packages.core_infrastructure.persistence.organizations
  4  from packages.core_domain.policy_sharing
  3  from packages.core_domain.events / decision_governance
  3  from packages.core_application.relation_service / idempotency / fact_service
  2  from packages.core_domain.relations / normative / dossier
  2  from packages.core_application.evaluation_service / decision_service / decision_governance_service
  1  from packages.core_infrastructure.persistence.evaluation / decision
  1  from packages.core_domain.rule_governance / organization_context / decision_authority
  1  from packages.core_application.policy_temporal_selection / dossier_service / dossier_pdf_template
```

Leitura: a vertical reutiliza **o núcleo de confiança inteiro** (evidência, fato,
política, regra, avaliação, decisão, governança de decisão, dossiê, relações,
normativo) através de `core_domain` + `core_application`, e usa `shared_kernel`
de forma pervasiva. Isso é reutilização saudável e prova que o Core **já é**
reutilizável na prática.

---

## 2. O Core está limpo de conceitos de vertical?

**Sim.** Busca por vocabulário de Livestock (`animal`, `cattle`, `bovine`,
`sisbov`, `veterinar`, `rebanho`, `sanitary`, `medication`, `pasture`, `herd`,
`pecu`) em `core_domain`, `core_application`, `core_integrity`, `shared_kernel`:
**zero ocorrências** em código (uma correspondência espúria em comentário).

Busca por `import ... livestock` nos mesmos pacotes: **zero**.

`core_infrastructure` não importa `livestock` em nenhum módulo **exceto** o
`env.py` do Alembic (exceção documentada — ver §3.1). As migrations de Livestock
que vivem sob `core_infrastructure` carimbam `titan.module_owner=titan_livestock`
no comentário da tabela, ou seja, o *ownership lógico* já está correto mesmo onde
o *arquivo físico* está no lugar errado.

**Conclusão:** o Core não tem vazamento conceitual. O risco para a segunda
vertical não é "o Core conhece Livestock"; é um pequeno conjunto de pontos de
**composição** e **infraestrutura de migrations** que assumem "há exatamente uma
vertical".

---

## 3. Problemas arquiteturais detectados

Ordenados por impacto sobre "adicionar uma segunda vertical sem duplicar o Core".

### 3.1 — BLOQUEADOR — História de migrations Alembic única e compartilhada

- Todas as migrations vivem em
  `packages/core_infrastructure/persistence/migrations/versions/` numa **única
  linha linear** (`0001`…`0086`). As migrations `0033`–`0075+` são de Livestock.
- `packages/core_infrastructure/persistence/migrations/env.py` **importa
  explicitamente** ~30 tabelas de `packages.livestock_infrastructure.persistence`
  para registrá-las na `MetaData` compartilhada; sem isso o `alembic check`
  proporia remover as tabelas da vertical.
- O teste de fronteira `test_dependency_boundaries.py` carrega uma **exceção
  nomeada** (`MIGRATIONS_COMPOSITION_ROOT`) só para esse arquivo, e o próprio
  comentário do teste diz: *"O caminho mais limpo a prazo é a vertical possuir o
  próprio ambiente de migrations; enquanto elas viverem sob o Core, esta exceção
  é necessária."*

**Efeito sobre Asset:** sem mudança, adicionar Asset significa (a) importar
`asset_infrastructure` no `env.py` do Core (ampliando a exceção para N verticais)
e (b) intercalar as migrations de Asset na mesma sequência linear de Core +
Livestock. Isso acopla o ciclo de release das três coisas e impede
versionar/reverter uma vertical isoladamente.

**Ação recomendada:** cada vertical possui o próprio ambiente Alembic
(`version_locations` múltiplo ou `env.py` por vertical), com a `MetaData`
continuando compartilhada apenas para resolução de FK. Fazer isso **primeiro para
Livestock**, de forma comportamentalmente neutra e verificável por diff de
schema, para que Asset já nasça no modelo correto. Detalhes e alternativa de
menor risco em `ASSET_VERTICAL_BOOTSTRAP_PLAN.md` §Passo 2.

### 3.2 — ESTRUTURAL — `MetaData` SQLAlchemy única para Core + verticais

- `packages/livestock_infrastructure/persistence/metadata.py` faz
  `livestock_metadata = organization_metadata` (a `MetaData` do Core).
- Justificativa correta: tabelas da vertical vivem no schema `core_audit` e têm
  FK para `core_identity.organizations`; o SQLAlchemy só resolve FK com as duas
  tabelas na mesma `MetaData` (ver ADR-0077).

**Efeito sobre Asset:** Asset deve seguir o mesmo padrão (reusar a `MetaData` do
Core). Consequência aceitável, mas precisa ser **decisão explícita**: nenhuma
vertical pode ter schema/banco fisicamente independente sem quebrar a resolução
de FK; e o ambiente de migrations de cada vertical precisa importar as tabelas do
Core para enxergar `organizations`. Não é defeito — é o preço do banco único do
monólito modular (ADR-0001 deixou explícito que a estratégia física de schemas é
decidida junto à persistência).

### 3.3 — ATRITO — `apps/api/` plano, com verticais misturadas

- `apps/api/` tem, no mesmo diretório plano: adapters de Core
  (`authentication.py`, `policy_governance.py`, `verification.py`, `problem.py`,
  `pagination.py`, `configuration.py`, `main.py`) e **14 módulos
  `livestock_*.py`**.
- `apps/api/main.py` importa **cada router de Livestock por nome** e os inclui um
  a um. Não há subpacote por vertical nem registry de routers.
- Existe teste (`test_core_named_http_adapters_do_not_import_livestock`) que
  protege apenas os arquivos `core_*.py` de importar Livestock.

**Efeito sobre Asset:** Asset adiciona `asset_*.py` como irmãos e mais edições
manuais em `main.py`. Funciona (apps compõem — ADR-0001), mas a ergonomia
degrada a cada vertical e o `main.py` vira ponto de conflito.

**Ação recomendada:** convenção `apps/api/<vertical>/` + um registry de routers
que `main.py` itera. Mudança apenas de import/organização; rotas idênticas.

### 3.4 — ATRITO — `apps/worker/` mono-vertical

- `apps/worker/livestock_handlers.py`; `WorkerHandlerRegistry.resolve(envelope)`
  **ignora o envelope** e devolve sempre o handler de Livestock.

**Efeito sobre Asset:** não há despacho por tipo de mensagem/vertical. Asset
precisa de um registry real keyed por `message_type`/vertical.

**Ação recomendada:** transformar `resolve()` em despacho real; comportamento do
handler de Livestock inalterado.

### 3.5 — OBSERVAÇÃO — Verticais dependem de `core_infrastructure.persistence.*`

- ~33 imports de `livestock_*` para `packages.core_infrastructure.persistence`
  (`events`, `organizations`, `evaluation`, `decision`).
- Parte é legítima e inevitável: porta de persistência de eventos
  (`DomainEventRepository`, `StoredDomainEvent`), `MetaData` compartilhada, alvos
  de FK. Mas é dependência de **infraestrutura interna do Core**, não apenas dos
  contratos de `core_domain`/`core_application`.
- Não há `core_contracts`. O "público" é o que os `__init__.py` reexportam,
  implicitamente.

**Efeito sobre Asset:** Asset herda o mesmo acoplamento. Com **dois** consumidores,
uma mudança acidental em `core_infrastructure.persistence.events` quebra duas
verticais em vez de uma.

**Ação recomendada (leve, não bloqueante):** declarar `__all__` e um teste que
sinalize alteração da superfície pública de `core_domain`/`core_application`
(e, se surgir necessidade concreta, um `core_contracts` fino para a porta de
eventos). Não extrair antecipadamente (ADR-0001 §"extração deve responder a
necessidade concreta").

### 3.6 — EXPECTATIVA — Core não tem motor de workflow nem notificações

- Busca por `workflow`/`notification` em `core_domain`/`core_application`:
  **zero**. Livestock constrói `*_workflow.py` ad hoc na própria camada de
  aplicação (`market_supply_workflow.py` etc.).
- O Core oferece primitivas de **decisão/avaliação/evento/outbox**, não uma
  máquina de estados genérica nem serviço de notificação.

**Efeito sobre Asset:** o ciclo de vida de Work Order, o estado de Material
Reservation e o agendamento de Maintenance são **workflow de domínio da
vertical** e vivem em `asset_application`. Isso é correto — mas precisa ser
expectativa registrada para ninguém tentar empurrar "workflow de Work Order"
para dentro do Core.

### 3.7 — OBSERVAÇÃO — Abstrações de integração vivem na vertical

- `livestock_application/erp_contract.py`, `erp_inbox.py`, `erp_outbox.py`,
  `territorial_adapter.py`. O Core fornece a mecânica de outbox/inbox; o
  **formato do contrato de integração** é propriedade da vertical.

**Efeito sobre Asset:** a integração com ERP/PLM/logística de Asset será
`asset_application`. Consistente. Risco: duas verticais reinventando andaime
semelhante de adapter de ERP. Não extrair antes de haver necessidade comprovada
nas duas.

### 3.8 — FORA DE ESCOPO (backend) — `apps/web/` é app único acoplado a `entityKinds`

- `apps/web/src/entityKinds.ts` e páginas por conceito de Livestock. Não bloqueia
  o backend; a UI de uma segunda vertical precisa de plano próprio (árvore de
  rotas separada ou app separado). Registrado, não tratado aqui.

---

## 4. Pontos que **não** são problema (evitar over-engineering)

| Item | Por que está OK |
|---|---|
| Core sem `core_contracts` físico | `__init__.py` curado já funciona como contrato; segundo consumidor só aumenta o valor de congelá-lo, não exige pacote novo |
| Banco único / schema `core_audit` compartilhado | Decisão consciente do monólito modular (ADR-0001, ADR-0003); RLS por Organization é a fronteira de isolamento, não o schema |
| Vertical depender de `core_application` services | Esperado e desejado — é a superfície de reutilização |
| Migrations com `titan.module_owner` no comentário | Ownership lógico já correto |
| `shared_kernel` pequeno (321 LOC) | Está no tamanho certo; **não** transformar em "common" |

---

## 5. Resumo executivo

1. **O Core já é reutilizável.** Livestock reutiliza o núcleo de confiança
   inteiro via contratos públicos; o Core não conhece nenhuma vertical.
2. **Não é preciso duplicar o Core** para adicionar Asset. Se fosse, a
   arquitetura estaria errada — e as evidências mostram que não está.
3. **O que falta** é generalizar três pontos que assumem "uma vertical":
   ambiente de migrations (bloqueador), composição HTTP (`apps/api`) e despacho
   do worker.
4. **A hipótese MONOREPO + MODULAR MONOLITH + SHARED CORE se confirma** contra o
   repositório real (detalhado em `REPOSITORY_STRUCTURE_PROPOSAL.md`).
5. **Primeiro passo recomendado:** aceitar estes documentos, depois generalizar o
   teste de fronteira arquitetural (`VERTICAL_PACKAGES`) — mudança só de teste,
   nenhum código de produção movido — provando as regras antes de a segunda
   vertical existir.

---

## STOP CONDITION

Ao concluir os seis documentos de `docs/asset/` + ADR:

**PARAR.** Não mover pacotes. Não implementar Titan Asset. Não criar migrations,
entidades ou endpoints. A implementação só ocorre após revisão e ACCEPT
explícito.

---

## Reconciliação com `PARALLEL_VERTICAL_SAFETY` (10/09/2026)

As conclusões deste assessment (Core limpo de vertical; reutilização já funciona; não é preciso duplicar o
Core) permanecem. Ajustes sob desenvolvimento paralelo e após a revisão adversarial:

- **§3.1 (BLOQUEADOR migrations).** A ação recomendada ("cada vertical possui o próprio ambiente Alembic")
  está incompleta: falta o filtro `include_object`/`include_name` por `titan.module_owner` (o `env.py` atual
  filtra por **schema**) e falta resolver `alembic upgrade head` → `heads`. Estratégia oficial: **Opção D → C**
  de `docs/architecture/MIGRATION_CONCURRENCY_STRATEGY.md`. A extração de Livestock é
  `BLOCKED_WHILE_LIVESTOCK_ACTIVE` — janela de integração coordenada com o Codex.
- **§3.3 / §3.4 (composição HTTP e worker).** Mover `apps/api/livestock_*.py` **agora** é editar arquivos que
  o Codex usa. Preferir mecanismo aditivo (`_registry.py` iterado por `main.py` sem mover os módulos de
  Livestock); a reorganização física fica para janela de integração. Asset nasce em `apps/api/asset/` sem
  depender disso.
- **§H1 (cadeia de integridade).** Confirmado: `event_integrity_table` é escopada por
  `record_owner_organization_id` (`events.py:247‑256`). Com duas verticais no mesmo tenant, os `append`
  interleavam e serializam. Classificado como **garantia global do Core**, não acoplamento vertical↔vertical
  (decisão F — `docs/architecture/DECISIONS_REQUIRED_PHASE0.md`); exige teste de concorrência.
- **§H2 (OM/Site).** A linha "Identidade/Organizations/`OrganizationContext`" da §1.4 assume que RLS por
  Organization basta para Asset. Isso **não foi testado** contra o escopo OM/Site da §18 da constituição.
  Questão diferida para a discovery de domínio (decisão G); nenhum conceito de Asset entra no Core.
- **§L2.** A auditoria de `operational_support.py` (pendente) é pré‑requisito da conclusão "Core limpo".
