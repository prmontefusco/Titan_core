# LIVESTOCK_LIFETIME_COMPLIANCE_PLAN

Status: DRAFT_FOR_APPROVAL
Version: 1.2
Date: 2026-08-04
Scope: Rastreabilidade sanitária vitalícia no Titan Livestock, demonstração sobre antimicrobianos, evaluation/decision explicável, dossier verificável e contrato de fronteira com ERP

## 1. Objetivo

Este documento transforma o diagnóstico revisado em uma proposta autoritativa e versionada de plano de implementação.

Este documento não autoriza implementação.

Todas as etapas deste plano começam com status `AGUARDANDO_AUTORIZACAO`.

Nenhuma etapa pode começar sem aprovação explícita.

## 2. Baseline Documental

### 2.1 Leitura de autoridade para este plano

- [AGENTS.md](/C:/programing/Titan/AGENTS.md)
- [VISION.md](/C:/programing/Titan/VISION.md)
- [DOMAIN.md](/C:/programing/Titan/DOMAIN.md)
- [ARCHITECTURE.md](/C:/programing/Titan/ARCHITECTURE.md)
- [DEVELOPMENT.md](/C:/programing/Titan/DEVELOPMENT.md)
- [docs/CHECKLIST_DE_IMPLEMENTACAO.md](/C:/programing/Titan/docs/CHECKLIST_DE_IMPLEMENTACAO.md)
- ADRs [0041](/C:/programing/Titan/docs/adr/0041-elegibilidade-por-mercado-de-destino.md) through [0055](/C:/programing/Titan/docs/adr/0055-dossier-verificavel-assinatura-e-validacao-independente.md)

### 2.2 Verificação da localização do checklist

Constatação confirmada:

- The file does exist at [docs/CHECKLIST_DE_IMPLEMENTACAO.md](/C:/programing/Titan/docs/CHECKLIST_DE_IMPLEMENTACAO.md).
- The file does not exist at repository root as `CHECKLIST_DE_IMPLEMENTACAO.md`.

### 2.3 Divergência de referência

A solicitação anexada exigiu a leitura de `CHECKLIST_DE_IMPLEMENTACAO.md` antes de qualquer implementação, mas não especificou o prefixo `docs/`.

A documentação do repositório já referencia o checklist em `docs/`, e não na raiz, incluindo:

- [docs/PLANO_DE_IMPLEMENTACAO_VALIDADO.md](/C:/programing/Titan/docs/PLANO_DE_IMPLEMENTACAO_VALIDADO.md:8)
- [docs/CORTE_MVP_BACKEND.md](/C:/programing/Titan/docs/CORTE_MVP_BACKEND.md:4)
- [docs/PLANO_DE_CONCLUSAO_DO_DOMINIO.md](/C:/programing/Titan/docs/PLANO_DE_CONCLUSAO_DO_DOMINIO.md:100)
- [docs/adr/0046-transformacao-industrial-e-rastreabilidade-de-produto.md](/C:/programing/Titan/docs/adr/0046-transformacao-industrial-e-rastreabilidade-de-produto.md:396)

### 2.4 Avaliação de bloqueio do checklist

Resultado:

- Este plano não classifica ausência de checklist como bloqueio do repositório, porque o checklist existe.
- Este plano classifica a divergência entre raiz e `docs/` como problema de controle documental que precisa ficar explícito no baseline.
- Nenhum conteúdo do checklist foi inventado aqui. Apenas o arquivo localizado foi referenciado.

## 3. Regras Globais de Controle

- Initial status of every stage is `AGUARDANDO_AUTORIZACAO`.
- No stage auto-approves the next stage.
- Any change to this plan requires a `PLAN_CHANGE_REQUEST`.
- [LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md) is append-only.
- This plan does not authorize changes to code, migration, ADR, `DOMAIN.md`, or `ARCHITECTURE.md`.
- Nenhuma etapa de implementação pode introduzir novo `Aggregate`, `Entity`, `Value Object` ou `Service` sem demonstrar primeiro que os conceitos existentes são insuficientes.

## 4. Princípios Arquiteturais

Toda etapa de implementação deve preferir:

1. Reuse before creation.
2. Derivation before persistence.
3. Composition before specialization.
4. Policy before hardcode.
5. Evidence before assertion.
6. Explanation before optimization.

## 5. Decisões Arquiteturais Comprovadas Relevantes Para Este Plano

- Cross-tenant continuity must happen through protocol, artifact, dossier, or received evidence, never direct tenant access.
  Evidence: ADR-0042.
- Eligibility is not a permanent animal property and must remain policy-driven by purpose/market.
  Evidence: ADR-0041 and ADR-0044.
- Rule lifecycle, adoption, and impact are governed separately from operational facts.
  Evidence: ADR-0043.
- Decisions must remain distinct from evaluations, authority, review, and dossier presentation.
  Evidence: ADR-0048 through ADR-0055.
- PDF is presentation only; dossier and verification content are primary.
  Evidence: ADR-0048 section 9 and ADR-0055 throughout.

## 6. Esclarecimentos Obrigatórios do Diagnóstico Revisado

### 5.1 Continuidade e aquisição: comparar alternativas antes de introduzir uma nova entidade

Problema a resolver:

- Preserve continuity of provenance, imported sanitary history, and coverage gaps when an animal enters a new Organization.

Conceitos existentes comprovados:

