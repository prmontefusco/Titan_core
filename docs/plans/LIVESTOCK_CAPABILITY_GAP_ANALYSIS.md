# Titan Livestock — Capability Gap Analysis

**Data da auditoria:** 12 de agosto de 2026
**Natureza:** análise estática, sem implementação
**Base de conclusão:** estado do repositório no instante da auditoria; planos e roadmap não foram tratados como funcionalidade.

## 1. Executive Summary

O Titan Livestock já possui uma cadeia funcional relevante de história vitalícia e decisão: registra Animal, identidade, propriedade/permanência, lotes, movimentos, reprodução/origem, tratamentos, medicamentos e lotes, prescrições, veterinários, campanhas sanitárias, transferências, fatos importados e correções; deriva `FactSnapshot`; executa `Policy`/`Rule`; persiste `Evaluation`; exige revisão humana quando a emissão automática não é autorizada; emite `Decision` sob `DecisionAuthorityProfile`; produz `Dossier` e `VerificationBundle`; e oferece APIs e testes PostgreSQL para a maior parte desse caminho.

Esse resultado é sustentado por código, não pelos planos: migrations `20260723_0033` a `20260731_0063`, serviços em `packages/livestock_application`, repositórios em `packages/livestock_infrastructure/persistence`, endpoints em `apps/api/livestock_*.py` e testes em `tests/livestock_*` e `tests/integration`.

A missão proposta é **compatível** com a arquitetura e o domínio atuais. A cadeia `realidade/evento → Fact/Evidence → provenance → coverage/gaps → FactSnapshot → Policy/Rules → Evaluation → Authority/review → Decision → Dossier/Verification` já é a direção normativa de `DOMAIN.md` (seções 5, 6, 10 e 13), `ARCHITECTURE.md` (Evidências; Fundamentação normativa; Decisões explicáveis; Verificação externa) e ADRs 0048–0055. Não há contradição arquitetural e não é necessário um segundo motor de compliance.

Contudo, a missão ainda não está comprovada de ponta a ponta para elegibilidade de mercado real. Os principais bloqueios são: (1) cobertura vitalícia é declarada sobretudo por `ReceivedTransferArtifact`, não uma avaliação completa de todos os intervalos e tipos de fato; (2) `NormativeBasisSnapshot` completo e a seleção multitemporal da ADR-0052 não atravessam integralmente o modelo persistido; (3) os perfis de mercado default em `market_eligibility.py` são configuração de vertical e não regras reais de UE/China/EUA; (4) autoridade externa, habilitação oficial e validação externa permanecem distintas e parcialmente implementadas; (5) o bundle verifica integridade/cobertura declarada, mas não comprova integralmente autoridade, trust e reexecução independente conforme ADR-0055; (6) não existe read model operacional seguro para readiness/impacto em escala.

Conclusão: o Titan é hoje uma **plataforma funcional de avaliação técnica e prova auditável com baseline sanitário**, mas não deve alegar autorização oficial de exportação nem cobertura vitalícia completa universal. Market eligibility deve ser uma reutilização/expansão das capacidades existentes, não um domínio paralelo.

## 2. Mission Compatibility

| Pergunta | Conclusão | Evidência |
|---|---|---|
| A. Compatível com arquitetura/domínio? | Sim | `VISION.md` (decisões baseadas em evidências); `DOMAIN.md` §§2, 5, 6, 10, 13; `ARCHITECTURE.md` seções Evidências, Fundamentação normativa e Decisões explicáveis. |
| B. Exige apenas capacidades da vertical? | Em grande parte | Tipos de fato sanitário, cobertura da vida do animal, regras e finalidades de mercado pertencem a Livestock; ADR-0041 mantém mercado como `purpose`. |
| C. Exige extensão do Core? | Extensão de implementação, não novo conceito central | `NormativeBasisSnapshot`, temporalidade, validation/admissibility, impact assessment, authority e verification já estão modelados no Core normativo, mas vários não possuem fluxo persistido completo. |
| D. Contradiz ADR existente? | Não | ADRs 0041, 0044 e 0048–0055 reforçam avaliação contextual, temporal, explicável e sem overclaim. |

Não se recomenda `MarketEligibility` como verdade persistida do Animal. ADR-0041 determina que elegibilidade é relação entre Subject, finalidade e Policy versionada; `Evaluation` e `Decision` já representam essa relação.

## 3. Repository Evidence Reviewed

Foram examinados os documentos de autoridade `AGENTS.md`, `VISION.md`, `DOMAIN.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md`, `docs/CHECKLIST_DE_IMPLEMENTACAO.md`, `docs/REQUISITOS_DE_PRODUCAO.md`; o índice e as ADRs aceitas, com foco em 0002, 0003, 0006, 0010, 0011, 0015, 0016, 0020, 0038–0055; planos LIV-C01–C09, POST-LIV e design packages em `docs/plans`; documentos de integração em `docs/integration`; migrations 0001–0063; código Core/Livestock; APIs; worker; validadores; frontend; e testes unitários, de aplicação, infraestrutura, arquitetura e PostgreSQL.

Regra de leitura aplicada:

- `DOMAIN.md` e `ARCHITECTURE.md` são visão normativa de destino, não prova de implementação.
- ADR aceita é decisão vinculante, não prova de código.
- checklist/plano/status é evidência de intenção e histórico; somente código+migration+fluxo+teste elevam uma capacidade a `PROVEN`.
- não foram executados testes nesta auditoria exclusivamente estática; “testes existem” significa presença e conteúdo correspondente, não novo resultado de execução.

### Divergências documentais encontradas

