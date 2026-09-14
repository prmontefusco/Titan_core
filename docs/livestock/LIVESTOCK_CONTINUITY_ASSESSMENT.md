# Livestock Continuity Assessment

**Data:** 2026-09-14
**Tipo:** Reconhecimento e diagnóstico (fase 0 de uma nova frente). **Não é SPEC, não é PLAN, não autoriza BUILD.**
**Autor:** sessão de assistência, a pedido do responsável.
**Escopo:** vertical Titan Livestock como um todo — domínio, aplicação, infraestrutura, API, UI, roteiros de validação e o ledger (`docs/CHECKLIST_DE_IMPLEMENTACAO.md`). Não cobre Titan Asset & Sustainment (vertical irmã em bootstrap) nem o Core além do necessário para explicar reutilização.
**Método:** leitura integral de `AGENTS.md`, `VISION.md`, `DOMAIN.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md`, `docs/CHECKLIST_DE_IMPLEMENTACAO.md` (5524 linhas, integral), `docs/CORTE_MVP_BACKEND.md`, `docs/livestock/COMMERCIAL_PASSPORT_CONCEPT.md`, `docs/livestock/COMMERCIAL_PASSPORT_IMPLEMENTATION_PLAN.md`, ADR-0080, ADR-0081, `docs/architecture/TITAN_TRUST_CORE_ASSESSMENT.md`, `docs/architecture/VERTICAL_OWNERSHIP_MATRIX.md`; mais inventário verificado do sistema de arquivos real (`packages/livestock_domain`, `packages/livestock_application`, `packages/livestock_infrastructure`, `apps/api`, `apps/web/src`, `apps/validacao`, migrations). Nenhum código foi lido linha a linha além do necessário para confirmar existência e assinatura pública; a fonte de verdade sobre comportamento foi o próprio checklist, que descreve testes e portões reais.

---

## 1. Resumo executivo

Titan Livestock é, hoje, a vertical mais madura do Titan — a única em produção conceitual completa, da fundação (Marco 8) até um produto de frontend operacional (Marco 19) e uma segunda onda de capacidades comerciais (Commercial Passport F1–F13, Market Supply, Market Optionality, AI Explanation Governance). O volume de disciplina arquitetural é incomum: 87 migrations, temporalidade bitemporal (`reference_time` × `knowledge_cutoff`) aplicada de forma consistente, uma auditoria adversarial completa em setembro de 2026 (FINDING-001 a FINDING-013, todos remediados), e um padrão de reuso do Core (`FactSnapshot → Policy/Rule → Evaluation → Decision → Dossier/VerificationBundle`) já provado por múltiplos consumidores dentro da própria vertical.

A resposta à pergunta principal do usuário — *como continuar evoluindo o Livestock de forma incremental, fortalecendo os fatos operacionais e a reutilização por produtos como Commercial Passport, sem abstrações desnecessárias nem duplicação* — é que **o mecanismo de reuso já existe e já funciona**: Commercial Passport (concluído F1–F13, mas release-gated), Market Eligibility Dossier (NEXT-05), Market Optionality Dossier section (F6) e o dossiê farmacológico original compartilham exatamente os mesmos `Dossier`/`VerticalSection`/`VerificationBundle` do Core, sem nenhum framework paralelo. ADR-0081 já declara isso formalmente ("Trust Core... não é módulo novo"). Não há necessidade de inventar uma nova camada de reuso — há necessidade de **alimentar essa camada com mais fatos operacionais reais e de decidir prioridades normativas que hoje ficam deliberadamente indeterminadas**.

Os gaps reais não são de arquitetura, e sim de **cobertura de fato e de decisão normativa pendente**: cadeia de fornecedor indireto via GTA (não iniciada), integração oficial SISBOV (bloqueada por ADR pendente), camada MapBiomas (não iniciada), e — o achado mais importante deste levantamento — **os caminhos de mercado China/UE hoje retornam `INDETERMINADO` por padrão** desde que o portão normativo fail-closed (ADR-0061, 13/08/2026) passou a exigir `NormativeBasisSnapshot` persistido, que ainda não existe para nenhum mercado real. Isso é comportamento correto e documentado, mas é uma regressão de experiência de demonstração em relação ao "fechamento do MVP" de 30/07/2026, e nenhum documento fora do checklist bruto avisa disso.

**Recomendação final: PROCEED**, com as prioridades da seção 8, sem nenhuma reformulação de arquitetura. Nenhum conflito entre `DOMAIN.md`/`ARCHITECTURE.md`/`DEVELOPMENT.md` e o código foi encontrado. Um conflito de **documentação operacional** (não de documento de autoridade) foi encontrado e está registrado na seção 6.1.

---

## 2. Estado atual da vertical Livestock