- [ReceivedTransferArtifact](/C:/programing/Titan/packages/livestock_domain/transfer_artifact.py)
- `HistoryCoverage` and `TransferArtifactGap`
- [ImportedLivestockFact](/C:/programing/Titan/packages/livestock_domain/imported_fact.py)
- [ExternalCounterparty](/C:/programing/Titan/packages/livestock_domain/external_counterparty.py)
- [ReceivedTransferArtifactService](/C:/programing/Titan/packages/livestock_application/transfer_artifact_service.py)
- [LivestockFactProvider](/C:/programing/Titan/packages/livestock_application/fact_provider.py)

Alternativa A: criar uma nova entidade ou aggregate

- Pros:
  - Could centralize acquisition workflow state in one aggregate.
  - Could make continuity intent more explicit in one domain object.
- Cons:
  - No accepted ADR currently requires a new aggregate for this behavior.
  - Existing code already represents received artifact, external source, coverage gap, and imported fact separately.
  - Introducing a new aggregate now would add domain surface before proving that orchestration with current concepts is insufficient.
  - AGENTS.md forbids inventing requirements and unnecessary abstractions.

Alternativa B: implementar como caso de uso de Application orquestrando conceitos existentes

- Pros:
  - Matches ADR-0042 more directly: transfer by artifact and imported assertion, not by shared record.
  - Reuses existing domain objects already covered by tests and persistence.
  - Is the minimum change consistent with current code and ADRs.
  - Avoids inventing a `ContinuityAssertion` class or `AnimalAcquisition` aggregate before necessity is proven.
- Cons:
  - Orchestration complexity remains in Application until a second proven case justifies a dedicated aggregate.

Recomendação:

- Recommend Alternative B as the minimum compliant path.

Justificativa:

- ADR-0042 requires continuity by artifact, provenance, and explicit gaps, all of which already exist in current code.
- The current repository already has the primitives needed for acquisition behavior, but not yet the orchestrating use case.
- No proven code conflict currently forces a new `AnimalAcquisition` aggregate.

### 5.2 Não uso de antimicrobianos deve permanecer conclusão de Policy, e não fato automático

Este plano separa explicitamente:

- absence of registered event:
  - No `TreatmentApplication` or imported treatment was found.
  - This is not proof of non-use.
- claim of non-use:
  - Would be a declaration or imported assertion if approved in future.
  - It is not inferred automatically here.
- historical coverage:
  - Determines whether the known period is sufficient for a policy question.
  - Current code already represents coverage only partially through transfer artifacts.
- evidence:
  - Must remain separate from the claim or event.
  - Current code already separates `evidence_references` from notes in treatment.
- policy conclusion:
  - Only Policy/Rule/Evaluation/Decision may conclude whether available coverage and evidence are sufficient.

### 5.3 Carência por mercado não pode ser pré-comprometida com uma tabela

O diagnóstico encontrou uma tensão real:

- [Medication.withdrawal_period_days](/C:/programing/Titan/packages/livestock_domain/medication.py) is currently a single technical field per medication.
- ADR-0041 explicitly rejects reusing one market's withdrawal period for another.

This plan therefore does not pre-decide a `WithdrawalRequirement` table.

The implementation analysis for the relevant stage must compare whether the requirement belongs to:

- technical medication fact:
  - current local product property used by the withdrawal calculator;
- governed Rule:
  - if market-specific withdrawal is encoded directly as a rule condition or rule logic;
- NormativeBasis:
  - if the requirement must be traceable as normative support for market-specific timing;
- versioned vertical configuration:
  - if market profile configuration resolves which requirement set applies;
- or a combination:
  - most likely technical local medication data plus governed market policy and normative basis.

Recomendação em nível de planejamento:

- Treat this as an explicit analysis gate in `LIV-C05`, not as a pre-authorized schema decision.

### 5.4 Precedência de Dossier e VerificationBundle sobre PDF

Este plano trata:

- Dossier content and identity as primary;
- VerificationBundle and validation semantics as primary for independent verification;
- PDF only as derived Presentation.

Isto se apoia em:

- [packages/core_application/dossier_service.py](/C:/programing/Titan/packages/core_application/dossier_service.py)
- ADR-0048
- ADR-0055

### 5.5 O comportamento de continuidade deve ser avaliado com os conceitos atuais antes de introduzir `ContinuityAssertion`

Este plano não cria nem presume uma classe `ContinuityAssertion`.

O comportamento atual deve ser avaliado primeiro por meio de:

- received artifact
- coverage gap
- imported fact
- external counterparty
- typed references and provenance

Somente uma insuficiência demonstrada desses conceitos pode justificar um novo tipo de domínio.

## 7. Ordem Proposta

A ordem proposta pelo usuário foi mantida porque a evidência atual a sustenta:

1. `LIV-C01` — baseline documental e referências normativas
2. `LIV-C02` — cobertura sanitária e lacunas
3. `LIV-C03` — aquisição e continuidade documental
4. `LIV-C04` — fatos sanitários importados no snapshot
5. `LIV-C05` — carência governada por Policy
6. `LIV-C06` — emissão autorizada de Decision
7. `LIV-C07` — Dossier/VerificationBundle sanitário
8. `LIV-C08` — contrato de integração ERP, sem Odoo real

Razão:

