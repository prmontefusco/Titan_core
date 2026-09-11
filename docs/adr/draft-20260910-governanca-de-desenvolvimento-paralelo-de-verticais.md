# ADR (RASCUNHO) — Governança de desenvolvimento paralelo de verticais Titan

**Número:** a alocar na integração (política D1 de
`docs/architecture/DECISIONS_REQUIRED_PHASE0.md`; ver `docs/architecture/AGENT_WORKTREE_SAFETY.md` §7).
Não assumir "0081".
**Data:** 10/09/2026
**Status:** RASCUNHO
**Estado operacional no MVP:** FUTURA_APROVADA (nenhuma capacidade movida; documentação apenas)
**Relação com ADR‑0080:** **complementa**, não substitui. ADR‑0080 decide *estrutura de repositório* para a 2ª
vertical; esta decide *como duas ou mais verticais são desenvolvidas ao mesmo tempo sem interferência*.
ADR‑0080 permanece PROPOSTA e ganha os itens de reconciliação no fim do seu texto.
**Relacionada a:** ADR‑0001 (monólito modular, estrutura), ADR‑0002/0003 (isolamento por Organization, RLS),
ADR‑0077 (FKs compostas por Organization), ADR‑0079 (assinatura/integridade de eventos).
**Documentos de apoio (fonte normativa do detalhe):** `docs/architecture/PARALLEL_VERTICAL_DEVELOPMENT_PROTOCOL.md`,
`VERTICAL_OWNERSHIP_MATRIX.md`, `SHARED_CHANGE_PROTOCOL.md`, `MULTI_VERTICAL_CI_GATES.md`,
`MIGRATION_CONCURRENCY_STRATEGY.md`, `NEW_VERTICAL_BOOTSTRAP_STANDARD.md`, `AGENT_WORKTREE_SAFETY.md`,
`CORE_CHANGE_REQUEST_TEMPLATE.md`, `DECISIONS_REQUIRED_PHASE0.md`, `PHASE0_ADVERSARIAL_REVIEW.md`.

---

## Contexto

Titan Livestock está em desenvolvimento ativo (Codex). Titan Asset & Sustainment começará em paralelo. Alguns
pontos do repositório assumem "existe exatamente uma vertical" e alguns pontos de composição são fisicamente
compartilhados (`apps/api/main.py`, `env.py` do Alembic, história linear única de migrations, `pyproject.toml`).
Sem regra explícita, o desenvolvimento de Asset produziria *diffs* em arquivos que o Codex está editando, e a
autoria concorrente de schema serializaria as duas verticais.

A revisão adversarial da Fase 0 (`PHASE0_ADVERSARIAL_REVIEW.md`) identificou um BLOQUEADOR (B1 — o design de
"ambiente de migrations por vertical" não funciona sem `include_object` por dono e sem resolver
`head`/`heads`) e HIGHs (H1 cadeia de integridade por Organization — **resolvida em 11/09/2026, era leitura
parcial de código: a cadeia já é por agregado**; H2 escopo OM/Site; H3 cobertura do entregável §48). A
restrição de desenvolvimento paralelo agrava B1 e adiciona o requisito "autoria concorrente de schema".

---

## Decisão

### 1. Invariante `PARALLEL_VERTICAL_SAFETY`

O desenvolvimento de uma vertical não pode modificar, mover, renomear, reestruturar, migrar ou depender da
implementação interna de outra vertical. Uma vertical pode ler/usar contratos públicos do Core e publicar
eventos/contratos desenhados para composição. Texto formal e completo em
`PARALLEL_VERTICAL_DEVELOPMENT_PROTOCOL.md` §1.

### 2. Três *development lanes*

**A — Livestock**, **B — Asset & Sustainment**, **C — Shared Integration**. Cada mudança pertence a exatamente
uma lane. Caminhos Lane C (`shared_kernel`, `core_*`, composição de API/worker/migrations, config global,
`tests/architecture`, `.github/workflows`) não pertencem a nenhuma vertical. Matriz path→dono em
`VERTICAL_OWNERSHIP_MATRIX.md`.

### 3. Core é somente‑leitura por padrão para verticais

Necessidade de mudar o Core → `CORE_CHANGE_REQUEST` (`CORE_CHANGE_REQUEST_TEMPLATE.md`) + PR de Shared
Integration + evolução de contrato em duas fases (aditivo primeiro; remoção só após todos os consumidores
migrados). Nunca "flag day".

### 4. Ownership mecanicamente verificável

`verticals.toml` (manifesto de composição, sem domínio, não importado pelo Core) como fonte da verdade;
File Ownership Guard reprova PR misto e PR de Lane C sem `CHANGE_CLASS=SHARED_INTEGRATION`; teste de
dependência genérico sobre o manifesto (escala para N verticais); *migration ownership gate* por
`titan.module_owner`; detecção de acesso cruzado à persistência; teste de colisão de namespace de evento;
*transaction boundary gate*. Detalhe e ordem de introdução em `MULTI_VERTICAL_CI_GATES.md`.