| Divergência | Arquivos | Classificação |
|---|---|---|
| `DEVELOPMENT.md` ainda afirma que não existe frontend, mas `apps/web` contém aplicação React, testes e build; checklist registra sua entrega. | `DEVELOPMENT.md`; `apps/web`; `docs/CHECKLIST_DE_IMPLEMENTACAO.md` Marco 18/produto frontend | DOCUMENTATION_GAP; diferença legítima de estágio/documento desatualizado. |
| `ARCHITECTURE.md` lista Object Storage/MinIO para Documents, enquanto ADR-0004 e requisitos de produção tratam MongoDB/GridFS; implementação atual possui storage local/abstração e não prova configuração produtiva. | `ARCHITECTURE.md` Stack/Armazenamento; `docs/adr/0004-*`; `docs/REQUISITOS_DE_PRODUCAO.md`; `packages/core_infrastructure/storage.py` | DOCUMENTATION_GAP; possível não conformidade documental, requer decisão/reconciliação humana antes de produção. |
| Status histórico contém estados intermediários “aguardando autorização”, mas entradas posteriores e checklist registram conclusão LIV-C01–C09. | `LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md`; `LIVESTOCK_EXECUTIVE_CLOSURE_LIV_C01_TO_C09.md`; checklist Marco 18 | diferença legítima de estágio; não é conflito funcional. |
| ADR-0055 descreve contrato completo de autoridade/trust/verificação; código entrega subconjunto dimensional. | ADR-0055; `core_domain/verification.py`; `core_application/verification_service.py` | implementação incompleta/documentação futura. |

## 4. Current Proven Capabilities

Evidência por camada:

- **MODEL EXISTS:** `packages/livestock_domain` e `packages/core_domain` contêm modelos de Animal, movimento, lote, medicamento, tratamento, transferência/importação, FactSnapshot, Policy, Rule, Evaluation, decisão/governança, Dossier e VerificationBundle.
- **PERSISTENCE EXISTS:** migrations 0033–0063 e repositórios Livestock/Core persistem as estruturas essenciais; tabelas protegidas são criadas com `organization_id`, RLS/FORCE RLS conforme migrations e contratos PostgreSQL.
- **APPLICATION FLOW EXISTS:** serviços de Animal, movimento, tratamento, aquisição, fact provider, elegibilidade, market eligibility, decisão/governança, dossier e verification.
- **API EXISTS:** endpoints de escrita/leitura em `apps/api/livestock_animals.py`, `livestock_writes.py`, `livestock_medications.py`, `livestock_treatments.py`, `livestock_sanitary_campaigns.py`, `livestock_queries.py` e `verification.py`.
- **AUTHORIZATION EXISTS:** `livestock_application/authorization.py`, dependencies/context da API, permissions semeadas, RLS e testes cross-tenant.
- **TESTS EXIST:** suites `tests/livestock_domain`, `tests/livestock_application`, `tests/integration/test_livestock_*`, `test_decision_governance_postgresql.py`, `test_dossier_postgresql.py` e `test_verification_bundle.py`.
- **END_TO_END_PROVEN (por testes existentes):** fluxo principal Animal→tratamento→elegibilidade→Decision→Dossier e worker/integration; não está provado como uma única execução para todos os 25 passos do cenário desta auditoria.

## 5. Lifetime History Assessment

| Item | Classificação | Evidência e limite |
|---|---|---|
| Animal | IMPLEMENTADO | `livestock_domain/animal.py`; migration 0034; `AnimalService`; POST/GET `/animals`; testes domain/application/PostgreSQL/API. |
| identidade individual | IMPLEMENTADO | `AnimalIdentifier`, tipos/estado; tabelas de identifiers em 0034; attach/deactivate via serviço/API e eventos. Identidade ≠ identificador é preservado. |
| propriedade | IMPLEMENTADO | `property.py`; migration 0033; `PropertyService`; API e testes PostgreSQL. |
| lotes/composição temporal | IMPLEMENTADO | `lot.py`; migration 0037; `LotService`; endpoints members/removals e consulta `at_time`; testes. |
| nascimento/origem | IMPLEMENTADO | `reproduction.py`, `BirthOutcome`, ADR-0040; migration 0044; endpoints parturition/origin; testes. Cadastro legado permanece honesto como origem não informada. |
| aquisição | IMPLEMENTADO_PARCIALMENTE | aquisição documental orquestrada por `DocumentaryAcquisitionService` e endpoint; aquisição comercial/contratual completa não é modelada como processo próprio. |
| transferência | IMPLEMENTADO | saída/transferência, contraparte e artefato recebido; migrations 0043, 0051–0053; endpoints e testes. Travessia real entre Organizations por sharing não está completa. |
| movimentação/permanência | IMPLEMENTADO | `movement.py`, migration 0036, `MovementService`, APIs e testes; múltiplos animais por movimento e stays temporais. |
| contraparte externa | IMPLEMENTADO | `external_counterparty.py`, migration 0051, service/API/testes. |
| histórico importado | IMPLEMENTADO | `ImportedLivestockFact`, migration 0053, service/API; entra no snapshot com `origin`, source artifact, confidence e tempos. |
| ReceivedTransferArtifact | IMPLEMENTADO | `transfer_artifact.py`, migration 0052, service/repository/API/testes PostgreSQL. |
| tratamentos | IMPLEMENTADO | `treatment.py`, migration 0041/0042, service/API; correção append-only e testes. |
| medicamentos | IMPLEMENTADO | `medication.py`, migration 0039/0047, service/API/testes. |
| MedicationBatch | IMPLEMENTADO | migration 0040, service/API; tratamento referencia lote. |
| prescrições | IMPLEMENTADO | `prescription.py`, migration 0039; veterinarian validado, medicamento, validade; API/testes. Não há motor geral que derive obrigatoriedade por mercado além de Rules. |
| veterinários | IMPLEMENTADO | `veterinarian.py`, migration 0038; verificação, API e testes. |
| campanhas sanitárias | IMPLEMENTADO | `sanitary_campaign.py`, migration 0048; service/API e avaliação mínima. |
| exames | AUSENTE | Não foi encontrado módulo/migration/API de laboratório ou exame clínico. Poderá ser novo tipo de Fact/Evidence; necessidade depende de requisito aprovado. |
| correções | IMPLEMENTADO | tratamentos e transformações criam novo registro; Core `CorrectionService`; migrations/eventos/testes. Não há correção homogênea para toda entidade Livestock. |
| Evidence | IMPLEMENTADO_PARCIALMENTE | Core evidence persistido (migrations 0016–0021), tratamento usa referências tipadas; nem todo fato Livestock exige ou cria Evidence verificável. |
| provenance | IMPLEMENTADO_PARCIALMENTE | `ProvenanceLink/Service` e persistência/testes; imported facts usam source reference. Grafo completo para cada evento vital não é universalmente materializado. |
| coverage | IMPLEMENTADO_PARCIALMENTE | `HistoryCoverage` e fato derivado `livestock.history_coverage`; cobertura existe quando há artefato recebido. Ausência vira `NAO_DECLARADA`, mas não há cálculo universal por tipo de fato/intervalo. |
| coverage gaps | IMPLEMENTADO_PARCIALMENTE | gaps `HISTORY_BEFORE_ACQUISITION_UNKNOWN`/`COVERAGE_BEFORE_TRANSFER`; gaps aparecem em dossier/bundle. Taxonomia não cobre todas as lacunas possíveis. |
| fatos locais vs importados | IMPLEMENTADO | `FactOrigin`; imported facts preservam origem; `LivestockFactProvider` agrega sem convertê-los em observação local. |
| continuidade histórica | IMPLEMENTADO_PARCIALMENTE | artefato+coverage+imported facts suportam continuidade declarada; não provam completude de toda a vida nem validam material externo integralmente. |
| FactSnapshot | IMPLEMENTADO | `core_domain/facts.py`; `LivestockFactProvider.provide` usa `FactSnapshot.create`; hash inclui source reference/tempos; persistido indiretamente na Evaluation, com testes. |

