# ADR-0066 — BuyerPolicy Fase 3: Feedback Estruturado, Composição com Matriz e Rate-Limiting

**Data da decisão original:** 21-27 de agosto de 2026
**Status:** ACEITA (decisões D1-D5 e escolha de Fluxo B confirmadas em 27/08/2026)
**Estado operacional no MVP:** PARCIALMENTE_IMPLEMENTADA — Incrementos 1 (Decision/Proposal) e 2
(Rate-Limiting & Auditoria) implementados e validados em 27/08/2026; Incremento 3 (Composição com Matriz)
implementado em 16/09/2026 (ver seção "O que foi de fato construído" abaixo). Incremento 4 (Snapshot &
Acesso Pós-Expiração) **não foi iniciado**. Ver `docs/CHECKLIST_DE_IMPLEMENTACAO.md`, entrada NEXT-11.
**Decisores:** responsável pelo produto e arquitetura do Titan
**Reconstruída retroativamente em:** 14/09/2026, a partir de `docs/plans/BUYERPOLICY_FASE3_DISCOVERY.md`,
`docs/plans/BUYERPOLICY_FASE3_REQUIREMENTS.md`, `docs/plans/BUYERPOLICY_FASE3_BUILD_PLAN.md` e
`docs/plans/BUYERPOLICY_FASE3_LAUNCH.md`.

---

## Nota sobre esta reconstrução

Este arquivo nunca foi escrito durante a implementação: a Fase 3 do BuyerPolicy foi planejada, decidida e
parcialmente construída entre 19 e 27 de agosto de 2026 citando "ADR-0066" como a decisão que a autoriza —
inclusive em `docs/adr/0068-avaliacao-compartilhada-e-propriedade-da-evaluation.md` e na própria entrada
`NEXT-11` do checklist — mas o arquivo correspondente nunca foi commitado (`git log --all` não encontra
nenhum rastro dele). Esta reconstrução preserva fielmente o conteúdo já decidido e registrado nos quatro
documentos de planejamento e no checklist; não inventa alternativa, decisão ou justificativa que não
estivesse já documentada em algum desses lugares. Onde uma decisão do REQUIREMENTS foi depois substituída
por uma decisão posterior (o caso do Fluxo A → Fluxo B), a substituição está registrada como tal, não
silenciada.

---

## Contexto

BuyerPolicy Fase 1 (ADR-0064, NEXT-09) implementou autoavaliação privada do comprador (origem
`INTERNAL_POLICY`, reconhecimento `INTERNAL_ONLY`). BuyerPolicy Fase 2 (ADR-0065, NEXT-10) implementou
compartilhamento bilateral mínimo: o comprador compartilha uma Policy `CONTRACT` com o fornecedor via
`AuthorizationGrant`; o fornecedor autoavalia seus próprios dados contra essa Policy; o resultado permanece
isolado, sem tocar a matriz de elegibilidade regulatória (ADR-0044) e sem ser visível ao comprador.

Com a Fase 2 em produção, quatro lacunas ficaram explícitas (Discovery, 19/08/2026):

1. **Sem feedback estruturado.** O fornecedor recebe um resultado (`CONFORM`/`NAOCONFORM`) mas não tem como
   contestar ou explicar uma não conformidade, e o comprador não tem como revisar e decidir sobre isso.
2. **Sem composição com a matriz regulatória.** A avaliação contratual (Fase 2) e a elegibilidade
   regulatória por mercado (ADR-0044) são trilhas completamente separadas; não há forma de saber se um
   fornecedor que passou no contrato também passa na matriz.
3. **Sem proteção contra força bruta.** A tabela de riscos da ADR-0065 já apontava que um fornecedor
   poderia tentar derivar o dataset do comprador por tentativa e erro de avaliações repetidas.
4. **Sem preservação de histórico pós-expiração.** Ao expirar um grant, a avaliação e qualquer proposta
   associada ficam "órfãs" — o fornecedor perde acesso ao critério que usou.

## Problema

As cinco questões críticas levantadas na Discovery, que esta ADR precisa responder antes de qualquer
BUILD:

1. Quem pode criar uma `SharedDecision` sobre uma avaliação compartilhada — só o fornecedor, só o
   comprador, ambos?
2. Como o comprador rejeita uma proposta do fornecedor — a `Evaluation` original fica marcada como negada,
   ou uma nova `Evaluation` é criada?
3. Rate-limit é por grant, por Organization ou global?
4. Composição com a matriz regulatória é automática (o fornecedor já vê o resultado composto) ou explícita
   (o comprador decide compor, por endpoint separado)?
5. Ao expirar um grant, como o fornecedor continua acessando o histórico do que já avaliou?

## Alternativas consideradas

### Composição com a matriz regulatória — Fluxo A vs. Fluxo B

**Fluxo A — Composição Transparente.** O fornecedor avalia contra a Policy compartilhada e o sistema
compõe automaticamente com a matriz do mercado relevante, devolvendo um `composite_verdict` direto.
Recomendado no REQUIREMENTS (21/08/2026, §2.2) pela simplicidade de UX.