| Marco/Frente | Estado | Evidência |
|---|---|---|
| Marco 8 — fundação (`RuralProperty`, `Animal`, `Veterinarian`, `LivestockLot`, `AnimalMovement`/`PropertyStay`) | CONCLUÍDO E APROVADO (23/07/2026) | `docs/CHECKLIST_DE_IMPLEMENTACAO.md:2690-2876` |
| Marco 9 — farmacovigilância e carência | CONCLUÍDO (23/07/2026) | idem `:2877-2994` |
| Marco 10 — eventos, timeline, dossiê JSON/PDF, API mínima, demo | CONCLUÍDO (24/07/2026) | idem `:3014-3337` |
| Marco 12 — API de leitura completa (36 rotas) | CONCLUÍDO (25/07/2026) | idem `:3339-3390` |
| Marco 13 — ciclo de vida do animal (saída, genealogia, nascimento/ADR-0040) | CONCLUÍDO E VALIDADO (25/07/2026) | idem `:3391-3610` |
| Marco 11 — transformação industrial e rastreabilidade de produto (abate/desossa, fan-out/fan-in, recall, correção) | CONCLUÍDO (28/07/2026), ADR-0046/0047 | idem `:566-587` — **nota:** `docs/CORTE_MVP_BACKEND.md` diz o oposto; ver §6.1 |
| Marco 17 — elegibilidade por mercado e conformidade territorial | PARCIAL — georreferenciamento/CAR/IBAMA concluídos e validados; FUNAI/PRODES/DETER lidos via API real desde 10/09/2026; nenhuma camada amarrada a `MarketProfile` por padrão | idem `:3611-3750`, `:5114-5127` |
| Marco 18 — conformidade sanitária vitalícia (LIV-C01–C09, POST-LIV-01/02A) | CONCLUÍDA | idem `:3751-3849` |
| POST-LIV-02B (adaptador Odoo) | DESENHADA, NÃO IMPLEMENTADA | idem `:3843` |
| POST-LIV-03 (SISBOV real) | Corte 1 concluído; Corte 2 **AGUARDANDO ADR** | idem `:3849-3853` |
| Marco 19 — primeiro produto de frontend do Livestock | CONCLUÍDA (06/08/2026), mais ~15 incrementos de UI até 10/09/2026 | idem `:3855-3880`, `:5023-5153` |
| NEXT-01 a NEXT-07 — coverage/admissibilidade, Policy temporal, autoridade por requisito, Market Eligibility Dossier, Market Readiness, Market Change Impact | CONCLUÍDOS, mas validados exclusivamente contra Policies fictícias (`SANITARY_TEST_A_v1`, `MARKET_TEST_A`, `AUTHORITY_TEST_A`) | idem `:3881-3938` |
| ADR-0058/POST-LIV-03 — captura externa SISBOV simulada | Corte 2B validado localmente | idem `:3943-3971` |
| Auditoria independente de 13/08/2026 — hardening temporal/normativo | ENCERRADA para os itens levantados; portão fail-closed de Market Eligibility mudou comportamento de produção (ver §6.2) | idem `:3973-4067` |
| NEXT-08/08b — autoria declarativa de regras (NR-5) | CONCLUÍDOS, fecha a NR-5 | idem `:4291-4317` |
| NEXT-09/10/11 — BuyerPolicy Fases 1–3 | CONCLUÍDOS | idem `:4319-4554` |
| NEXT-12 — Market Supply & Lifetime Compliance | CUT A–F3.5V concluídos; **buyer-facing/cross-tenant real NÃO iniciado**; endpoint existe atrás de duas feature flags e ainda falha fechado sem pipeline | idem `:4555-4730` |
| Market Optionality (F0–F7) + AI Explanation Governance (ADR-0074/0075) | CONCLUÍDOS; endpoint feature-flagged, Gemini atrás de flag desligada por padrão | idem `:4731-4816` |
| FINDING-001 a FINDING-013 (auditoria adversarial de 08–09/09/2026) | TODOS CONCLUÍDOS | idem `:4817-5022` |
| Commercial Passport F1–F13 | CONCLUÍDO; **release-gated**, `TITAN_COMMERCIAL_PASSPORT_API_ENABLED` desligada por padrão | idem `:41-397`; `docs/livestock/COMMERCIAL_PASSPORT_IMPLEMENTATION_PLAN.md` |

**Leitura de conjunto:** a vertical não tem "trabalho pela metade" no sentido comum — cada frente listada acima fechou com testes, portão e (na maioria) validação manual contra API/PostgreSQL/Keycloak reais. O que existe é **capacidade construída e não ligada por decisão deliberada** (feature flags desligadas, `MarketProfile` sem regra amarrada, normative basis não persistida para mercado real) — um padrão consistente e correto pelo próprio `AGENTS.md`/`DEVELOPMENT.md` ("nunca invente requisitos"), mas que precisa ser visível para quem decide o que priorizar a seguir.

---

## 3. Capacidades existentes (auditoria por área solicitada)

### Property
`packages/livestock_domain/property.py` (`RuralProperty`) + `geometry.py` (`PropertyGeometry`, versionada, nunca sobrescrita, digest sobre o payload original do SICAR). Importação do CAR via `packages/livestock_infrastructure/geodata/car_client.py` (provider `Titan_geodata`, opcional, `503` nomeando a variável ausente). Camadas do próprio imóvel (`RESERVA_LEGAL`, `APPS`, `USO_RESTRITO`) tratadas como dimensão por `(property_id, layer, version)`, distintas de camadas territoriais externas (embargo, terra indígena, desmatamento). `environmental_embargo_service.py`/`environmental_embargo_assertion_service.py` cruzam geometria vigente contra IBAMA real. `territorial_overlap_service.py`/`territorial_timeline_service.py` leem FUNAI/PRODES/DETER reais (validado 10/09/2026 contra `Titan_geodata` real, `apps/validacao/funai.py` 5/5 e `apps/validacao/timelines_territoriais.py` 6/6). `protected_area_stay_service.py` cruza `PropertyStay` com as camadas do próprio CAR. `territorial_capture.py`/`territorial_adapter.py` fornecem captura **versionada e sintético-realista** (perfis `PRODES_LIKE`/`DETER_LIKE`/`FUNAI_LIKE`/`IBAMA_LIKE`) para reconstrução histórica — distinto das leituras em tempo real acima, porque o provider não oferece arquivo ponto-no-tempo das camadas externas.

