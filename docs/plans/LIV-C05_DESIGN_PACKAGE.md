# LIV-C05_DESIGN_PACKAGE

Status: DESIGN_GATE_PENDING_HUMAN_DECISION
Artifact ID: `LIV-C05-DP-v1`
Date: 2026-08-04
Requested execution stage: `LIV-C06`
Plan stage referenced by plan v1.2: `LIV-C05`
Scope: Carencia governada por Policy, sem introduzir regra concreta de mercado sem fundamento aprovado

## 1. Estado atual comprovado

### 1.1 Autorizacao e divergencia de numeracao

- O pedido atual exige confirmacao de `LIV-C06` como etapa autorizada.
- O status append-only confirma `LIV-C06: AUTORIZADA` em [docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md).
- O plano v1.2 ainda nomeia "carencia governada por Policy" como `LIV-C05` em [docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md).
- O artefato pedido pelo usuario e [docs/plans/LIV-C05_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/LIV-C05_DESIGN_PACKAGE.md), embora a execucao solicitada use o numero `LIV-C06`.

### 1.2 Onde `withdrawal_period_days` existe hoje

- O dado persistido do medicamento esta em [packages/livestock_domain/medication.py](/C:/programing/Titan/packages/livestock_domain/medication.py): `Medication.withdrawal_period_days`.
- A migration que materializou o campo esta em [packages/core_infrastructure/persistence/migrations/versions/20260723_0039_create_medication_and_prescription_tables.py](/C:/programing/Titan/packages/core_infrastructure/persistence/migrations/versions/20260723_0039_create_medication_and_prescription_tables.py).
- A API de medicamento o expoe como "dias de carencia declarados para o produto" em [apps/api/livestock_medications.py](/C:/programing/Titan/apps/api/livestock_medications.py).

### 1.3 Como a carencia e calculada hoje

- O calculo tecnico local esta em [packages/livestock_application/withdrawal_service.py](/C:/programing/Titan/packages/livestock_application/withdrawal_service.py).
- `WithdrawalCalculator._contribution_of()` resolve `TreatmentApplication -> MedicationBatch -> Medication` e congela `medication.withdrawal_period_days` em `WithdrawalContribution`.
- A regra de agregacao esta em [packages/livestock_domain/withdrawal.py](/C:/programing/Titan/packages/livestock_domain/withdrawal.py):
  - `compute_withdrawal_ends(applied_at, withdrawal_period_days)`
  - `build_animal_withdrawal_status()`
  - `AnimalWithdrawalStatus.eligible_from = max(withdrawal_ends_at)`
- O `FactSnapshot` recebe esse resultado em [packages/livestock_application/fact_provider.py](/C:/programing/Titan/packages/livestock_application/fact_provider.py) como fato `livestock.withdrawal`.

### 1.4 Como a elegibilidade consome o resultado

- A regra farmacologica local esta em [packages/livestock_application/eligibility.py](/C:/programing/Titan/packages/livestock_application/eligibility.py):
  - `build_eligibility_rule()`
  - `RuleCondition(fact_type="livestock.withdrawal", payload_key="in_withdrawal", expected_value=False)`
- A avaliacao tecnica usa `PolicyEvaluationService` e `RuleEvaluationEngine` em [packages/core_application/evaluation_service.py](/C:/programing/Titan/packages/core_application/evaluation_service.py).
- O snapshot preserva `snapshot_hash`, `reference_time` e `knowledge_cutoff` em [packages/core_domain/facts.py](/C:/programing/Titan/packages/core_domain/facts.py).

### 1.5 Onde MarketProfile influencia hoje

- A configuracao atual de mercado esta em [packages/livestock_application/market_eligibility.py](/C:/programing/Titan/packages/livestock_application/market_eligibility.py):
  - `MarketProfile`
  - `MarketWithdrawalBasis`
  - `DEFAULT_MARKET_PROFILES`
- Hoje China e Estados Unidos possuem `declared_withdrawal_period_days=30` e `withdrawal_basis.source_kind="VERTICAL_CONFIGURATION"` no proprio codigo.
- `_with_market_withdrawal_basis()` reescreve o fato `livestock.withdrawal` no snapshot usando o prazo declarado pelo perfil, sem alterar `TreatmentApplication` nem `Medication`.
- Se `ELIGIBILITY_RULE_CODE` estiver adotada e `withdrawal_basis` ausente, a matriz retorna `INDETERMINADO` com gap `CARENCIA_POR_MERCADO_AUSENTE`.

