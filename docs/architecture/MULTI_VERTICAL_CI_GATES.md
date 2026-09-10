# MULTI_VERTICAL_CI_GATES — Portões mecânicos para desenvolvimento paralelo de verticais

**Status:** Proposta para revisão. Documentação apenas — nenhum workflow/teste alterado.
**Data:** 10 de setembro de 2026
**Base:** `PARALLEL_VERTICAL_DEVELOPMENT_PROTOCOL.md`, `VERTICAL_OWNERSHIP_MATRIX.md`, `.github/workflows/quality.yml`.

Princípio (restrição §5): **não depender só de disciplina de desenvolvedor**. Cada regra abaixo é
mecanicamente verificável. Nada aqui é implementado nesta fase; é o desenho a executar em PRs de Shared
Integration, cada um pequeno.

---

## 1. Pirâmide de testes em três níveis

### Nível 1 — Portão rápido de vertical
Gatilho: PR **exclusivo de uma vertical** (só caminhos de uma lane).
Roda: testes de domínio/aplicação/infra daquela vertical + `tests/architecture` + `ruff`/`mypy` do escopo
tocado. **Não** roda a suíte da outra vertical.
Objetivo: retorno em minutos; as lanes não esperam uma pela outra.

### Nível 2 — Compatibilidade compartilhada
Gatilho: PR que toca **qualquer** caminho Lane C (`core_*`, `shared_kernel`, composição de migrations/API/
worker, config global) — ou seja, `CHANGE_CLASS=SHARED_INTEGRATION`.
Roda: **todos** os testes do Core + **todos** de Livestock + **todos** de Asset + `tests/architecture` +
`tests/integration` + testes de migration.
Regra dura: **nenhuma asserção existente é enfraquecida** para o *shared change* passar (§6).

### Nível 3 — Portão completo pré‑merge
Gatilho: antes de merge em `integration/main`.
Roda: suíte completa do repositório. Livestock verde **e** Asset verde **e** Core verde, juntos
(matriz de compatibilidade, `SHARED_CHANGE_PROTOCOL.md` §6).

> Implementação sugerida na CI atual (`quality.yml`, job único hoje): dividir em jobs por escopo com
> `paths:`/filtro de caminho para o Nível 1, e um job "shared" disparado por caminho Lane C para o Nível 2/3.

---

## 2. File Ownership Guard

Um *check* de CI que, dado o conjunto de arquivos do PR e o manifesto
[`verticals.toml`](VERTICAL_OWNERSHIP_MATRIX.md) + a matriz de caminhos:

- classifica cada arquivo como `livestock` / `asset` / `shared` / `unclassified`;
- **FALHA** se um PR rotulado Lane A toca caminho `asset`‑owned;
- **FALHA** se um PR rotulado Lane B toca caminho `livestock`‑owned;
- **FALHA** se um PR toca caminho Lane C sem o rótulo `CHANGE_CLASS=SHARED_INTEGRATION`;
- **FALHA** se algum arquivo cai em `unclassified` (obriga classificação explícita antes da escrita);
- um PR `CHANGE_CLASS=SHARED_INTEGRATION` **não** pode conter também caminhos de feature de vertical
  (proíbe o PR misto — `SHARED_CHANGE_PROTOCOL.md` §2).

