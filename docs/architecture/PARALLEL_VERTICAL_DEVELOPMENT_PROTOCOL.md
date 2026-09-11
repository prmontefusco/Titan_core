# PARALLEL_VERTICAL_DEVELOPMENT_PROTOCOL — Desenvolvimento concorrente de verticais Titan

**Status:** Proposta para revisão. Documentação/arquitetura apenas — nenhum código de produção alterado.
**Data:** 10 de setembro de 2026
**Autoridade:** estende `AGENTS.md` §"Trabalho com agentes de IA" e ADR‑0001; subordinado aos documentos de
autoridade (`VISION.md`, `DOMAIN.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md`) e às ADRs aceitas.
**Motivação:** Titan Livestock está em desenvolvimento ativo (Codex). Titan Asset & Sustainment começará em
paralelo. Nenhuma das duas pode parar para a outra existir, e a solução deve valer para a vertical nº 3, 4, …

**Documentos irmãos:**
[`VERTICAL_OWNERSHIP_MATRIX.md`](VERTICAL_OWNERSHIP_MATRIX.md) ·
[`SHARED_CHANGE_PROTOCOL.md`](SHARED_CHANGE_PROTOCOL.md) ·
[`MULTI_VERTICAL_CI_GATES.md`](MULTI_VERTICAL_CI_GATES.md) ·
[`MIGRATION_CONCURRENCY_STRATEGY.md`](MIGRATION_CONCURRENCY_STRATEGY.md) ·
[`NEW_VERTICAL_BOOTSTRAP_STANDARD.md`](NEW_VERTICAL_BOOTSTRAP_STANDARD.md) ·
[`AGENT_WORKTREE_SAFETY.md`](AGENT_WORKTREE_SAFETY.md) ·
[`CORE_CHANGE_REQUEST_TEMPLATE.md`](CORE_CHANGE_REQUEST_TEMPLATE.md) ·
[`DECISIONS_REQUIRED_PHASE0.md`](DECISIONS_REQUIRED_PHASE0.md)

---

## 1. Invariante `PARALLEL_VERTICAL_SAFETY`

> **O desenvolvimento de uma vertical Titan não pode modificar, mover, reformatar, renomear, reestruturar,
> migrar ou depender da implementação interna de outra vertical.**

Formalmente, para verticais distintas `A` e `B`:

```
dev(A)  MUST NOT  mutate | import | query-tables-of | depend-on-migration-of |
                  use-internal-types-of | patch-API-of | alter-tests-of   B
```

Uma vertical **pode**: ler e usar contratos públicos do Core; publicar eventos/contratos desenhados
explicitamente para composição.
Uma vertical **não pode**: nada da lista acima contra outra vertical, nem "limpar" modificações
desconhecidas em arquivos que não são seus.

Este invariante tem prioridade arquitetural sobre conveniência de implementação (constituição §19). Ele
**não** substitui as fronteiras de dependência já vigentes (ADR‑0001, `tests/architecture/`,
`docs/asset/DEPENDENCY_RULES.md`); acrescenta a regra vertical ⊥ vertical e a torna verificável
sob concorrência.

---

## 2. Três *development lanes*

Toda mudança pertence a exatamente uma lane. A lane determina quem pode escrever, qual portão de CI se aplica
e como o PR é serializado. A tabela path→dono canônica está em
[`VERTICAL_OWNERSHIP_MATRIX.md`](VERTICAL_OWNERSHIP_MATRIX.md); o resumo:

### LANE A — Livestock  *(Codex, ativo)*
`packages/livestock_*/**` · `tests/livestock_*/**` · adapters HTTP e handlers de worker de Livestock ·
`apps/api/livestock_*` (layout atual) · docs específicos de Livestock.
Agentes de Asset tratam estes caminhos como **somente‑leitura**.

