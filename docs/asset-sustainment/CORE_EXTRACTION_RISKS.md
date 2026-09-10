# CORE_EXTRACTION_RISKS — Riscos da reorganização e segurança de migração

**Versão:** 1.0
**Status:** Proposta para revisão (Fase 8)
**Data:** 10 de setembro de 2026

"Extração" aqui **não** significa tirar o Core do repositório. Significa
generalizar os pontos que hoje assumem "uma vertical" — sobretudo o ambiente de
migrations — para que uma segunda vertical não precise de fork.

---

## 1. Princípios inegociáveis de qualquer reorganização

Toda etapa deve:

1. **Preservar comportamento** — nenhuma mudança observável na API, no schema do
   banco, nos eventos publicados ou na cadeia de integridade.
2. **Preservar APIs existentes** — rotas, contratos OpenAPI, códigos de erro
   idênticos byte a byte.
3. **Preservar migrations** — `alembic upgrade head` produz o mesmo schema; hashes
   de revisão existentes não são reescritos.
4. **Preservar testes** — nenhuma asserção de teste existente é enfraquecida ou
   removida para "passar". Testes novos podem ser adicionados.
5. **Evitar mudanças massivas** — cada etapa é um PR pequeno, revisável em uma
   sessão.
6. **Permitir revisão incremental** — cada etapa é independente e revertível.

**Nunca** misturar "reorganizar Core" com "implementar Titan Asset" no mesmo
commit/PR.

---

## 2. Riscos por área

### R1 — Extração do ambiente de migrations da vertical *(risco ALTO)*

**O que muda:** mover as ~43 migrations de Livestock de
`core_infrastructure/persistence/migrations/versions/` para um diretório de
versões próprio da vertical; dar à vertical um `env.py` (ou entrada em
`version_locations`) que importa as tabelas do Core como alvo de FK + as próprias.

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| `alembic check` passa a propor drop/create de tabelas da vertical | Alta se feito errado | Bloqueia CI | Manter `MetaData` **única** (a do Core); a vertical só ganha `version_locations` próprio, não `MetaData` própria. Ver `livestock_infrastructure/persistence/metadata.py`. |
| Ordenação de migrations quebra (tabela de vertical antes de `organizations`) | Média | `upgrade` falha em banco limpo | Usar `depends_on` na primeira migration da vertical apontando para a revisão que cria `core_identity.organizations`. |
| Schema resultante difere do atual | Baixa | Corrupção silenciosa de contrato | **Teste de aceite obrigatório:** subir banco limpo com `main` atual → dump de schema (`pg_dump --schema-only`); repetir com o branch de extração; `diff` deve ser vazio (ignorando ordem de statements). |
| Revisões existentes reescritas (hash muda) | Baixa | Bancos já migrados ficam órfãos | Não editar arquivos de revisão existentes; só movê-los e ajustar `down_revision`/`version_locations`. Se algum `down_revision` cruzar a fronteira Core↔vertical, converter para múltiplas cabeças + `depends_on` em vez de reescrever a cadeia. |
| `apps/`, `apps/validacao`, `tests/integration` assumem `alembic upgrade head` único | Alta | Testes de integração vermelhos | Configurar `alembic.ini` com múltiplos `version_locations`; `upgrade head` passa a resolver todas as cabeças. Rodar as 85 suites de `tests/integration` antes de abrir o PR. |
| A exceção `MIGRATIONS_COMPOSITION_ROOT` no teste de fronteira fica obsoleta | Certa | Teste desatualizado | Generalizar a exceção para "qualquer `env.py` sob `packages/*/persistence/migrations/`" no mesmo PR. |

**Alternativa de menor risco (recomendada para começar):** **não mexer nas
migrations de Livestock agora.** Dar a Asset o próprio ambiente de migrations
desde o dia 1, aceitar assimetria temporária (Livestock sob o Core, Asset
autônomo), e agendar a extração de Livestock como trabalho separado com o teste
de diff de schema. Isso desbloqueia Asset sem tocar no que já funciona.

### R2 — Generalização do teste de fronteira arquitetural *(risco BAIXO)*

**O que muda:** `CORE_PACKAGES` + `VERTICAL_PACKAGES`; parametrização; novos
testes vertical⊥vertical (`DEPENDENCY_RULES.md` §7).

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Vertical `asset` ainda não existe → `require_existing_root` falha | Certa se ingênuo | Teste vermelho sem motivo | Parametrização que pula vertical inexistente **e** um teste-guarda que falha se *nenhuma* vertical foi verificada (mesma filosofia do `require_existing_root` atual). |
| Teste novo encontra violação real preexistente em Livestock | Baixa (grep já feito: limpo) | PR cresce | Se aparecer, é achado legítimo — tratar em PR próprio antes. |

**Este é o Passo 1.** Nenhum código de produção muda. Livestock permanece verde.

### R3 — Subpacote `apps/api/<vertical>/` + registry de routers *(risco BAIXO–MÉDIO)*

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Import path de módulos `apps.api.livestock_*` muda e quebra `tests/api` + `apps/web` build helpers | Alta | Testes vermelhos | Mudança puramente mecânica de imports; `grep -r "apps.api.livestock_" ` para achar todos os pontos; um PR só de "mover + reimportar". |
| Ordem de inclusão de routers muda e afeta precedência de rota / OpenAPI | Baixa | Contrato OpenAPI difere | Snapshot do OpenAPI (`/openapi.json`) antes e depois; diff deve ser vazio salvo reordenação sem efeito. `tests/api` deve cobrir isso; se não cobre, adicionar snapshot test **antes** do refactor. |
| `main.py` com feature flags (`TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED` etc.) | Média | Rota some/aparece por engano | Preservar exatamente a lógica de flag ao mover para o registry. |

