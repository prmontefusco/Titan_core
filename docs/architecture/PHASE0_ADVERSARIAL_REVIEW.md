# PHASE0_ADVERSARIAL_REVIEW — Revisão adversarial dos artefatos de prontidão do Core para a 2ª vertical

**Autor:** Claude (Role B — arquiteto crítico / revisor adversarial, §31 da constituição multi‑agente)
**Data:** 10 de setembro de 2026
**Objeto:** `docs/asset/` (6 documentos) + `docs/adr/0080-segunda-vertical-e-reutilizacao-do-core-sem-fork.md`
**Estado:** Revisão registrada. Findings abertos até correção nos documentos‑alvo, exceto H1 (rebaixada para
OBSERVAÇÃO em 11/09/2026, com dois testes de concorrência reais em
`tests/integration/test_domain_events_postgresql.py` — únicos arquivos de código que este documento passou
a referenciar como evidência fechada).

Classificação por severidade conforme §31: **BLOQUEADOR / HIGH / MEDIUM / LOW / OBSERVAÇÃO**.
Para BLOQUEADOR/HIGH: cenário · invariante afetado · consequência provável · evidência · correção recomendada · teste de regressão.

---

## Resumo do julgamento

Os 6 documentos são de alta qualidade: baseados em evidência (greps, contagem de imports, LOC), recusam‑se
corretamente a implementar, identificam a Opção A (monorepo + monólito modular + Core compartilhado) pelos
motivos certos, mantêm `shared_kernel` contido e exigem que *entitlement* de SLI seja `Evaluation → Decision`
do Core em vez de lógica ad hoc. A tese central — "o Core já é reutilizável; não é preciso fork" — está
substancialmente correta.

Persistem: **um bloqueador técnico** (o mecanismo de "ambiente de migrations por vertical, `MetaData` única",
como escrito, não funciona sem duas peças ausentes — **resolvido** em S‑M1/S‑M2/S‑M3) e lacunas HIGH em
autorização sub‑Organization (OM/Site) e cobertura do entregável da §48. A suspeita original de acoplamento
de integridade entre verticais (H1) **não se confirmou**: o código já serializa por agregado, não por
Organization — ver correção ao final de H1.

> A restrição de desenvolvimento paralelo (Livestock ativo sob o Codex) introduzida após esta revisão
> **agrava B1** e cria um requisito novo — autoria concorrente de schema — tratado em
> [`MIGRATION_CONCURRENCY_STRATEGY.md`](MIGRATION_CONCURRENCY_STRATEGY.md).

---

## BLOQUEADOR

### B1 — "Ambiente de migrations por vertical + `MetaData` única" quebra `alembic check` e `alembic upgrade head`

**Cenário.** Passo 2 do `ASSET_VERTICAL_BOOTSTRAP_PLAN.md` e §3 da ADR‑0080: cada vertical ganha
`version_locations` próprio e um `env.py` que "importa as tabelas‑alvo de FK do Core"; a `MetaData` permanece
única (`organization_metadata`). Um desenvolvedor roda `alembic check` (gate do `CLAUDE.md` e da CI) e
`alembic upgrade head`.

**Invariante afetado.** ADR‑0001 §comportamento preservado; princípios 1–3 do próprio `CORE_EXTRACTION_RISKS.md`
(schema idêntico; `alembic check` limpo).

**Consequência provável.**

1. **`alembic check` propõe `DROP TABLE` de toda vertical não importada no `env.py` corrente.**
   `organization_metadata` é um singleton povoado por efeito de import. Hoje
   `packages/core_infrastructure/persistence/migrations/env.py` importa ~30 tabelas de
   `livestock_infrastructure` **exatamente para** `alembic check` não propor removê‑las, e filtra autogeração
   por **schema** (`include_name=include_managed_schema`, schemas `core_identity`/`core_audit`) — **não** por
   dono de módulo. Um `env.py` por vertical que importe só as próprias tabelas + as do Core reintroduz o bug
   que o `env.py` único existe para evitar. Os documentos nunca mencionam `include_object`/`include_name`
   filtrando por `titan.module_owner` — a peça que torna o `alembic check` por vertical correto.