- `LIV-C01` must freeze documentary baseline first.
- `LIV-C02` and `LIV-C03` must precede imported history semantics.
- `LIV-C05` depends on the coverage/continuity model and on imported facts being explicit.
- `LIV-C06` through `LIV-C07` depend on upstream content being modeled honestly.
- `LIV-C08` must remain last because the ERP contract must not lead domain authority.

## 8. Etapas do Plano

### LIV-C01

- ID estável: `LIV-C01`
- status: `AGUARDANDO_AUTORIZACAO`
- objetivo:
  - Congelar o baseline documental e normativo do planejamento de conformidade sanitária vitalícia.
- problema comprovado:
  - O caminho da solicitação referenciou `CHECKLIST_DE_IMPLEMENTACAO.md` de forma ambígua, enquanto as referências do repositório apontam para `docs/CHECKLIST_DE_IMPLEMENTACAO.md`.
  - O backend e o checklist evoluíram em múltiplos documentos e ADRs e precisam de um baseline único e explícito para o plano de conformidade.
- pré-requisitos:
  - Ler os documentos de autoridade e localizar o checklist.
- portões:
  - Confirmar o caminho do checklist e as referências documentadas.
  - Confirmar que nenhuma implementação começa a partir de referências documentais ambíguas ou desatualizadas.
- ADRs aplicáveis:
  - ADR-0041 through ADR-0055 as baseline set.
- invariantes:
  - Nenhum conteúdo do checklist é inventado.
  - Nenhuma ausência no caminho de raiz pode ser ocultada se for relevante para as instruções.
  - As etapas do plano permanecem não autorizadas até aprovação explícita.
- fora de escopo:
  - Código, migrations, mudanças de API e edição de ADRs.
- contratos afetados:
  - Contrato documental apenas.
- arquivos comprovados:
  - [docs/CHECKLIST_DE_IMPLEMENTACAO.md](/C:/programing/Titan/docs/CHECKLIST_DE_IMPLEMENTACAO.md)
  - [docs/PLANO_DE_IMPLEMENTACAO_VALIDADO.md](/C:/programing/Titan/docs/PLANO_DE_IMPLEMENTACAO_VALIDADO.md)
  - [docs/CORTE_MVP_BACKEND.md](/C:/programing/Titan/docs/CORTE_MVP_BACKEND.md)
  - [docs/PLANO_DE_CONCLUSAO_DO_DOMINIO.md](/C:/programing/Titan/docs/PLANO_DE_CONCLUSAO_DO_DOMINIO.md)
  - [docs/adr/0046-transformacao-industrial-e-rastreabilidade-de-produto.md](/C:/programing/Titan/docs/adr/0046-transformacao-industrial-e-rastreabilidade-de-produto.md)
- migrations:
  - Nenhuma.
- testes unitários:
  - None.
- testes PostgreSQL:
  - None.
- testes RLS:
  - None.
- testes E2E:
  - None.
- critérios de aceitação em checklist:
  - [ ] Checklist location is explicitly recorded.
  - [ ] Reference divergence is explicitly recorded.
  - [ ] No invented checklist text was added.
  - [ ] Block condition is explicitly stated if checklist becomes unavailable.
- evidências obrigatórias:
  - Evidência de busca comprovando a localização do checklist.
  - Evidência de busca comprovando as referências na documentação.
- riscos:
  - Desvio de baseline entre documentos.
  - Trabalho futuro citando o caminho errado do checklist.
- rollback:
  - Substituir a versão do plano por baseline documental corrigido por `PLAN_CHANGE_REQUEST`.
- condição de bloqueio:
  - Se o checklist se tornar indisponível ou contraditório em relação aos documentos de autoridade.
- próxima etapa permitida:
  - `LIV-C02`

### LIV-C02

- ID estável: `LIV-C02`
- status: `AGUARDANDO_AUTORIZACAO`
- Architectural Question:
  - Can lifetime sanitary coverage be represented without introducing a new `Aggregate`?
- objetivo:
  - Definir o modelo mínimo conforme para cobertura sanitária e lacunas explícitas ao longo de todo o histórico vitalício.
- problema comprovado:
  - O código atual modela lacunas de cobertura apenas para `ReceivedTransferArtifact`, e ainda não como modelo geral de cobertura sanitária vitalícia.
  - O código atual não permite que uma Policy distinga de forma consistente cobertura vitalícia completa de conhecimento local parcial entre histórico local e importado.
- pré-requisitos:
  - `LIV-C01` approved baseline.
- Decision rule:
  - A solução preferida é a que introduz a menor superfície de domínio.
  - A solução preferida é a que preserva semânticas já aceitas.
  - A solução preferida é a que exige o menor número de conceitos persistentes.
  - A solução preferida é a que minimiza impacto de migration.
  - A solução preferida é a que permanece compatível com ADRs já aceitas.
- portões:
  - Responder explicitamente: "É possível representar cobertura sanitária reutilizando exclusivamente os conceitos já existentes no Core? Se sim, nenhuma nova entidade ou `Aggregate` deverá ser introduzido."
  - Comprovar a representação mínima necessária para cobertura e lacunas sem transformar ausência em prova negativa.
  - Manter cobertura distinta de claim, evidence e decision.
- ADRs aplicáveis:
  - ADR-0042
  - ADR-0048
  - ADR-0051
  - ADR-0052
- invariantes:
  - Ausência de evento nunca prova ausência de tratamento.
  - Lacuna de cobertura é explícita.
  - Cobertura é insumo de Policy, não resultado direto de conformidade.