### 1.6 Quais decisoes atuais dependem dessa semantica

- A decisao farmacologica local depende de `livestock.withdrawal.in_withdrawal` em [packages/livestock_application/eligibility.py](/C:/programing/Titan/packages/livestock_application/eligibility.py).
- A decisao por mercado pode depender da recomputacao de `_with_market_withdrawal_basis()` em [packages/livestock_application/market_eligibility.py](/C:/programing/Titan/packages/livestock_application/market_eligibility.py).
- O Dossier atual copia o fato `livestock.withdrawal`, a cadeia de evidencias e a `Rule.normative_source`, mas nao preserva `NormativeBasisSnapshot` materializado para carencia de mercado:
  - [packages/core_application/dossier_service.py](/C:/programing/Titan/packages/core_application/dossier_service.py)
  - [packages/livestock_application/dossier_template.py](/C:/programing/Titan/packages/livestock_application/dossier_template.py)

### 1.7 Prescricao hoje

- `Prescription` existe em [packages/livestock_domain/prescription.py](/C:/programing/Titan/packages/livestock_domain/prescription.py).
- Ela preserva `dosage`, `administration_route`, `reason` e alvos, mas nao possui campo para requisito clinico especifico de carencia.
- `TreatmentApplication` apenas referencia `prescription_id` em [packages/livestock_domain/treatment.py](/C:/programing/Titan/packages/livestock_domain/treatment.py).
- Logo, a prescricao atual pode contextualizar o tratamento, mas nao estabelece hoje um periodo prescrito versionado de carencia.

### 1.8 Policy, Rule, RuleExecutionContext e Dossier hoje

- `Policy` continua generica e versionada em [packages/core_domain/policy.py](/C:/programing/Titan/packages/core_domain/policy.py).
- `Rule` hoje preserva `normative_source` como string e `RuleCondition` declarativa em [packages/core_domain/rule.py](/C:/programing/Titan/packages/core_domain/rule.py).
- `RuleExecutionContext` e contrato de aplicacao, nao entidade normativa persistida, em [packages/core_domain/rule_execution.py](/C:/programing/Titan/packages/core_domain/rule_execution.py).
- `Evaluation` preserva `context_hash`, mas o caminho atual de mercado nao materializa `NormativeBasisSnapshot` especifico de carencia em [packages/core_domain/evaluation.py](/C:/programing/Titan/packages/core_domain/evaluation.py).

### 1.9 Testes reais comprovados

- [tests/livestock_application/test_market_eligibility.py](/C:/programing/Titan/tests/livestock_application/test_market_eligibility.py) cobre:
  - mercado sem regra
  - mercado sem base declarada
  - recomputacao com `MarketWithdrawalBasis`
  - multiplos mercados lado a lado
  - dependencia de estabelecimento
- O teste chave da implementacao atual e `test_market_specific_withdrawal_basis_does_not_silently_reuse_local_medication_period`.
- Nao ha hoje teste cobrindo:
  - prescricao mais restritiva
  - conflito explicito entre bula, prescricao e Policy
  - ausencia de `NormativeBasis`
  - classificacao explicita de regra interna vs regulatoria no caminho da carencia

### 1.10 Artefatos de etapas anteriores

- Artefatos documentais separados encontrados:
  - [docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_C01_BASELINE.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_C01_BASELINE.md)
  - [docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_C02_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_C02_DESIGN_PACKAGE.md)
- Nao foram encontrados arquivos dedicados de conclusao para `LIV-C03` e `LIV-C04` em `docs/plans`.
- Como evidencia de conclusao, permanecem as entradas append-only `0012` e `0013` do status.

## 2. Problema exato

O repositório atual mistura parcialmente cinco camadas distintas:

- Dado tecnico do medicamento:
  - `Medication.withdrawal_period_days`
  - `active_ingredient`
  - `trade_name`
  - fabricante
- Fato da aplicacao:
  - `TreatmentApplication.applied_at`
  - lote aplicado
  - dose observada
  - evidencia
- Requisito de carencia:
  - quantos dias devem ser exigidos para determinada finalidade
  - por qual fonte
  - com qual vigencia
- Regra regulatoria/contratual/interna:
  - qual requisito vale para qual finalidade e mercado
  - como conflitos, ausencia e proibicao sao tratados