### Animal
`animal.py` (`Animal`, `AnimalIdentifier` com histórico de brincos/SISBOV/RFID). `exit.py`/`exit_service.py` — saída terminal (morte/abate/venda/transferência definitiva) como fato derivado, nunca campo mutável, com `UNIQUE(animal_id)` no banco. `reproduction.py`/`reproduction_service.py` — nascimento como origem da identidade (ADR-0040), natimorto distinto de morte, gemelar como um só parto. `parentage.py`/`parentage_service.py` — maternidade genética vs. gestacional, paternidade múltipla só entre vínculos declarados, tudo via `UniversalRelation` do Core (sem tabela própria). FINDING-002 Parte A (08/09/2026) blindou `animals` com trigger PostgreSQL que só aceita incremento unitário de `version`; FINDING-003 (09/09/2026) escopou as FKs de propriedade por Organization.

### Lot
`lot.py` (`LivestockLot`, `LotMembership`) + `lot_service.py`. Regra de exclusividade rígida para lotes operacionais/manejo; sobreposição permitida para lotes sanitários/comerciais. Composição temporal consultável (`/lots/{id}/members?at_time=`).

### Movement
`movement.py` (`AnimalMovement` — fato autoritativo; `PropertyStay` — projeção reconstruível). ADR-0062/T-05A: `PropertyStay` histórico é reconstruído **exclusivamente** a partir da cadeia append-only de `AnimalMovement`, nunca da projeção mutável atual — invariante testado (T0/T1/T2, sequência conflitante, isolamento entre Organizations).

### Treatments / Medications / Withdrawal periods
`medication.py`, `prescription.py`, `treatment.py`, `withdrawal.py`. Correção sempre por novo registro apontando para o original (nunca sobrescrita); carência calculada com contribuições auditáveis (`WithdrawalContribution`, congela o prazo usado). `medication_classification.py` — `MedicationSanitaryClassificationAssertion` versionada (ADR-0056), distingue `NO_ASSERTION`/`UNKNOWN`/`DOES_NOT_APPLY`. Leitores temporais estritos (ADR-0062 T-05C1/C2) reconstroem aplicação e carência histórica só quando material canônico e evento correspondem byte a byte. `erp_outbox.py`/`erp_inbox.py` — contrato outbound neutro (LIV-C08/POST-LIV-02A), simulado (`apps/worker/livestock_handlers.py`), sem adaptador Odoo real.

### Sanitary campaigns
`sanitary_campaign.py`/`sanitary_campaign_service.py` — campanha oficial e exigibilidade mínima. `sanitary_requirement_service.py` gera fato por campanha (`sanitary_requirement_fact_type`), consumível por regra governada — mecanismo pronto, **nenhum `MarketProfile` amarrado por padrão** (decisão normativa deliberadamente adiada). Leitor temporal estrito T-05C3 reconstrói atendimento histórico só com evento canônico correspondente.

### Genealogy/reproduction
Ver "Animal" acima. Vocabulário `DECLARADO`/`DOCUMENTADO`/`VERIFICADO_EM_FONTE` traduzido para `ConfidenceTier` na fronteira, sem vazar para o Core. Limite conhecido e registrado: ciclo profundo de parentesco não é detectado (só visitados diretos); doadora de embrião de outra Organization não pode ser registrada (exige decomposição própria, é caso de origem externa declarada, não vínculo).

### Animal exit/death/sale/slaughter
`exit.py` cobre a saída do animal individual. `transformation.py`/`transformation_service.py` (`SlaughterService`, `DeboningService`) cobrem o abate/desossa como `TransformationEvent` fan-out/fan-in (ADR-0046), com correção append-only (`corrects_transformation_id`, ADR-0047), bloqueio pessimista provado contra PostgreSQL real (`ThreadPoolExecutor`+`Barrier`), e dossiê próprio de `TraceableItem` reaproveitando `RecallService`/`LivestockTimelineService` do Core sem alterá-los. **Este bloco está completo desde 28/07/2026** — ver nota de discrepância documental em §6.1.

### Timeline
`timeline_service.py` (`LivestockTimelineService`) — `animal_timeline`, `lot_timeline`, `treatment_timeline`, `item_timeline` (produto). Ordenação por chave total `(occurred_at, tipo do agregado, id, origem, sequência, id da origem)`, nunca só por instante. Corte bitemporal (`occurred_until` × `known_until`) desde o Passo 10.1b. Porta `CanonicalDomainEventReader` do Core (ADR-0063) permite reconstrução histórica estrita de identificadores/tratamentos/carência/campanhas sem tocar em projeção atual.

