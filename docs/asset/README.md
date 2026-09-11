# docs/asset — Titan Asset & Sustainment (vertical)

Toda documentação específica da vertical Asset & Sustainment vive sob `docs/asset/`, namespaced por tipo,
para que a fronteira de propriedade (`PARALLEL_VERTICAL_SAFETY`) seja um único prefixo de caminho.

```
docs/asset/
  README.md                  este arquivo
  01_PRODUCT_VISION.md        documentos numerados da discovery (§48 da constituição)
  ...
  20_EXECUTION_ROADMAP.md
  ASSET_VERTICAL_BOOTSTRAP_PLAN.md, CORE_REUSE_ASSESSMENT.md, ...   assessment da Fase 0
  adr/
    draft-<AAAAMMDD>-<slug>.md      ADRs específicas de Asset & Sustainment, em rascunho
                                    (número alocado só na integração — mesma política de docs/adr/README.md)
  specs/
    proposed/ | approved/ | implemented/ | rejected/
                                    SPECs de Asset & Sustainment, mesmo lifecycle de docs/specs/README.md,
                                    mesmo template (docs/specs/_template.md) — só o local muda
```

## Por que um namespace próprio

`docs/adr/` e `docs/specs/` são convenções **compartilhadas** do repositório (Core + toda vertical). Uma ADR
ou SPEC específica de Asset & Sustainment misturada lá dentro não tem como ser reconhecida como "caminho da
lane Asset" por um portão mecânico (`scripts/check_file_ownership.py`) sem enumerar arquivo a arquivo. Com
tudo sob `docs/asset/**`, a regra vira um prefixo só — o mesmo padrão que `packages/asset_*` já segue.

**ADR ou SPEC que não é específica de Asset & Sustainment** (decide algo que também vale para Livestock ou
para o Core) **não entra aqui** — continua em `docs/adr/`/`docs/specs/` como Shared Integration. Exemplo:
`docs/adr/draft-20260910-governanca-de-desenvolvimento-paralelo-de-verticais.md` decide paralelismo entre
verticais em geral, então fica em `docs/adr/`, não em `docs/asset/adr/`.

## Pendência de Shared Integration

`docs/architecture/verticals.toml` (Lane C, branch `integration/core/parallel-vertical-foundation`) ainda
referencia `docs/asset-sustainment/` como `doc_roots` de `asset` — path antigo. Precisa de um PR de Shared
Integration atualizando para `docs/asset/` antes daquela stack ser mesclada com o trabalho desta vertical.
`VERTICAL_OWNERSHIP_MATRIX.md`, `MULTI_VERTICAL_CI_GATES.md` e `ADR-0080` (todos em `docs/architecture/`/
`docs/adr/` na mesma stack) têm a mesma referência a corrigir no mesmo PR.

## Verticais futuras

O mesmo padrão vale para qualquer vertical nova: `docs/<vertical_id>/`, com `adr/` e `specs/` próprios
quando precisar de uma ADR ou SPEC específica — não antes (constituição §38, "não criar estrutura vazia").
