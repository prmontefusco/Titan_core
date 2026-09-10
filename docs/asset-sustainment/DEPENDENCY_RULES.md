# DEPENDENCY_RULES — Regras formais de dependência entre módulos

**Versão:** 1.0
**Status:** Proposta para revisão (Fase 3)
**Data:** 10 de setembro de 2026
**Base:** ADR-0001 §"Direção das dependências", `ARCHITECTURE.md`,
`tests/architecture/test_dependency_boundaries.py`

Estas regras estendem — não substituem — as já vigentes. A única novidade
conceitual é a regra **vertical ⊥ vertical**, que hoje é verdadeira por acaso
(só existe uma vertical) e passa a ser verdadeira por contrato.

---

## 1. Nomenclatura de camadas

Para qualquer módulo `X` (Core ou vertical):

```
X_domain          invariantes, entidades, contratos, eventos de domínio
X_application     casos de uso, portas (Protocols), orquestração
X_infrastructure  adapters: persistência, mensageria, HTTP externo, crypto
```

Prefixos: `core_*`, `livestock_*`, `asset_*`. `shared_kernel` é camada única.

---

## 2. Matriz de dependência permitida

Legenda: ✅ permitido · ❌ proibido (falha de build/teste) · ➖ N/A

| De ↓  \  Para → | `shared_kernel` | `core_domain` | `core_application` | `core_infrastructure` | `livestock_*` | `asset_*` | `apps/*` | frameworks (fastapi, sqlalchemy) |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| `shared_kernel` | ➖ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `core_domain` | ✅ | ➖ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `core_application` | ✅ | ✅ | ➖ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `core_infrastructure` | ✅ | ✅ | ✅ | ➖ | ❌ ¹ | ❌ ¹ | ❌ | ✅ |
| `livestock_domain` | ✅ | ✅ | ❌ | ❌ | ➖ | ❌ | ❌ | ❌ |
| `livestock_application` | ✅ | ✅ | ✅ | ✅ ² | ➖ | ❌ | ❌ | ❌ ³ |
| `livestock_infrastructure` | ✅ | ✅ | ✅ | ✅ | ➖ | ❌ | ❌ | ✅ |
| `asset_domain` | ✅ | ✅ | ❌ | ❌ | ❌ | ➖ | ❌ | ❌ |
| `asset_application` | ✅ | ✅ | ✅ | ✅ ² | ❌ | ➖ | ❌ | ❌ ³ |
| `asset_infrastructure` | ✅ | ✅ | ✅ | ✅ | ❌ | ➖ | ❌ | ✅ |
| `apps/*` (composição) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ➖ | ✅ |

**Notas:**

1. **`core_infrastructure` → vertical: proibido, com exatamente uma exceção
   nomeada** — o ponto de composição de migrations
   (`.../migrations/env.py`), enquanto as migrations das verticais viverem sob o
   Core. A regra alvo (`REPOSITORY_STRUCTURE_PROPOSAL.md`) elimina até essa
   exceção movendo o ambiente de migrations para cada vertical.
2. **vertical_application → `core_infrastructure`: permitido apenas para portas
   de persistência sancionadas** (hoje: `core_infrastructure.persistence.events`,
   `core_infrastructure.persistence.organizations`). É acoplamento tolerado, não
   incentivado; a direção desejada é depender de contratos de
   `core_application`. Ver §5.
3. **vertical_application → framework (fastapi/sqlalchemy): proibido.** Caso de
   uso não conhece HTTP nem ORM. `vertical_infrastructure` conhece.

---

## 3. Regras em forma canônica (as pedidas)

```
asset_*        -> core_*         ALLOWED
livestock_*    -> core_*         ALLOWED
shared_kernel  -> (nada)         (base do grafo)

asset_*        -> livestock_*    FORBIDDEN
livestock_*    -> asset_*        FORBIDDEN

core_*         -> livestock_*    FORBIDDEN
core_*         -> asset_*        FORBIDDEN
core_*         -> apps/*         FORBIDDEN

<vertical>_domain      -> <vertical>_application     FORBIDDEN  (dependência aponta para dentro)
<vertical>_domain      -> qualquer *_infrastructure  FORBIDDEN
<vertical>_*           -> fastapi | sqlalchemy       FORBIDDEN em domain e application
```