### Evidence
Livestock não duplica `Evidence` do Core — referencia via `UniversalReference` tipado (10.2a), com `evidence_notes` separado de evidência (anotação de operador nunca vira prova). `EvidenceLookupPort` recusa citar evidência inexistente ou de outra Organization com a **mesma** mensagem ("não encontrada"), evitando oráculo. FINDING-002 Parte B (09/09/2026) tornou `evidences` append-only de verdade no Core (assinatura/verificação/revogação como tabelas próprias, nunca `UPDATE` na linha base).

### Eligibility
Duas trilhas coexistem, coerentes entre si, não duplicadas: (a) `market_eligibility.py` — matriz China/EUA/UE em produção desde 26–27/07/2026, avaliação independente por finalidade, sujeito secundário (frigorífico), `REAVALIACAO_NECESSARIA`; hoje **também** sob o portão fail-closed de `NormativeBasisSnapshot` (ADR-0061) — ver §6.2. (b) `eligibility.py` — elegibilidade farmacológica interna, com sua própria fotografia normativa controlada (`InternalPharmacologicalNormativeBasisSnapshotProvider`), usada como âncora operacional do dossiê.

### Market readiness
`market_readiness.py` (`MarketReadinessService`) — read model transitório sobre Decisions/Evaluations já existentes, nunca reexecuta Rule nem emite Decision; `READY` só sob contexto exato. `market_optionality.py` compõe isso em relatórios multi-mercado, impacto de mudança de Policy e explicações guiadas por IA (todas fail-closed, todas application-only, nenhuma persistida como fonte de verdade).

### Commercial Passport integration
F1–F13 completos (ver §2). Reutiliza `MarketReadinessReport` como pipeline produtiva inicial (F9), `DossierService`/`VerificationBundleService` para emissão formal (F10), sem framework paralelo. Release-gated (`TITAN_COMMERCIAL_PASSPORT_API_ENABLED=false` por padrão) — **não alterado por este assessment**, apenas referenciado conforme instrução.

### Dossier/VerificationBundle usage
Quatro seções verticais independentes já usam o mesmo `VerticalSection`/`Dossier`/`VerificationBundle` do Core: dossiê farmacológico (10.2b), `MarketEligibilityDossierSectionBuilder` (NEXT-05), `MarketOptionalityDossierSectionBuilder` (F6), `CommercialPassportDossierSectionBuilder` (F5). `LivestockVerificationBundleInterpreter` (ADR-0060) é o único ponto de extensão — Core nunca interpreta `namespace == livestock` diretamente. Isso é a prova concreta, dentro do próprio repositório, de que o padrão de reuso pedido pelo usuário já está funcionando para múltiplos produtos.

### Audit/provenance
Cadeia de eventos append-only com hash encadeado desde o Marco 4, agora com assinatura Ed25519 por elo (FINDING-007, 09/09/2026, `packages/core_integrity/event_chain.py`). `ProvenanceService` e `evidence_content()` reaproveitados sem alteração pela vertical. RLS forçado e explícito em praticamente toda tabela sensível (permissions, quarentena, idempotência, grants — FINDING-008/009/010). Triggers PostgreSQL recusam `UPDATE`/`DELETE`/`TRUNCATE` em tabelas históricas mesmo para role administrativa (FINDING-002).

### Authorization and Organization boundaries
RLS por Organization em toda tabela da vertical; defesa em profundidade explícita (`OrganizationContextService` confere `membership.organization_id == requested_organization_id`, não confia só em RLS — achado do Passo 10.4a). Permissão granular (nunca papel) em toda rota. `organization_id` nunca aceito do cliente. FKs de propriedade agora compostas por Organization (FINDING-003). Market Supply implementa um segundo nível de autorização inteiro (`AuthorizationGrant` bilateral, `AggregationPrivacyPolicy`, differencing, audit owner-scoped) — sofisticado, mas sem nenhum consumidor buyer-facing real ainda.

### UI Livestock
`apps/web/src/pages/`: `LivestockHome`, `AnimalSearch`/`AnimalDetail`/`AnimalTimeline`/`AnimalEligibility`, `LotSearch`/`LotDetail`, `TreatmentForm`, `MarketMatrix`, `MarketRuleGovernance`, `MarketSupplyAggregate`, `CommercialExplanation`, `CommercialPassport`, `DecisionReview`, `AdminDashboard`, `TerritorialCaptureQa`. Padrões compartilhados (`DetailPage`, `AsyncStates`, `PageContext`) extraídos só depois de segundo consumidor real — sem antecipação. FINDING-012 corrigiu retry de token expirado. Fora de escopo deliberado: seletor de Organization, gestão de Membership/convite, Roles/Capabilities UI, audit browser, operations dashboard (ADMIN-CUT-01 é explícito sobre isso).

### apps/validacao Livestock scripts
38 scripts, todos sob o padrão do `AGENTS.md` (descobrem Organization/entidades sozinhos, mostram requisição/resposta, explicam o porquê, sondam ambiente antes do primeiro passo, suportam `--pausar`). Cobrem desde o fluxo fundacional (`__main__.py`) até os mais recentes: `commercial_passport_api.py`, `market_supply_aggregate_api.py`, `market_optionality_ai_explanation_api.py`, `ai_explanation_pipeline_smoke.py`, `captura_territorial_sintetica.py`, `captura_externa_sisbov_simulada.py`. `fumaca.py` roda a suíte inteira em sequência.

