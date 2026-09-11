# NEW_VERTICAL_BOOTSTRAP_STANDARD — Onboarding genérico de uma vertical Titan (nº 3, 4, 5, …)

**Status:** Proposta para revisão. Documentação apenas.
**Data:** 10 de setembro de 2026
**Objetivo (restrição §22):** adicionar uma vertical **sem** outro redesenho arquitetural.

---

## 1. O que uma vertical nova precisa fazer

| Passo | Ação | Artefato |
|---|---|---|
| 1 | Escolher `vertical_id` estável, único, minúsculo (não é o nome de exibição). | entrada em `verticals.toml` |
| 2 | Declarar pacotes próprios: `packages/<id>_domain`, `_application`, `_infrastructure` (só quando o 1º slice os exercer — sem pacote vazio). | `package_roots` |
| 3 | Registrar as fronteiras de arquitetura: a vertical entra na lista lida por `tests/architecture` a partir do manifesto; nenhuma lógica de teste nova é escrita. | `verticals.toml` |
| 4 | Definir namespace de evento/mensagem (`<id>.*`) com dono único. | `event_namespaces` |
| 5 | Definir ownership de banco/migration: `migration_owner = titan_<id>`, `version_locations` próprio, `env.py` próprio com filtro por `titan.module_owner` + allowlist de FK do Core (padrão da Opção C em [`MIGRATION_CONCURRENCY_STRATEGY.md`](MIGRATION_CONCURRENCY_STRATEGY.md)). | `migration_owner`, `migration_locations` |
| 6 | Consumir **apenas** contratos públicos do Core (`core_domain`/`core_application` reexportados + allowlist de `DEPENDENCY_RULES.md` §5). Necessidade além disso → `CORE_CHANGE_REQUEST`. | — |
| 7 | Adicionar o adapter de composição: `apps/api/<id>/` (routers + `dependencies.py`) registrado no `_registry.py`; `apps/worker/<id>_handlers.py` registrado no `dispatch.py`. | subpacote + registro |
| 8 | Adicionar os testes da vertical (`tests/<id>_domain`, `_application`, `_infrastructure`). | suíte da vertical |
| 9 | Provar que não importa nem consulta tabelas de irmãs (portões de [`MULTI_VERTICAL_CI_GATES.md`](MULTI_VERTICAL_CI_GATES.md) §3 e §5). | CI verde |
| 10 | Passar o portão de compatibilidade global (Nível 3): Core + todas as verticais verdes juntas. | CI verde |

---

## 2. O que uma vertical nova **não** pode precisar fazer

- copiar `packages/core_*` (fork proibido — ADR‑0080);
- editar código de domínio de vertical existente;
- mover pacotes existentes;
- importar tabelas de irmãs;
- criar *helper* compartilhado "porque o código parece parecido" (constituição §38; AGENTS.md §"Regras
  obrigatórias" — nada de abstração para necessidade futura sem uso atual);
- trocar `head`→`heads` de novo (feito uma vez, em `MIGRATION_CONCURRENCY_STRATEGY.md` S‑M1);
- reescrever `tests/architecture` (a lógica já é genérica sobre `verticals.toml`).

Se qualquer item acima for necessário para adicionar a vertical nº 3, a arquitetura **não está generalizada**
— parar e revisar.

---

## 3. Manifesto/registro de verticais (restrição §32)

Recomendação: **sim** a um registro pequeno e explícito, **na camada de composição/documentação**, não no
Core.

- Arquivo: `docs/architecture/verticals.toml` (fonte declarativa) — descrito em
  [`VERTICAL_OWNERSHIP_MATRIX.md`](VERTICAL_OWNERSHIP_MATRIX.md) §2.
- Contém **apenas fatos de composição técnica**: `vertical_id`, roots de pacote/teste, entrypoint de
  registro HTTP, entrypoint de registro no worker, ownership de migration, namespaces de evento, roots de doc.
- **Não** contém comportamento de domínio. **Não** faz `packages/core_*` depender de vertical (é lido por
  `tests/` e CI e, no máximo, por um módulo de composição em `apps/`).
- Só implementar quando houver evidência de que simplifica o suporte a N verticais — o gatilho é o Passo 1 de
  [`MULTI_VERTICAL_CI_GATES.md`](MULTI_VERTICAL_CI_GATES.md) (G1). Até lá, a lista vive só neste documento.

Um entrypoint de registro em `apps/` (ex.: `apps/api/_registry.py` que itera adapters de vertical) **pode**
importar cada vertical — é o papel da composição (`DEPENDENCY_RULES.md` §2 permite `apps/* → vertical`). O
Core continua proibido de importar verticais.

---

## 4. Estrutura de PRs para uma vertical nova

```
PR 0 (Shared Integration)   registrar <id> em verticals.toml; adaptar _registry.py / dispatch.py para
                            aceitar o novo adapter (aditivo, sem tocar Livestock/Asset)
PR 1 (Lane <id>)            packages/<id>_domain do 1º slice + testes de invariante
PR 2 (Lane <id>)            packages/<id>_infrastructure/persistence/migrations (env.py + 1ª revisão)
PR 3 (Lane <id>)            packages/<id>_application do 1º slice
PR 4 (Lane <id>)            apps/api/<id>/ + registro; apps/worker/<id>_handlers.py se houver mensagem
PR 5 (Lane <id>)            suíte de integração ponta a ponta do slice; apps/validacao/<id>/
```

Nenhum PR de Lane `<id>` altera `packages/core_*`. Se precisar, vira PR de Shared Integration próprio, com CCR
e (se muda contrato) ADR.

---

## 5. Validação do padrão — experimento mental "Vertical C"

Aplicar o cenário de aceitação (`PARALLEL_VERTICAL_DEVELOPMENT_PROTOCOL.md` §9) com três verticais autorando
ao mesmo tempo. O padrão passa se:

- `verticals.toml` ganha 1 entrada; `tests/architecture` não muda;
- Vertical C tem `version_locations` e *branch label* próprios; `alembic upgrade heads` compõe as três;
- nenhum `env.py` de A ou B é tocado;
- `_registry.py`/`dispatch.py` ganham 1 registro aditivo cada;
- os portões de ownership, namespace e acesso à persistência cobrem C automaticamente (são genéricos sobre o
  manifesto);
- Livestock e Asset não recebem nenhum *diff*.