- Resultado calculado:
  - `withdrawal_ends_at`
  - `eligible_from`
  - `in_withdrawal`
- Decisao de elegibilidade:
  - `EvaluationOutcome`
  - `DecisionResult`
  - matriz por mercado

Problema comprovado:

- hoje o dado persistido universal e o numero do medicamento;
- a variacao por mercado e introduzida por configuracao da vertical em memoria;
- `MarketProfile` passa a carregar numero concreto de prazo, embora ADR-0049 diga que `MarketProfile` nao e fonte de regra;
- `Rule.normative_source` hoje e texto, nao `NormativeBasis` materializada;
- `Prescription` nao carrega requisito clinico especifico de carencia;
- o Dossier atual explica a conta, mas nao a origem normativa/contratual do requisito de carencia por mercado.

Conclusao do problema:

- o repositorio ja distingue bem `Medication`, `TreatmentApplication`, `Policy`, `Rule`, `Evaluation` e `Decision`;
- o que ainda nao esta corretamente separado e a titularidade do requisito de carencia aplicavel para cada finalidade.

## 3. Alternativas

### Alternativa A

Manter periodo no `Medication` e fazer `Policy` apenas selecionar.

- Aderencia as ADRs:
  - baixa; viola o principio de ADR-0041 de nao reutilizar prazo de um mercado em outro.
- Superficie de dominio:
  - minima.
- Necessidade de migration:
  - nenhuma imediata.
- Reprodutibilidade:
  - parcial; reproduz o numero tecnico local, nao a origem normativa do requisito de mercado.
- Interoperabilidade:
  - fraca; mistura dado tecnico de produto com requisito externo.
- Impacto em dados legados:
  - baixo.
- Risco de duplicacao:
  - alto; cada caller tendera a reinterpretar o mesmo numero.
- Impacto no Dossier:
  - Dossier continuaria sem distinguir dado tecnico de requisito normativo.
- Impacto no `RuleExecutionContext`:
  - baixo, mas porque o contexto seguiria semanticamente insuficiente.
- Veredito:
  - rejeitada.

### Alternativa B

`Medication` preserva dados tecnicos; `Policy`/`Rule` define o requisito aplicavel.

- Aderencia as ADRs:
  - boa; alinha-se a ADR-0041, ADR-0043, ADR-0049 e ADR-0050.
- Superficie de dominio:
  - moderada.
- Necessidade de migration:
  - possivelmente nenhuma se o requisito puder ser derivado sem persistencia nova.
- Reprodutibilidade:
  - boa se o requisito for preservado no snapshot e na evaluation.
- Interoperabilidade:
  - melhor que A.
- Impacto em dados legados:
  - medio; `withdrawal_period_days` legado precisa ser reclassificado como tecnico.
- Risco de duplicacao:
  - medio; ainda falta explicar como prescricao e dado tecnico compoem o requisito.
- Impacto no Dossier:
  - positivo se o requisito aplicado for explicitado.
- Impacto no `RuleExecutionContext`:
  - exige contexto mais rico do que hoje.
- Veredito:
  - viavel, mas incompleta sozinha.

### Alternativa C

Criar estrutura versionada especializada de requisito de carencia.

- Aderencia as ADRs:
  - potencialmente boa.
- Superficie de dominio:
  - alta.
- Necessidade de migration:
  - alta.
- Reprodutibilidade:
  - alta.
- Interoperabilidade:
  - boa.
- Impacto em dados legados:
  - alto.
- Risco de duplicacao:
  - medio.
- Impacto no Dossier:
  - positivo.
- Impacto no `RuleExecutionContext`:
  - positivo, mas exige nova modelagem.
- Veredito:
  - prematura; antes exigiria nova prova, possivel nova ADR e possivel alteracao de `DOMAIN.md`.

### Alternativa D

Composicao entre dado tecnico, prescricao, `Policy` e `NormativeBasis`.

- Aderencia as ADRs:
  - a melhor entre as alternativas; respeita separacao entre fato, regra, fundamento e decisao.
- Superficie de dominio:
  - minima se implementada primeiro por orquestracao e snapshot, sem nova entidade persistente.
- Necessidade de migration:
  - nenhuma obrigatoria na primeira iteracao se `withdrawal_period_days` legado permanecer como dado tecnico.
- Reprodutibilidade:
  - boa, desde que o requisito composto e sua classificacao entrem no snapshot/Dossier.
