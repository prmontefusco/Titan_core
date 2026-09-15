# NormativeBasis real para China/EUA/UE — Decisão de produto

**Data:** 15 de setembro de 2026
**Tipo:** decisão de produto/domínio, não Discovery de engenharia — o mecanismo técnico já existe e está
provado (`ADR-0061`); o que falta é conteúdo com autoridade real, que `DOMAIN.md` proíbe este agente de
fornecer sozinho.

---

## Contexto

Desde a `ADR-0061` (13/08/2026), `MarketEligibilityService` só emite `Evaluation`/`Decision` de mercado
quando uma fonte de aplicação entrega exatamente um `NormativeBasisSnapshot` tipado e elegível — ausência
retorna `INDETERMINADO`, nunca aprovação implícita. O único adaptador concreto hoje,
`InternalPharmacologicalNormativeBasisSnapshotProvider`/`PersistedInternalTestNormativeBasisSnapshotProvider`
(`packages/livestock_application/eligibility.py`, `internal_test_normative_basis.py`), serve exclusivamente
`INTERNAL_TEST` — jurisdição, autoridade de aprovação e classificação da fonte são todas fixadas em valores
internos, nunca `NormativeSourceClassification.OFFICIAL` (que existe no enum de `core_domain/normative.py`,
mas não tem nenhum adapter que o produza).

Ou seja: **China, EUA e UE avaliam hoje como `INDETERMINADO`, sempre** — não porque a Policy/Rule de mercado
esteja errada, mas porque nenhuma fonte real de `NormativeBasis` foi registrada para elas. Isso está correto
por desenho (fail-closed), mas é uma lacuna de conteúdo, não de mecanismo.

Nesta sessão foi conduzida pesquisa regulatória via IA (`docs/livestock/MARKET_NORMATIVE_BASIS_RESEARCH_RESULT_2026-09-14.md`),
com uma camada preliminar de checagem independente. Isso move o material de "nada" para "Claim com
corroboração parcial" — mas `DOMAIN.md` e o próprio guia de intake (`docs/livestock/MARKET_NORMATIVE_BASIS_INTAKE_GUIDE.md`)
são explícitos: uma Claim de IA, mesmo corroborada, não é `NormativeBasis`. "Aprovação privada não é
apresentada como entendimento oficial sem Evidence específica." Eu (este agente) não tenho, e não posso
simular, a competência regulatória declarada que o guia exige no passo 1 — isso é uma decisão humana, não
uma pesquisa adicional que eu possa fazer para resolver o bloqueio.

## Achado crítico desta sessão, que muda o quadro para a UE especificamente

A pesquisa (corroborada de forma independente) registra que **a União Europeia suspendeu a importação de
carnes e produtos de origem animal do Brasil a partir de 03/09/2026**, por insuficiência de garantias sobre
controle de antimicrobianos — não por contaminação pontual. Isso é anterior a qualquer decisão que este
documento tome: mesmo que uma `NormativeBasis` de UE fosse registrada hoje com conteúdo perfeito, a UE está,
neste momento, **em embargo geral**, não em "elegibilidade sujeita a critérios". Uma `NormativeBasis`/`Rule`
de UE que não modelar esse embargo geral estaria descrevendo um mercado que não existe mais no estado atual.

Isso não é um bloqueador técnico — é um lembrete de que qualquer trabalho de UE precisa, no mínimo, decidir
como representar "mercado suspenso" (provavelmente uma nova regra bloqueante, não apenas ausência de base
normativa), antes ou junto com qualquer registro de `NormativeBasis`.

## Evidência

| Item | Estado | Fonte |
|---|---|---|
| Mecanismo fail-closed (`ADR-0061`) | Implementado e testado | `packages/livestock_application/eligibility.py:155-227`, `internal_test_normative_basis.py:152-191` |
| Padrão reutilizável de catálogo versionado (`applies_at`/`known_as_of`, seleção única, falha fechada em ambiguidade) | Implementado, provado só para `INTERNAL_TEST` | `internal_test_normative_basis.py` |
| `NormativeSourceClassification.OFFICIAL` | Existe no enum, **nenhum adapter o produz** | `packages/core_domain/normative.py:19` |
| Narrativas centrais de China/EUA/UE/Indonésia | Claim de IA, 5 afirmações centrais corroboradas por busca independente | `docs/livestock/MARKET_NORMATIVE_BASIS_RESEARCH_RESULT_2026-09-14.md` linhas 19-28 |
| Citações técnicas granulares (números de decreto, LMR, seções de CFR) | **Não verificadas** — exigem revisão humana com fonte primária | idem, linhas 29-47 |
| UE em embargo desde 03/09/2026 | Corroborado por fonte independente (Agência Brasil) | idem, linha 25 |
| Competência regulatória declarada para validar citações (passo 1 do guia de intake) | **Não designada nesta sessão nem em nenhuma anterior** | busca no repositório: nenhuma menção a revisor/advogado/compliance designado |