## 6. Sanitary Compliance Assessment

O baseline sanitário é funcional para carência e campanhas, mas não é um sistema clínico completo.

| Capacidade | Resultado | Evidência/limite |
|---|---|---|
| tratamento + medicamento/lote | PROVEN | modelos, migrations 0039–0042, APIs e testes. |
| prescrição quando exigida | PARTIAL | prescrição existe e pode ser vinculada; a exigência depende de Rule/Policy e não há catálogo normativo real completo. |
| carência | PROVEN para regra existente | `WithdrawalCalculator`; facts `livestock.withdrawal`; eligibility/market eligibility; testes positivos/negativos/importados. |
| tratamento registrado ≠ ausência | PROVEN | snapshot contém contribuições explícitas; ausência de coverage ou regra gera gap/indeterminação em fluxos governados. |
| lacunas históricas | PARTIAL | coverage gaps explícitos, porém escopo limitado a transferência/documentação declarada. |
| fatos locais/importados | PROVEN | `LivestockFactProvider._imported_sanitary_facts`; testes LIV-C04. |
| origem de Evidence | PARTIAL | source artifact/reference e confidence preservados; ValidationAssessment/admissibility não atravessam todo o fluxo. |
| Rules/Policy/Evaluation | PROVEN | Core services + persistência + API elegibilidade; Rules governadas por adoption. |
| outcome explicável/indeterminação | PROVEN | `RuleResultStatus` e `EvaluationOutcome`; `DecisionReason`; testes. |
| ausência não promovida a conformidade | PARTIAL | fluxos de coverage/market falham fechado; risco subsiste quando uma Rule só testa fatos presentes sem requisito explícito de coverage. |
| proposal/revisão/authority/Decision | PROVEN no fluxo implementado | migrations 0060–0062, governance service, endpoints proposal/reviews, testes PostgreSQL/API. Autoridade é Titan-interna/declarada, não autoridade oficial externa. |
| Dossier verificável | PARTIAL | Dossier e bundle verificáveis por hash/dimensões; falta contrato integral ADR-0055 de trust, autoridade externa e reprodução completa. |

### Caminhos perigosos de falso positivo

1. `MarketProfile` somente falha por carência ausente quando o requisito configurado a exige; uma Policy sem Rule de coverage pode aprovar sobre snapshot incompleto. Isso é `POLICY_GAP + EVIDENCE_GAP`.
2. `HistoryCoverage` ausente é declarado no Dossier, mas não é automaticamente uma Rule bloqueante universal — corretamente, pois o efeito depende da Policy; o risco é publicar Policy mal configurada.
3. Imported fact carrega confidence/origin, porém ausência de `EvidenceAdmissibilityAssessment` completo pode fazer uma Rule consumi-lo sem limiar de admissibilidade explícito.
4. Fonte/qualificação externa declarada pode alimentar Fact; isso não equivale a validação oficial atual. APIs e apresentações devem conservar limitações.

## 7. Market Eligibility Readiness

A pergunta central pode ser representada corretamente com conceitos existentes:

`Subject + reference_time + FactSnapshot/coverage + Policy/Rules + NormativeBasisSnapshot + Evaluation + Authority/Decision + Dossier`.

Avaliação dos nomes analíticos:

| Conceito | Necessidade | Decisão de reutilização |
|---|---|---|
| MarketProfile | já existe como configuração da vertical | EXTEND; não promover automaticamente a Aggregate. Pode ser projeção/configuração governada de Policies/Rules. |
| MarketEligibility | não como entidade | DERIVE de Evaluation/Decision por purpose. |
| MarketEligibilityAssessment | equivalente a Evaluation | REUSE. |
| EligibilityGap | equivalente a RuleResult/DecisionReason/CoverageGap | DERIVE; não criar agora. |
| MarketReadiness | consulta agregada | DERIVE/read model. |
| EligibilityPortfolio | conjunto de avaliações por purpose | DERIVE/read model. |
| MarketChangeImpact | ImpactAssessment/Reevaluation | REUSE/EXTEND implementação Core. |

Requisitos por mercado, finalidade, produto, jurisdição, território, estabelecimento, propriedade, origem, cobertura mínima, tratamentos, carência, documentos e habilitação cabem em `Policy`, `Rule`, `NormativeBasisSnapshot`, Subjects tipados, Facts/Evidence e dependências. Validação/habilitação externa exige `SourceProfile/ValidationAssessment/EvidenceAdmissibilityAssessment` — conceitos já normativos, mas implementação incompleta.

O código atual prova três purposes enumerados e perfis default em `market_eligibility.py`, mas **não prova requisitos reais** desses países. Comentários no próprio arquivo reconhecem que campanhas reais exigem decisão normativa. Portanto os nomes dos mercados são suporte técnico/demonstração, não certificação regulatória.

## 8. Multi-Market Readiness