A lane do PR vem de um rótulo/*prefix* de branch (`vertical/asset/*`, `vertical/livestock/*`,
`integration/*` — ver [`AGENT_WORKTREE_SAFETY.md`](AGENT_WORKTREE_SAFETY.md)), não de heurística sobre o
conteúdo.

---

## 3. Teste de dependência que escala para N verticais

Substitui a proposta `VERTICAL_PACKAGES = ("livestock", "asset")` *hard‑coded* de `DEPENDENCY_RULES.md` §7 por
**fonte da verdade explícita + lógica genérica** (resolve **M1** e **M2** do
[`PHASE0_ADVERSARIAL_REVIEW.md`](PHASE0_ADVERSARIAL_REVIEW.md)).

Comportamento desejado, sobre a lista de verticais **lida de `verticals.toml`**:

```
para cada vertical A registrada:            core_*  não importa  A
para cada par A != B de verticais:          A       não importa  B
para cada vertical A:                       A_domain      não importa A_application nem *_infrastructure
                                            A_application não importa fastapi/sqlalchemy
                                            imports de A_application/A_infrastructure para core_infrastructure
                                              ⊆ allowlist de DEPENDENCY_RULES.md §5
exceção de migrations:                       qualquer env.py sob packages/*/persistence/migrations/ pode
                                              importar tabelas do Core (alvo de FK) e as próprias
