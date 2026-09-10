# MIGRATION_CONCURRENCY_STRATEGY — Autoria concorrente de schema por múltiplas verticais

**Status:** Proposta para revisão. Documentação apenas — nenhuma migration criada, `alembic.ini` intocado.
**Data:** 10 de setembro de 2026
**Resolve:** BLOQUEADOR **B1** do [`PHASE0_ADVERSARIAL_REVIEW.md`](PHASE0_ADVERSARIAL_REVIEW.md).
**Novo requisito (restrição §9):** *"Livestock e Asset podem autorar mudanças de schema concorrentemente."*
O design de migrations anterior (`ASSET_VERTICAL_BOOTSTRAP_PLAN.md` Passo 2; ADR‑0080 §3) **não pode ser
aceito** até isto estar resolvido.

---

## 1. Estado atual (evidência)

| Fato | Evidência |
|---|---|
| `alembic.ini` tem **um** `script_location`, **nenhum** `version_locations` | `alembic.ini` |
| História **linear única** `0001`…`0086`; `0033`–`0075+` são de Livestock | `packages/core_infrastructure/persistence/migrations/versions/` |
| `env.py` importa ~30 tabelas de `livestock_infrastructure` para registrá‑las na `MetaData` compartilhada | `.../migrations/env.py` (bloco de `assert ... .metadata is target_metadata`) |
| `env.py` filtra autogeração por **schema** (`include_name=include_managed_schema`, schemas `core_identity` e `core_audit`) — **não** por dono de módulo | `.../migrations/env.py` `MANAGED_SCHEMAS` / `include_managed_schema` |
| Tabelas de Livestock vivem no schema `core_audit` (compartilhado), com FK para `core_identity.organizations` | `CORE_REUSE_ASSESSMENT.md` §3.2 |
| CI roda `alembic upgrade head` (singular) e `alembic check` | `.github/workflows/quality.yml` passos "Aplicar migrations" e "Verificar paridade do schema" |
| `alembic upgrade head` aparece em `CLAUDE.md`, `AGENTS.md`, `DEVELOPMENT.md`, `apps/validacao/*`, ~30 linhas do checklist | grep |
| Teste de fronteira carrega exceção nomeada `MIGRATIONS_COMPOSITION_ROOT` só para `env.py` | `tests/architecture/test_dependency_boundaries.py` |

**Consequência da concorrência sob o modelo atual:** duas lanes que autoram migração ao mesmo tempo colidem
em (a) o **mesmo diretório** `versions/`, (b) a **mesma cadeia linear** (ambas encadeiam em `down_revision`
apontando para a cabeça, gerando duas cabeças no merge e conflito de `down_revision`), (c) o **mesmo `env.py`**
(Lane C) se cada uma precisar registrar tabelas novas. Isso serializa a autoria de schema — o que a restrição
§9 proíbe aceitar sem análise.

---

## 2. Critérios de avaliação (restrição §9)

Autoria concorrente · probabilidade de conflito de merge · `alembic check` · instalação em banco limpo ·
upgrade de banco existente (dev/prod) · rollback · *branch labels* · `depends_on` · FK para o Core ·
`MetaData` compartilhada · ownership de módulo · 3ª/4ª vertical · simplicidade de CI · ergonomia de
desenvolvimento · **risco ao trabalho de Livestock em andamento**.

---

## 3. Opções

### OPÇÃO A — Grafo global único + cabeça única + lane de merge serializada

Mantém tudo como está; toda migração (Core ou vertical) entra na mesma cadeia linear; uma "janela de merge de
migration" serializa quem numera a próxima revisão.

| Critério | Avaliação |
|---|---|
| Autoria concorrente | **Ruim.** Só uma lane numera a próxima revisão por vez; a outra espera ou *rebase*. |
| Conflito de merge | Alto em `down_revision` e no diretório `versions/`. |
| `alembic check` / instalação / upgrade / rollback | **Ótimos** (é o que já funciona hoje). |
| Ownership de módulo | Só por `titan.module_owner` no comentário; nada impede DDL cruzada. |
| 3ª/4ª vertical | Piora linearmente. |
| Risco a Livestock | **Baixo** se nada muda; **alto** se a "janela de merge" trava PRs de Livestock. |