2. **`alembic upgrade head` (singular) passa a falhar com `Multiple head revisions are present`.**
   `CORE_EXTRACTION_RISKS.md:49` e `REPOSITORY_STRUCTURE_PROPOSAL.md:205` afirmam que "`upgrade head` passa a
   resolver todas as cabeças" — **factualmente errado**. Com múltiplas cabeças é preciso `alembic upgrade heads`,
   revisão de *merge*, ou linearização por `down_revision`/`depends_on`. `alembic upgrade head` aparece em
   `AGENTS.md`, `CLAUDE.md`, `DEVELOPMENT.md`, `apps/validacao/*`, `.github/workflows/quality.yml`
   (passo "Aplicar migrations") e ~30 linhas de `docs/CHECKLIST_DE_IMPLEMENTACAO.md`. O Passo 2 não é
   "mecânico / comportamentalmente neutro".

**Evidência.** `packages/core_infrastructure/persistence/migrations/env.py` (import das tabelas de Livestock +
`include_managed_schema` por schema); `alembic.ini` (sem `version_locations`, um `script_location`);
`.github/workflows/quality.yml` (`alembic upgrade head`, `alembic check`); `tests/architecture/test_dependency_boundaries.py:14‑25`
(comentário de `MIGRATIONS_COMPOSITION_ROOT`); `CORE_EXTRACTION_RISKS.md:49`; `REPOSITORY_STRUCTURE_PROPOSAL.md:205`.

**Correção recomendada.** Ver [`MIGRATION_CONCURRENCY_STRATEGY.md`](MIGRATION_CONCURRENCY_STRATEGY.md):
(a) `env.py` de cada vertical com `include_object`/`include_name` que aceita apenas objetos cujo
`table.info["titan.module_owner"]` casa com a vertical **e** os alvos de FK do Core (allowlist explícita);
(b) escolher e escrever explicitamente a estratégia de cabeça — cabeça única encadeada, ou múltiplas cabeças
com troca `head → heads` repo‑wide num PR de Shared Integration próprio, antes de qualquer migration de Asset;
(c) reclassificar a "alternativa de menor risco" 2A: ela **não escapa** do problema de múltiplas cabeças.

**Teste de regressão.** (a) `pg_dump --schema-only` idêntico antes/depois em banco limpo sob role restrita,
rodando cada `env.py` isolado; (b) teste que executa `alembic check` por vertical e exige "no changes";
(c) teste que executa `alembic upgrade heads` do zero e confere contagem de tabelas por `titan.module_owner`.

---

## HIGH

### H1 — A cadeia de integridade é por Organization, não por vertical: duas verticais "isoladas" passam a compartilhar uma cadeia de hash e um ponto de serialização

**Cenário.** Uma Organization operadora que roda as duas verticais (frota de veículos *e* operação pecuária, ou
o tenant operador). Asset e Livestock fazem `append` de eventos concorrentemente para a mesma Organization.

**Invariante afetado.** §24 (auditoria/integridade), §29 (consistência transacional) e a afirmação dos
documentos de que Asset↔Livestock "não compartilham nada além do banco e do schema `core_audit`".

**Consequência provável.** O `previous_hash` do `event_integrity_table` é buscado com filtro **apenas**
`record_owner_organization_id == event.organization_id.value`
(`packages/core_infrastructure/persistence/events.py:247‑256`). A cadeia é **por Organization**; todo `append`
naquela Organization — de qualquer vertical — é um read‑modify‑write que precisa ser serializado. Adicionar
Asset amplia o domínio de serialização para duas verticais declaradas isoladas, faz a verificação da cadeia
de um tenant ler eventos das duas intercalados, e acopla o *throughput* de auditoria entre elas.

**Evidência.** `packages/core_infrastructure/persistence/events.py:247‑256`; `CORE_REUSE_ASSESSMENT.md` §1.4
(`26` imports de `core_infrastructure.persistence.events` — maior acoplamento de infra do Core).