- fora de escopo:
  - Regras de carência específicas por mercado.
  - Integração com ERP.
- contratos afetados:
  - Conteúdo do snapshot para avaliação sanitária.
  - Conteúdo do Dossier para declaração de cobertura e lacuna.
- arquivos comprovados:
  - [packages/livestock_domain/transfer_artifact.py](/C:/programing/Titan/packages/livestock_domain/transfer_artifact.py)
  - [packages/livestock_application/fact_provider.py](/C:/programing/Titan/packages/livestock_application/fact_provider.py)
  - [packages/livestock_application/dossier_template.py](/C:/programing/Titan/packages/livestock_application/dossier_template.py)
  - [tests/livestock_domain/test_transfer_artifact_domain.py](/C:/programing/Titan/tests/livestock_domain/test_transfer_artifact_domain.py)
- migrations:
  - A determinar apenas se a cobertura não puder permanecer derivada.
- testes unitários:
  - Semântica de lacuna de cobertura.
  - Cobertura desde o nascimento vs. cobertura a partir de data posterior.
- testes PostgreSQL:
  - Comportamento de cobertura persistida ou derivada, conforme o desenho aprovado.
- testes RLS:
  - Material de cobertura de uma Organization não pode vazar para outra.
- testes E2E:
  - Animal com histórico vitalício local completo.
  - Animal com histórico parcial conhecido e lacuna declarada.
- critérios de aceitação em checklist:
  - [ ] Coverage and gap semantics are explicit.
  - [ ] No absence of event is promoted to non-use.
  - [ ] Policy can consume coverage as input.
  - [ ] Dossier can declare lacunas honestly.
- evidências obrigatórias:
  - Referências de código mostrando a implementação parcial atual.
  - Testes provando ausência de alegação silenciosa de completude.
- riscos:
  - Superestimar completude.
  - Confundir lacuna com inelegibilidade.
- rollback:
  - Remover apenas adições novas específicas de cobertura, preservando o comportamento anterior de lacunas baseadas em artifact.
- condição de bloqueio:
  - Se a semântica aprovada exigir contradição com ADR-0042 ou ADR-0052.
- próxima etapa permitida:
  - `LIV-C03`

### LIV-C03

- ID estável: `LIV-C03`
- status: `AGUARDANDO_AUTORIZACAO`
- Architectural Question:
  - Can acquisition continuity be represented through orchestration instead of a dedicated `Aggregate`?
- objetivo:
  - Implementar o comportamento mínimo conforme de aquisição e continuidade documental com o menor desenho justificável.
- problema comprovado:
  - O repositório atual possui `transfer artifact`, `imported fact` e `external counterparty`, mas ainda não tem uma orquestração explícita de ponta a ponta para continuidade local na aquisição.
- pré-requisitos:
  - `LIV-C01`
  - `LIV-C02`
- Decision rule:
  - A solução preferida é a que introduz a menor superfície de domínio.
  - A solução preferida é a que preserva semânticas já aceitas.
  - A solução preferida é a que exige o menor número de conceitos persistentes.
  - A solução preferida é a que minimiza impacto de migration.
  - A solução preferida é a que permanece compatível com ADRs já aceitas.
- portões:
  - Comparar explicitamente Alternativa A vs. Alternativa B.
  - Aprovar o caminho mínimo antes de qualquer implementação.
  - Se nenhuma das alternativas for suficiente, interromper a implementação até nova aprovação arquitetural explícita para novo `Aggregate`.
- ADRs aplicáveis:
  - ADR-0042
  - ADR-0048
  - ADR-0051
  - ADR-0052
- invariantes:
  - Não há leitura/escrita cross-tenant.
  - `Imported fact` nunca se torna fato local.
  - Cobertura anterior à aquisição permanece explícita.
  - Nenhuma `ContinuityAssertion` é introduzida sem prova de insuficiência dos conceitos atuais.
- fora de escopo:
  - Identidade global de animal.
  - Transformação de produto após abate.
- contratos afetados:
  - Contrato de orquestração de aquisição/Application.
  - Entradas do snapshot para histórico importado.
- arquivos comprovados:
  - [packages/livestock_domain/transfer_artifact.py](/C:/programing/Titan/packages/livestock_domain/transfer_artifact.py)
  - [packages/livestock_domain/imported_fact.py](/C:/programing/Titan/packages/livestock_domain/imported_fact.py)
  - [packages/livestock_application/transfer_artifact_service.py](/C:/programing/Titan/packages/livestock_application/transfer_artifact_service.py)
  - [packages/livestock_application/imported_fact_service.py](/C:/programing/Titan/packages/livestock_application/imported_fact_service.py)
  - [tests/livestock_application/test_transfer_artifact_service.py](/C:/programing/Titan/tests/livestock_application/test_transfer_artifact_service.py)
- migrations:
  - A determinar conforme o caminho aprovado.
- testes unitários:
  - Aquisição com dossier verificado.
  - Aquisição sem histórico prévio.
  - Declaração de lacuna na fronteira de transferência.
- testes PostgreSQL:
  - Persistência e recuperação de artifacts do lado da aquisição ou resultados orquestrados.
- testes RLS:
  - Nenhuma visibilidade do tenant de origem pelo tenant de destino.