### R4 — Despacho real no worker *(risco BAIXO)*

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| `resolve()` deixa de devolver sempre o handler de Livestock e passa a exigir chave no envelope | Média | Mensagem sem `message_type` conhecido cai em erro | Fallback explícito preservando o comportamento atual para os tipos de mensagem que Livestock já processa; teste com o envelope real de `LivestockErpInboxHandler`. |

### R5 — Congelar superfície pública do Core (`__all__` + teste) *(risco BAIXO)*

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Adicionar `__all__` esconde um nome que algum módulo importava sem passar pelo `__init__` | Média | `ImportError` | `grep` por imports profundos (`from packages.core_domain.<módulo> import`) antes; `__all__` reflete o que o `__init__` já reexporta, não reduz. |
| Teste de estabilidade vira ruído (falha a cada adição legítima) | Média | Fricção | O teste compara com uma lista versionada e falha pedindo atualização **consciente** da lista + nota no PR — é um lembrete, não um bloqueio. |

### R6 — Risco transversal: mudança concorrente no repo

O repo tem alterações não commitadas em `apps/web` e `docs/CHECKLIST`. Livestock
e Core evoluem semanalmente.

| Risco | Mitigação |
|---|---|
| Rebase doloroso se a reorganização demorar | Etapas pequenas e mescladas rápido; nunca um branch de reorganização de longa duração. |
| Colisão com trabalho de Livestock em `apps/api` | Coordenar a janela do Passo 3 (mover `livestock_*.py`) com quem mexe em rotas de Livestock. |

---

## 3. Critérios de aceite por etapa (resumo)

| Etapa | Verde significa |
|---|---|
| Passo 1 (teste de fronteira) | Suite `tests/architecture` passa; Livestock sem violação; teste-guarda garante que ≥1 vertical foi checada. |
| Passo 2 (migrations por vertical) | `pg_dump --schema-only` idêntico antes/depois; `tests/integration` (85) verdes sem alterar asserção; `alembic check` limpo. |
| Passo 3 (`apps/api/<vertical>/`) | `/openapi.json` idêntico; `tests/api` verdes; `grep` não acha `apps.api.livestock_` fora de `apps/api/livestock/`. |
| Passo 4 (dispatch worker) | Teste com envelope real de Livestock passa; reconciliação de outbox inalterada. |
| Passo 5 (superfície pública) | `mypy` + `pytest` verdes; lista pública versionada revisada no PR. |

---

## 4. Plano de reversão

- **Passos 1, 3, 4, 5:** revert do PR. Sem estado externo afetado.
- **Passo 2 (migrations):** o mais delicado. Reversão = revert do PR **e**
  confirmação de que nenhum ambiente aplicou uma revisão com novo caminho. Como
  as revisões não são reescritas (só movidas), o `alembic_version` no banco
  continua válido; o revert restaura o `version_locations` único. Fazer o Passo 2
  **primeiro em Livestock, sozinho**, num PR que não depende de mais nada, é o
  que torna a reversão barata.

---

## 5. Recomendação de sequência (menor risco primeiro)

1. Passo 1 — teste de fronteira generalizado (só teste).
2. Passo 3 — `apps/api/<vertical>/` + registry (mecânico).
3. Passo 4 — dispatch do worker.
4. **Decisão:** Passo 2A (Asset com migrations próprias, Livestock intocado) para
   desbloquear Asset **ou** Passo 2B (extrair Livestock também) se a assimetria
   for considerada inaceitável. 2A é o caminho de menor risco.
5. Passo 5 — congelar superfície pública (pode vir antes do 1º slice de Asset).
6. **Só então:** trilha separada do primeiro slice de Asset
   (`ASSET_VERTICAL_BOOTSTRAP_PLAN.md`), com ADR/plano próprios.

---

## 6. Reconciliação com `PARALLEL_VERTICAL_SAFETY` (10/09/2026)

Este documento continua válido como catálogo de riscos, com três correções:

- **R1 / Passo 2A não é "sem tocar no que funciona".** Assim que Asset tem cabeça de migration própria, há
  duas cabeças e `alembic upgrade head` (singular) falha em toda a CI, `CLAUDE.md`, `AGENTS.md`,
  `DEVELOPMENT.md`, `apps/validacao/*` e no checklist. A troca `head → heads` é repo‑wide e vira um PR de
  Shared Integration próprio (S‑M1 de `docs/architecture/MIGRATION_CONCURRENCY_STRATEGY.md`),
  comportamentalmente neutro enquanto houver uma cabeça.
- **`alembic check` por vertical exige `include_object`/`include_name` por `titan.module_owner`.** O `env.py`
  atual filtra por **schema** (`include_managed_schema`), não por dono; sem o filtro por dono, um `env.py` de
  vertical que importe só as próprias tabelas faz o `alembic check` propor `DROP` das tabelas das outras
  verticais. Peça ausente deste documento, adicionada em `MIGRATION_CONCURRENCY_STRATEGY.md` S‑M2.
- **Sequência.** A estratégia oficial passa a ser **Opção D → C** de
  `MIGRATION_CONCURRENCY_STRATEGY.md` §4 (cadeia de Livestock intocada agora; extração numa janela de
  integração coordenada com o Codex; `BLOCKED_WHILE_LIVESTOCK_ACTIVE`).