### 5. Estratégia de migrations concorrentes: Opção D → C

Cadeia de Livestock **intocada** agora; Asset nasce com `env.py`/`versions/` próprios, *branch label* `asset`,
filtro `include_object` por `titan.module_owner=titan_asset` + allowlist de FK do Core, `MetaData` do Core
compartilhada, 1ª revisão com `depends_on` para a revisão do Core que cria `core_identity.organizations`.
`alembic upgrade head` → `alembic upgrade heads` em todo o repositório, num PR de Shared Integration próprio,
comportamentalmente neutro enquanto houver uma cabeça. Extração da cadeia de Livestock fica para uma janela de
integração, com diff `pg_dump --schema-only` como aceite. Detalhe, opções A–E e ordem de PRs em
`MIGRATION_CONCURRENCY_STRATEGY.md`. **Isto substitui o Passo 2 de `ASSET_VERTICAL_BOOTSTRAP_PLAN.md` e o §3
da ADR‑0080.**

### 6. Worktree e branch

Layout multi‑worktree obrigatório para trabalho concorrente (`Titan-livestock/`, `Titan-asset/`,
`Titan-core-integration/`, worktrees de revisão read‑only); prefixo de branch (`vertical/<id>/*`,
`integration/*`) é a fonte da lane; protocolo de pré‑edição (registrar HEAD/status/branch/worktree);
STOP‑ON‑COLLISION; comandos destrutivos proibidos contra trabalho alheio. Detalhe em
`AGENT_WORKTREE_SAFETY.md`.

### 7. Número de ADR sob concorrência

Rascunho usa `draft-<AAAAMMDD>-<slug>.md` sem número; o número sequencial é alocado só na integração, pelo
integrador. ADR aceita nunca é renumerada.

### 8. Pirâmide de CI em três níveis

Nível 1 (portão rápido de vertical), Nível 2 (compatibilidade compartilhada — obrigatório para qualquer toque
em Lane C, roda Core + todas as verticais), Nível 3 (portão completo pré‑merge). Matriz de compatibilidade:
`integration/main` só é válido com Core + toda vertical verdes juntos.

---

## Fronteiras

- Esta ADR **não** decide o modelo de domínio de Titan Asset (vai para a ADR do 1º slice).
- **Não** decide se `sustainment` é o mesmo `vertical_id` de `asset` ou vertical irmã (decisão B —
  `DECISIONS_REQUIRED_PHASE0.md`).
- Decisão F (escopo da cadeia de integridade) está **resolvida** desde 11/09/2026: a cadeia já é escopada
  por agregado (`organization, aggregate_type, aggregate_id`), confirmado por teste de concorrência real
  (`tests/integration/test_domain_events_postgresql.py`) — ver `DECISIONS_REQUIRED_PHASE0.md` decisão F.
- **Não** decide a autorização OM/Site (decisão G) — diferida para a discovery de domínio; nenhum conceito de
  Asset entra no Core.
- **Não** decide estratégia de frontend multi‑vertical (`apps/web`).

---

## Impacto de Segurança

- **Isolamento reforçado, não enfraquecido.** A regra vertical ⊥ vertical passa a ser verificada por CI
  (import, acesso a persistência, ownership de migration, namespace de evento). RLS por Organization
  (ADR‑0002/0003) permanece a fronteira de isolamento de dados; nada aqui a altera.
- **Superfície de mudança do Core controlada:** verticais não editam `core_*`/`shared_kernel` em branch de
  feature; toda mudança de primitiva de identidade/RLS/`organization_context`/integridade é Shared Integration
  com regressão obrigatória dos cenários de isolamento de Livestock sob role restrita.
- **OM/Site (H2):** explicitamente diferido; proíbe‑se introduzir escopo sub‑Organization sem `CORE_CHANGE_REQUEST`
  provando horizontalidade — evita uma primitiva de autorização especulativa.
- **Comandos destrutivos de Git** contra trabalho alheio ficam proibidos sem autorização do dono — reduz risco
  de perda de trabalho e de sobrescrita de evidência de trabalho concorrente.

## Impacto de Auditoria

- **H1 (resolvida):** a suspeita original — cadeia de integridade escopada só por
  `record_owner_organization_id`, interleavando `append` de duas verticais no mesmo tenant — não se
  confirmou. `DomainEventRepository.append` (`events.py`) serializa via `pg_advisory_xact_lock` numa chave
  `(organization, aggregate_type, aggregate_id)`; a cadeia é **por agregado**. Provado por dois testes de
  concorrência real (`ThreadPoolExecutor`+`Barrier`, conexões independentes) em
  `tests/integration/test_domain_events_postgresql.py`: mesmo agregado continua serializando corretamente;
  agregados diferentes (simulando duas verticais) não esperam um pelo outro. É **garantia do Core por
  agregado**, não acoplamento vertical↔vertical (restrição §17) — sem precisar de reinterpretação, porque o
  design já era esse. Qualquer alteração futura dessa semântica é Shared Integration com ADR própria
  (candidata: seção nova em ADR‑0079), e os dois testes acima quebram primeiro se alguém a estreitar.