**Veredito:** rejeitada como estado‑alvo — viola a restrição §9. Serve só como *fallback* se todas as outras
se mostrarem inviáveis.

### OPÇÃO B — Uma raiz de composição + `version_locations` por módulo + múltiplas cabeças / *branch labels* + `upgrade heads`

`alembic.ini` ganha `version_locations` apontando para um diretório por dono; cada dono tem sua *branch label*
(`core`, `livestock`, `asset`); `env.py` continua único (Lane C) e importa as tabelas de todos os donos;
troca‑se `upgrade head` → `upgrade heads` em todo o repositório.

| Critério | Avaliação |
|---|---|
| Autoria concorrente | **Boa.** Cada lane encadeia na cabeça da própria *branch label*; sem colisão de `down_revision` entre lanes. |
| Conflito de merge | Baixo (diretórios separados; cabeças separadas). |
| `alembic check` | **Precisa de `include_object` por `titan.module_owner`** para checar por vertical; com `env.py` único importando tudo, um `check` global continua possível. |
| Instalação limpa / upgrade | `alembic upgrade heads` aplica todas as *branches*; `depends_on` na 1ª migration de cada vertical aponta para a revisão do Core que cria `core_identity.organizations`. |
| Rollback | Por *branch label* (`downgrade <label>@-1`). |
| `env.py` único | **Continua sendo ponto Lane C compartilhado** — cada tabela nova de vertical exige editar o `env.py` (Lane C). Atrito residual. |
| Risco a Livestock | **Médio:** a troca `head→heads` é repo‑wide e toca a CI que roda o gate de Livestock. |

**Veredito:** viável. Fraqueza: `env.py` único permanece compartilhado.

### OPÇÃO C — `env.py` por vertical + `include_object`/`include_name` por dono + múltiplas cabeças / *branch labels*

Cada vertical tem `packages/<vertical>_infrastructure/persistence/migrations/{env.py,versions/}` próprio. Cada
`env.py`:

- importa **as próprias tabelas** + **as tabelas‑alvo de FK do Core** (allowlist explícita, hoje
  `core_identity.organizations` e o que `DEPENDENCY_RULES.md` §5 sancionar);
- usa a **`MetaData` do Core** (`organization_metadata`), como `livestock_infrastructure/persistence/metadata.py`
  já faz — necessário para o SQLAlchemy resolver a FK;
- define `include_name`/`include_object` que aceita um objeto **somente** se
  `object.info.get("titan.module_owner") == "titan_<vertical>"` **ou** o objeto está na allowlist de alvos de
  FK do Core. É isto que impede o `alembic check` da vertical de propor `DROP` das tabelas das outras.

`alembic.ini` ganha `version_locations` com uma entrada por vertical + a do Core; *branch labels* por dono;
`upgrade head` → `upgrade heads` repo‑wide.

| Critério | Avaliação |
|---|---|
| Autoria concorrente | **Ótima.** Diretórios, cabeças e `env.py` totalmente separados por lane. |
| Conflito de merge | **Mínimo** (nenhum arquivo compartilhado entre lanes na trilha de migration). |
| `alembic check` | **Correto por vertical** graças ao filtro por `titan.module_owner`; um `check` por *branch label*/dono. |
| Instalação limpa / upgrade | `alembic upgrade heads`; `depends_on` da 1ª revisão de cada vertical → revisão do Core que cria `organizations`. |
| Rollback | Por dono, isolado. |
| Ownership de módulo | Reforçado pelo próprio filtro do `env.py` + portão de CI (§5). |
| 3ª/4ª vertical | Custo constante: copiar o padrão do `env.py`, adicionar `version_locations`, *branch label*. |
| `tests/architecture` | Exceção `MIGRATIONS_COMPOSITION_ROOT` generalizada para "qualquer `env.py` sob `packages/*/persistence/migrations/`". |
| Risco a Livestock | **Médio** — exige extrair o ambiente de migrations de Livestock (R1, risco ALTO em `CORE_EXTRACTION_RISKS.md`) **ou** conviver com assimetria (Opção D). |