**Fluxo B — Composição Explícita.** O fornecedor avalia contra a Policy compartilhada e recebe apenas o
resultado contratual, isolado (como já era na Fase 2). O comprador — não o fornecedor — chama um endpoint
separado (`POST /shared-policies/{id}/compose-with-matrix`) para obter o veredito composto. O fornecedor
nunca vê o efeito da matriz do comprador.

**Decisão (27/08/2026): Fluxo B.** A escolha final inverteu a recomendação original do REQUIREMENTS. O
`BUYERPOLICY_FASE3_BUILD_PLAN.md` registra a justificativa: o Fluxo B é coerente com a decisão D4 (abaixo)
e com a própria tabela de riscos da Fase 3 ("composição expõe matriz → mitigação: endpoint separado"). Um
fornecedor que visse o resultado composto automaticamente aprenderia, por tentativa, detalhes da matriz
regulatória do comprador — exatamente o vazamento que o isolamento da Fase 2 foi desenhado para evitar.

### Avaliação com sujeitos de outra Organization

**Opção A (adotada).** O fornecedor continua avaliando apenas seus próprios sujeitos; o comprador não
avalia sujeitos do fornecedor unilateralmente.
**Opção B (rejeitada nesta fase).** O comprador roda uma avaliação em nome do fornecedor via endpoint
próprio.
**Opção C (rejeitada nesta fase).** O fornecedor compartilha também seus dados brutos, e o comprador vê o
resultado final diretamente.

**Decisão:** Opção A, pela mesma razão que fundamentou o isolamento da Fase 2 — reduzir exposição de
dataset e manter RLS simples. Opções B e C ficam registradas como possível Fase 4, condicionadas a demanda
explícita e a um novo tipo de grant (`BILATERAL_DATA_SHARING`).

## Decisão

**Adotar as cinco decisões de design (D1-D5) e o Fluxo B de composição**, conforme REQUIREMENTS/BUILD_PLAN:

- **D1 — Quem cria `SharedDecision`:** apenas o fornecedor (beneficiary do grant). O fornecedor propõe
  (`status=PROPOSTA`); o comprador aprova, rejeita ou pede reavaliação (`status=REVISADA`). Evita que o
  comprador crie uma proposta em nome do fornecedor.
- **D2 — Imutabilidade da `Evaluation`:** `SharedDecision` referencia a `Evaluation` original (Fase 2) sem
  modificá-la, conforme ADR-0052. Reavaliação necessária produz nova `Evaluation`, nunca reescreve a
  anterior.
- **D3 — Escopo do rate-limit:** por grant, não por Organization nem global. Cada grant delimita
  finalidade, validade e contraparte — dois contratos com o mesmo fornecedor não competem pela mesma cota,
  e um grant "premium" pode ter limite maior sem afetar os demais.
- **D4 — Composição é opcional:** o fornecedor sempre vê o resultado contra a Policy contratual isolada; o
  comprador decide, separadamente, se quer compor com a matriz. Não há composição automática (ver Fluxo B
  acima).
- **D5 — Sujeitos cross-Organization:** não permitido nesta fase (Opção A acima).

### Contratos públicos previstos

```text
POST /v1/rule-governance/policies/shared-policies/{policy_id}/propose
POST /v1/rule-governance/policies/shared-policies/{policy_id}/decisions/{decision_id}/review
GET  /v1/rule-governance/policies/shared-policies/{policy_id}/decisions
POST /v1/rule-governance/policies/shared-policies/{policy_id}/evaluate   (já existente, Fase 2)
POST /v1/rule-governance/policies/shared-policies/{policy_id}/compose-with-matrix   (Incremento 3)
GET  /v1/rule-governance/policies/{policy_id}/access-log
GET  /v1/rule-governance/policies/shared-policies/{policy_id}/history   (Incremento 4, pós-expiração)
```

### Persistência prevista

- `core_audit.shared_decisions` — `SharedDecision` (proposta/revisão), com FKs para grant/evaluation/
  policy/organizations, RLS bilateral (visível a proposer e reviewer).
- `core_audit.shared_policy_access_log` — trilha append-only de leitura/avaliação/proposta/revisão, com
  RLS bilateral, sem política de `UPDATE`/`DELETE`.
- `SharedDecision.policy_snapshot_json` — cópia da definição da Policy capturada no momento da proposta,
  para acesso de leitura por até 90 dias após a expiração do grant (Incremento 4).

## O que foi de fato construído (14/09/2026)

- **Incremento 1 — Decision/Proposal:** implementado e validado em 27/08/2026. `SharedDecision`
  (`packages/core_domain/policy_sharing.py`), `TransactionalSharedDecisionRepository`, `SharedDecisionService`,
  três endpoints HTTP, permissões `POLICY.COMPARTILHAMENTO_PROPOR`/`POLICY.COMPARTILHAMENTO_REVISAR`,
  migration `20260827_0076`, roteiro `apps/validacao/buyerpolicy_shared_decision.py`.
