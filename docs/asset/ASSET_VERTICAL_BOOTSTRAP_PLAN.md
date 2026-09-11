# ASSET_VERTICAL_BOOTSTRAP_PLAN — Estrutura mínima e sequência para iniciar Titan Asset & Sustainment

**Versão:** 1.0
**Status:** Proposta para revisão (Fases 6, 7 e 8)
**Data:** 10 de setembro de 2026

> **Nada aqui é autorização para implementar.** Este documento descreve a
> estrutura mínima e a ordem de passos. A implementação só começa após ACCEPT
> explícito, e o primeiro slice de Asset é uma **trilha separada** com seu
> próprio plano/ADR.

---

## 1. Regra de ouro (ADR-0001 §"Crescimento incremental")

> É proibido criar package para funcionalidade futura, duplicar camadas sem
> comportamento ou extrair abstração apenas por semelhança nominal. Diretórios,
> contratos e adaptadores surgem no primeiro passo que efetivamente os utiliza.

Portanto: **não** criar sete pacotes de bounded context vazios. Criar
`asset_domain`, `asset_application`, `asset_infrastructure` — e mesmo esses,
apenas quando o primeiro slice os exercer.

---

## 2. Bounded contexts candidatos — avaliação por invariante

O critério de fronteira **não** é o nome do subdomínio; é **onde um invariante
transacional deixa de valer**. Contexts que compartilham uma fronteira de
consistência forte começam juntos; só se separam quando um invariante precisa
cruzar uma transação.

| Context candidato | Invariante central (a validar com o negócio) | Fronteira de consistência | Decisão inicial |
|---|---|---|---|
| **Asset Management** | Um Asset (ex.: Vehicle) tem exatamente **uma** configuração-base vigente no instante T; transições de estado de ciclo de vida são monotônicas e auditáveis | Asset + baseline de configuração | Módulo `asset` (núcleo) |
| **Product Configuration** | A cadeia de supersessão de uma revisão de configuração é acíclica; faixas de efetividade não se sobrepõem para a mesma posição | Part/Config + efetividade | Junto de `asset` no início (mesma transação de "montar baseline") |
| **Parts Engineering** | Uma Part tem revisões com supersessão acíclica; intercambiabilidade é simétrica dentro de um grupo | Part + revisões | Junto de Product Configuration inicialmente |
| **Inventory** | `disponível = em_mãos − reservado ≥ 0` por (item, localização); nenhuma reserva referencia quantidade inexistente | StockItem + Reservation | Módulo `asset` (mesma transação que cria reserva a partir de demanda) **ou** módulo próprio se a reserva for assíncrona — decidir no slice |
| **Logistics** | Custódia de um item é uma cadeia sem buracos temporais; transferência de custódia preserva proveniência | Reutiliza `core_domain.provenance` / `relations` | **Não é módulo novo** no início — usa Core |
| **Maintenance** | Uma Work Order não fecha com tarefa obrigatória aberta; material reservado ≤ material demandado; toda transição registra evento | Work Order + tasks + demanda de material | Módulo `sustainment` |
| **SLI / Sustainment Contracts** | Uma Work Order resolve para **exatamente uma** linha de contrato ativa no instante do serviço; entitlement não excede cobertura contratada | Contract + coverage + entitlement | Módulo `sustainment` |

### 2.1 Corte inicial proposto: **dois módulos, não sete**

```
asset_*        Vehicle · Part · Configuration/Effectivity · Inventory · Reservation
sustainment_*  SLI Contract · Coverage/Entitlement · Work Order · Material demand
```

Justificativa:

- **Asset ↔ Sustainment** têm invariantes que se cruzam apenas por **referência**
  (uma Work Order aponta para um Vehicle e consome Inventory), não por
  transação compartilhada → fronteira limpa entre os dois módulos desde o
  início.