**Arquiteturalmente PASS.** ADR-0041 e `MarketEligibilityService` avaliam o mesmo `subject_id` e `FactSnapshot` contra policies/purposes independentes. Não duplicam Animal, fatos nem histórico e não persistem flag `eligible` no Animal. `MarketEligibilityMatrix` é resultado derivado.

Falta para ponta a ponta real:

- policies/normative bases aprovadas por mercado e produto;
- seleção temporal inequívoca com conflitos/lacunas normativas;
- dependências multi-Subject plenamente compostas sem converter composição comercial em Decision do Animal;
- persistência/read model para consulta eficiente de última avaliação por purpose;
- reavaliação em lote e impacto governado;
- testes E2E com duas versões de Policy e múltiplos mercados reais fictícios.

## 9. Temporal/Regulatory Change Readiness

`Policy` possui `valid_from`, `valid_to`, status e versionamento; repositories oferecem `get_active_at`; Evaluation preserva policy/rule versions, `snapshot_hash` e `context_hash` (migration 0061). ADR-0051 é parcialmente implementada por `FactSnapshot.create`; ADR-0052 está parcialmente implementada porque os tempos `observed_at`, `recorded_at`, `known_at` existem em facts importados e timeline oferece `known_until`.

Limites:

- `NormativeBasisSnapshot` completo, com referências/dispositivos/digests/knowledge cut, não aparece como estrutura persistida equivalente nas migrations atuais;
- a seleção contextual completa da ADR-0052 (valid time, transaction/knowledge time, jurisdiction, applicability) não está provada por serviço genérico;
- `MarketProjectionStatus.REAVALIACAO_NECESSARIA` compara policy usada/atual, mas não executa impacto/reavaliação de população automaticamente;
- `HistoricalReproductionService` existe, mas reprodução integral do runtime/normative snapshot não está comprovada para market eligibility.

É possível futuramente detectar market change, localizar Subjects por evaluations/policy/provenance e criar novas Evaluations/Decisions sem reescrever anteriores. Para escala, falta `ImpactAssessment`/projection operacional e worker governado; a semântica já está decidida.

## 10. Coverage And Indetermination Assessment

Semântica explícita encontrada:

- Rule: `ATENDIDA`, `NAO_ATENDIDA`, `PENDENTE`, `NAO_APLICAVEL`, `INDETERMINADA` (`DOMAIN.md`; `core_domain/evaluation.py`).
- Evaluation: satisfeita, não satisfeita, informação insuficiente, evidência conflitante, validação externa pendente, revisão necessária, indeterminado.
- Decision: aprovada, rejeitada, aprovada com restrições, indeterminada.
- Market projection: elegível, não elegível, condicionado, indeterminado, ausente.
- Verification: válida/inválida/indeterminada/não executada por dimensão.

`ABSENCE OF EVIDENCE != EVIDENCE OF ABSENCE` está materializada em `HistoryCoverage`, Fact gaps, sanitary/territorial services e verification coverage. O ponto fraco é governança de Policy: a engine somente pode declarar insuficiência quando a Rule expressa a Evidence/cobertura requerida. Recomenda-se um gate de publicação/teste de políticas de elegibilidade que assegure requisitos explícitos de coverage/admissibility, em vez de hardcode universal.

## 11. Authority And Overclaim Assessment

O modelo distingue corretamente:

- `EvaluationOutcome`: conclusão técnica, sem autoridade operacional;
- `DecisionProposal`: proposta imutável, não Decision;
- `DecisionAuthorityProfile`: competência declarada e delimitada;
- `Decision`: emissão sob autoridade, método e reasons;
- habilitação/certificação externa: facts/evidence/qualifications separadas.

Evidência: ADRs 0053–0054; `core_domain/decision_authority.py`, `decision_governance.py`; migrations 0060/0062; `DecisionService` valida Organization, purpose, validade e emissão; endpoints de review.

Risco de overclaim: um `Decision` emitido pelo Titan demonstra conclusão sob perfil de autoridade registrado no Titan; não demonstra que UE, China ou autoridade sanitária reconhecem o emissor. `MarketEligibilityStatus.ELEGIVEL` em apresentação comercial deve ser acompanhado de purpose, policy/version, reference time, scope, gaps e autoridade/limitações. A frase segura é: “Segundo Policy X e o material disponível, os requisitos avaliáveis foram satisfeitos.”

## 12. Dossier/Verification Readiness

O `LivestockDossierTemplate` incorpora subject, finalidade, snapshot/facts, timeline, coverage, imported material, evaluation, proposal/decision e limitações. `VerificationBundleService` deriva escopos/gaps do Dossier; `BundleVerifier` valida estrutura, serialização, integridade, assinatura, temporalidade, revogação e coverage de modo dimensional.

Status por requisito do futuro “Market Eligibility Dossier”:

| Conteúdo | Estado |
|---|---|
| Subject, purpose/market, Policy/version, reference time, Evaluation/Decision, Facts/Evidence | PROVEN/PARTIAL conforme componente |
| coverage/gaps/imported provenance/indeterminação | PROVEN no escopo declarado Livestock |
| NormativeBasisSnapshot completo | PARTIAL |
| Authority interna e review | PROVEN no fluxo LIV-C06 |
| autoridade/reconhecimento externo | NOT_PROVEN |
| dependências externas e limitações | PARTIAL |
| assinatura/trust/validação independente integral ADR-0055 | PARTIAL |

Não criar outro Dossier. Estender template/manifesto e completar os componentes Core existentes.

## 13. ERP/Odoo Boundary Assessment

`erp_contract.py`, `erp_outbox.py`, `erp_inbox.py`, POST-LIV-02A e testes preservam contrato neutro e acknowledgement técnico. O worker/outbox não entrega autoridade sanitária ao ERP.

Conclusões:

- ERP stock movement ≠ prova de tratamento: preservado.
- completion/acknowledgement ERP ≠ conclusão sanitária/Evidence: preservado.
- Odoo não cria autoridade: design package afirma a limitação; adaptador Odoo não está implementado.
- Titan não depende do ORM Odoo: não há import/dependência Odoo no código.
- outbound contract é neutro: `erp_contract.py` e simulador POST-LIV-02A.

