# SISBOV — Corte 3 (promoção de captura/review a Fact) — Discovery

**Data:** 15 de setembro de 2026
**Sessão:** Discovery (pré-planning)
**Escopo:** avaliar se o "Corte 3" de `ADR-0058` — mapear a captura simulada revisada do SISBOV para
`ImportedLivestockFact`/contribuição dimensional — está pronto para SPEC/PLAN/BUILD. Priorizado em
`docs/livestock/LIVESTOCK_CONTINUITY_ASSESSMENT.md` §6.5/§8 item 7 como "SISBOV Corte 2 (SISBOV real) —
retomar quando a ADR pendente for decidida" (numeração do assessment; o corte propriamente dito é o
"Corte 3" nomeado dentro da própria `ADR-0058`).

---

## Contexto

`POST-LIV-03` construiu, em vários incrementos (12–13 de agosto de 2026), um caminho completo de captura
externa simulada do SISBOV: `ExternalSourceCaptureArtifact` (Corte 2, `ADR-0058`) preserva o resultado
técnico de uma consulta ao simulador local (`SISBOV_SIMULATOR_LOCAL`/`SIMULATED`) com digest, RLS e
imutabilidade; o Corte 2B acrescenta uma `review_projection` allowlisted e uma
`ExternalSourceCaptureAssociationReview` append-only, permitindo que um operador confirme candidato de
associação a um Animal local — sem nunca alterar o Animal, Facts, coverage, Evidence, Evaluation ou
Decision. Isso foi validado ponta a ponta em 12/08/2026 (`apps/validacao/captura_externa_sisbov_simulada.py`,
5 passos, API real).

O que falta é exatamente o que `ADR-0058` já nomeou como próximo corte, sem implementá-lo:

> "Corte 3: somente após escolher campos reais e Policy consumidora, importar Facts e/ou contribuições
> dimensionais explicitamente aprovadas."

E o Design Package do Corte 2B reforça o mesmo limite: "O Corte 3 — mapeamento de Facts e coverage —
continua bloqueado até existir campo específico, Policy consumidora e regra de admissibilidade aprovados."

Ou seja: o bloqueio não é técnico — é a ausência de duas decisões de domínio (quais campos, qual Policy os
consome) mais o fato de que a única fonte disponível hoje é o simulador local, nunca o SISBOV oficial.

## O que já existe e é 100% reaproveitável quando as decisões existirem

- `ExternalSourceCaptureArtifact` + `review_projection` + `ExternalSourceCaptureAssociationReview` —
  captura, revisão e confirmação de candidato já persistidas e testadas.
- O padrão de promoção de material revisado para `ImportedLivestockFact` **já foi construído nesta mesma
  sessão**, para GTA (`docs/specs/implemented/2026-09-15-declaracao-gta-documental.md`): um novo
  `fact_type` (`livestock.gta_declared`), validação de payload na fronteira HTTP, sem nova classe de
  domínio. O mesmo padrão se replica para um eventual `livestock.sisbov_identity` — a mecânica de "revisão
  confirmada → Fact declarado" não precisa ser reprovada de novo; GTA já provou que o padrão funciona fora
  do caminho do próprio SISBOV.