- **Dentro de `asset`**, Vehicle/Part/Config/Inventory compartilham a operação
  "montar e reservar" → começam no mesmo módulo; dividir em
  `asset_configuration` / `asset_inventory` só quando a reserva virar fluxo
  assíncrono próprio (evento + saga), se virar.
- **Logistics** e **cadeia de custódia** reutilizam `core_domain.provenance`,
  `relations` e eventos — nenhum módulo novo até haver invariante que o Core não
  cubra.

> Todos os prefixos acima (`asset_`, `sustainment_`) são **uma vertical só** do
> ponto de vista das regras de dependência: `sustainment_*` pode depender de
> `asset_*`? **A definir na ADR do slice.** Recomendação: tratar como *um único
> módulo vertical com dois pacotes internos* (`asset_*` e `sustainment_*` podem
> se referenciar), e a fronteira externa é "essa vertical ⊥ livestock". Se o
> negócio mostrar que Sustainment é vendável sem Asset Management, aí sim viram
> duas verticais irmãs com isolamento mútuo.

---

## 3. Reutilização do Core pela vertical Asset (mapa explícito)

Asset deve conseguir tudo abaixo **sem conhecer Livestock**:

| Necessidade de Asset | Fornecido pelo Core | Módulo(s) |
|---|---|---|
| Identidade, Organizations, Memberships, principal autenticado, `OrganizationContext` | `core_domain` (`AuthenticatedPrincipal`, `OrganizationContext`, `User`), `core_application.organization_context`, `core_infrastructure.organization_context`, `core_infrastructure.persistence.{organizations,users,external_identities}` | Core |
| Autorização por permissão (nunca por papel) | `core_domain.authorization` (`Permission`, `Role`); padrão em `livestock_application.authorization` | Core + padrão |
| Auditoria append-only, cadeia de hash, checkpoints | `core_application.event_log`, `core_infrastructure.persistence.events`, `core_integrity` | Core |
| Entrega assíncrona confiável (outbox/inbox) | `core_application` (outbox/inbox services), `core_infrastructure.persistence.{outbox,inbox}`, RabbitMQ adapter | Core |
| Idempotência e concorrência otimista | `core_application.idempotency`, `core_application.concurrency` (`OptimisticConcurrencyConflict`) | Core |
| Políticas, regras, avaliação, decisão explicável, governança de decisão | `core_domain.{policy,rule,evaluation,decision,decision_governance,normative}` + `core_application.{evaluation_service,decision_service,decision_governance_service,rule_service,policy_service}` | Core — p.ex. **entitlement de SLI** e **elegibilidade de garantia** como Evaluation→Decision |
| Documentos (certificados, ordens de serviço assinadas, laudos) | `core_application.document_service` (`AttachmentRepositoryPort`, `BlobStoragePort`) | Core (fronteira Mongo/GridFS ainda FUTURA — ver `ARCHITECTURE.md`) |
| Dossiê verificável / VerificationBundle com seção de vertical | `core_domain.dossier` (`VerticalSection`), ADR-0060 | Core — **dossiê de sustainment** para auditoria contratual |
| Proveniência e custódia (Part, lote, shipment) | `core_domain.provenance`, `core_domain.relations` | Core |
| Correção, supersessão, análise de impacto | `core_domain.corrections`, serviços de `core_application` | Core |
| Tempo válido vs. tempo de conhecimento (efetividade de contrato, de Part) | `shared_kernel.temporal` | Shared kernel |
| Referências estáveis entre capacidades, ids opacos | `shared_kernel.references.UniversalReference`, `shared_kernel.identifiers.TypedId` | Shared kernel |
| Serialização canônica para hash de payload | `shared_kernel.serialization` | Shared kernel |

**O que o Core NÃO fornece** (e Asset implementa na própria camada de aplicação):

- Máquina de estados / workflow de Work Order → `asset_application`
  (`work_order_service.py`), como Livestock faz com seus `*_workflow.py`.
- Cálculo de disponibilidade de estoque e política de reserva → `asset_domain` +
  `asset_application`.