Market eligibility não exige mudar a fronteira. ERP pode consumir resultado publicado e devolver receipt técnico; novos Facts/Evidence só entram por caso de uso Titan com validação/provenance.

## 14. Future Generalization Assessment

| Conceito | Classificação | Justificativa |
|---|---|---|
| Policy, Rule, FactSnapshot, Evaluation, Decision, Dossier, Evidence, Provenance, Coverage genérica | JA_EXISTE_NO_CORE | linguagem normativa do Core já cobre múltiplas verticais. |
| Animal, tratamento, medicamento, campanha, veterinário, reprodução | MANTER_NO_LIVESTOCK | significado sanitário/biológico da vertical. |
| Market purpose/profile e composição por estabelecimento | MANTER_NO_LIVESTOCK | ADR-0041 evita contaminar Core com mercado pecuário. |
| `HistoryCoverage` de transferência | CANDIDATO_FUTURO_A_CORE | padrão aplicável a cadeia de custódia, mas há uso atual apenas Livestock; não mover agora. |
| `TraceableItem`/Transformation quantitativa | CANDIDATO_FUTURO_A_CORE | poderia servir crops/forestry/carbon, mas Core já possui Transformation/Batch; avaliar reutilização antes de mover. |
| exames/laboratório multiespécie | NAO_HA_EVIDENCIA_SUFICIENTE | requisito não aprovado nem implementado. |
| espécies adicionais, crops, forestry, carbon | NAO_HA_EVIDENCIA_SUFICIENTE | somente teste arquitetural; não justifica generalização atual. |

## 15. Security And Tenant Isolation Assessment

Pontos comprovados:

- tabelas Livestock/Core protegidas carregam Organization e migrations aplicam RLS/FORCE RLS;
- repositories recebem Organization/context; API resolve principal/membership/permission;
- testes PostgreSQL e API exercitam ausência de contexto, outra Organization e reutilização de conexão;
- outbox/inbox carregam Organization, deduplicação e quarentena; worker reconstrói contexto;
- dossier tem permissão própria e testes impedem leitura pelo papel errado/cross-tenant;
- estado de integração é persistido e diagnosticado por `operational_support`.

Gaps:

- consultas futuras de readiness/portfolio não podem usar agregação global sem scope organizacional; qualquer projection precisa `organization_id`, RLS e testes cross-tenant;
- composição entre Organizations/subjects ainda não tem sharing/grant completo no fluxo Livestock;
- operação produtiva (secrets, TLS, backup, observability, RPO/RTO, workers) permanece bloqueada conforme `REQUISITOS_DE_PRODUCAO.md`;
- validação externa/market authority não pode confiar em payload/ack externo sem source validation e admissibility.

## 16. End-to-End Scenario Assessment

| # | Passo | Status | Evidência |
|---:|---|---|---|
| 1 | nasce em A | PASS | ADR-0040; reproduction service/API/migration 0044/testes. |
| 2 | identificação | PASS | AnimalIdentifier/migration 0034/service/API. |
| 3 | tratamento | PASS | TreatmentApplication/API/testes. |
| 4 | medicamento e lote | PASS | migrations 0039–0041 e invariantes. |
| 5 | carência | PASS | WithdrawalCalculator/fact/rules/testes. |
| 6 | muda para B | PASS | Movement+PropertyStay, migration 0036. |
| 7 | histórico anterior importado | PASS | artifact+ImportedLivestockFact+fact provider. |
| 8 | lacuna documental | PASS | HistoryCoverage gaps. |
| 9 | nova Evidence recebida | PARTIAL | Evidence e imported fact existem; validação/admissibility completa não universal. |
| 10 | snapshot | PASS | FactSnapshot.create no provider. |
| 11 | Policy mercado X | PARTIAL | seleção/purpose existe; base normativa real e multitemporal completa não provada. |
| 12 | Rules executadas | PASS | PolicyEvaluationService/Rule engine. |
| 13 | regra satisfeita | PASS | RuleResultStatus/testes. |
| 14 | regra falha | PASS | idem. |
| 15 | regra indeterminada por gap | PARTIAL | estados/gaps existem; depende de Policy declarar cobertura. |
| 16 | Evaluation | PASS | serviço, migration 0025/0061, repository/testes. |
| 17 | revisão exigida | PASS | autoridade/policy e refusal path. |
| 18 | DecisionProposal | PASS | governance service/migration 0062. |
| 19 | revisão | PASS | endpoint reviews e testes. |
| 20 | Decision sob autoridade | PASS | DecisionService/Profile/migration 0060. |
| 21 | Dossier | PASS | template/service/repository/API. |
| 22 | Bundle validado independentemente | PARTIAL | BundleVerifier e testes offline; trust/authority/reproduction ADR-0055 incompletos. |
| 23 | Policy muda | PASS conceitual/PARTIAL operacional | policy versions/get_active_at/projection status. |
| 24 | reavaliação | PARTIAL | nova execução possível; impacto/worker em massa ausente. |
| 25 | anteriores históricas | PASS | append-only/hash/versioning e testes de reavaliação/correção. |

## 17. Capability Matrix