- testes E2E:
  - Animal adquirido com histórico externo verificável.
  - Animal adquirido sem histórico e com lacuna explícita.
- critérios de aceitação em checklist:
  - [ ] Alternative A vs B comparison is documented.
  - [ ] Minimum path is justified with code and ADR evidence.
  - [ ] No new aggregate is introduced without explicit approval.
  - [ ] No continuity claim is invented automatically from identifier coincidence.
- evidências obrigatórias:
  - Seção explícita de comparação.
  - Rastreabilidade de `artifact` para `imported fact` e então para uso em snapshot.
- riscos:
  - Sobremodelagem de domínio.
  - Acoplamento silencioso entre tenants.
- rollback:
  - Remover a orquestração de aquisição preservando os primitivos existentes de `transfer artifact` e `imported fact`.
- condição de bloqueio:
  - Se o comportamento aprovado não puder ser alcançado com os conceitos atuais e nenhuma decisão sobre novo `aggregate` estiver autorizada.
- próxima etapa permitida:
  - `LIV-C04`

### LIV-C04

- ID estável: `LIV-C04`
- status: `AGUARDANDO_AUTORIZACAO`
- Architectural Question:
  - How can imported sanitary facts enter snapshot/evaluation while preserving provenance and confidence as separate dimensions?
- objetivo:
  - Garantir que fatos sanitários importados participem de snapshot/evaluation com proveniência e confiança preservadas.
- problema comprovado:
  - O `fact provider` atual já inclui contribuições importadas de carência, mas fatos sanitários importados ainda não foram generalizados por completo para avaliação sanitária vitalícia.
- pré-requisitos:
  - `LIV-C02`
  - `LIV-C03`
- Decision rule:
  - A solução preferida é a que introduz a menor superfície de domínio.
  - A solução preferida é a que preserva separação entre proveniência, confiança e observação local.
  - A solução preferida é a que exige o menor número de conceitos persistentes.
  - A solução preferida é a que minimiza impacto de migration.
  - A solução preferida é a que permanece compatível com ADRs já aceitas.
- portões:
  - Preservar origem e confiança de forma independente.
  - Não inferir não uso.
- ADRs aplicáveis:
  - ADR-0042
  - ADR-0048
  - ADR-0050
  - ADR-0051
- invariantes:
  - Origem importada e confiança permanecem independentes.
  - `Imported evidence` não se torna observação local.
  - O snapshot deve preservar insumos de proveniência relevantes para a evaluation.
- fora de escopo:
  - Autoridade final de decisão específica por mercado.
- contratos afetados:
  - `LivestockFactProvider`
  - Consumo de `imported fact` em `Evaluation`
- arquivos comprovados:
  - [packages/livestock_application/fact_provider.py](/C:/programing/Titan/packages/livestock_application/fact_provider.py)
  - [packages/livestock_domain/imported_fact.py](/C:/programing/Titan/packages/livestock_domain/imported_fact.py)
  - [tests/livestock_domain/test_imported_fact_domain.py](/C:/programing/Titan/tests/livestock_domain/test_imported_fact_domain.py)
- migrations:
  - Apenas se o escopo aprovado exigir novas categorias persistidas de `imported fact`.
- testes unitários:
  - Tratamento importado documentado vs. alegação de baixa confiança.
  - Fatos importados conflitantes.
- testes PostgreSQL:
  - Persistência e recuperação de `imported fact` por animal.
- testes RLS:
  - Fatos importados permanecem isolados por Organization proprietária.
- testes E2E:
  - Tratamento de terceiro afeta a avaliação sanitária sem se tornar fato local.
- critérios de aceitação em checklist:
  - [ ] Imported facts reach snapshot with provenance.
  - [ ] Origin and confidence are preserved.
  - [ ] No automatic “non-use” fact is created.
- evidências obrigatórias:
  - Payload de snapshot comprovando a semântica da contribuição importada.
  - Testes comprovando o tratamento independente de proveniência e confiança.
- riscos:
  - Colapso entre proveniência e confiança.
  - Extrapolação de `imported fact` além do escopo admissível.
- rollback:
  - Remover novos consumidores de `imported fact` preservando o armazenamento já existente.
- condição de bloqueio:
  - Se a semântica de `imported fact` exigir um novo conceito central ainda não aceito.
- próxima etapa permitida:
  - `LIV-C05`

### LIV-C05

- ID estável: `LIV-C05`
- status: `AGUARDANDO_AUTORIZACAO`
- Architectural Question:
  - Where does market-governed withdrawal belong: `Medication`, `Policy`, `NormativeBasis`, configuração da vertical ou combinação?
- objetivo:
  - Resolver como a carência governada por mercado deve ser modelada e avaliada sem hardcode em `Animal`.
- problema comprovado:
  - O código atual usa um único `withdrawal_period_days` em `Medication`, enquanto a ADR-0041 rejeita reuso silencioso entre mercados.
- pré-requisitos:
  - `LIV-C02`
  - `LIV-C04`
- Decision rule:
  - A solução preferida é a que introduz a menor superfície de domínio.
  - A solução preferida é a que preserva semânticas já aceitas.
  - A solução preferida é a que exige o menor número de conceitos persistentes.
  - A solução preferida é a que minimiza impacto de migration.
  - A solução preferida é a que permanece compatível com ADRs já aceitas.
  - A solução preferida é a que mantém compatibilidade com integrações futuras, incluindo SISBOV, ERP e certificadoras.