- BOM / efetividade / intercambiabilidade → `asset_domain`.
- Contrato de integração com ERP/PLM/WMS → `asset_application` (padrão dos
  `erp_*` de Livestock, **sem** extrair abstração compartilhada antes de haver
  necessidade nas duas verticais).
- Notificações a oficinas/clientes → não há capacidade de notificação no Core;
  se necessário, começa como projeção + outbox na vertical.

---

## 4. Estrutura mínima do primeiro slice (Fase 7 — sem implementar)

Slice-alvo: **Vehicle + Part + Inventory + SLI Contract + Work Order + Material
Reservation + Workshop Dashboard**. Serve para **provar que os boundaries estão
certos**, não para entregar negócio.

```text
packages/asset_domain/
  __init__.py                  superfície pública (contratos, eventos)
  vehicle.py                   agregado Vehicle; referência à baseline de config; estado de ciclo de vida
  part.py                      Part, revisão, supersessão acíclica, efetividade
  inventory.py                 StockItem, quantidade por (item, localização); Reservation como VO
  sustainment_contract.py      SLIContract, linha de cobertura, resolução de entitlement no tempo
  work_order.py                WorkOrder, task, demanda de material; invariantes de fechamento
  events.py                    eventos de domínio da vertical (WorkOrderOpened, MaterialReserved, ...)

packages/asset_application/
  __init__.py
  authorization.py             constantes de Permission da vertical (espelha livestock_application.authorization)
  event_recorder.py            AssetOperationContext (espelha LivestockOperationContext)
  vehicle_service.py
  part_service.py
  inventory_service.py
  reservation_service.py        cria/consome Reservation a partir de demanda de Work Order; invariante disponível ≥ 0
  sustainment_contract_service.py
  work_order_service.py         workflow do ciclo de vida da Work Order
  workshop_dashboard.py         serviço de leitura / projeção (NÃO é bounded context novo)

packages/asset_infrastructure/
  __init__.py
  persistence/
    __init__.py
    metadata.py                = organization_metadata do Core (mesmo padrão de Livestock)
    migrations/                 ambiente Alembic PRÓPRIO da vertical desde o dia 1
      env.py
      versions/
    vehicle_repository.py
    part_repository.py
    inventory_repository.py
    reservation_repository.py
    sustainment_contract_repository.py
    work_order_repository.py
    dashboard_read_repository.py

apps/api/asset/
  __init__.py
  dependencies.py              raiz de composição HTTP (espelha apps/api/livestock_dependencies.py)
  vehicles.py                  routers
  parts.py
  inventory.py
  sustainment_contracts.py
  work_orders.py
  dashboard.py

apps/worker/asset_handlers.py  só se o slice tiver mensagem assíncrona
```

Notas de projeto:

- **Workshop Dashboard = read model.** Um serviço de projeção em
  `asset_application` + repositório de leitura em `asset_infrastructure`. Não
  cria agregado nem context.
- **Material Reservation** vive dentro de `asset` (mesma transação que a demanda
  da Work Order a origina, no corte inicial). Se o negócio exigir reserva
  assíncrona/cross-warehouse, promove-se a fluxo próprio com evento — e aí a
  fronteira `inventory` vs. `work order` fica evidente.
- **Entitlement de SLI** deve ser uma `Evaluation` → `Decision` do Core (regra
  governada + decisão explicável), não um `if` em `work_order_service`. É o teste
  mais forte de que o Core está sendo reutilizado de verdade.
- Cada migration da vertical carimba `titan.classification=...;titan.module_owner=titan_asset`.
- Tabelas no schema `core_audit`, FK para `core_identity.organizations`, RLS por
  Organization — idêntico ao padrão de Livestock (ADR-0002, ADR-0003, ADR-0077).

---

## 5. Sequência de passos (Fase 8 — pequenas etapas verificáveis)

**Preparação do terreno (trilha "reorganizar Core", sem tocar em negócio):**