| Capability | Status | Evidence | Gap | Severity | Recommended action |
|---|---|---|---|---|---|
| História individual e temporal | PROVEN | migrations 0033–0044; services/APIs/tests | exames e algumas correções não cobertos | MEDIUM | ampliar só por requisito aprovado |
| Continuidade via transferência/importação | PARTIAL | 0051–0053; acquisition/fact provider | coverage declarada, não universalmente provada | HIGH | NEXT-01 |
| Compliance de carência | PROVEN | withdrawal/eligibility + testes | bases reais por mercado ausentes | HIGH | NEXT-02 |
| Campanha sanitária | PARTIAL | 0048; service/API | requisito real por mercado não adotado | MEDIUM | Policy governada |
| Evidence/provenance/admissibility | PARTIAL | Core evidence/provenance | admissibility/validation incompletas no fluxo | HIGH | NEXT-01 |
| FactSnapshot | PROVEN | facts.py/provider/evaluation tests | normative snapshot não equivalente | HIGH | NEXT-02 |
| Policy/Rule governance | PROVEN | 0049–0050; API/tests | cobertura de expressividade e gates semânticos | HIGH | NEXT-02 |
| Market matrix multimercado | PARTIAL | market_eligibility.py/API/tests | perfis demonstrativos, não compliance real | CRITICAL | NEXT-02/NEXT-03 |
| Multi-Subject composition | PARTIAL | dependent subject/gaps | composição operacional formal incompleta | MEDIUM | NEXT-04 |
| Temporalidade regulatória | PARTIAL | policy validity/context hash | ADR-0052 incompleta | HIGH | NEXT-02 |
| Proposal/review/authority/Decision | PROVEN | 0060–0062/endpoints/tests | reconhecimento externo não provado | HIGH | NEXT-03 |
| Dossier/Verification | PARTIAL | dossier/bundle/verifier/tests | ADR-0055 integral ausente | HIGH | NEXT-05 |
| Readiness/portfolio/lot selection | PARTIAL | matrix/lot evaluation | projection segura/escala ausente | MEDIUM | NEXT-06 |
| Market change impact | PLANNED | ADR-0052/domain impact concepts | fluxo/persistência operacional ausente | MEDIUM | NEXT-07 |
| Odoo adapter | PLANNED | POST-LIV-02B design only | nenhum código | LOW | não bloquear missão |
| Produção | BLOCKED | requisitos de produção | TLS/backup/DR/observability/topologia | CRITICAL | programa operacional separado |

## 18. Gap Register

| ID | Gap | Classificação | Evidência |
|---|---|---|---|
| G-01 | coverage vitalícia não é calculada por dimensão/intervalo; depende de declaração/artefato | DOMAIN_GAP, APPLICATION_GAP, EVIDENCE_GAP, TEST_GAP | `HistoryCoverage`; fact provider; poucos gap codes. |
| G-02 | ValidationAssessment/EvidenceAdmissibility não integram universalmente facts importados à avaliação | APPLICATION_GAP, PERSISTENCE_GAP, EVIDENCE_GAP | DOMAIN/ARCH modelam; fluxo Livestock usa source/confidence diretamente. |
| G-03 | NormativeBasisSnapshot e seleção multitemporal completas ausentes | PERSISTENCE_GAP, APPLICATION_GAP, TEMPORAL_GAP | ADR-0051/0052 vs migrations/modelos atuais. |
| G-04 | perfis default com nomes de mercados não são requisitos normativos reais | POLICY_GAP, DOCUMENTATION_GAP, AUTHORITY_GAP | `DEFAULT_MARKET_PROFILES`; comentário de campanha; ausência de bases reais. |
| G-05 | publicação de Policy pode omitir gate de coverage/admissibility | POLICY_GAP, EVIDENCE_GAP, TEST_GAP | engine executa condições declaradas; ausência não é universalmente bloqueada. |
| G-06 | autoridade Titan não demonstra habilitação/reconhecimento oficial externo | AUTHORITY_GAP, INTEGRATION_GAP | ADR-0053; DecisionAuthorityProfile interno. |
| G-07 | bundle não fecha integralmente trust, autoridade, tempo e reprodução ADR-0055 | APPLICATION_GAP, SECURITY_GAP, EVIDENCE_GAP, TEST_GAP | verifier atual vs ADR-0055. |
| G-08 | impacto de mudança/reavaliação em massa sem projection/worker | APPLICATION_GAP, PERSISTENCE_GAP, OBSERVABILITY_GAP | apenas freshness/projection status e conceitos de impacto. |
| G-09 | readiness/portfolio/seleção N sem read model eficiente e tenant-safe | APPLICATION_GAP, PERSISTENCE_GAP, SECURITY_GAP | APIs atuais avaliam pontualmente/lote. |
| G-10 | sharing/travessia entre Organizations não fecha cadeia real | SECURITY_GAP, APPLICATION_GAP | ADR-0042 e Core sharing são direção; artifacts são recebidos localmente. |
| G-11 | exames/laboratórios ausentes | DOMAIN_GAP, APPLICATION_GAP, API_GAP, PERSISTENCE_GAP | nenhum módulo/migration/API; necessidade ainda humana/normativa. |
| G-12 | produção não pronta | SECURITY_GAP, OBSERVABILITY_GAP, INTEGRATION_GAP | `REQUISITOS_DE_PRODUCAO.md`. |
| G-13 | documentos de stack/frontend divergentes | DOCUMENTATION_GAP | ARCHITECTURE/DEVELOPMENT vs código. |

## 19. P0/P1/P2/P3/P4 Priorities

**P0 — missão fundamental**

- G-01/G-02: sem coverage/admissibility robustas, ausência pode ser confundida por Policy incompleta.
- G-04/G-05: impedir apresentação de perfis demonstrativos como elegibilidade real.
- G-12 antes de qualquer operação com dados reais/produção.

**P1 — Market Eligibility coerente**

- G-03 temporal/normative snapshot.
- G-06 autoridade/reconhecimento externo e linguagem de escopo.
- G-07 dossier/bundle integralmente verificável no perfil alegado.
- G-10 continuidade autorizada entre Organizations para cadeia real.

**P2 — operação real/escala**

- G-08 impacto/reavaliação em massa.
- G-09 readiness/read models/seleção N tenant-safe.
- observabilidade operacional e reconciliação de integrações.

**P3 — evolução útil**

- G-11 exames, quando uma Policy real comprovar necessidade.
- composição formal de operação/estabelecimento/lote.
- Odoo adapter, se houver demanda operacional.

**P4 — especulativo**

- mover `HistoryCoverage` ou Transformation ao Core agora;
- plataforma agro genérica, novas espécies/crops/carbon sem caso aprovado;
- nova entidade `EligibilityGap`, `MarketReadiness` ou `EligibilityPortfolio` como verdade de domínio.

## 20. Reuse Analysis

