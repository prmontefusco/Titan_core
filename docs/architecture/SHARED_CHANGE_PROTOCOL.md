# SHARED_CHANGE_PROTOCOL — Como mudar o que é compartilhado sem quebrar uma vertical ativa

**Status:** Proposta para revisão. Documentação apenas.
**Data:** 10 de setembro de 2026
**Base:** `PARALLEL_VERTICAL_DEVELOPMENT_PROTOCOL.md` (Lane C), ADR‑0001, constituição §35.

---

## 1. O que é "Shared Integration"

Qualquer mudança que toque um caminho **Lane C** (lista em
[`VERTICAL_OWNERSHIP_MATRIX.md`](VERTICAL_OWNERSHIP_MATRIX.md) §3). Em particular, é **sempre** Shared
Integration mudar (restrição §35):

- `packages/shared_kernel`, `packages/core_*` — contrato, comportamento ou schema;
- `core_identity`, infraestrutura de `core_audit`, primitivas de RLS, `organization_context`;
- integridade de eventos, `outbox`/`inbox`;
- composição do Alembic (`alembic.ini`, `env.py`, `version_locations`);
- composição de `apps/api` (`main.py`, futuro `_registry.py`);
- composição de `apps/worker` (`main.py`, futuro `dispatch.py`);
- `pyproject.toml` / `uv.lock`;
- `.github/workflows/**`, `tests/architecture/**`.

Uma vertical **não tem autoridade** para mudar esses mecanismos diretamente.

---

## 2. Regra de separação de PR

**Proibido** um PR do tipo *"implementa inventário de Asset + refatora o Core + move a API de Livestock"*.

Em vez disso:

```
PR A  →  Shared preparation only        (Lane C, CHANGE_CLASS=SHARED_INTEGRATION)
PR B  →  Asset feature only             (Lane B)
PR C  →  Livestock feature only         (Lane A)
```

Cada um independentemente revisável e revertível. PR B/C só começam depois que PR A fez merge e as verticais
atualizaram o *baseline* (`PARALLEL_VERTICAL_DEVELOPMENT_PROTOCOL.md` §7).

---

## 3. Questionário obrigatório de um PR de Shared Integration

Todo PR `CHANGE_CLASS=SHARED_INTEGRATION` responde, no corpo:

1. Por que é necessário?
2. Qual vertical pediu?
3. É de fato genérico (horizontal), não específico de uma vertical?
4. Pode quebrar outra vertical? Como isso foi testado?
5. Muda contrato público do Core?
6. Muda comportamento de banco (schema, RLS, integridade)?
7. Muda composição de API?
8. Muda composição de worker?
9. Muda autorização?
10. Muda semântica de auditoria/integridade?
11. Pode ser revertido isoladamente?

Se **5–10** têm algum "sim", o PR exige o **Nível 2** de CI
([`MULTI_VERTICAL_CI_GATES.md`](MULTI_VERTICAL_CI_GATES.md)) e revisão arquitetural (Claude) antes do merge.

---

## 4. CORE_CHANGE_REQUEST

Antes de um PR de Shared Integration que **mude o Core**, a vertical solicitante abre um
**CORE_CHANGE_REQUEST** ([template](CORE_CHANGE_REQUEST_TEMPLATE.md)) e **para** a parte dependente da
implementação até a revisão. O CCR prova horizontalidade, mapeia impacto em Livestock, compatibilidade,
autorização, auditoria/integridade, migrations e testes, e responde: *"a vertical resolve isto localmente sem
violar arquitetura? SIM/NÃO"*. Se SIM, não há mudança de Core.

---

## 5. Evolução de contrato do Core em duas fases (nunca "flag day")

Enquanto Livestock e Asset evoluem em paralelo, uma mudança de contrato do Core **não** pode forçar a outra
vertical a mudar no mesmo instante. Sequência obrigatória:

```
FASE A   Core adiciona a nova capacidade SEM remover a antiga.           (Shared Integration PR)
FASE B   Asset adota a nova capacidade.                                  (Lane B, quando quiser)
FASE C   Livestock adota a nova capacidade, se útil, independentemente.  (Lane A, quando quiser)
FASE D   Só depois de todos os consumidores migrados: remover o contrato antigo.  (Shared Integration PR)
         Pré‑condição de D: prova (grep + teste) de que o contrato antigo não tem mais consumidor.
```

Corolário (restrição §33): se um contrato do Core mudar de forma **não** retrocompatível, todos os
consumidores afetados são atualizados **no mesmo PR de Shared Integration** — o que só é aceitável para
mudanças pequenas; o caminho normal é a evolução escalonada A→D.

---

## 6. Matriz de compatibilidade do repositório

`integration/main` só é válido se **Core + toda vertical presente = verde junto**. Nenhuma vertical faz merge
deixando outra vermelha "para consertar depois". Se um PR de Lane C deixa Livestock vermelho, ele **não
mergeia** — corrige‑se o Core ou o consumo, nunca se enfraquece o teste de Livestock (constituição §21;
[`MULTI_VERTICAL_CI_GATES.md`](MULTI_VERTICAL_CI_GATES.md) §"No test weakening").

---

## 7. Regressão de contrato preservada

Para PR de Shared Integration, proteger no mínimo (restrição §20):

- paths e response schemas do OpenAPI **existentes** de Livestock;
- códigos de erro existentes;
- envelopes de evento existentes;
- semântica de schema de banco;
- comportamento de autorização e de RLS;
- semântica de evento de auditoria.

**Refactor puro de composição, sem feature nova:** OpenAPI global **byte‑idêntico** antes/depois.
**PR que adiciona rota de Asset:** o OpenAPI global cresce legitimamente — exigir apenas
*"subconjunto de contrato de Livestock: inalterado"* + *"contrato novo de Asset: aditivo"*.

---

## 8. Docs compartilhados

Documentação arquitetural universal (`docs/architecture/**`, `docs/adr/**`, `ARCHITECTURE.md`, `DOMAIN.md`) só
muda por Shared Integration. Asset **não** reescreve docs de Livestock para descrever Asset; cria regra
compartilhada genérica quando algo é de fato universal. `docs/CHECKLIST_DE_IMPLEMENTACAO.md` é *append‑only*
por lane: cada uma acrescenta sua entrada no mesmo commit da mudança, nunca reescreve a da outra (AGENTS.md
§"O checklist é o ledger").