### checklist entries related to Livestock
O checklist é a única fonte de verdade de status (por regra do próprio `AGENTS.md`) e está atualizado até 14/09/2026 (Commercial Passport F13). Está coerente internamente; a única divergência encontrada foi contra um documento **fora** do checklist (`CORTE_MVP_BACKEND.md`) — ver §6.1.

---

## 4. Principais fluxos já implementados (ponta a ponta, validados)

1. **Cadastro → tratamento → bloqueio por carência → correção → reavaliação → dossiê** (`apps/demo`, Marco 10.6) — a demonstração canônica da tese do produto.
2. **Fazenda → animal → histórico/importação → frigorífico → elegibilidade China/EUA/UE** (`apps/validacao/simulacao_comercial.py`, 11/11 passos).
3. **Nascimento → genealogia → saída do rebanho**, com regularização de registro atrasado mesmo após a saída (Marco 13).
4. **Abate → desossa → correção → recall através da cadeia** (`apps/validacao/transformacao_industrial.py`, 28/28 passos).
5. **Georreferenciamento → importação do CAR → embargo IBAMA → matriz de mercado** (validado com 3 CAR reais de MS, desvio de área 0,02–0,04%).
6. **Governança de regra declarativa → publicação → adoção → tela de autoria** (NEXT-08/08b, fecha a NR-5).
7. **BuyerPolicy: avaliação interna → compartilhamento bilateral → autoavaliação de fornecedor → composição com matriz** (NEXT-09/10/11).
8. **Commercial Passport: consulta dinâmica → emissão formal → Dossier/VerificationBundle**, validado autenticado e fail-closed (F1–F13).
9. **Market Supply: grant → população candidata → readiness → privacidade → auditoria durável → resposta pública uniforme**, validado ponta a ponta contra PostgreSQL real (F3.5U) — mas sem nenhum comprador real por trás.

---

## 5. Componentes relevantes (mapa por camada)

| Camada | Onde | Observação |
|---|---|---|
| Domain | `packages/livestock_domain/` — 27 arquivos, ~4.1k LOC | Agregados/entidades + invariantes em `__post_init__`; nenhum framework, nenhum SQL, nenhum HTTP |
| Application | `packages/livestock_application/` — 69 arquivos, ~21.3k LOC | Concentra a maior parte da lógica (elegibilidade, temporalidade, Market Supply, Market Optionality, AI Explanation) — coerente com `ARCHITECTURE.md` (Application coordena Policy/Evaluation/temporalidade), mas é o ponto de maior massa de código e maior risco de complexidade acumulada |
| Infrastructure | `packages/livestock_infrastructure/` — 36 arquivos, ~8k LOC | Repositórios transacionais (RLS-aware), `geodata/car_client.py`, `sisbov_simulator_http.py`, `ai_explanation_provider.py` (Gemini), template de PDF |
| API | `apps/api/livestock_*.py` (14 routers) + `livestock_dependencies.py` (raiz de composição) | Nenhuma rota `PUT`/`PATCH`/`DELETE`; contrato de erro uniforme; 3 rotas feature-flagged (`commercial_passport`, `market_supply`, `market_optionality_explanation`) |
| Web | `apps/web/src/pages/` (13 páginas) + `apps/web/src/api/` (10 clients) | Ver §3 "UI Livestock" |
| Validação | `apps/validacao/` (38 scripts) | Ver §3 "apps/validacao" |
| Migrations | `packages/core_infrastructure/persistence/migrations/versions/` (87 arquivos, ambiente **compartilhado** com o Core; extração para ambiente próprio está desenhada em ADR-0080 mas `BLOCKED_WHILE_LIVESTOCK_ACTIVE`) | — |

---

## 6. Lacunas reais

### 6.1. Documento de status desatualizado e incorreto — `docs/CORTE_MVP_BACKEND.md`

**Não é conflito com documento de autoridade** (`DOMAIN.md`/`ARCHITECTURE.md`/`DEVELOPMENT.md`) — é um documento operacional (`docs/CORTE_MVP_BACKEND.md`) que ficou parado em 27–30/07/2026 e hoje contradiz tanto o checklist quanto o código real:

- Seção "O que está fora do MVP", item 5, afirma: *"Nada do Marco 11 em diante (abate, EPCIS/GS1, `TransformationEvent`, fan-out/fan-in de produto) está implementado."*
- O próprio `docs/CHECKLIST_DE_IMPLEMENTACAO.md` (linhas 566–587) registra o Marco 11 completo — ADR-0046, ADR-0047, Passos 11.2 a 11.7, `packages/livestock_domain/transformation.py`, `packages/livestock_application/transformation_service.py`, `apps/api/livestock_transformations.py`, `apps/validacao/transformacao_industrial.py` — **concluído em 28/07/2026, dois dias antes da última atualização registrada do próprio `CORTE_MVP_BACKEND.md`.**
- O inventário do sistema de arquivos confirma que os módulos existem e têm testes (173 testes só no Passo 11.7).