- portões:
  - Comparar se o requisito pertence a dado técnico do medicamento, `Rule` governada, `NormativeBasis`, configuração versionada da vertical ou combinação.
  - Nenhuma decisão de tabela/schema antes da aprovação dessa comparação.
- ADRs aplicáveis:
  - ADR-0041
  - ADR-0044
  - ADR-0049
  - ADR-0050
- invariantes:
  - Nenhuma regra de mercado externo é inventada a partir de dado local de produto.
  - Ausência de declaração de carência para o mercado produz resultado indeterminado, não aprovação.
  - `Rule`, `NormativeBasis` e dado técnico do produto permanecem distintos.
- fora de escopo:
  - Expansão completa do domínio de exames/vacinação.
- contratos afetados:
  - Semântica de `Medication`
  - Avaliação de elegibilidade por mercado
  - Explicação no Dossier da base de carência
- arquivos comprovados:
  - [packages/livestock_domain/medication.py](/C:/programing/Titan/packages/livestock_domain/medication.py)
  - [packages/livestock_domain/withdrawal.py](/C:/programing/Titan/packages/livestock_domain/withdrawal.py)
  - [packages/livestock_application/market_eligibility.py](/C:/programing/Titan/packages/livestock_application/market_eligibility.py)
  - [tests/livestock_application/test_market_eligibility.py](/C:/programing/Titan/tests/livestock_application/test_market_eligibility.py)
- migrations:
  - A determinar apenas após decisão de modelagem aprovada.
- testes unitários:
  - Mercado com base declarada de carência.
  - Mercado sem base declarada de carência.
- testes PostgreSQL:
  - Estratégia persistida se novas tabelas/configurações forem aprovadas.
- testes RLS:
  - Isolamento de Policy/configuração por Organization quando aplicável.
- testes E2E:
  - Carência ainda vigente.
  - Carência concluída.
  - Market-specific indeterminate when basis absent.
- critérios de aceitação em checklist:
  - [ ] Modeling comparison is explicit.
  - [ ] Approved shape does not silently reuse local withdrawal data for foreign markets.
  - [ ] Dossier explains basis honestly.
- evidências obrigatórias:
  - Seção de comparação entre ADR e código.
  - Tensão atual documentada com arquivos exatos.
- riscos:
  - Compromisso prematuro com schema.
  - Mistura entre preocupações técnicas e normativas.
- rollback:
  - Preservar o comportamento atual de campo único até que o caminho de migration aprovado esteja totalmente validado.
- condição de bloqueio:
  - Se não existir decisão de modelagem aprovada após a comparação.
- próxima etapa permitida:
  - `LIV-C06`

### LIV-C06

- ID estável: `LIV-C06`
- status: `AGUARDANDO_AUTORIZACAO`
- Architectural Question:
  - What is the minimum authorized path that produces an official `Decision` without collapsing `Evaluation`, authority, review and emission?
- objetivo:
  - Levar decisões sanitárias vitalícias para o fluxo autorizado de `Decision` exigido pelas ADRs 0048 a 0054.
- problema comprovado:
  - Governança central e autoridade já estão parcialmente implementadas, mas os documentos revisados e as ADRs ainda registram lacunas residuais no fluxo de emissão em nível de produção.
- pré-requisitos:
  - `LIV-C04`
  - `LIV-C05`
- Decision rule:
  - A solução preferida é a que introduz a menor superfície de domínio.
  - A solução preferida é a que preserva separação entre `Evaluation`, `Decision`, authority e review.
  - A solução preferida é a que exige o menor número de conceitos persistentes novos.
  - A solução preferida é a que minimiza impacto de migration.
  - A solução preferida é a que permanece compatível com ADRs já aceitas.
- portões:
  - Nenhuma emissão oficial de `Decision` sem autoridade, perfil e fluxo de revisão quando exigidos.
- ADRs aplicáveis:
  - ADR-0048
  - ADR-0052
  - ADR-0053
  - ADR-0054
- invariantes:
  - `Evaluation` não é `Decision`.
  - `Proposal` não é `Decision`.
  - Exigência de revisão humana bloqueia emissão oficial automática.
- fora de escopo:
  - Reconhecimento jurídico externo.
- contratos afetados:
  - `DecisionAuthorityProfile`
  - `DecisionProposal`
  - Fluxo de avaliação sanitária para `Decision`
- arquivos comprovados:
  - [packages/core_domain/decision.py](/C:/programing/Titan/packages/core_domain/decision.py)
  - [packages/core_domain/evaluation.py](/C:/programing/Titan/packages/core_domain/evaluation.py)
  - [packages/core_domain/decision_governance.py](/C:/programing/Titan/packages/core_domain/decision_governance.py)
  - [tests/integration/test_decision_governance_postgresql.py](/C:/programing/Titan/tests/integration/test_decision_governance_postgresql.py)
- migrations:
  - Já parcialmente presente; novas migrations apenas se lacunas incrementais aprovadas exigirem.
- testes unitários:
  - Recusa quando falta autoridade.
  - Criação de `Proposal` quando revisão é exigida.
- testes PostgreSQL:
  - Roundtrip de persistência de governança.
- testes RLS:
  - Registros de governança de `Decision` isolados entre Organizations.
- testes E2E:
  - Cenário com revisão obrigatória.
  - Emissão válida com autoridade.
  - Tentativa de emissão sem autoridade.
