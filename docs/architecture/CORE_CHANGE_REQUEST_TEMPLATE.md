# CORE_CHANGE_REQUEST_TEMPLATE — Pedido de mudança no Titan Core a partir de uma vertical

**Status:** Template normativo. Documentação apenas.
**Data:** 10 de setembro de 2026
**Uso:** quando uma vertical (Livestock, Asset, futura) descobre que precisa de algo que o Core não fornece.
**Regra:** abrir o CCR e **parar a parte dependente da implementação** até a revisão. Não modificar
`packages/core_*` / `packages/shared_kernel` num branch de feature de vertical
(`PARALLEL_VERTICAL_DEVELOPMENT_PROTOCOL.md` §3).

---

## Template

```
CORE_CHANGE_REQUEST

ID:                 CCR-<AAAAMMDD>-<slug>
Vertical solicitante:   livestock | asset | <id>
Branch de origem:   vertical/<id>/<tarefa>
Autor:              <agente/pessoa>
Data:               <AAAA-MM-DD>

--- NECESSIDADE ---
Need:
  O que a vertical precisa fazer e não consegue com os contratos públicos atuais.

Why this is horizontal rather than <id>-specific:
  Argumento de que a capacidade serve o Core / mais de uma vertical, não só esta.
  (Se não for horizontal, o CCR deve ser rejeitado e a vertical resolve localmente.)

Current Core limitation:
  Módulo/contrato exato que hoje impede (arquivo:linha quando aplicável).

Proposed Core capability:
  Forma proposta — novo contrato, novo parâmetro, nova porta. Mínimo viável.

--- IMPACTO ---
Existing Livestock behavior potentially affected:
  Enumerar consumidores atuais (grep) e o efeito. "Nenhum" exige a prova do grep.

Future vertical benefit:
  Como a vertical nº 3+ se beneficia.

Backward compatibility:
  A mudança é aditiva (Fase A de SHARED_CHANGE_PROTOCOL.md §5)? Se não, justificar.

Authorization impact:
  Muda permissão, papel, OrganizationContext, RLS? Como?

Audit/integrity impact:
  Muda evento de auditoria, cadeia de hash, checkpoints, outbox/inbox? Como?

Migration impact:
  Exige migration de Core? Em qual branch label? depends_on?

Tests required:
  Testes de invariante, autorização, concorrência, compatibilidade N-vertical.

--- DECISÃO ---
Can <id> solve this locally without violating architecture?   YES / NO
  Se YES: descrever a solução local. O CCR provavelmente não procede.
  Se NO: por quê (qual invariante/fronteira a solução local violaria).

Recommendation:
  PROCEED (abrir PR de Shared Integration)  |  SOLVE LOCALLY  |  DEFER  |  REJECT

Confidence:
  ALTA | MÉDIA | BAIXA  + o que reduz a incerteza.

Owner decision required:  YES / NO
```

---

## Fluxo

1. Vertical abre `docs/architecture/ccr/CCR-<data>-<slug>.md` (ou anexa ao PR de feature como bloco).
2. **Claude** (Role B) revisa horizontalidade, impacto em invariantes, autorização, auditoria.
3. **Gemini** revisa impacto de workflow/integração se o contrato for consumido em fluxo ponta a ponta.
4. Se `PROCEED`: cria‑se um **PR de Shared Integration** (Fase A — aditivo) seguindo
   [`SHARED_CHANGE_PROTOCOL.md`](SHARED_CHANGE_PROTOCOL.md); se muda contrato/decisão material, também uma ADR
   (rascunho `draft-...`, número alocado na integração — [`AGENT_WORKTREE_SAFETY.md`](AGENT_WORKTREE_SAFETY.md)
   §7).
5. Vertical retoma a parte parada só depois do merge da Fase A e da atualização do *baseline*.

---

## Exemplo ilustrativo (não é um CCR aberto)

**H2 do [`PHASE0_ADVERSARIAL_REVIEW.md`](PHASE0_ADVERSARIAL_REVIEW.md) — escopo OM/Site.** Se a discovery de
Asset concluir que uma OM precisa de isolamento de dados **dentro** de uma Organization operadora, e que RLS
por `titan.organization_id` não basta, o caminho correto é um CCR:

- *Need:* escopo de autorização sub‑Organization, genérico.
- *Why horizontal:* qualquer vertical com sites/filiais sob um mesmo tenant tem a mesma necessidade
  (Livestock: propriedades sob um mesmo grupo).
- *Proposed capability:* um `scope` opcional no `OrganizationContext` + predicado de RLS parametrizado —
  **sem** nenhum conceito `OM`/`Vehicle`/`Workshop` no Core (constituição §18; restrição §18).
- *Decision:* `Owner decision required: YES` — é mudança de primitiva de isolamento.

Enquanto a discovery não fecha, **nada disso é implementado** (restrição §18).