| Passo | Conteúdo | Toca produção? | Critério de aceite |
|---|---|---|---|
| **0** | Estes 6 docs + ADR-0080. **STOP para ACCEPT.** | Não | Revisão aprovada |
| **1** | Generalizar `tests/architecture/test_dependency_boundaries.py`: `VERTICAL_PACKAGES`, parametrização, testes vertical⊥vertical, exceção de migrations generalizada | Só teste | `tests/architecture` verde; Livestock sem violação; guarda contra "nenhuma vertical checada" |
| **2** | `apps/api/livestock/` + `apps/api/core/` + `apps/api/_registry.py`; `main.py` itera o registry | Mecânico (imports) | `/openapi.json` idêntico; `tests/api` verde |
| **3** | `apps/worker/dispatch.py`: `resolve()` vira despacho real keyed por `message_type` | Sim, pequeno | Envelope real de Livestock processado igual; reconciliação inalterada |
| **4** | `__all__` + teste de estabilidade da superfície pública em `core_domain` e `core_application` | Só metadados | `mypy` + `pytest` verdes |
| **5** | *(opcional agora)* Extrair ambiente de migrations de Livestock para a própria vertical, com teste de diff de `pg_dump` | Sim, ALTO risco | `pg_dump --schema-only` idêntico; `tests/integration` (85) verde |

**Trilha "implementar Titan Asset" (só começa após Passo 1–4 e ACCEPT do slice):**

| Passo | Conteúdo | Pré-requisito |
|---|---|---|
| **A1** | ADR do primeiro slice + modelo de domínio (invariantes de Vehicle/Part/Inventory/Contract/WorkOrder validados com o negócio) | Passo 0 aceito |
| **A2** | `packages/asset_domain` — só as entidades/contratos do slice; testes de invariante | A1 |
| **A3** | `packages/asset_infrastructure/persistence/migrations` — ambiente próprio; tabelas do slice; RLS | A2 |
| **A4** | `packages/asset_application` — serviços do slice; entitlement via Evaluation→Decision do Core | A2, A3 |
| **A5** | `apps/api/asset/` — routers + `dependencies.py`; registrado no `_registry.py` | A4, Passo 2 |
| **A6** | Workshop Dashboard como projeção de leitura | A4 |
| **A7** | Suite de integração ponta a ponta do slice; verificação em `apps/validacao/asset/` | A5, A6 |

Cada passo A* é um PR; nenhum deles altera `core_*` (se precisar alterar, vira PR
próprio na trilha de Core, com ADR se mudar contrato).

---

## 6. Como saber que os boundaries estão certos (critério de sucesso da Fase 7)

1. `asset_*` não importa `livestock_*` — teste de fronteira verde.
2. `core_*` não ganhou nenhum arquivo, símbolo ou string por causa de Asset.
3. O entitlement de SLI é uma `Decision` explicável do Core, com `Evaluation` e
   `Rule` governada — não lógica ad hoc.
4. Auditoria, cadeia de integridade, outbox e dossiê de Asset funcionam usando
   só capacidades do Core.
5. Remover `packages/livestock_*` do checkout (hipoteticamente) não quebra a
   compilação de `packages/asset_*`.
6. O diff do slice não contém a palavra "livestock" em `packages/asset_*` nem em
   `apps/api/asset/`.

Se qualquer um falhar, a fronteira está errada — parar e rever antes de seguir.

---

## 7. Reconciliação com `PARALLEL_VERTICAL_SAFETY` (10/09/2026)

> Livestock está em desenvolvimento ativo (Codex). Vale o invariante
> `PARALLEL_VERTICAL_SAFETY` (`docs/architecture/PARALLEL_VERTICAL_DEVELOPMENT_PROTOCOL.md`): o bootstrap de
> Asset **não pode** reorganizar Livestock enquanto Livestock estiver ativo. As afirmações deste documento de
> que os Passos 2–4 são "mecânicos / comportamentalmente neutros" ficam **qualificadas** abaixo.

### 7.1 Classificação de cada passo da §5