- **Incremento 2 — Rate-Limiting & Auditoria:** implementado e validado em 27/08/2026. Cota de 10
  avaliações/minuto por grant via `InMemoryRateLimiter` (reaproveitado da ADR-0039, sem Redis), `429
  LIMITE_DE_AVALIACOES_EXCEDIDO`, trilha `core_audit.shared_policy_access_log` (migration `20260827_0077`,
  append-only por policy de banco, não por convenção), endpoint `GET .../access-log`, roteiro
  `apps/validacao/buyerpolicy_rate_limit_auditoria.py`.
- **Incremento 3 — Composição com Matriz:** implementado em 16/09/2026, após
  `docs/plans/BUYERPOLICY_INCREMENTO3_BUILD_PLAN.md` resolver os detalhes que este registro (e o
  `BUYERPOLICY_FASE3_BUILD_PLAN.md`) deixaram para sessão posterior. `POST .../compose-with-matrix`
  (`apps/api/policy_governance.py`) roda somente sob o comprador (owner do grant), troca de contexto para o
  fornecedor para ler a `Evaluation` contratual e rodar `MarketEligibilityService` restrito ao mercado
  pedido, e devolve exclusivamente `composite_verdict` — nenhum `rule_results` de nenhum dos lados atravessa
  a resposta. Nova permissão `POLICY.COMPARTILHAMENTO_COMPOR` e nova ação de auditoria `COMPOSE` (mesma cota
  de `/evaluate`, D3). **Ressalva:** os caminhos `ELEGIVEL`/`INELEGIVEL` exigiriam uma Policy contratual com
  fato real resolvível e regra governada de mercado adotada — os testes cobrem `REQUER_REVISAO` e todos os
  caminhos de erro/isolamento/auditoria; ver detalhes no BUILD PLAN.
- **Incremento 4 — Snapshot & Acesso Pós-Expiração:** **não iniciado.**

## Consequências

### Positivas

- Feedback estruturado e rate-limiting/auditoria — a metade da Fase 3 com menor acoplamento a outras
  decisões pendentes — chegaram a produção com testes e validação manual.
- O isolamento da Fase 2 (fornecedor nunca revela dataset bruto, comprador nunca acessa facts do
  fornecedor) foi preservado; nenhuma das decisões de Fase 3 o relaxa.
- A escolha do Fluxo B, mesmo revertendo a recomendação inicial do REQUIREMENTS, mantém a matriz
  regulatória do comprador não exposta ao fornecedor por tentativa e erro.

### Negativas / riscos

- Acesso pós-expiração (Incremento 4) não existe: um grant expirado hoje deixa a avaliação e a proposta
  associada sem caminho de leitura para o fornecedor, exatamente o risco que a Discovery já havia
  identificado.
- Numeração de ADR ficou órfã por quase um mês (21/08 a 14/09/2026) até esta reconstrução — risco
  documental já registrado em `docs/CHECKLIST_DE_IMPLEMENTACAO.md`.

## Relacionadas

- ADR-0064 — BuyerPolicy Fase 1 (autoavaliação privada, origem `INTERNAL_POLICY`)
- ADR-0065 — BuyerPolicy Fase 2 (compartilhamento contratual mínimo)
- ADR-0068 — Autoavaliação compartilhada: propriedade da `Evaluation` (desbloqueou o Incremento 3, mas o
  Incremento 3 em si não foi construído)
- ADR-0044 — Matriz de elegibilidade por mercado com regras governadas (alvo da composição do Incremento 3)
- ADR-0052 — Temporalidade e imutabilidade de `Evaluation`
- ADR-0039 — Rate limiter em memória, reaproveitado para D3

## Riscos (da tabela original do REQUIREMENTS, com status atualizado)

| Risco | Mitigação prevista | Estado em 14/09/2026 |
|---|---|---|
| Exposição de dataset do fornecedor | Fornecedor só avalia seus próprios sujeitos (Opção A) | Mitigado — implementado desde a Fase 2 |
| Força bruta de avaliações | Rate-limit por grant + log de acesso | Mitigado — Incremento 2 concluído |
| Perda de histórico pós-expiração | Snapshot automático + acesso por 90 dias | **Não mitigado — Incremento 4 não construído** |
| Composição expõe matriz ao fornecedor | Endpoint separado (Fluxo B) | Mitigado — Incremento 3 implementado em 16/09/2026 |
| Assimetria de autoria da proposta | Apenas beneficiary cria `SharedDecision` | Mitigado — Incremento 1 concluído |

## Próximos passos, se esta frente for retomada

Não autorizados por este registro — exigem decisão própria antes de BUILD:

1. Incremento 4 (snapshot e acesso pós-expiração).
2. Reavaliar se a Fase 4 (sujeitos cross-Organization, `BILATERAL_DATA_SHARING`) tem demanda real.
