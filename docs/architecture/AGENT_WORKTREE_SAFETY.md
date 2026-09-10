# AGENT_WORKTREE_SAFETY — Segurança de worktree e branch para múltiplos agentes concorrentes

**Status:** Proposta para revisão. Documentação apenas.
**Data:** 10 de setembro de 2026
**Base:** `PARALLEL_VERTICAL_DEVELOPMENT_PROTOCOL.md` §5, AGENTS.md §"Trabalho com agentes de IA".
**Estado atual:** `git worktree list` mostra só `D:/projects/Titan [main]`; `.claude/worktrees/` existe e está
vazio. Não há prática multi‑worktree em uso — este documento a estabelece.

---

## 1. Regra fundamental

**Dois agentes não editam a mesma working tree ao mesmo tempo.** Cada lane ativa trabalha num *worktree* Git
próprio, com branch próprio.

---

## 2. Layout de worktree obrigatório

```
Titan/                     checkout de integração   — branch: integration/main  (ou main)
Titan-livestock/           git worktree             — branch: vertical/livestock/<tarefa>
Titan-asset/               git worktree             — branch: vertical/asset/<tarefa>
Titan-core-integration/    git worktree             — branch: integration/core/<tarefa>   (Shared Integration)
Titan-review-*/            git worktree read-only    — branch: review/<agente>/<data>       (Claude / Gemini)
```

Criação (o dono da lane roda, uma vez):

```bash
git worktree add ../Titan-asset -b vertical/asset/bootstrap
```

- Worktrees de revisão (Claude/Gemini) são **somente‑leitura** ou usam branch de revisão independente; nunca
  editam o checkout de outro agente.
- Gemini/Antigravity idem: não edita o checkout ativo de outro agente.

---

## 3. Convenção de branch

| Prefixo | Lane | Portão de CI (ver [`MULTI_VERTICAL_CI_GATES.md`](MULTI_VERTICAL_CI_GATES.md)) |
|---|---|---|
| `vertical/livestock/*` | A | Nível 1 (rápido de vertical) |
| `vertical/asset/*` | B | Nível 1 |
| `integration/core/*`, `integration/*` | C | Nível 2 → Nível 3; exige rótulo `CHANGE_CLASS=SHARED_INTEGRATION` |
| `review/*` | — | nenhum merge; artefatos de revisão |

O prefixo do branch é a fonte da lane para o File Ownership Guard — não se infere lane do conteúdo do *diff*.

---

## 4. Protocolo de pré‑edição (registrar antes de escrever qualquer arquivo)

```
git rev-parse HEAD          → baseline SHA
git status --short          → estado da árvore
git branch --show-current   → branch
pwd                         → caminho do worktree
```

Então aplicar o **STOP‑ON‑COLLISION** de `PARALLEL_VERTICAL_DEVELOPMENT_PROTOCOL.md` §5: determinar dono do
arquivo; checar modificação concorrente; comparar com o baseline do plano. Se o arquivo é de outra lane ativa,
tem modificação desconhecida, mudou *upstream* desde o planejamento, ou é Lane C sem autorização → **PARAR** e
emitir `CONCURRENT_CHANGE_DETECTED`.

---

## 5. Comandos destrutivos proibidos contra trabalho alheio

Sem autorização explícita do dono:

`git reset --hard` · `git clean -fd` · `git clean -fdx` · `git checkout -- <arquivo alheio>` ·
`git restore <arquivo alheio>` · `git stash pop` sobre trabalho desconhecido · *force‑push* sobre branch
alheio · reescrever/`rebase` commits alheios.

**Nunca "limpar" modificações desconhecidas.** Modificação desconhecida é evidência de trabalho concorrente —
parar, não apagar.

---

## 6. Cadência de sincronização

`PARALLEL_VERTICAL_DEVELOPMENT_PROTOCOL.md` §6: antes de um PR de vertical ficar pronto, atualizar do
`integration/main` aceito mais recente, rerodar Nível 1, rerodar testes da vertical, rerodar Nível 2 quando a
atualização trouxe mudança de Lane C. Nunca `rebase` às cegas sobre worktree sujo/desconhecido — resolver o
estado sujo primeiro (com o dono, se não for seu).

---

## 7. Colisão de número de ADR (restrição §25)

Problema: dois agentes assumem "próxima ADR = 0081" e um sobrescreve o outro. `docs/adr/` hoje vai até `0080`;
o processo de `docs/adr/README.md` não define alocação sob concorrência.

**Política:**

1. **Rascunho** de ADR usa nome temporário único, **sem número**:
   `docs/adr/draft-<AAAAMMDD>-<slug>.md`, com `Status: RASCUNHO` e cabeçalho
   `Número: a alocar na integração`.
2. O **número sequencial** (`NNNN`) é alocado **apenas no momento da integração**, por quem faz o merge em
   `integration/main`, olhando o maior número já presente em `docs/adr/` naquele instante — operação
   serializada como qualquer mudança de Lane C.
3. Se dois rascunhos convergem para integração ao mesmo tempo, o integrador aloca números distintos em ordem
   de merge e renomeia os arquivos de rascunho.
4. **ADR aceita nunca é renumerada** (`docs/adr/README.md` — "Reabertura não reescreve o histórico").
5. Referências cruzadas em rascunho usam o nome `draft-...`; são reescritas para `ADR‑NNNN` na alocação.

---

## 8. `.claude/worktrees/`

Diretório já existente (vazio). Pode hospedar worktrees efêmeros de agente. Worktree que um agente cria e não
deixa alteração é limpo automaticamente; worktree com alteração **não é apagado** por outro agente — regra §5.