- critérios de aceitação em checklist:
  - [ ] No automatic official decision on review-required path.
  - [ ] Authority profile is resolved and persisted where required.
  - [ ] Proposal/review path is explicit.
- evidências obrigatórias:
  - Testes para ausência de autoridade e exigência de revisão.
  - Cadeia de `Decision` pronta para Dossier com referências de autoridade.
- riscos:
  - Apresentar resultados técnicos como decisões oficiais.
  - Quebrar o fluxo automático existente sem comportamento explícito de migration.
- rollback:
  - Manter decisões históricas legíveis ao reverter mudanças do novo fluxo de emissão.
- condição de bloqueio:
  - Se o fluxo de decisão sanitária ainda depender de lacunas de chamador não resolvidas nas ADRs 0052 ou 0054.
- próxima etapa permitida:
  - `LIV-C07`

### LIV-C07

- ID estável: `LIV-C07`
- status: `AGUARDANDO_AUTORIZACAO`
- Architectural Question:
  - What is the minimum canonical Dossier/VerificationBundle content that honestly represents lifetime sanitary compliance before any PDF `Presentation`?
- objetivo:
  - Expandir o conteúdo sanitário de Dossier e VerificationBundle para o escopo de conformidade vitalícia, com PDF apenas como `Presentation` derivada.
- problema comprovado:
  - O Dossier atual já preserva o núcleo de decision/evaluation e a cadeia vertical de carência, mas ainda não demonstra por completo cobertura sanitária vitalícia, lacunas, escopo de histórico importado e base de Policy para o problema ampliado.
- pré-requisitos:
  - `LIV-C02`
  - `LIV-C04`
  - `LIV-C06`
- Decision rule:
  - A solução preferida é a que introduz a menor superfície de domínio.
  - A solução preferida é a que preserva semânticas já aceitas de Dossier e VerificationBundle.
  - A solução preferida é a que privilegia derivação e composição antes de persistência nova.
  - A solução preferida é a que minimiza impacto de migration.
  - A solução preferida é a que permanece compatível com ADRs já aceitas.
- portões:
  - O conteúdo normativo canônico do Dossier e o contrato do VerificationBundle são implementados e testados antes de qualquer PDF ser tratado como entrega normativa.
  - PDF é tratado apenas depois que o conteúdo canônico e o contrato verificável estiverem definidos.
- ADRs aplicáveis:
  - ADR-0048
  - ADR-0051
  - ADR-0055
- invariantes:
  - PDF não é fonte normativa.
  - O Dossier não pode sugerir cobertura vitalícia completa quando existirem lacunas.
  - `Imported evidence` não é exibida como fato local.
  - Verificação offline é dimensional e pode ser parcial.
  - Dependência externa ausente não é apresentada como adulteração.
- fora de escopo:
  - UX pública final.
- contratos afetados:
  - Conteúdo documental do Dossier
  - Seleção de conteúdo de `bundle-verification`
- arquivos comprovados:
  - [packages/core_application/dossier_service.py](/C:/programing/Titan/packages/core_application/dossier_service.py)
  - [packages/livestock_application/dossier_template.py](/C:/programing/Titan/packages/livestock_application/dossier_template.py)
  - [tests/integration/test_dossier_postgresql.py](/C:/programing/Titan/tests/integration/test_dossier_postgresql.py)
- migrations:
  - Nenhuma, salvo se o conteúdo aprovado exigir novas referências persistidas.
- testes unitários:
  - Dossier com cobertura completa.
  - Dossier com cobertura parcial e lacunas explícitas.
- testes PostgreSQL:
  - Roundtrip e verificação offline do conteúdo expandido do dossier.
- testes RLS:
  - Dossier e `evidence` subjacente permanecem isolados por tenant.
- testes E2E:
  - Dossier parcial.
  - Dossier completo.
  - Verificação independente sem dependência do banco operacional, com resultado dimensional e possivelmente parcial.
- critérios de aceitação em checklist:
  - [ ] O conteúdo normativo canônico do Dossier e o contrato do VerificationBundle são implementados e testados antes de qualquer PDF ser tratado como entrega normativa.
  - [ ] Cobertura, eventos, medicamentos, carências, lacunas, Policy, evaluation e decision são representados com honestidade.
  - [ ] O conteúdo de verificação declara limites, componentes examinados e dimensões validadas, indeterminadas ou não executadas.
  - [ ] Verificação offline parcial não é apresentada como verificação integral.
- evidências obrigatórias:
  - `ValidationReport` ou `VerificationReport` offline contendo dimensões, limitações, componentes examinados e resultado agregado.
  - Recomposição de hash sobre o conteúdo canônico do dossier.
- riscos:
  - Dossier excessivamente grande por cópia crua de timeline.
  - Desvio de implementação orientada por PDF primeiro.
- rollback:
  - Reverter a seção vertical expandida preservando o comportamento central já existente do dossier.
- condição de bloqueio:
  - Se o conteúdo canônico do bundle não puder ser definido sem semântica upstream ainda não resolvida.
- próxima etapa permitida:
  - `LIV-C08`

### LIV-C08

- ID estável: `LIV-C08`
- status: `AGUARDANDO_AUTORIZACAO`
- Architectural Question:
  - What is the minimum ERP contract that preserves Titan as the sole authority over sanitary facts?
