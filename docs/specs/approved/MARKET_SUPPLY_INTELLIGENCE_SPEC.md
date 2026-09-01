# SPEC: Market Supply Intelligence

- **Nível:** CRITICAL
- **Estado:** aprovada como baseline arquitetural; BUILD/CUT F nao autorizado
- **Decisão de Discovery:** PROCEED para DESIGN ONLY; ADR-0069 aceita; produção exige nova autorização de CUT F
- **Owner de produto:** Founder / Product Owner
- **Data:** 2026-08-28

## Problema e usuário

Compradores e frigoríficos podem precisar estimar capacidade de atendimento por mercado e janela comercial antes de escolher animais ou propriedades específicas. Produtores precisam responder a essa demanda sem expor rebanho, dados sanitários ou dossiês individuais antes de autorização adequada.

## Contexto e objetivo

O objetivo desta SPEC é definir, para revisão humana, os conceitos futuros `CommercialDemand`, Candidate Population semantics, `SupplyForecast`, `SupplyDemandAnalysis`, `GapAnalysis` e `SupplyIntelligenceReport` como camada analítica não regulatória. Nenhum código, migration, API ou acesso cross-tenant é autorizado por este documento.

## Fora de escopo

- implementação de persistência;
- endpoint, worker, fila, projection persistida ou API cross-tenant;
- forecast real ou IA/ML;
- marketplace, pagamentos, crédito, seguro ou reserva comercial;
- integração oficial MAPA/IAGRO/SISBOV;
- alteração de `Evaluation`, `Decision`, `Dossier`, `VerificationBundle`, `Fact` ou `Evidence`;
- CUT F.

## Comportamento e regras de negócio

`CommercialDemand` representa intenção comercial contextual da Organization compradora/frigorífico, não Policy. Pertence inicialmente a Titan Livestock, não ao Core. Sua existência não concede acesso automático a produtores.

Candidate Population representa o conjunto considerado por uma análise. A direção aprovada é `CandidatePopulationCriteria -> PopulationResolver -> CandidatePopulationSnapshot`; não é Aggregate Root standalone na primeira implementação.

`SupplyForecast` representa projeção determinística e explicável sob premissas explícitas, não Decision, Evaluation ou future eligibility. É computed-on-demand por padrão; snapshot imutável só existe quando houver artefato histórico/compartilhado. CUT F não deve introduzir ML/IA.

`SupplyDemandAnalysis` compõe demanda, readiness atual e forecast opcional.

`GapAnalysis` deriva de `RuleResult`, `missing_evidence_types`, coverage assessments, evaluation limitations, readiness gap information e source/knowledge limitations. Não cria taxonomia paralela.

`SupplyIntelligenceReport` é o nome aceito para o artefato analítico separado de Dossier/VerificationBundle. Ele pode ser hashable no futuro sem virar Dossier ou VerificationBundle.

Toda análise futura deve declarar `generated_at`, `reference_time`, `knowledge_cutoff`, Policy/versão, população de origem, filtros, premissas, limitações e autorização.

Fluxo conceitual futuro:

```text
CommercialDemand
 -> CandidatePopulationCriteria
 -> PopulationResolver
 -> CandidatePopulationSnapshot / resolved context
 -> MarketReadiness
 -> GapAnalysis
 -> optional SupplyForecast
 -> SupplyDemandAnalysis
 -> SupplyIntelligenceReport
```

## Critérios de aceite

- A SPEC e o Design Package são revisáveis sem produzir código.
- Todas as decisões arquiteturais restantes aparecem em HUMAN REVIEW.
- ADR-0069 está aceita como arquitetura, sem autorizar BUILD.
- `MarketReadiness` existente é reutilizado como read model derivado.
- Forecast permanece explicitamente fora de `Evaluation`, `Decision` e Dossier regulatório.
- O design usa `aggregate-first, identity-last`.
- O primeiro corte comercial futuro é decomposto e proposto, mas CUT F não é iniciado.

## Plano técnico

Nenhum plano de BUILD é autorizado. O design futuro deverá, se aprovado, criar corte posterior com:

- ownership de produto Livestock e persistência apenas quando necessária;
- autorização por Purpose/GrantScope/FieldScope;
- modelo temporal de demanda e forecast;
- forma de artefato analítico não regulatório `SupplyIntelligenceReport`;
- testes de privacidade, temporalidade e isolamento.

## Verificação e observabilidade

Verificação desta SPEC: revisão documental. Verificação futura exigirá testes unitários, tenant isolation, temporal, idempotency, auditoria e roteiros em `apps/validacao` se houver API observável.

## Documentação afetada

- `docs/plans/MARKET_SUPPLY_INTELLIGENCE_DESIGN_PACKAGE.md`
- `docs/adr/0069-market-supply-intelligence-analises-nao-regulatorias.md`
- `docs/product/MARKET_SUPPLY_INTELLIGENCE_CONCEPT.md`

## Riscos, alternativas e perguntas abertas

Riscos: vazamento por agregados, forecast lido como elegibilidade futura, CommercialDemand confundido com Policy, gap paralelo divergente de RuleResult.

Decisões resolvidas pelo Product Owner:

- `CommercialDemand` é Livestock-owned e pertence à Organization compradora/frigorífico.
- Candidate Population segue criteria/resolver/snapshot e não nasce como Aggregate Root standalone.
- SupplyForecast é computed-on-demand por padrão, determinístico no início e sem ML/IA em CUT F.
- Hipóteses corretivas participam apenas como cenários/premissas explícitas.
- GapAnalysis deriva de material canônico existente.
- `SupplyIntelligenceReport` é o nome aceito e fica separado de Dossier/VerificationBundle.

HUMAN REVIEW restante:

- Autorizar ou rejeitar CUT F e sua decomposição concreta.
- Aprovar contrato técnico de persistência/API para cada corte futuro.
- Aprovar forma técnica de snapshot/digest/artefato antes de produção.