Isso não bloqueia trabalho — mas qualquer pessoa (ou agente) que use `CORTE_MVP_BACKEND.md` como referência de escopo vai subestimar a vertical e potencialmente reimplementar algo que já existe. Como o próprio documento se declara "não é o checklist, é a leitura de cima para baixo", o risco é justamente ele ser lido como se fosse atual. Ele também não reflete nenhuma das frentes de agosto/setembro (Marco 18, Marco 19, NEXT-01 a NEXT-12, Commercial Passport, Market Supply, Market Optionality, AI Explanation, FINDING-001 a 013).

**Recomendação:** atualizar `docs/CORTE_MVP_BACKEND.md` para refletir o estado de 14/09/2026, ou marcá-lo explicitamente como "HISTÓRICO — consulte `docs/CHECKLIST_DE_IMPLEMENTACAO.md` para o estado atual" no topo do arquivo. Isto é edição de documentação, cabe dentro das regras desta frente (não é código, não é migration, não é API).

### 6.2. Mercados de produção (China/UE) hoje respondem `INDETERMINADO` por padrão

Em 13/08/2026, a ADR-0061 introduziu um portão fail-closed: `MarketEligibilityService` não avalia nem persiste `Evaluation`/`Decision` quando não existe `NormativeBasisSnapshot` temporal elegível para a Policy/Rule do mercado (checklist, linha 4017). O checklist registra explicitamente: *"os caminhos HTTP para UE/China passam a declarar a lacuna, em vez de alegar elegibilidade ou reprovação sob fundamento inexistente."* Hoje só existe uma base normativa persistida controlada para o caso `MARKET_TEST_A` (fictício) e para a elegibilidade farmacológica interna (`InternalPharmacologicalNormativeBasisSnapshotProvider`) — **nenhum mercado real (China/EUA/UE) tem `NormativeBasis` persistida.**

Isso é comportamento correto pela própria filosofia do produto (nunca inventar fundamento normativo) e está documentado no ponto exato em que aconteceu — mas é uma mudança de comportamento observável em relação ao "fechamento do MVP" de 30/07/2026, quando os mesmos três mercados respondiam de forma decisiva via `apps/validacao/simulacao_comercial.py`. Nenhum documento de resumo (nem `CORTE_MVP_BACKEND.md`, que é anterior a essa mudança) avisa disso hoje.

**Não é um bug** — é uma lacuna de decisão normativa que precisa ser resolvida por quem decide produto: registrar `NormativeBasis` real (mesmo que mínima/interna) para os mercados já demonstrados, ou aceitar formalmente que a demonstração comercial de julho está temporariamente indisponível até essa base existir.

### 6.3. Fornecedor indireto / GTA — maior lacuna de valor comercial, não iniciada

ADR-0042 modela contraparte externa e artefato de transferência recebido, mas a cadeia real cria→recria→engorda depende da GTA (estadual, heterogênea) — **não há ingestão nenhuma.** As próprias notas de rumo do produto (NR-6, NR-8) já identificam isso como o maior gap de valor comercial e como o "wedge" de adoção mais barato (GTA é obrigatória e dolorosa para o produtor). Nada foi implementado; é trabalho de descoberta, não de código.

### 6.4. Camadas territoriais reais incompletas

CAR, IBAMA (real) e FUNAI/PRODES/DETER (real, desde 10/09/2026) estão lidos. **MapBiomas não foi tocado.** Nenhuma das quatro camadas externas está amarrada por padrão a um `MarketProfile` — decisão normativa, não técnica, deliberadamente adiada em cada entrada do checklist que a toca. A reconstrução histórica versionada dessas camadas (necessária para decisões retroativas, como o próprio domínio exige) só existe em forma sintético-realista (`T-05D`), porque o provider `Titan_geodata` não oferece arquivo ponto-no-tempo real das camadas externas — isso é uma limitação de fonte externa, registrada, não do Titan.

### 6.5. SISBOV oficial bloqueado por ADR pendente

`POST-LIV-03` Corte 1 (captura simulada, `SISBOV_SIMULATOR_LOCAL`) está concluído e validado. Corte 2 (promoção de captura/review para fato admissível) está explicitamente **aguardando ADR** — decisão consciente, não esquecimento.

### 6.6. Adaptador ERP real (Odoo) — só desenho

`POST-LIV-02B` tem dois documentos de design aprovados e zero código. O contrato outbound neutro (LIV-C08/POST-LIV-02A) já existe e funciona com um simulador local — a porta está pronta, falta o adaptador real, e isso depende de decisão humana explícita (o próprio checklist registra isso).

### 6.7. Market Supply — grande investimento de engenharia sem consumidor real

NEXT-12 é provavelmente o maior volume de trabalho isolado do checklist (dezenas de cortes, CUT A a F3.5V, mais de dez ADRs/SPECs). Todo ele é `application-only` até muito perto do fim, e o único endpoint HTTP exige **duas** feature flags (`TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED` e `TITAN_MARKET_SUPPLY_AGGREGATE_PIPELINE_ENABLED`) e ainda assim não tem nenhum comprador real testando. Isto não é um defeito — é disciplina de release gate — mas é uma quantidade de capacidade "pronta e esperando" grande o bastante para merecer uma decisão explícita de produto: comprometer-se com um piloto buyer-facing, ou parquear conscientemente a frente.