- objetivo:
  - Definir a fronteira do contrato de integração com ERP sem introduzir autoridade de domínio acoplada a Odoo.
- problema comprovado:
  - O repositório e os documentos de autoridade deixam explícito que ERP não é a fonte autoritativa do histórico sanitário vitalício, mas ainda não existe neste plano um contrato de fronteira MVP explicitamente congelado para integração operacional futura.
- pré-requisitos:
  - `LIV-C05`
  - `LIV-C07`
- Decision rule:
  - A solução preferida é a que introduz a menor superfície de domínio.
  - A solução preferida é a que preserva Titan como única autoridade dos fatos sanitários.
  - A solução preferida é a que exige o menor número de conceitos persistentes novos.
  - A solução preferida é a que minimiza impacto de migration.
  - A solução preferida é a que permanece compatível com ADRs já aceitas.
- portões:
  - Manter o Titan como autoridade dos eventos sanitários de vida.
  - Manter a integração com ERP idempotente, observável e segura quanto a efeitos externos.
- ADRs aplicáveis:
  - ADR-0042
  - ADR-0048
  - ADR-0050
- invariantes:
  - Baixa de estoque no ERP não prova aplicação.
  - Conclusão de tarefa no ERP não prova manejo.
  - Titan e ERP permanecem desacoplados em nível de tabela/ORM/banco.
  - Confirmação técnica do ERP não altera, autoriza nem substitui o fato sanitário original registrado no Titan.
  - Nenhuma operação administrativa proveniente do ERP gera automaticamente `Evidence`, `Fact`, `Evaluation` ou `Decision`.
- fora de escopo:
  - Integração real com Odoo.
  - Implantação externa.
- contratos afetados:
  - Contrato de integração de saída do Titan.
  - Recibo técnico, acknowledgement ou confirmação idempotente da plataforma operacional.
  - Estado de entrega, retry e reconciliação, sem autoridade do ERP sobre o fato sanitário original.
- arquivos comprovados:
  - [AGENTS.md](/C:/programing/Titan/AGENTS.md)
  - [VISION.md](/C:/programing/Titan/VISION.md)
  - [ARCHITECTURE.md](/C:/programing/Titan/ARCHITECTURE.md)
  - [docs/CHECKLIST_DE_IMPLEMENTACAO.md](/C:/programing/Titan/docs/CHECKLIST_DE_IMPLEMENTACAO.md)
- migrations:
  - Nenhuma na etapa de planejamento.
- testes unitários:
  - Testes de serialização de contrato e idempotência quando implementado.
- testes PostgreSQL:
  - Comportamento de persistência de outbox/integração quando implementado.
- testes RLS:
  - Nenhum vazamento cross-tenant por meio do estado de integração.
- testes E2E:
  - Baixa idempotente no ERP a partir de evento sanitário do Titan.
  - Falha no ERP sem perda do evento sanitário do Titan.
  - Retry seguro com reconciliação e sem reescrever a verdade sanitária do Titan.
- critérios de aceitação em checklist:
  - [ ] A fronteira do ERP está explícita.
  - [ ] Nenhuma autoridade do ERP sobre fatos sanitários é implícita.
  - [ ] A integração prevê confirmação técnica idempotente, retry seguro e reconciliação.
  - [ ] A semântica de falha preserva a verdade do evento no Titan.
- evidências obrigatórias:
  - Exemplos de contrato, acknowledgement técnico e declaração explícita de não autoridade do ERP.
- riscos:
  - Desvio de autoridade de domínio em direção ao ERP.
  - Acoplamento operacional oculto.
- rollback:
  - Desabilitar o adapter ou a publicação operacional, preservando mensagens e estados já registrados.
  - Manter a versão publicada do contrato.
  - Introduzir correção ou nova versão se o contrato já tiver consumidores.
- condição de bloqueio:
  - Se o contrato exigir nova dependência externa ou decisão de arquitetura ainda não aprovada.
- próxima etapa permitida:
  - None. Requires fresh approval cycle.

## 9. Decisões Pendentes

- Se a cobertura sanitária geral permanece derivada ou precisa de estruturas persistidas.
- Se a continuidade de aquisição pode permanecer como orquestração de Application ou precisa de `aggregate` dedicado após prova.
- Qual combinação modelará corretamente a carência governada por mercado.
- Qual mercado real ou `NormativeBasis` consumirá primeiro as regras sanitárias expandidas.
- Se algum novo conceito específico de exame é necessário para o MVP.

## 10. Resumo das Condições de Bloqueio

- Bloqueio documental apenas se o checklist se tornar indisponível ou contraditório em relação aos documentos de autoridade.
- Bloqueio de modelagem se `LIV-C03` não puder ser alcançado com os conceitos atuais e nenhum novo `aggregate` for aprovado.
- Bloqueio de modelagem se `LIV-C05` não tiver resposta aprovada para a titularidade da carência entre medication/rule/normative basis/configuration.
- Bloqueio de emissão se `LIV-C06` ainda depender de lacunas não resolvidas de caller em autoridade/revisão.

## 11. Primeira Etapa Recomendada

Primeira etapa recomendada:

- `LIV-C01`

Razão:

- Tem o menor raio de impacto.
- Fecha explicitamente a ambiguidade do caminho do checklist.
- Estabelece o baseline documental necessário antes de aprovar qualquer etapa de modelagem.