- **Ledger:** `docs/CHECKLIST_DE_IMPLEMENTACAO.md` permanece append‑only por lane; cada vertical registra sua
  entrada no mesmo commit da mudança, sem reescrever a da outra.
- **ADRs:** a política de alocação de número na integração preserva o histórico (`docs/adr/README.md` —
  "reabertura não reescreve o histórico").

## Impacto de Migração

- `alembic.ini` ganha `version_locations` e *branch labels*; `env.py` de Asset é novo (Lane B); um *helper*
  de `include_object` por `titan.module_owner` é aditivo em `core_infrastructure` (Lane C).
- `alembic upgrade head` → `alembic upgrade heads` em `CLAUDE.md`, `AGENTS.md`, `DEVELOPMENT.md`,
  `apps/validacao/*`, `.github/workflows/quality.yml`, `docs/CHECKLIST_DE_IMPLEMENTACAO.md` — PR de Shared
  Integration único, comportamentalmente neutro com uma cabeça.
- Revisões existentes são **imutáveis**; a extração da cadeia de Livestock (janela futura) move arquivos sem
  reescrever `revision`/`down_revision` que cruze fronteira (usa `depends_on`/múltiplas cabeças).
- Aceite de cada passo: `pg_dump --schema-only` idêntico; `tests/integration` (85) verdes sem alterar
  asserção; `alembic check` limpo por vertical.

## Implicações de Teste

- Novos testes de arquitetura genéricos sobre `verticals.toml`; contrato reforçado da guarda
  `require_existing_root` para N verticais.
- Novos portões de CI (ownership de arquivo, ownership de migration, acesso a persistência, namespace de
  evento, fronteira de transação) — cada um em PR pequeno de Shared Integration.
- Nenhuma asserção existente de Livestock/Core é enfraquecida; regra "no test weakening" (constituição §21)
  vira verificação de *diff* nos PRs.

---

## Alternativas consideradas

| Alternativa | Motivo da rejeição |
|---|---|
| Manter só a coordenação "um agente por arquivo" (AGENTS.md atual) | Não escala a duas verticais grandes editando em paralelo; colisão provável em `apps/api/main.py` e na trilha de migrations. |
| Grafo global único de migrations + lane de merge serializada | Serializa a autoria de schema — viola a restrição de desenvolvimento paralelo. |
| Mover `apps/api/livestock_*` e extrair migrations de Livestock **agora** para dar simetria a Asset | Mexe em código que o Codex está desenvolvendo (restrição §7); reclassificado como `REQUIRES_INTEGRATION_WINDOW`. |
| Reservar faixas de número de ADR por lane | Desperdiça faixa, ainda colide dentro da lane, polui a numeração. |
| Schema físico por vertical (`titan_asset.*`) já | Muda decisão consciente de schema único (ADR‑0001/0003); FK para `core_identity` ainda exige `MetaData` compartilhada; registrado como evolução possível. |

---

## Consequências

**Positivas.** Livestock e Asset avançam em paralelo sem *diffs* cruzados; autoria concorrente de schema
possível; regras vertical ⊥ vertical viram enforcement; onboarding da Nª vertical não exige redesenho;
B1 resolvido.

**Negativas.** Disciplina operacional nova (worktrees, rótulo `CHANGE_CLASS`, `verticals.toml`); a troca
`head→heads` toca vários documentos; assimetria temporária (Livestock sob o Core, Asset autônomo) até a janela
de extração; autonomia da vertical continua lógica, não física (mitigação: Nível 2/3 de CI).

**Neutras.** `main.py` e `alembic.ini` deixam de crescer por vertical ao custo de um registry e múltiplos
`version_locations` (pago uma vez).

---

## Critérios de aceitação

- Os 6 documentos de `docs/asset/` **e** os 8 de `docs/architecture/` (mais este rascunho)
  revisados.
- Invariante `PARALLEL_VERTICAL_SAFETY` acordado como vinculante.
- Decisões A e C de `DECISIONS_REQUIRED_PHASE0.md` aceitas; D, E registradas; B, F, G com caminho definido.
- Estratégia de migrations **D → C** aceita como oficial (substitui o Passo 2 do bootstrap e o §3 da ADR‑0080).
- Claro que o 1º passo de execução é **só** infra de Shared Integration (G1–G3 de `MULTI_VERTICAL_CI_GATES.md`
  e S‑M1–S‑M3 de `MIGRATION_CONCURRENCY_STRATEGY.md`), sem mover código de produção de vertical.

## Plano de reversão

Enquanto nenhum código for movido, reverter é marcar este rascunho como `DESCARTADO`. Depois de iniciada a
execução, cada passo (Sx‑Mx, Gx) é um PR independente e revertível; o passo de extração de migrations de
Livestock é o único com cuidado extra e só ocorre em janela de integração isolada.