**Conclusão parcial:** ao contrário de MapBiomas (fonte inexistente em qualquer repositório) e mais perto de
Market Supply (engenharia pronta, decisão pendente), aqui a peça que falta é uma decisão de produto —
mas com uma complicação que nem Market Supply nem GTA têm: **a única fonte disponível é permanentemente
`SIMULATED`**, por desenho deliberado de `ADR-0058` (invariante 3: "`SIMULATED` é imutável... nunca pode ser
promovido por edição posterior a oficial, validado ou reconhecido").

## Achado novo desta sessão: agora existe um consumidor de Policy real e concreto

A pesquisa normativa de mercado (`docs/livestock/MARKET_NORMATIVE_BASIS_RESEARCH_RESULT_2026-09-14.md`,
linhas 271-277) confirma que a **União Europeia exige SISBOV obrigatoriamente**: dupla identificação
individual (brinco + bottom eletrônico), registro na Base Nacional de Dados Únicos, mínimo de 90 dias em
ERAS (Estabelecimento Rural Aprovado no SISBOV) e 40 dias na última ERAS antes do embarque (IN MAPA
nº 17/2006 e nº 51/2018; Decisão da Comissão 2008/61/CE). China e EUA **não** exigem SISBOV especificamente
(China exige rastreabilidade até a fazenda de origem por outros meios; EUA usa identificação individual via
EPE/CZI, não SISBOV).

Isso muda o quadro: pela primeira vez existe um `MarketProfile` real (UE) cuja Policy poderia, em tese,
consumir um Fact de identidade SISBOV. Antes desta pesquisa, "Policy consumidora" era uma incógnita total;
agora há um candidato nomeado.

## Por que isso ainda não autoriza o Corte 3

O achado acima resolve metade do bloqueio da `ADR-0058` (existe Policy candidata) mas não resolve a outra
metade, nem o problema estrutural mais sério:

1. **A fonte continua sendo o simulador, não o SISBOV oficial.** Promover uma captura `SIMULATED` a Fact
   consumível por uma Policy de elegibilidade de UE significaria, na prática, que uma decisão de mercado
   real poderia ser influenciada por dado fabricado localmente — exatamente o que a invariante 3 da
   `ADR-0058` e a disciplina fail-closed da `ADR-0061` (`NormativeBasisSnapshot`, decidida nesta mesma
   sessão para Market Eligibility) existem para impedir. Não é uma limitação de engenharia; é o próprio
   propósito do design.
2. **Não há acesso real ao SISBOV/MAPA.** `ADR-0058` já reserva esse trabalho como etapa separada
   ("Integração oficial: somente após contrato oficial confirmado, autorização de uso,
   ServiceIdentity/credenciais externas, capability review e desenho de segurança próprios"). Isso não foi
   pesquisado nesta sessão e é, por natureza, um esforço maior — credenciamento junto ao MAPA, autenticação,
   possivelmente LGPD/dados de produtor — mais parecido com a Opção C da Discovery de GTA (integração
   estadual direta) do que com a Opção A (declaração documental) que foi aprovada para GTA.
3. **O padrão "revisão confirmada → Fact declarado" já foi provado, e não é pelo SISBOV.** A entrega de GTA
   nesta sessão prova a mecânica completa (payload validado, `fact_type` novo, rejeição 422, consulta,
   segunda ocorrência sem conflito, negação de permissão) sem depender do simulador SISBOV. Isso remove a
   principal razão técnica que poderia justificar avançar o Corte 3 só como prova de conceito: a prova de
   conceito já existe, feita com dado real (guia declarada pelo operador), não simulado.

Promover a captura simulada a Fact agora serviria unicamente para provar o mecanismo pela segunda vez, com
dado que nenhuma Policy real deveria consumir — precisamente a abstração sem uso atual que `AGENTS.md`
proíbe.

## Opções

**A — Avançar o Corte 3 mesmo assim, com Fact marcado `SIMULATED` e Policy de UE recusando-o
explicitamente.**
Tecnicamente possível (o Fact carregaria a marca de simulação e a Policy de elegibilidade real nunca o
aceitaria como prova). Rejeitada: não teria efeito de negócio nenhum — a Policy de UE ainda retornaria
`INDETERMINADO` para identidade SISBOV de qualquer Animal real, porque a única fonte aceitável nunca está
disponível. Seria código para provar um mecanismo já provado por GTA.

**B — Buscar acesso oficial ao SISBOV/MAPA antes de qualquer Corte 3.**
Resolve o problema pela raiz (fonte real, não simulada), mas é um esforço de integração externa
significativo — credenciamento junto ao MAPA, autenticação, possivelmente LGPD — que `ADR-0058` já isola
deliberadamente como etapa própria, fora do escopo de "Corte 3". Não há indicação de que esse acesso já
esteja disponível ou solicitado.

**C — DEFER o Corte 3 nesta Discovery, com gatilho explícito de retomada.**
Documentar que o bloqueio de Policy consumidora foi parcialmente resolvido (UE), mas que o bloqueio de fonte
real permanece total, e que a próxima ação concreta é a Opção B — fora do escopo de uma Discovery de
engenharia interna.

## Trade-offs

| Opção | A favor | Contra |
|---|---|---|
| A — Corte 3 com dado simulado | Fecha formalmente o "próximo corte" nomeado pela ADR-0058 | Sem efeito de negócio; reprova mecanismo já provado por GTA; risco de o Fact `SIMULATED` ser reutilizado incorretamente no futuro |
| B — acesso oficial MAPA/SISBOV | Única opção que resolve o problema de verdade | Esforço de integração externa relevante, fora do escopo desta sessão; requer decisão/autorização própria (credenciamento, segurança, possivelmente LGPD) |
| C — DEFER com gatilho | Honesto sobre o que mudou (Policy UE) e o que não mudou (fonte); não gera código sem uso real | Não avança código nesta sessão |

## Recomendação

**DEFER.** O achado sobre a UE resolve metade do bloqueio original da `ADR-0058` (existe Policy candidata
concreta), mas a parte estrutural — fonte real de SISBOV, não simulada — permanece inteiramente ausente, e
`ADR-0058` já isola essa integração oficial como etapa própria e maior. Diferente de GTA (Opção A funciona
hoje, sem integração externa) e mais parecido com a Opção C daquela mesma Discovery (integração estadual
direta), avançar SISBOV de verdade depende de um esforço de integração externa que não foi solicitado nem
pesquisado nesta sessão.

## Decisão necessária

Se você quiser seguir com SISBOV agora, a decisão é: **autorizar a investigação de acesso oficial ao
SISBOV/MAPA** (Opção B) — isso é trabalho de descoberta próprio (quem contata o MAPA, que credenciamento
existe, prazo, custo), não uma SPEC de engenharia. Só depois de existir uma fonte real (ou pelo menos um
caminho concreto e autorizado até ela) faz sentido reabrir o Corte 3 da `ADR-0058`, agora against a Policy
real de elegibilidade UE em vez de um Fact simulado sem consumidor legítimo.

Enquanto isso não acontecer, o Corte 3 fica bloqueado pelo mesmo motivo de sempre — mas agora com a causa
raiz mais precisa: não falta decisão de Policy (a UE resolve isso), falta fonte real.