**Veredito:** melhor estado‑alvo. Custo: precisa da extração de Livestock **ou** de uma transição (D).

### OPÇÃO D — Transição: cadeia de Livestock intocada; verticais novas em *branch* isolada; camada de composição instala todas

Estado **intermediário**, não final:

- A cadeia atual Core+Livestock em `core_infrastructure/.../versions/` **não é mexida** (a migration de
  Livestock existente é imutável — restrição §11 — e o Codex está trabalhando: restrição §7).
- **Asset nasce direto no modelo da Opção C**: `env.py` próprio, `versions/` próprio, *branch label* `asset`,
  filtro por `titan.module_owner`, `depends_on` → revisão do Core que cria `organizations`.
- `alembic.ini` passa a ter `version_locations = <core+livestock atual>  <asset novo>`; *branch labels*
  `core_livestock` (a cadeia atual) e `asset`.
- **`upgrade head` → `upgrade heads` em todo o repo** (CI, `CLAUDE.md`, `AGENTS.md`, `DEVELOPMENT.md`,
  `apps/validacao/*`, checklist) — num **PR de Shared Integration próprio**, comportamentalmente neutro
  (com uma cabeça, `heads` == `head`), **antes** da 1ª migration de Asset.
- A extração da cadeia de Livestock para `livestock_infrastructure/.../migrations/` (chegando à Opção C plena)
  fica como trabalho **separado**, agendado para uma **janela de integração** quando o Codex não estiver no
  meio de uma migration, com teste de diff `pg_dump --schema-only` como aceite (R1).

| Critério | Avaliação |
|---|---|
| Autoria concorrente | **Boa desde já** para o par Livestock↔Asset (cabeças e diretórios separados). |
| Risco a Livestock | **Baixo:** nada da cadeia de Livestock é tocado; só se adiciona `version_locations` e se troca `head→heads`. |
| Assimetria temporária | Livestock ainda sob `core_infrastructure`, Asset autônomo — cosmético, aceitável. |
| `alembic check` | Asset checa por `titan.module_owner`; Livestock+Core seguem no `check` por schema atual. |
| Caminho para C plena | Um passo adicional agendado, não um bloqueio. |

**Veredito:** **recomendada como primeira execução.** É a Opção C aplicada só a Asset, com Livestock
preservado, convergindo para C quando houver janela.

### OPÇÃO E — Modelo melhor a partir das restrições reais

Considerada: **schema físico por vertical** (`titan_asset.*` em vez de `core_audit.*`). Reduziria a
necessidade do filtro por `titan.module_owner` (o filtro por schema do `env.py` já separaria). Rejeitada
agora porque: (a) muda a decisão consciente de schema único do monólito (ADR‑0001/0003) e o padrão de
`livestock_infrastructure/persistence/metadata.py`; (b) FK entre `titan_asset` e `core_identity` continua
exigindo `MetaData` compartilhada de qualquer modo; (c) RLS por Organization — e não o schema — é a fronteira
de isolamento. Fica **registrada como evolução possível** se a 3ª/4ª vertical tornar o filtro por
`module_owner` frágil.

---

## 4. Recomendação

**Executar a Opção D agora; convergir para a Opção C plena numa janela de integração.**

Ordem (cada item é um PR de Shared Integration independente e revertível, **nenhum** misturado com feature de
vertical — restrição §6):