## Opções

**A — Buscar revisão humana com competência regulatória declarada, seguindo o guia de intake à risca.**
Alguém (jurídico, compliance regulatório, ou consultoria de comércio exterior pecuário) confirma, contra
fonte primária, cada citação técnica da seção 6 do prompt original, decide o desenho real de Policy/Rule por
mercado (inclusive como modelar o embargo de UE) e só então este trabalho vira SPEC. É o único caminho que
`DOMAIN.md` reconhece como legítimo para uma `NormativeBasis` que afeta decisão real de exportação.

**B — Registrar agora uma `NormativeBasis` "mínima interna" com apenas as 5 narrativas já corroboradas por
esta sessão, replicando o padrão `INTERNAL_TEST`.**
Tecnicamente trivial — o catálogo já existe, só precisaria de conteúdo novo e classificação `OFFICIAL` em
vez de `INTERNAL_TEST`. Rejeitada por este agente sem autorização humana explícita e informada: mesmo as
narrativas "corroboradas" foram verificadas por busca web deste agente, não por alguém com competência
regulatória declarada — usar isso como base de uma `Decision` real de exportação é exatamente a "aprovação
privada apresentada como entendimento oficial" que `DOMAIN.md` proíbe. Além disso, ignoraria o embargo de UE
se feito sem desenho de Rule específico para ele.

**C — Aceitar formalmente `INDETERMINADO` como estado atual e comunicar isso, sem novo código.**
Fecha o risco "regressão silenciosa" já nomeado em `LIVESTOCK_CONTINUITY_ASSESSMENT.md` §6.2/§7 — não é mais
uma lacuna silenciosa, é um estado documentado e intencional. Não avança a capacidade de mercado real, mas
não cria falsa confiança nem viola `DOMAIN.md`.

## Trade-offs

| Opção | A favor | Contra |
|---|---|---|
| A — revisão humana formal | Único caminho legítimo para uma `NormativeBasis` real; resolve a UE (embargo) e as demais ao mesmo tempo | Exige encontrar/designar alguém com competência regulatória; fora do que este agente pode fazer sozinho |
| B — mínima interna sem revisão | Rápido, mecanismo já pronto | Viola `DOMAIN.md` (aprovação privada como oficial); risco real — pode influenciar decisão real de exportação com base não verificada; ignora embargo de UE se feito sem cuidado |
| C — aceitar `INDETERMINADO` e comunicar | Honesto, zero risco novo, fecha o achado do assessment | Não avança capacidade comercial |

## Recomendação

**C agora, com A como caminho de retomada.** Não tenho base — nem autoridade sob `DOMAIN.md` — para escolher
B. A decisão de buscar e designar um revisor com competência regulatória real (Opção A) é comercial/jurídica,
não técnica, e pertence a você. Enquanto isso não acontecer, aceitar e comunicar `INDETERMINADO` (Opção C) é
o único estado que reflete a verdade da base normativa hoje — e evita o risco concreto que a `ADR-0061` foi
escrita para prevenir.

## Decisão necessária

1. Existe, ou você quer designar, alguém com competência regulatória declarada (jurídico/compliance/
   consultoria de comércio exterior) para validar as citações técnicas da pesquisa antes de qualquer
   `NormativeBasis` real ser registrada?
2. Enquanto isso não existir: formalizar Opção C (aceitar/comunicar `INDETERMINADO`) como o registro desta
   sessão?

---

## Decisão tomada em 15/09/2026

**Opção C confirmada.** Respondendo à pergunta 1: ainda não há revisor designado ("ainda não sei quem").
Nenhum código, Policy, Rule ou `NormativeBasis` foi alterado por esta decisão.

**Estado resultante:** China, EUA e UE permanecem formalmente `INDETERMINADO` em `MarketEligibilityService`
— não como lacuna silenciosa (o risco nomeado em `LIVESTOCK_CONTINUITY_ASSESSMENT.md` §6.2/§7), mas como
estado documentado e aceito, com causa raiz precisa: falta autoridade real, não falta pesquisa nem
mecanismo. O material desta sessão (pesquisa + checagem preliminar + este documento) fica pronto para
retomada assim que a Opção A tiver um revisor.

**Gatilho de retomada:** alguém com competência regulatória declarada (jurídico, compliance regulatório ou
consultoria de comércio exterior pecuário) designado para validar as citações técnicas granulares da
pesquisa (`docs/livestock/MARKET_NORMATIVE_BASIS_RESEARCH_RESULT_2026-09-14.md`, seção "O que NÃO foi
checado") e decidir o desenho real de Policy/Rule por mercado — incluindo, para a UE, como modelar o embargo
vigente desde 03/09/2026 (que precisa de tratamento próprio, distinto de "base normativa ausente").