**Correção recomendada.** Ver [`DECISIONS_REQUIRED_PHASE0.md`](DECISIONS_REQUIRED_PHASE0.md) decisão **F**.
Documentar o escopo da cadeia como **garantia global do Core**, não dependência vertical↔vertical
(distinção do §17 da restrição de paralelismo). Nenhum código de Asset toca semântica de integridade;
qualquer mudança é Shared Integration com ADR própria.

**Teste de regressão.** Concorrência com `ThreadPoolExecutor` + `Barrier` (padrão já usado em Livestock)
fazendo `append` simultâneo de eventos de dois módulos para a mesma Organization; verificar integridade da
cadeia e ausência de deadlock/hash órfão.

---

**CORREÇÃO (11/09/2026, decisão F fechada — evidência abaixo).** A premissa desta finding estava
**errada**: `DomainEventRepository.append` (`events.py`, método completo — não só as linhas 247‑256 citadas
acima, que vieram de uma leitura parcial) serializa via `pg_advisory_xact_lock` numa chave
`f"{organization_id}:{aggregate_type}:{aggregate_id}"`, e a busca de `previous_hash` filtra por
`(record_owner_organization_id, aggregate_type, aggregate_id, aggregate_version)` — **não** só por
Organization. A cadeia de integridade é **por agregado**, não uma cadeia global por Organization. Duas
verticais no mesmo tenant escrevendo em tipos de agregado diferentes (`WorkOrder` de Asset vs. `Animal` de
Livestock) usam chaves de advisory lock diferentes e **não** esperam uma pela outra nem interleiam na mesma
cadeia.

Provado empiricamente por dois testes de concorrência reais (conexões/transações independentes por thread,
sem mock) em `tests/integration/test_domain_events_postgresql.py`:
`test_concurrent_appends_to_the_same_aggregate_serialize_via_advisory_lock` (mesmo agregado continua
serializando corretamente sob concorrência real — sem essa trava, duas transações que veem
"agregado vazio" ao mesmo tempo poderiam corromper a cadeia) e
`test_concurrent_appends_to_different_aggregates_do_not_serialize` (agregados diferentes, mesma
Organization, thread B commita antes de thread A apesar de A segurar a transação aberta — prova que não há
espera cruzada).

**H1 fica rebaixada para OBSERVAÇÃO**: o design já é a garantia que a correção original pedia; não há ação
pendente além de manter os dois testes de concorrência no gate (`MULTI_VERTICAL_CI_GATES.md` Nível 2) e não
introduzir, no futuro, um lock ou busca de `previous_hash` escopados só por Organization. Decisão **F**
(`DECISIONS_REQUIRED_PHASE0.md`) fechada como **F1‑confirmado‑por‑teste**, não apenas F1‑por‑documentação.

**Lição de processo:** este é um lembrete de que uma finding baseada em leitura parcial de código (só um
trecho de uma função maior) pode inverter a conclusão. A revisão adversarial deve ler o método inteiro, não
o trecho que o grep trouxe.

### H2 — O assessment conclui "Core fornece autorização, Asset só reutiliza" sem testar isso contra o escopo OM/Site (sub‑Organization) que §18/§26 implicam

**Cenário.** §18 da constituição: `Customer → Organization → OM/Site → Vehicles/Local Stock/Workshop`. Uma
Organization operadora atende várias OMs; cada OM vê apenas seus veículos, contratos e estoque local.

**Invariante afetado.** §26 (autorização antes da divulgação; fail‑closed); a fronteira de isolamento que os
documentos assumem suficiente (RLS por `titan.organization_id`).

**Consequência provável.** Livestock isola por **Organization**. Se OM/Site é partição **dentro** de uma
Organization operadora, RLS‑por‑Organization não isola dado de OM e `OrganizationContext` do Core é
insuficiente — seria preciso uma primitiva de escopo nova no Core. Se cada OM é uma Organization, há impacto
em identidade, *memberships*, contratos cross‑Organization e na cadeia de integridade (H1). Qualquer caminho é
superfície do Core que os documentos dizem não ser necessária.