| # | Conteúdo | Toca produção? | Aceite |
|---|---|---|---|
| **S‑M0** | Este documento + decisão **A** de [`DECISIONS_REQUIRED_PHASE0.md`](DECISIONS_REQUIRED_PHASE0.md) aceita. | Não | Revisão aprovada. |
| **S‑M1** | `alembic.ini`: introduzir `version_locations` (só a localização atual) + *branch label* `core_livestock` na cabeça atual. Trocar `upgrade head` → `upgrade heads` em CI, `CLAUDE.md`, `AGENTS.md`, `DEVELOPMENT.md`, `apps/validacao/*`, checklist. | Sim, mecânico | Com **uma** cabeça, `heads` produz schema idêntico; `pg_dump --schema-only` idêntico; `tests/integration` (85) verdes sem alterar asserção; `alembic check` limpo. |
| **S‑M2** | Convenção `include_object`/`include_name` por `titan.module_owner` documentada e um *helper* compartilhado em `core_infrastructure` (Lane C) que cada `env.py` de vertical importará. Sem novo `env.py` ainda. | Sim, aditivo | `mypy`+`pytest` verdes; *helper* coberto por teste unitário com tabelas sintéticas. |
| **S‑M3** | Generalizar a exceção `MIGRATIONS_COMPOSITION_ROOT` do teste de fronteira para "qualquer `env.py` sob `packages/*/persistence/migrations/`". | Só teste | `tests/architecture` verde. |
| **A‑M1** *(trilha Asset)* | `packages/asset_infrastructure/persistence/migrations/{env.py,versions/}` com *branch label* `asset`, `MetaData` do Core, filtro por `titan.module_owner=titan_asset` + allowlist de FK, 1ª revisão com `depends_on` → revisão do Core que cria `core_identity.organizations`. | Sim (Lane B) | `alembic upgrade heads` do zero cria o schema completo; `alembic check` com o `env.py` de Asset diz "no changes"; `pg_dump` do schema de Livestock inalterado. |
| **S‑M4** *(janela de integração, quando houver)* | Extrair a cadeia Core+Livestock: mover revisões de Livestock para `livestock_infrastructure/.../migrations/versions/`, `env.py` próprio de Livestock, *branch label* `livestock` separada de `core`. **Não reescreve** revisões (só move + ajusta `version_locations`/`down_revision` sem cruzar fronteira; se cruzar, vira múltiplas cabeças + `depends_on`). | Sim, ALTO risco | `pg_dump --schema-only` byte‑a‑byte idêntico antes/depois; `tests/integration` (85) verdes; coordenado com o Codex fora de qualquer migration de Livestock em curso. |

Asset pode começar domínio/aplicação **sem esperar** S‑M4. A trilha Asset de migration (`A‑M1`) só depende de
S‑M1–S‑M3.

---

## 5. Ownership e imutabilidade de migration (restrições §10 e §11)

**Ownership (enforcement, não convenção):**

- Migration de Asset **não** cria/dropa/altera tabela com `titan.module_owner != titan_asset`.
- Migration de Livestock **não** toca tabela `titan_asset`.
- Migration do Core **não** muta silenciosamente tabela de vertical.
- Portão de CI (detalhe em [`MULTI_VERTICAL_CI_GATES.md`](MULTI_VERTICAL_CI_GATES.md) §"Migration ownership"):
  para cada arquivo de revisão novo/alterado no PR, resolver o `vertical_id` pelo `version_locations` /
  `migration_owner` do manifesto; inspecionar as operações (`op.create_table`, `op.drop_table`,
  `op.add_column`, `op.execute` com DDL) e o schema/dono das tabelas‑alvo; **falhar** se uma operação atinge
  tabela cujo `titan.module_owner` ≠ dono da revisão (exceto operações puramente aditivas sobre alvos de FK
  do Core explicitamente sancionadas). Não depender só de convenção de nome de arquivo.

**Imutabilidade:**

- Revisão já mergeada/aplicada em ambiente compartilhado é **imutável**. Nunca reescrever histórico para
  resolver conflito Asset↔Livestock.
- Uma revisão pode ser *rebased*/renumerada/religada **apenas antes** de qualquer merge/aplicação
  compartilhada.
- Corrida entre duas branches: **detectar → reconciliar explicitamente → criar relação legal de
  branch/merge (`depends_on` ou revisão de merge) → testar de banco limpo → testar do estado anterior do
  banco**. Nunca editar histórico em silêncio.

---

## 6. Sub‑decisões que permanecem abertas

Encaminhadas a [`DECISIONS_REQUIRED_PHASE0.md`](DECISIONS_REQUIRED_PHASE0.md):

- **A** — confirmar Opção D→C (este documento) como estratégia oficial de migrations.
- Momento da janela S‑M4 (extração de Livestock) — depende da agenda do Codex.
- Se `sustainment` tem `migration_owner` próprio ou compartilha `titan_asset` — segue a decisão **B**.