### 6.8. Timezone por propriedade não modelado (FINDING-011)

Toda a vertical opera em UTC estrito; não há timezone IANA por `RuralProperty`. Aceitável hoje (o achado da auditoria confirmou que não há conversão implícita incorreta), mas se uma implantação real precisar de datas civis locais (ex.: para determinar "dia do abate" versus instante UTC), essa modelagem ainda não existe.

### 6.9. Ambiente de migration ainda compartilhado com o Core

Reconhecido pela própria ADR-0080 como débito técnico esperado, com extração desenhada (Opção D→C de `MIGRATION_CONCURRENCY_STRATEGY.md`) mas **bloqueada enquanto Livestock estiver ativo** (janela de integração coordenada com a vertical Asset). Não é urgente; é relevante para quando a vertical Asset atingir maturidade suficiente para justificar a janela.

---

## 7. Riscos arquiteturais e de produto

| Risco | Natureza | Nota |
|---|---|---|
| Confundir capacidade construída com capacidade disponível | Produto | Commercial Passport, Market Supply e Market Optionality estão "prontos" mas atrás de feature flags — decisões de negócio pendentes, não bugs |
| `CORTE_MVP_BACKEND.md` desatualizado sendo usado como referência de escopo | Documentação | Ver §6.1 — risco concreto de retrabalho |
| Regressão silenciosa de "mercado real funciona" para "mercado real indeterminado" sem aviso central | Produto/comunicação | Ver §6.2 |
| Concentração de lógica em `livestock_application` (~21k LOC, ~5× o domínio) | Arquitetural, baixo | Consistente com `ARCHITECTURE.md` (Application coordena temporalidade/Policy), mas é o maior pacote da vertical e o de maior custo de manutenção; nenhuma violação de camada encontrada, apenas volume |
| Governança de desenvolvimento paralelo (Asset & Sustainment em bootstrap) | Processo | `ADR-0080`, `docs/architecture/VERTICAL_OWNERSHIP_MATRIX.md` e `PARALLEL_VERTICAL_DEVELOPMENT_PROTOCOL.md` definem Lane A (Livestock) com fronteiras de arquivo explícitas; qualquer trabalho futuro nesta frente deve respeitar essas fronteiras e não tocar `packages/core_*`, `packages/asset_*` ou o ambiente de migration compartilhado sem processo de Shared Integration |
| GTA/fornecedor indireto sem verificação automática | Produto/risco regulatório | Contaminação por fazenda embargada pode viajar pela cadeia sem o Titan enxergar — risco nomeado pelo próprio `CORTE_MVP_BACKEND.md` e ainda válido |
| `Assertion` como padrão emergente não generalizado (NR-7) | Arquitetural, monitorado | Já apareceu 4+ vezes (continuidade, contraparte, fato importado, paternidade); decisão consciente de não generalizar ainda — reavaliar na próxima ocorrência |

**Nenhum risco de primeira ordem** (violação de `DOMAIN.md`/`ARCHITECTURE.md`, vazamento de conceito de vertical para o Core, abstração antecipada sem segundo consumidor) foi encontrado.

---

## 8. Prioridades recomendadas

Ordenadas por razão prática (decisão barata primeiro, depois engenharia de maior alavancagem comercial):

1. **Atualizar ou aposentar `docs/CORTE_MVP_BACKEND.md`** (documentação, custo mínimo, evita retrabalho e desinformação de agentes futuros).
2. **Decisão de produto sobre `NormativeBasis` para mercados reais** (China/EUA/UE) — registrar base normativa real (mesmo mínima) ou aceitar formalmente o `INDETERMINADO` como estado atual e comunicar isso.
3. **Discovery de ingestão de GTA** — maior valor comercial não capturado, já apontado três vezes pelas próprias notas de rumo do produto (NR-6/NR-8); usa o padrão de contraparte externa/proveniência (ADR-0042) já provado.
4. **Decisão normativa: amarrar pelo menos uma camada territorial (FUNAI/PRODES/DETER/IBAMA) ou uma campanha sanitária a um `MarketProfile` real** — mecanismo pronto nos dois casos, falta somente a decisão de qual mercado exige o quê.
5. **Decisão de produto sobre Market Supply**: comprometer-se com piloto buyer-facing (existe F3.5 SPEC/PLAN pronto) ou parquear conscientemente.
6. **MapBiomas** como quarta camada territorial, reusando o padrão já estabelecido (`TerritorialOverlapService`/`TerritorialTimelineService`/`TerritorialSourceCapture`).
7. **POST-LIV-03 Corte 2** (SISBOV real) — retomar quando a ADR pendente for decidida.
8. Itens de menor urgência: timezone por propriedade (só se um deployment real exigir), extração do ambiente de migration (só quando a janela de integração com Asset abrir).

---

## 9. Plano incremental proposto

Nenhum destes itens é autorização de BUILD — são a sequência de `DISCOVERY`/`DECISION` que o próprio `DEVELOPMENT.md` exige antes de qualquer código, na ordem de prioridade acima:

1. **Incremento de documentação** (sem DISCOVERY formal, é correção de fato): atualizar `docs/CORTE_MVP_BACKEND.md` ou marcá-lo histórico.
2. **DECISION curta**: `NormativeBasis` para mercados reais — decisão de produto, não código; se aprovada, vira um corte pequeno e simétrico ao que já existe para `MARKET_TEST_A`/farmacológico.
3. **DISCOVERY formal**: ingestão de GTA — problema, fontes estaduais, heterogeneidade, alternativas, antes de qualquer SPEC.
4. **DECISION por mercado/camada**: qual `MarketProfile` consome qual fato territorial/sanitário já existente — não é trabalho de engenharia, é aprovação normativa.
5. **DECISION de produto**: Market Supply piloto vs. parque consciente.
6. **DISCOVERY leve** (reaproveitamento de padrão já maduro): MapBiomas.
7. Retomar POST-LIV-03 Corte 2 quando a ADR pendente for resolvida.

Cada um destes, se aprovado, deve gerar sua própria entrada no checklist no mesmo commit, como o `AGENTS.md` exige — não neste documento.

---

## 10. Itens explicitamente fora de escopo (desta frente e, em grande parte, já fora de escopo do produto)

- Qualquer alteração em Commercial Passport além desta leitura de estado (instrução explícita do usuário).
- Qualquer abstração nova no Core ou pacote `trust_*` — proibido por ADR-0081 e pela instrução desta frente.
- Rastreabilidade de produto além do que o Marco 11 já entrega (fan-out/fan-in já existe; alinhamento formal a EPCIS/GS1 é frente própria, NR-2).
- Finance, Insurance, marketplace, matching comprador-produtor, score financeiro — fora de escopo declarado do próprio Commercial Passport e do produto como um todo.
- Verificador ZKP / HTML-Wasm / runtime Wasm determinístico — `FUTURA_APROVADA` por ADR-0078, não MVP.
- Adaptador Odoo real — aguarda decisão humana explícita (POST-LIV-02B).
- Seletor de Organization, gestão de Membership/convite, Roles/Capabilities UI — decisões RED de tenancy/autorização, fora de escopo do frontend atual por decisão consciente (ADMIN-CUT-01, LIV-PROD-02).
- Autoria de regra via sandbox Wasm (ADR-0036) — caminho caro, NR-5 já fechou o caminho barato (`RuleCondition` declarativa); só revisitar se a maioria das regras reais não couber nas primitivas declarativas.
- Qualquer trabalho em `packages/asset_*`, `packages/core_*` ou no ambiente de migration compartilhado sem processo de Shared Integration (ADR-0080, `VERTICAL_OWNERSHIP_MATRIX.md`).

---

## 11. Arquivos/módulos prováveis de fases futuras

| Frente futura (se aprovada) | Arquivos centrais a tocar |
|---|---|
| Atualizar `CORTE_MVP_BACKEND.md` | `docs/CORTE_MVP_BACKEND.md` (só este) |
| `NormativeBasis` real por mercado | `packages/livestock_application/internal_test_normative_basis.py` (padrão a replicar), `market_eligibility.py`, migration nova análoga a `20260813_0074` |
| GTA / fornecedor indireto | `packages/livestock_domain/external_counterparty.py`, `imported_fact.py`, `transfer_artifact.py`, `packages/livestock_application/fact_provider.py` (hub central de fatos), novo adapter de infraestrutura |
| Amarrar `MarketProfile` a fato territorial/sanitário | `packages/livestock_application/market_eligibility.py`, catálogo de `livestock_rule_governance.py` — nenhuma tabela nova esperada |
| MapBiomas | `packages/livestock_infrastructure/geodata/car_client.py`, `territorial_overlap_service.py`/`territorial_timeline_service.py`, `fact_provider.py` |
| POST-LIV-03 Corte 2 | `packages/livestock_application/sisbov_simulator.py`, `external_source_capture_service.py`, nova ADR primeiro |
| Market Supply piloto buyer-facing | `apps/api/livestock_market_supply.py` (já existe, só falta pipeline real), `packages/livestock_application/market_supply*.py` (já existem, application-only) |
| Extração do ambiente de migration | `packages/core_infrastructure/persistence/migrations/` → novo `packages/livestock_infrastructure/persistence/migrations/`, coordenado com `docs/architecture/MIGRATION_CONCURRENCY_STRATEGY.md` |

---

## 12. Recomendação final

# PROCEED

Nenhum conflito entre `DOMAIN.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md` e o código foi encontrado — a única divergência real é documental e operacional (`CORTE_MVP_BACKEND.md`, §6.1), não arquitetural. O mecanismo de reuso que o usuário pediu para fortalecer — fatos operacionais alimentando Commercial Passport, elegibilidade de mercado, dossiês, auditoria e certificações — **já existe e já está provado por quatro consumidores reais dentro do próprio Core** (`VerticalSection`/`Dossier`/`VerificationBundle`). Não há necessidade de nova abstração; há necessidade de decisões normativas pendentes (§6.2 a §6.6) e de um discovery formal (GTA, §6.3) para o maior gap de valor comercial ainda aberto. A vertical pode continuar evoluindo incrementalmente exatamente pela disciplina que já demonstrou — DISCOVERY → DECISION → SPEC → PLAN → BUILD, uma coisa de cada vez, ledger atualizado no mesmo commit.