### LANE B — Asset & Sustainment
`packages/asset_*/**` e, se a discovery justificar, `packages/sustainment_*/**` · `tests/asset_*/**`,
`tests/sustainment_*/**` · `apps/api/asset/**` · `apps/validacao/asset/**` · handlers de worker de Asset ·
`docs/asset/**`.
Agentes de Livestock tratam estes caminhos como **somente‑leitura**.

### LANE C — Shared Integration
`packages/shared_kernel/**` · `packages/core_*/**` · `apps/api/main.py` e um futuro `apps/api/_registry.py` ·
`apps/worker/main.py` e um futuro `apps/worker/dispatch.py` · raiz de composição do Alembic, `alembic.ini`,
configuração do registro de migrations · `pyproject.toml`, `uv.lock` · `tests/architecture/**` · testes de
integração cross‑vertical · `.github/workflows/**` · arquivos globais de bootstrap/composição.

Estes arquivos **não pertencem** às lanes A ou B. Mudanças aqui são: explícitas, pequenas, serializadas,
revisadas, retrocompatíveis salvo aprovação explícita, e testadas contra **todas** as verticais presentes
(Nível 2 em [`MULTI_VERTICAL_CI_GATES.md`](MULTI_VERTICAL_CI_GATES.md)).

---

## 3. Core é somente‑leitura por padrão

Num branch de feature de vertical, o Core (`packages/core_*`, `packages/shared_kernel`) é **somente‑leitura**.

Se uma vertical descobre que precisa de algo do Core: **não** modificar o Core. Abrir um
**CORE_CHANGE_REQUEST** ([template](CORE_CHANGE_REQUEST_TEMPLATE.md)) e **parar aquela parte** da
implementação até a revisão. A mesma regra vale para Livestock e futuras verticais.

A evolução de contrato do Core é em duas fases (nunca "flag day") — ver
[`SHARED_CHANGE_PROTOCOL.md`](SHARED_CHANGE_PROTOCOL.md) §"Evolução de contrato do Core".

---

## 4. Protocolo de comportamento dos agentes

| Agente / papel | Pode | Não pode |
|---|---|---|
| **Codex / Livestock** | Alterar caminhos da Lane A; continuar o trabalho de Livestock. | Refatorar Asset ou docs de Asset por oportunismo; tocar Lane C sem tarefa de Shared Integration atribuída. |
| **Codex / Asset** (quando usado) | Alterar caminhos da Lane B. | Tocar Core/Lane A/Lane C fora de tarefa de Shared Integration explícita; importar/consultar Livestock. |
| **Claude** (arquitetura/auditoria) | Inspecionar todos os caminhos; escrever em `docs/architecture/**` e ADRs propostas. | Modificar código de produção de qualquer vertical ativa durante revisão; "consertar" uma vertical enquanto revisa outra. |
| **Gemini / Antigravity** (workflow/UX/integração) | Inspecionar todos os caminhos. | "Consertar" outra vertical durante a revisão; mover lógica de negócio para o frontend. Toda proposta transversal vira *finding* / change request. |

Regra geral (constituição §35): superfície de mudança mínima; nada de refatoração oportunista fora da tarefa.

---

## 5. STOP‑ON‑COLLISION

Antes de escrever qualquer arquivo, o agente **registra**: `git rev-parse HEAD`, `git status --short`, branch
atual, caminho do worktree (ver [`AGENT_WORKTREE_SAFETY.md`](AGENT_WORKTREE_SAFETY.md)). Então:

1. determina a lane/dono do arquivo;
2. verifica `git status` e se o arquivo tem modificações concorrentes;
3. compara com o *baseline* de quando o plano foi feito.

**PARAR** se o arquivo: pertence a outra lane ativa; contém modificações desconhecidas; mudou *upstream*
desde o planejamento; é arquivo protegido da Lane C sem autorização de Shared Integration.

Ao parar: **não** fazer merge manual, **não** sobrescrever, **não** restaurar, **não** resolver escolhendo
"ours"/"theirs". Modificação desconhecida é **evidência de trabalho concorrente**, não sujeira. Emitir:

```
CONCURRENT_CHANGE_DETECTED
Arquivo:
Dono / lane:
Tarefa atual:
Por que este arquivo precisaria mudar:
Alternativas seguras:
Integração necessária: SIM/NÃO
```

Comandos **proibidos** contra trabalho que não é seu, sem autorização do dono: `git reset --hard`,
`git clean -fd[x]`, `git checkout -- <arquivo alheio>`, `git restore <arquivo alheio>`, `git stash pop` sobre
trabalho desconhecido, *force‑push* sobre branch alheio, reescrita de commits alheios.

---

## 6. Cadência de sincronização

Trabalho de feature não vive muito tempo contra um Core antigo. Antes de um PR de vertical ser considerado
pronto:

- atualizar a partir do `integration/main` aceito mais recente;
- rerodar os portões de arquitetura (Nível 1);
- rerodar os testes da vertical;
- rerodar os testes de compatibilidade compartilhada (Nível 2) quando a atualização trouxe mudança de Lane C.

Nunca *rebase* às cegas sobre worktree sujo/desconhecido.

---

## 7. Ordem de merge

```
Livestock feature ──────────────┐
                                ├──▶ integration/main
Asset feature ──────────────────┤
                                │
Shared Core change ──[GATE N2]──┘
```

- PRs **exclusivos de uma vertical** progridem em paralelo, sem ordem entre si.
- Mudanças de **Shared Integration** são **serializadas** e passam pelo Nível 2 antes do merge.
- Quando Asset depende de uma mudança de Core ainda não mergeada:
  `PR de Shared Integration do Core → gate N2 → merge → Asset atualiza baseline → Asset continua`.
  **Nunca** embutir a mudança de Core dentro do PR de feature de Asset (constituição §35; restrição §30).
- **Matriz de compatibilidade (restrição §33):** um commit em `integration/main` só é válido se
  `Core + toda vertical presente` estiver verde junto. Nenhuma vertical faz merge deixando outra vermelha de
  propósito.

---

## 8. Alocação de números de ADR sob concorrência

Dois agentes não podem assumir independentemente "próxima ADR = 0081". Política em
[`AGENT_WORKTREE_SAFETY.md`](AGENT_WORKTREE_SAFETY.md) §"Colisão de número de ADR": ADRs em rascunho usam nome
temporário único (`draft-<AAAAMMDD>-<slug>.md`); o número sequencial é alocado **apenas na integração**, pelo
integrador. ADR aceita nunca é renumerada.

---

## 9. Cenário de aceitação (a prova)

A arquitetura é bem‑sucedida se, às 09:00, o Codex implementa uma feature de Livestock (domínio + API +
possivelmente uma migration de Livestock) **e**, ao mesmo tempo, outro agente implementa/revê Asset (domínio +
aplicação + persistência + possivelmente uma migration de Asset), e:

- nenhum agente para porque o outro mudou código de domínio;
- nenhum agente edita arquivo do outro;
- nenhuma migration muta tabela da outra vertical;
- os *event/message types* não colidem;
- ambos consomem os mesmos contratos públicos do Core;
- se uma mudança de Core for necessária, ela vai por uma lane separada de Shared Integration.

Após ambos os merges, a CI completa prova: **Core verde · Livestock verde · Asset verde · fronteiras
arquiteturais verdes · grafo de migrations válido · instalação limpa válida · upgrade válido · acesso
cross‑vertical ausente**.

Repetir o experimento mental com **Vertical C**. Se adicioná‑la exigir redesenhar Livestock ou Asset, a
arquitetura ainda não está generalizada — ver [`NEW_VERTICAL_BOOTSTRAP_STANDARD.md`](NEW_VERTICAL_BOOTSTRAP_STANDARD.md).

---

## 10. Modo de execução atual

Documentação/arquitetura apenas. **Não** modificar código de Livestock ou Asset, criar migrations, mover
routers, mudar despacho do worker, mudar comportamento do Core, mudar schema, ou alterar asserção de teste
existente. Aguardar ACCEPT explícito do dono.