- Interoperabilidade:
  - melhor; permite diferenciar tecnico, regulatorio, contratual e interno.
- Impacto em dados legados:
  - baixo a medio.
- Risco de duplicacao:
  - menor que nas demais, se houver um unico ponto de composicao.
- Impacto no Dossier:
  - positivo; pode explicar fundamento, limitacoes e conflitos.
- Impacto no `RuleExecutionContext`:
  - exige contexto e reason codes mais explicitos.
- Veredito:
  - recomendada.

## 4. Recomendacao minima

Recomenda-se a Alternativa D, implementada pelo caminho minimo abaixo:

- `Medication.withdrawal_period_days` permanece como dado tecnico local do produto, nunca como verdade regulatoria universal.
- `Policy` e `Rule` continuam sendo o lugar da exigencia aplicavel para a finalidade.
- `MarketProfile` deve apenas resolver/selecionar contexto e politica publicada; nao deve continuar sendo fonte silenciosa do numero normativo.
- `Prescription` nao substitui `Policy` nem `NormativeBasis`.
- Como a modelagem atual de `Prescription` nao carrega requisito clinico especifico de carencia, ela permanece nesta etapa apenas como contexto/evidence do tratamento.
- `NormativeBasis` continua obrigatoria quando a origem alegada for regulatoria; quando a origem for interna ou contratual, isso deve aparecer classificado explicitamente, sem ser apresentado como norma externa.

Justificativa:

- e a menor solucao que preserva semantica historica;
- nao hardcode mercado no dominio operacional;
- nao cria nova fonte de verdade concorrente;
- permite regras futuras;
- trata ausencia e conflito honestamente.

## 5. Contrato alvo

### 5.1 Entradas

- fato tecnico do medicamento:
  - principio ativo
  - apresentacao/dose observada
  - `withdrawal_period_days` tecnico
  - fonte local e versao do medicamento
- fato da aplicacao:
  - `TreatmentApplication`
  - lote
  - instante
  - evidencias
- contexto de prescricao:
  - `prescription_id` quando existir
  - sem criar requisito clinico silencioso onde nao ha dado
- contexto de selecao:
  - finalidade/mercado
  - `Policy` publicada
  - `Rule` publicada
  - classificacao do requisito: regulatorio, contratual ou interno
- fundamento:
  - `NormativeBasis` quando aplicavel
  - ou classificacao explicita de "interna/contratual" quando nao houver base normativa externa

### 5.2 Selecao de requisito

- o requisito aplicavel nao nasce do medicamento;
- o requisito aplicavel nao nasce do animal;
- o requisito aplicavel e selecionado pela `Policy`/`Rule` no contexto da finalidade;
- ausencia de requisito aplicavel nao produz carencia zero; produz gap/indeterminacao.

### 5.3 Composicao

- composicao explicita entre:
  - dado tecnico do produto
  - fato da aplicacao
  - contexto de prescricao, se houver dado clinico material
  - requisito selecionado pela policy
- sem composicao publicada, multiplos requisitos aplicaveis permanecem conflito ou indeterminacao.

### 5.4 Resultado tecnico

- resultado tecnico precisa distinguir:
  - carencia tecnica
  - carencia exigida pela policy
  - carencia efetivamente usada na avaliacao
  - limite final calculado

### 5.5 Reason codes, gaps e conflitos

- gaps minimos conceituais:
  - `WITHDRAWAL_REQUIREMENT_ABSENT`
  - `NORMATIVE_BASIS_ABSENT`
  - `PRESCRIPTION_REQUIREMENT_NOT_MODELED`
  - `MULTIPLE_WITHDRAWAL_REQUIREMENTS_WITHOUT_COMPOSITION`
- conflitos minimos conceituais:
  - divergencia entre dado tecnico e requisito de policy
  - divergencia entre prescricao e requisito de policy
  - divergencia entre classificacao alegada e fundamento disponivel

### 5.6 Snapshot

- o snapshot precisa preservar:
  - o fato `livestock.withdrawal` tecnico
  - o requisito aplicado ou a ausencia dele
  - a classificacao da origem do requisito
  - as limitacoes e conflitos detectados
- o `RuleExecutionContext` continua sendo contrato de aplicacao; nao deve virar tabela nova nesta etapa.

### 5.7 Dossier