| Passo (§5) | Conteúdo | Classificação | Observação |
|---|---|---|---|
| 0 | 6 docs + ADR‑0080 | `SAFE_IN_PARALLEL` | Documentação. Somar a este a revisão de `docs/architecture/`. |
| 1 | Generalizar `tests/architecture` (`VERTICAL_PACKAGES`, vertical⊥vertical) | `SHARED_BUT_BACKWARD_COMPATIBLE` | Lane C. Só teste. Livestock verde: o guard só reprova PR **misto**. Usar o contrato de guarda N‑vertical de `MULTI_VERTICAL_CI_GATES.md` §3; registrar só `("livestock","asset")` e adiar `sustainment` (decisão B). |
| 2 | `apps/api/livestock/` + `apps/api/core/` + `_registry.py`; `main.py` itera | **`REQUIRES_INTEGRATION_WINDOW`** | Mover `apps/api/livestock_*.py` é editar arquivos que o Codex usa. Preferir mecanismo **aditivo**: introduzir `_registry.py` que `main.py` passa a iterar **sem mover os módulos de Livestock**; a mudança para `apps/api/livestock/` ocorre numa janela coordenada. Asset nasce em `apps/api/asset/` sem depender disso. |
| 3 | `apps/worker/dispatch.py`: `resolve()` vira despacho real | `SHARED_BUT_BACKWARD_COMPATIBLE` | Lane C. Preservar exatamente o caminho de mensagem de Livestock (fallback explícito para os `message_type` que Livestock já processa). Coordenar a janela se o Codex estiver mexendo no worker. |
| 4 | `__all__` + teste de estabilidade da superfície pública do Core | `SHARED_BUT_BACKWARD_COMPATIBLE` | Lane C. `__all__` reflete o que o `__init__` já reexporta (não reduz). |
| 5 | Extrair ambiente de migrations de Livestock | **`BLOCKED_WHILE_LIVESTOCK_ACTIVE`** | Risco ALTO (R1). Só em janela de integração com o Codex fora de qualquer migration em curso; aceite por diff `pg_dump --schema-only`. **Não é pré‑requisito de Asset** (ver §7.2). |

### 7.2 Migrations — este documento é substituído por `MIGRATION_CONCURRENCY_STRATEGY.md`

O Passo 2 de migrations descrito aqui (e o §3 da ADR‑0080) **não resolve** autoria concorrente de schema nem
o BLOQUEADOR B1 (`alembic check` por vertical sem filtro por dono; `alembic upgrade head` com múltiplas
cabeças). A estratégia oficial passa a ser a **Opção D → C** de
`docs/architecture/MIGRATION_CONCURRENCY_STRATEGY.md`:

- cadeia de Livestock **intocada** agora;
- Asset com `env.py`/`versions/` próprios, *branch label* `asset`, filtro `include_object` por
  `titan.module_owner`, `depends_on` para a revisão do Core que cria `core_identity.organizations`;
- `alembic upgrade head` → `alembic upgrade heads` repo‑wide, em PR de Shared Integration próprio.

### 7.3 Ordem revisada

**Trilha "preparar terreno" (Shared Integration, sem tocar negócio de Livestock):**
G1 (`verticals.toml` + File Ownership Guard) → G2 (teste de dependência N‑vertical) → G3 (split de CI) →
S‑M1 (`version_locations` + `head→heads`) → S‑M2 (helper `include_object`) → S‑M3 (exceção de migrations
generalizada) → Passo 3 (dispatch do worker) → Passo 4 (`__all__`). Passo 2 (mover `apps/api/livestock_*`) e
Passo 5 (extrair migrations de Livestock) ficam para **janela de integração**.

**Trilha "implementar Asset"** (A1…A7 da §5) segue como está, com A3 usando o `env.py` próprio de Asset
(Opção C) e podendo começar após S‑M1–S‑M3 + ACCEPT do slice — **sem esperar** os passos bloqueados.