**Evidência.** `CORE_REUSE_ASSESSMENT.md` §5 item 1; `ASSET_VERTICAL_BOOTSTRAP_PLAN.md` §3 (linha "Identidade,
Organizations … `OrganizationContext`" marcada como fornecida, sem ressalva de OM/Site); constituição §18.

**Correção recomendada.** Manter a questão **aberta** até a discovery de domínio (§18 da restrição de
paralelismo). Se surgir necessidade de escopo genérico no Core, abrir `CORE_CHANGE_REQUEST` provando
horizontalidade. Nenhum conceito `OM`/`MilitaryOrganization`/`Workshop`/`Vehicle` entra no Core.
Ver [`DECISIONS_REQUIRED_PHASE0.md`](DECISIONS_REQUIRED_PHASE0.md) decisão **G**.

**Teste de regressão.** Sob role `NOLOGIN NOSUPERUSER NOBYPASSRLS` (padrão de
`tests/integration/test_organization_postgresql.py`): um principal com contexto da OM A não lê
veículos/contratos/estoque da OM B **dentro da mesma Organization operadora**.

### H3 — Estes 6 documentos não são o entregável da §48; falta o conjunto 01–20 e o `MULTI_AGENT_ARCHITECTURE_REVIEW.md`

**Cenário.** A §48 lista 20 arquivos numerados (`01_PRODUCT_VISION.md` … `20_EXECUTION_ROADMAP.md`) mais ADRs;
a §49 exige `MULTI_AGENT_ARCHITECTURE_REVIEW.md`. O que existe é um assessment de **reuso do Core e estrutura
de repositório** — Fase 0 legítima, escopo diferente.

**Invariante afetado.** §37 (Definition of Done) e §38 (ordem obrigatória: Vision → Domain Map → … → Roadmap
antes de implementar).

**Consequência provável.** Nenhum dos 6 cobre discovery de domínio (Ubiquitous Language, Domain Model,
Aggregate Analysis, Invariants, Domain Events, Command Model, Temporal Model, Authorization Model, Audit Model,
Integration Model, 3D Asset Model, SLI Contract Model, Inventory Model, Maintenance Model, UX Operating Model,
Risk Register, Execution Roadmap). Aceitar a ADR‑0080 isolada pode passar a impressão de que a discovery
terminou.

**Evidência.** `ls docs/asset/` (6 arquivos, nenhum 01–20); ausência de
`MULTI_AGENT_ARCHITECTURE_REVIEW.md`; ADR‑0080 §"Critérios de aceitação".

**Correção recomendada.** Enquadrar os 6 como **"Fase 0 — Prontidão do Core / estrutura de repositório"** e
registrar em `docs/CHECKLIST_DE_IMPLEMENTACAO.md` que §48 (01–20) e §49 seguem pendentes. A ADR‑0080 pode ser
aceita quanto à estrutura; não fecha a discovery de domínio.

---

## MEDIUM

### M1 — `require_existing_root` deixa `tests/architecture` vermelho no minuto em que `"asset"` entra em `VERTICAL_PACKAGES`

`DEPENDENCY_RULES.md` §7 quer `VERTICAL_PACKAGES = ("livestock", "asset")` no Passo 1, descrito como "só teste,
Livestock verde". Mas `require_existing_root` faz `assert root.exists()`
(`tests/architecture/test_dependency_boundaries.py:29‑37`) e `packages/asset_domain` não existirá. A mitigação
(parametrizar + pular ausente + guarda "≥1 vertical checada") **altera a semântica da guarda**. Não é "risco
BAIXO". **Correção:** o Passo 1 especifica o novo contrato da guarda ("falha se nenhuma vertical conhecida foi
verificada" + "falha se uma vertical registrada existe mas não foi varrida"), com teste do próprio teste.
Detalhe em [`MULTI_VERTICAL_CI_GATES.md`](MULTI_VERTICAL_CI_GATES.md) §Dependency test.

### M2 — O teste de fronteira do Passo 1 depende de uma decisão de domínio que só a ADR do slice toma

`ASSET_VERTICAL_BOOTSTRAP_PLAN.md` §2.1 deixa aberto se `sustainment_*` importa `asset_*` (mesma vertical) ou
não (irmãs isoladas) e recomenda a primeira; o Passo 1 quer congelar `VERTICAL_PACKAGES` e escrever
`test_verticals_do_not_import_each_other` **agora**. Se tratar `sustainment` como vertical, proíbe o import
que a recomendação quer permitir; se não tratar, há buraco de cobertura. **Correção:** Passo 1 usa só
`("livestock", "asset")` e adia `sustainment` explicitamente, ou a ADR do slice precede o Passo 1.

### M3 — "Nenhuma transação cruza duas verticais" é intenção declarada sem mecanismo de enforcement

As regras de import ganham 6 testes novos; a regra "sem transação cross‑vertical" ganha zero. Com
`MetaData`/pool/sessão únicos, nada impede um `apps/*` de abrir uma transação que chama serviço de duas
verticais. **Correção:** especificar o invariante de runtime e como verificá‑lo — ver
[`MULTI_VERTICAL_CI_GATES.md`](MULTI_VERTICAL_CI_GATES.md) §Transaction boundary e §16 da restrição de
paralelismo.

### M4 — ADR‑0080 não tem as seções "Impacto de Segurança" e "Impacto de Auditoria" que a §30 exige

A §30 lista Security impact e Audit impact como conteúdo obrigatório de ADR. A ADR‑0080 os cobre de forma
difusa. Dados H1 e H2, as seções teriam conteúdo real. **Correção:** adicionar as duas seções antes de mudar
o status para ACEITA.

---

## LOW / OBSERVAÇÃO

- **L1 (LOW).** Notificação (oficina, cliente, alerta de SLA) é candidata forte a capacidade horizontal do
  Core e não recebe o mesmo cuidado dado à "abstração de ERP". Pré‑registrar: "nasce em `asset_application`;
  candidata a Core quando a 2ª consumidora aparecer — não extrair antes".
- **L2 (OBSERVAÇÃO).** A conclusão "o Core está limpo" depende de auditoria ainda pendente de
  `operational_support.py` (`CURRENT_PACKAGE_CLASSIFICATION.md`). Fazer antes do ACCEPT.
- **L3 (OBSERVAÇÃO).** `apps/web` totalmente diferido — aceitável para um assessment de backend, mas
  `18_UX_OPERATING_MODEL.md` / `19_RISK_REGISTER.md` (inexistentes) precisam carregá‑lo, e o roadmap não pode
  declarar o slice "pronto" sem o dashboard de oficina.
- **L4 (OBSERVAÇÃO).** Critério de sucesso nº 5 do bootstrap ("remover `livestock_*` não quebra `asset_*`")
  não vale para o ambiente de migrations enquanto a Opção 2A mantiver Livestock sob o Core com o `env.py`
  importando `livestock_infrastructure`. Ajustar o critério para escopo de pacotes, ou notar a exceção.

---

## O que está certo e não deve ser mexido

- Opção A (monorepo / monólito modular / Core compartilhado) — comparação A/B/C/D sólida, coerente com ADR‑0001.
- `shared_kernel` congelado com alarme de LOC.
- Corte inicial de dois módulos em vez de sete bounded contexts vazios (§38 + crescimento incremental).
- **Entitlement de SLI como `Evaluation → Decision` governada** — teste real de reuso do Core, corretamente exigido.
- STOP CONDITION explícita em todos os documentos.

---

## Recomendação

Não aceitar a ADR‑0080 como está. Bloqueio em **B1**. Resolver B1 e H1–H2 no texto, adicionar as seções §30
(M4), reenquadrar o conjunto como Fase 0 explícita (H3). Feito isso, a **estrutura** pode ser aceita; a
discovery de domínio (§48 01–20, §49) segue pendente.