- o Dossier deve explicar:
  - o que era dado tecnico
  - o que era requisito de policy
  - se a origem era regulatoria, contratual ou interna
  - quais limitacoes impediram promocao a elegibilidade

## 6. Migracao

- Migration obrigatoria nesta etapa:
  - nao comprovada.
- Tratamento do legado:
  - `Medication.withdrawal_period_days` permanece como dado tecnico legado.
- Provenance/versionamento do legado:
  - nao existe hoje provenance normativa suficiente nesse campo; isso deve permanecer declarado como limitacao, nao reinterpretado como regra.
- Decisoes antigas:
  - nao podem ser reescritas.
- Rollback:
  - qualquer implementacao futura deve permitir reverter a nova composicao preservando `TreatmentApplication`, `Evaluation` e `Decision` historicas.

## 7. Testes obrigatorios

Os seguintes cenarios devem existir antes de considerar a etapa concluida:

1. medicamento com dado tecnico conhecido
2. medicamento sem dado tecnico
3. `Policy` sem requisito de carencia
4. `Policy` com requisito maior que a bula
5. `Policy` com requisito menor que a bula
6. prescricao mais restritiva
7. conflito entre fontes
8. ausencia de `NormativeBasis`
9. regra interna explicitamente classificada
10. mudanca posterior de `Policy`
11. reproducao historica
12. duas Organizations isoladas
13. Dossier com fundamento e limitacoes
14. nenhuma regra aplicavel
15. multiplas regras aplicaveis sem composicao
16. principio ativo proibido
17. carencia ainda vigente
18. carencia cumprida

Estado atual comprovado:

- parte de 1, 3, 10, 14, 17 e 18 ja aparece indiretamente nos testes de matriz;
- 4, 5, 6, 7, 8, 9, 11, 12, 13, 15 e 16 ainda nao estao cobertos para esta semantica.

## 8. Criterios de aceitacao

- [ ] `Medication.withdrawal_period_days` deixa de ser tratado como verdade regulatoria universal.
- [ ] `MarketProfile` deixa de ser fonte silenciosa do requisito concreto de carencia.
- [ ] Ausencia de regra aplicavel nao produz carencia zero.
- [ ] Ausencia de dado nao produz conformidade.
- [ ] Carencia tecnica, prescrita e normativa ficam distinguiveis.
- [ ] Divergencia entre bula, prescricao e `Policy` nao e resolvida silenciosamente.
- [ ] O snapshot preserva requisito aplicado, gaps e conflitos.
- [ ] O Dossier explica fundamento e limitacoes.
- [ ] Nenhuma nova entidade, enum, agregado ou tabela e criada sem prova de insuficiencia dos conceitos atuais.

## 9. Bloqueios

### Bloqueios comprovados nesta execucao

- Divergencia de numeracao entre o pedido atual (`LIV-C06`) e o plano aprovado (`LIV-C05`) para a mesma semantica.
- Nao existe hoje contrato implementado que preserve requisito de carencia com classificacao regulatoria/contratual/interna e fundamento material no caminho de `Evaluation`/`Dossier`.
- `Prescription` nao carrega requisito clinico especifico de carencia; portanto, nao ha base para fazer override clinico silencioso nesta etapa.
- O caminho atual usa `MarketProfile.withdrawal_basis` como configuracao concreta em codigo para China/EUA, sem `NormativeBasis` aprovada.

### Decisao de gate

Esta execucao para no Design Package.

Motivo:

- a recomendacao minima esta definida;
- mas a implementacao imediata exigiria escolher, sem nova decisao humana registrada, entre:
  - continuar usando configuracao concreta da vertical como fonte do requisito; ou
  - bloquear/retirar essa fonte ate que a regra/policy/fundamento estejam explicitamente aprovados.

Esse ponto e arquitetural e muda a autoridade do requisito. Portanto, a execucao nao deve prosseguir silenciosamente.

### PLAN_CHANGE_REQUEST

Nao ha `PLAN_CHANGE_REQUEST` formal nesta execucao, porque a recomendacao minima ainda cabe nos conceitos atuais.

Porem, qualquer implementacao que exija:

- nova entidade generica no Core;
- alteracao de `DOMAIN.md`;
- nova ADR para promover `MarketProfile` ou `PolicyApplicability` a conceito do Core;
- reinterpretacao destrutiva do legado;
- regra normativa concreta sem fundamento aprovado;

devera parar e produzir `PLAN_CHANGE_REQUEST`.