| Gap P0/P1 | Core equivalente? | Livestock equivalente? | Derivar/Policy/read model? | Persistência/entidade/ADR? | Resultado |
|---|---|---|---|---|---|
| G-01 coverage | Evidence, Provenance, FactSnapshot | HistoryCoverage/gaps | derivar avaliação de cobertura; Policy define mínimo | projection/assessment pode precisar persistência; nova entidade só após desenho | EXTEND |
| G-02 admissibility | Validation/EvidenceAdmissibility já normativos | origin/confidence/source artifact | Policy/Rule + assessment | implementar conceitos Core existentes; ADR não necessária se fiel | REUSE/EXTEND |
| G-03 temporal | NormativeBasisSnapshot, operations temporais | policy provider/timeline | seleção por serviço | persistência Core existente precisa extensão; ADRs 0051/0052 já decidem | REUSE/EXTEND |
| G-04 perfis reais | Policy/Rule/NormativeBasis | MarketProfile | perfis derivados de policies | não precisa nova entidade inicialmente | REUSE/DERIVE |
| G-05 gate de publicação | Rule governance | catalogs/adoptions | validação de Policy/Rule | pode ser regra de aplicação/teste; sem entidade | EXTEND |
| G-06 autoridade externa | DecisionAuthorityProfile, ValidationAssessment | establishment qualification | validar fonte/competência | pode exigir integração/Evidence; ADR só para reconhecimento concreto | EXTEND; ADR_REQUIRED para perfil oficial específico |
| G-07 bundle | Dossier/Bundle/ValidationReport | Livestock template | estender manifesto/verifier | persistência de validation report pode ser necessária; não novo dossier | REUSE/EXTEND |
| G-10 sharing | grants/authorization já normativos | transfer artifact | artifact continua Evidence, não acesso | implementar Core sharing antes de cross-tenant live | REUSE/EXTEND |

Nenhum P0/P1 exige, com a evidência atual, `MarketEligibility` persistida, `EligibilityGap` entidade ou segundo motor. Quando o comportamento puder ser Policy/Rule, projection ou derivação, essa é a opção mínima.

## 21. Recommended Minimal Roadmap

### NEXT-01 — Coverage e admissibilidade sanitária explícitas

- **Objetivo:** provar quais intervalos/tipos de histórico foram avaliados e impedir conclusão positiva quando a Policy exige material ausente.
- **Problema/evidência:** G-01/G-02; `HistoryCoverage` cobre somente artefato de transferência e imported facts não passam por assessment completo.
- **Pré-requisitos:** ADR-0015/0042/LIV-C02–C04.
- **Reutiliza:** Evidence, Provenance, ValidationAssessment, EvidenceAdmissibility, FactSnapshot, RuleResult.
- **Mudança mínima:** assessment derivado de coverage por finalidade/tipo/intervalo e inclusão como fact/assessment; gate de Policy explícito.
- **Fora de escopo:** mercado real, dashboard, novo Aggregate universal.
- **Testes:** local/importado, intervalo completo/parcial/ausente, conflito, cross-tenant, snapshot/dossier/bundle.
- **Aceite:** ausência obrigatória sempre produz insuficiência/indeterminação com reason/gap; fato importado preserva admissibilidade.
- **Riscos/rollback:** rules existentes podem mudar outcome; feature/version gate e nova Policy version resolvem rollback.
- **Bloqueio:** taxonomia mínima de cobertura por requisito precisa decisão humana se não estiver inferível da primeira Policy real.

### NEXT-02 — Policy temporal e base normativa de mercado demonstrativa governada

- **Objetivo:** provar duas versões fictícias de uma Policy de mercado com seleção `reference_time`/knowledge time e snapshot normativo.
- **Problema:** G-03/G-04/G-05.
- **Reutiliza:** Policy, Rule governance, NormativeBasisSnapshot, context hash, HistoricalReproduction.
- **Mudança mínima:** completar persistência/seleção/snapshot e retirar default demonstrativo de qualquer alegação oficial.
- **Fora de escopo:** regras reais de países.
- **ADRs:** 0049–0052.
- **Testes:** overlap fail-closed, gap temporal, v1/v2, historical reproduction, knowledge cutoff, Organization isolation.
- **Aceite:** pergunta histórica seleciona material inequívoco; conflito/ausência não aprova.
- **Rollback:** nova versão/feature path, sem reescrever evaluations.
- **Bloqueio:** contrato mínimo de NormativeBasisSnapshot deve seguir ADR-0051/52; conflito com schema atual exige revisão antes de migration.

### NEXT-03 — Limites de autoridade e perfil externo verificável

- **Objetivo:** distinguir tecnicamente decisão interna, avaliação técnica e reconhecimento externo.
- **Problema:** G-06/overclaim.
- **Reutiliza:** DecisionAuthorityProfile, ValidationAssessment, Evidence, AssertionScope, establishment qualification.
- **Mudança mínima:** expor scope/issuer/authority evidence/limitations e exigir perfil específico para rótulo externo.
- **Fora de escopo:** afirmar reconhecimento por autoridade real.
- **ADRs:** 0053/0054; nova ADR somente ao integrar autoridade concreta.
- **Testes:** autoridade expirada, purpose/Organization errado, fonte indisponível, apresentação sem overclaim.
- **Aceite:** nenhuma API/UI chama avaliação técnica de autorização oficial.
- **Rollback:** contratos versionados/campos aditivos.
- **Bloqueio:** decisão humana sobre quais autoridades/perfis reais serão suportados.

### NEXT-04 — Composição operacional multi-Subject

- **Objetivo:** compor Animal + estabelecimento + lote/operação sem criar Decision falsa sobre Animal.
- **Problema:** dependências já aparecem como `CONDICIONADO`, mas composição formal é parcial.
- **Reutiliza:** Evaluation/Decision por Subject, MarketRequirement dependency, relations.
- **Mudança mínima:** resultado derivado que referencia decisões componentes e tempos.
- **Fora de escopo:** seleção comercial automática ou Decision regulatória da operação.
- **Testes:** dependência ausente/expirada/indeterminada e tempos inconsistentes.
- **Aceite:** composição nunca altera decisões componentes.
- **Rollback:** projection derivada descartável.
- **Bloqueio:** definir Subject operacional somente se uso real exigir persistência; pode permanecer DTO/read model.

### NEXT-05 — Market Eligibility Dossier pelo mecanismo existente