Exceção única e explícita, com data de validade:

```
core_infrastructure/persistence/migrations/env.py -> <vertical>_infrastructure.persistence
    ALLOWED enquanto o ambiente de migrations for único.
    Alvo: remover ao dar a cada vertical seu próprio ambiente Alembic.
```

---

## 4. `shared_kernel` — política de contenção

`shared_kernel` **deve permanecer extremamente pequeno**. Hoje: 5 arquivos, 321
LOC (`identifiers`, `references`, `temporal`, `serialization`).

Critérios cumulativos para admitir algo em `shared_kernel`:

1. **Universal de verdade** — usado (ou claramente será) por Core **e** por mais
   de uma vertical.
2. **Sem estado, sem I/O** — nada de persistência, rede, relógio de parede
   concreto (o `Clock` é Protocol; `SystemClock` é a única impl concreta e
   trivial).
3. **Contrato, não conveniência** — se for "função utilitária que deu jeito",
   não entra.
4. **Estável** — mudança quebra todo o grafo; só entra o que já está maduro.

**Proibido:** transformar `shared_kernel` em pasta `common`/`utils`/`helpers`.
Helper de uma vertical mora na vertical. Helper do Core mora no Core. Um teste
deve falhar se `shared_kernel` crescer além de um limite de arquivos/LOC
acordado (ex.: sinalizar acima de ~600 LOC ou ~8 arquivos) — o limite é um
alarme de revisão, não um corte rígido.

---

## 5. Superfície pública do Core (o que uma vertical pode importar)

**Permitido:**

- `packages.shared_kernel` e submódulos.
- `packages.core_domain` e submódulos (contratos, entidades, eventos, VOs).
- `packages.core_application` — **serviços e portas** reexportados no `__init__`.
- `packages.core_infrastructure.persistence.events` — porta de persistência de
  eventos de domínio (`DomainEventRepository`, `StoredDomainEvent`,
  `EventAppendConflict`, `EventIntegrityEd25519Signer`).
- `packages.core_infrastructure.persistence.organizations` — `MetaData`
  compartilhada e `set_local_organization_context` (necessário para RLS + FK).
- `packages.core_infrastructure.organization_context` /
  `packages.core_application.organization_context` — construção de
  `OrganizationContext` a partir do principal autenticado.

**Desencorajado (tolerado só onde já existe, não expandir):**

- Importar repositórios concretos de outros agregados do Core
  (`core_infrastructure.persistence.evaluation`, `...decision`) diretamente da
  vertical. Preferir o serviço de `core_application` correspondente.

**Proibido:**

- Qualquer módulo `core_infrastructure.persistence.<agregado>` que não esteja na
  lista de permitidos acima, importado por uma vertical, salvo para registrar
  tabela-alvo de FK no ambiente de migrations **da própria vertical**.
- Importar de `apps/*`.
- Importar internals não reexportados (qualquer coisa fora do `__init__` de
  `core_domain`/`core_application` deve ser tratada como privada; hoje não há
  `__all__`, então isto é convenção até o Passo 5 do plano torná-la verificável).

---

## 6. Isolamento vertical ⊥ vertical (a regra nova)

- `asset_*` **nunca** importa `livestock_*` e vice-versa — nem domain, nem
  application, nem infrastructure, nem tabelas, nem tipos, nem constantes.
- Nenhuma vertical lê tabelas de outra vertical, mesmo compartilhando o schema
  `core_audit` e o banco. Colaboração entre verticais (se algum dia necessária)
  ocorre por **evento publicado** ou **contrato público**, nunca por acesso
  direto — igual à regra Core/vertical (ADR-0001 §Ownership).
- Um `apps/*` **pode** compor as duas (é o papel da composição), mas um router de
  `apps/api/asset/` não importa `apps/api/livestock/` e vice-versa.

---

## 7. Enforcement (como estas regras deixam de ser texto)

Estender `tests/architecture/test_dependency_boundaries.py`:

1. Substituir a constante `CORE_PACKAGES` por duas listas:
   `CORE_PACKAGES` e `VERTICAL_PACKAGES = ("livestock", "asset")` (Asset entra na
   lista mesmo antes de existir; `require_existing_root` deve ser tolerante a
   vertical ainda não criada, ou o teste parametrizado pula o que não existe —
   decisão a registrar no PR do Passo 1).
2. Parametrizar `test_core_does_not_import_verticals` sobre `VERTICAL_PACKAGES`.
3. Novo teste `test_verticals_do_not_import_each_other`: para cada par ordenado
   `(a, b)` de verticais distintas, nenhum módulo de `a_*` importa `b_*`.
4. Novo teste `test_vertical_domain_does_not_import_application_or_infra`:
   generaliza para toda vertical a regra já existente para `core_domain`.
5. Novo teste `test_vertical_application_does_not_import_framework`.
6. Novo teste `test_vertical_application_infra_imports_are_allowlisted`: imports
   de `<vertical>_application`/`<vertical>_infrastructure` para
   `core_infrastructure` só podem alcançar a allowlist da §5.
7. Manter a exceção `MIGRATIONS_COMPOSITION_ROOT`, mas generalizá-la para
   "qualquer `env.py` sob `packages/*/persistence/migrations/`", de modo que o
   ambiente de migrations **de cada vertical** possa importar as próprias tabelas
   e as tabelas-alvo de FK do Core sem violar a fronteira.

O Passo 1 do `ASSET_VERTICAL_BOOTSTRAP_PLAN.md` é **apenas** esta extensão de
teste, com Livestock permanecendo verde e nenhum código de produção movido.

---

## 8. O que estas regras deliberadamente **não** decidem

- Estratégia física de schemas/bancos por vertical (permanece: schema
  `core_audit` único, `MetaData` compartilhada, RLS por Organization).
- Se o Core vira pacote versionado separado (Opção B em
  `REPOSITORY_STRUCTURE_PROPOSAL.md`) — decisão futura, não agora.
- Formato dos contratos de integração externa de cada vertical (ERP/PLM/logística
  são propriedade da vertical).
- Estratégia de frontend multi-vertical.

---

## 9. Reconciliação com `PARALLEL_VERTICAL_SAFETY` (10/09/2026)

Estas regras permanecem a base normativa de dependência. Acréscimos sob desenvolvimento paralelo:

- **Fonte da verdade das verticais.** A lista `VERTICAL_PACKAGES = ("livestock", "asset")` da §7 passa a ser
  lida de um manifesto explícito (`docs/architecture/verticals.toml`), com a lógica de teste **genérica** sobre
  ela — para que a vertical nº 3 não exija reescrever `tests/architecture`. Detalhe em
  `docs/architecture/MULTI_VERTICAL_CI_GATES.md` §3 e `VERTICAL_OWNERSHIP_MATRIX.md` §2.
- **Contrato da guarda para N verticais.** `require_existing_root` ganha semântica nova: pula vertical
  registrada mas ainda não criada; **falha** se nenhuma vertical registrada foi varrida; **falha** se uma
  vertical que existe no disco não foi varrida. (Resolve M1 do `PHASE0_ADVERSARIAL_REVIEW.md`.)
- **`sustainment`.** Fica **fora** de `VERTICAL_PACKAGES` no Passo 1 até a decisão B
  (`docs/architecture/DECISIONS_REQUIRED_PHASE0.md`): se `sustainment_*` é a mesma vertical de `asset_*`
  (pode referenciá‑la) ou vertical irmã isolada. Escrever a decisão antes de congelar o teste vertical⊥vertical.
- **Isolamento não é só import.** Import test é necessário mas insuficiente — acrescentam‑se portões de
  ownership de migration (`titan.module_owner`), detecção de SQL cru contra tabela de outra vertical, colisão
  de namespace de evento e fronteira de transação. Detalhe em `MULTI_VERTICAL_CI_GATES.md`.
- **Exceção de migrations.** A exceção única (`.../migrations/env.py -> <vertical>_infrastructure`) é
  generalizada para "qualquer `env.py` sob `packages/*/persistence/migrations/`" e passa a ter **escopo por
  `titan.module_owner`**, não só por schema.