```

Contrato da guarda `require_existing_root` sob N verticais (resolve **M1**):

- se uma vertical está **registrada no manifesto** e seu `package_roots` **existe** → é varrida;
- se está registrada mas **ainda não existe no disco** (ex.: `asset` no dia do Passo 1) → é **pulada**, e o
  teste registra "pulada: não criada";
- **FALHA** se *nenhuma* vertical registrada foi efetivamente varrida (mesma filosofia do
  `require_existing_root` atual — evita aprovação vazia);
- **FALHA** se uma vertical registrada existe no disco mas o teste não conseguiu varrê‑la (regressão de
  configuração).
- A lista de verticais **nunca** é inferida do sistema de arquivos (evita o red flag "trata pacote arbitrário
  como vertical").

`sustainment` entra na lista **como parte de `asset`** ou como vertical própria conforme a decisão **B**
([`DECISIONS_REQUIRED_PHASE0.md`](DECISIONS_REQUIRED_PHASE0.md)); até lá, o Passo 1 registra só
`("livestock", "asset")` e adia `sustainment` por escrito.

---

## 4. Migration ownership gate

Para cada arquivo de revisão Alembic novo/modificado no PR:

1. resolver `vertical_id`/dono pela `version_locations` de origem (manifesto `migration_locations`/
   `migration_owner`);
2. via AST/inspeção, coletar as operações (`op.create_table`, `op.drop_table`, `op.add_column`,
   `op.drop_column`, `op.alter_column`, `op.rename_table`, `op.execute("...DDL...")`) e as tabelas/schemas
   alvo;
3. resolver o `titan.module_owner` de cada tabela alvo (do `info`/comentário já presente, ou do manifesto);
4. **FALHAR** se uma operação atinge tabela cujo dono ≠ dono da revisão — salvo operação **puramente
   aditiva** sobre alvo de FK do Core explicitamente sancionado;
5. **FALHAR** se uma revisão de Core faz `alter/drop` de tabela de vertical (constituição §42 — "core
   migration muta tabela de vertical silenciosamente");
6. **FALHAR** se `op.execute` contém DDL que o *parser* não consegue atribuir a um dono (fail‑closed).

Isto não substitui convenção de nome de arquivo — **complementa** com verificação do conteúdo.

---

## 5. Isolamento de acesso à persistência (além de import)

Teste de import é necessário mas insuficiente: `asset_infrastructure` poderia rodar SQL cru contra tabela de
Livestock sem importar pacote de Livestock. Camadas de verificação:

| Camada | Verifica |
|---|---|
| **Ownership de tabela SQLAlchemy** | Toda `Table` definida em `asset_infrastructure` tem `info["titan.module_owner"] == "titan_asset"`. Teste falha se faltar ou divergir. |
| **AST de SQL literal** | Varre `asset_infrastructure` por `text("...")`, `op.execute("...")`, f‑strings SQL; extrai nomes de tabela/schema; **falha** se referenciam tabela cujo dono ∈ {outras verticais}. Heurística explícita, allowlist para nomes ambíguos. |
| **Inspeção de schema (integração)** | Sob a role restrita de runtime, um teste tenta `SELECT` numa tabela `titan_livestock.*` a partir de um repositório de Asset e **espera falha** (import + RLS). |
| **Privilégios de banco (avaliar, não obrigatório)** | Se a role de runtime puder ser particionada por `GRANT` por schema/tabela sem *overengineering*, isso torna o isolamento uma garantia do SGBD. Registrado como opção; não pré‑implementar. |

Meta: `asset_infrastructure` usa **tabelas autorizadas do Core + tabelas de Asset**, nunca de Livestock — e
vice‑versa.

---

## 6. "No test weakening" (constituição §21)

Padrão **proibido**: *"a vertical nova quebrou um teste antigo, então relaxa o teste antigo"*. Quando um teste
existente falha por causa de trabalho de outra lane ou de um shared change, decidir:

- **A —** o teste expõe regressão real → **corrigir a implementação**.
- **B —** o teste codificava premissa de "uma vertical só" → **substituir por um invariante N‑vertical mais
  forte**, com evidência, em PR de Shared Integration.
- **C —** o comportamento mudou por ADR aprovada → **atualizar o teste explicitamente** e documentar o
  impacto no PR e no checklist.

Nunca afrouxar salvaguarda em silêncio. O portão de CI sinaliza *diffs* que removem/enfraquecem `assert` em
`tests/livestock_*`, `tests/core_*`, `tests/architecture` dentro de um PR que não seja `CHANGE_CLASS` com
justificativa B/C.

---

## 7. Colisão de namespace de evento/mensagem

Cada `message_type`/tipo de evento tem **exatamente um** módulo dono. Namespaces por prefixo (`core.*`,
`livestock.*`, `asset.*`, `sustainment.*` — validar contra as convenções já existentes antes de fixar nomes).

Teste de colisão: coletar todos os identificadores de evento/mensagem declarados em `packages/*` e
`apps/worker/*`; **falhar** se dois módulos de donos diferentes declaram o mesmo identificador, ou se um
identificador usa prefixo de namespace que não é do seu dono (mapa prefixo→dono vem de `verticals.toml`
`event_namespaces`). Cobre o requisito da restrição §14.

---

## 8. Transaction boundary gate (resolve M3)

Invariante de runtime (restrição §16): uma unidade de trabalho envolve **dados de uma vertical + capacidades
autorizadas do Core**; nunca muta duas verticais irmãs na mesma transação.

Verificação proposta (integração, não só estático):

- No *composition root* de cada requisição/handler, a sessão/transação carrega um `vertical_id` de contexto
  (o mesmo já usado para `SET LOCAL` de RLS). Um *guard* de teste falha se, dentro de uma transação, um
  repositório com `titan.module_owner` diferente do `vertical_id` de contexto executa escrita.
- Colaboração cross‑vertical, se algum dia necessária, é por **evento publicado** ou **contrato público** —
  nunca transação compartilhada, salvo ADR futura que demonstre invariante de consistência forte exigindo
  outro modelo (constituição §29; não inventar agora).

---

## 9. Ordem de introdução dos portões (PRs de Shared Integration, pequenos)

| # | Portão | Depende de |
|---|---|---|
| G1 | `verticals.toml` + File Ownership Guard + rótulo `CHANGE_CLASS` na CI | — |
| G2 | Teste de dependência N‑vertical (§3) + contrato da guarda `require_existing_root` | G1 |
| G3 | Split da CI em Nível 1 / Nível 2‑3 por filtro de caminho | G1 |
| G4 | Migration ownership gate (§4) | G1, `MIGRATION_CONCURRENCY_STRATEGY.md` S‑M2 |
| G5 | Isolamento de acesso à persistência (§5) | G1 |
| G6 | Colisão de namespace de evento (§7) | G1 |
| G7 | Transaction boundary gate (§8) | G1; provavelmente após o 1º slice de Asset ter serviços |

G1–G3 podem preceder qualquer código de Asset e valem imediatamente para Livestock (Livestock permanece
verde: o guard só reprova PR **misto**, e os PRs de Livestock não são mistos).