- **Objetivo:** completar perfil de Dossier/Bundle para eligibility sem formato paralelo.
- **Problema:** G-07.
- **Reutiliza:** Dossier, BundleManifest, VerificationBundle, ValidationReport.
- **Mudança mínima:** componentes/requirements do perfil, authority/trust/temporal/coverage e test vectors.
- **Fora de escopo:** PDF como fonte, trust anchor real sem decisão.
- **ADRs:** 0010/0055.
- **Testes:** componente ausente, assinatura/trust/authority indeterminados, offline parcial, tampering, redaction.
- **Aceite:** relatório dimensional declara exatamente o verificável e as limitações.
- **Rollback:** novo profile version, bundles antigos preservados.
- **Bloqueio:** material criptográfico/trust de produção depende de decisão humana/infraestrutura.

### NEXT-06 — Read model tenant-safe de readiness e seleção

- **Objetivo:** derivar contagens, gaps e “N animais que satisfazem Policy X”.
- **Problema:** G-09.
- **Reutiliza:** Evaluation/Decision/RuleResults; não cria verdade nova.
- **Mudança mínima:** projection reconstruível por Organization, Policy/version/reference time.
- **Fora de escopo:** dashboard, flags permanentes, decisão comercial automática.
- **Testes:** RLS/cross-tenant, stale projection, paginação, composição, reference time.
- **Aceite:** resultado identifica policy/version e freshness; pode ser reconstruído.
- **Rollback:** descartar/rebuild projection.
- **Bloqueio:** apenas após semântica NEXT-01/02 estável.

### NEXT-07 — Impacto de mudança e reavaliação governada

- **Objetivo:** localizar Subjects potencialmente afetados por nova Policy e gerar novas avaliações sem reescrever história.
- **Problema:** G-08.
- **Reutiliza:** ImpactAssessment, Reevaluation, outbox/inbox/worker.
- **Mudança mínima:** trigger, scope, projection de dependências e job idempotente.
- **Fora de escopo:** recall/decisão downstream automática.
- **Testes:** partial/truncated/inaccessible, retry, concurrent policy change, tenant isolation.
- **Aceite:** anteriores permanecem intactos e impacto parcial nunca é completo.
- **Rollback:** cancelar jobs/projection; não apagar assessments históricos.
- **Bloqueio:** volume/SLO e política de reavaliação exigem decisão operacional.

## 22. HUMAN_DECISIONS_REQUIRED

1. **Qual é o primeiro mercado/finalidade/produto real a ser suportado?** O repositório não contém base normativa real aprovada. Alternativas: programa privado fictício/controlado (menor risco), mercado oficial específico (maior integração/autoridade) ou apenas baseline sanitário interno. Recomendação: começar com programa privado claramente rotulado. Bloqueia NEXT-02 real e NEXT-03.
2. **Quem possui competência para aprovar NormativeBasis e emitir Decision para esse perfil?** Alternativas: autoridade interna da Organization, certificadora/terceiro, autoridade pública reconhecida. Impacto cresce em Evidence, integração, segregação e linguagem. Recomenda-se manter decisão técnica interna até haver reconhecimento verificável. Bloqueia alegação oficial.
3. **Qual cobertura mínima é material para a primeira Policy?** Intervalos, tipos de fatos, documentos e tolerâncias não podem ser inventados pelo código. Bloqueia critérios concretos de NEXT-01.
4. **Qual fonte externa e nível de validação sustentam habilitação/certificação?** Alternativas: declaração, documento recebido, consulta autenticada ou integração oficial. Recomenda-se fail-closed e status indeterminado na indisponibilidade. Bloqueia perfil externo de NEXT-03.
5. **Qual contrato de armazenamento de Documents prevalece para a evolução?** `ARCHITECTURE.md` e ADR-0004/requisitos divergem entre object storage e MongoDB/GridFS. Exige decisão/reconciliação documental antes de produção ou expansão de anexos.
6. **Quais SLO/RPO/RTO, região, backup, secrets/trust e observabilidade de produção?** Listados como “a definir” em requisitos de produção. Bloqueiam uso produtivo, não a análise/POC.

## 23. Explicit Non-Recommendations

- Não criar segundo motor de compliance/eligibility.
- Não persistir `eligible`/market flags no Animal.
- Não criar `EligibilityGap` enquanto RuleResult, DecisionReason e CoverageGap forem suficientes.
- Não criar `MarketReadiness`/`EligibilityPortfolio` como aggregates; usar read models.
- Não codificar regras reais de UE, China, Coreia, Japão ou EUA sem NormativeBasis/autoridade aprovadas.
- Não converter seleção de lote/comercial em Decision regulatória.
- Não tratar ERP/Odoo receipt, estoque ou conclusão administrativa como Evidence sanitária.
- Não mover conceitos Livestock ao Core sem segundo uso comprovado.
- Não chamar PDF de Dossier nem hash de verificação integral.
- Não iniciar recall, reavaliação, comunicação ou ação downstream automaticamente por mudança de Policy.

## 24. Final Assessment

O Titan Livestock já consegue preservar uma parte substancial e auditável da vida do animal e aplicar regras sanitárias versionadas sobre snapshots, com outcomes explicáveis, indeterminação, revisão, autoridade interna, decisão e dossiê. Essa é uma base arquitetural coerente e rara: o mesmo histórico pode ser avaliado contra múltiplas Policies sem duplicação ou mutação do Animal.

A capacidade atual, porém, deve ser descrita com precisão: **baseline de avaliação técnica e compliance sanitário governado, com market matrix parcialmente pronta**, não autorização oficial de exportação nem prova universal de completude vitalícia. A prioridade não é adicionar entidades; é fechar coverage/admissibility, temporalidade normativa, autoridade externa e verificação integral usando os conceitos Core já aprovados. Readiness, portfolio, planejamento de lote e impacto de mudança são derivados/projections posteriores, nunca novas verdades de domínio.

O menor caminho coerente é NEXT-01 → NEXT-02 → NEXT-03 → NEXT-05; composição, projections e reavaliação em massa vêm depois que a semântica individual estiver fechada. Produção permanece bloqueada pelos requisitos operacionais explícitos.
