# LIV-C06_DESIGN_PACKAGE

Status: DRAFT_FOR_IMPLEMENTATION
Artifact ID: `LIV-C06-DP-v1`
Plan version: 1.2
Stage: `LIV-C06`
Date: 2026-08-04
Derived from:

- [LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md)
- Stage `LIV-C06`

## 1. Objetivo

Definir o menor caminho autorizado para emissão oficial de `Decision` sanitária, preservando a separação entre `Evaluation`, `Decision`, `DecisionProposal`, `DecisionReview`, autoridade e Dossier.

## 2. Escopo

Este artefato cobre:

- a pergunta arquitetural de `LIV-C06`;
- o estado atual comprovado de autoridade, proposta, revisão e emissão;
- a lacuna residual entre o núcleo de governança já implementado e o fluxo oficial de produção;
- a recomendação mínima para implementação da etapa;
- os testes e gates necessários para considerar a etapa concluída.

Este artefato não cobre:

- implementação de código nesta etapa documental;
- mudança de `DOMAIN.md`, `ARCHITECTURE.md` ou ADRs;
- novo agregado, nova entidade central ou nova migration sem prova de necessidade;
- autorização automática de `LIV-C07`.

## 3. Entradas

- [AGENTS.md](/C:/programing/Titan/AGENTS.md)
- [VISION.md](/C:/programing/Titan/VISION.md)
- [DOMAIN.md](/C:/programing/Titan/DOMAIN.md)
- [ARCHITECTURE.md](/C:/programing/Titan/ARCHITECTURE.md)
- [DEVELOPMENT.md](/C:/programing/Titan/DEVELOPMENT.md)
- [docs/CHECKLIST_DE_IMPLEMENTACAO.md](/C:/programing/Titan/docs/CHECKLIST_DE_IMPLEMENTACAO.md)
- [LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md)
- [LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md)
- [LIVESTOCK_LIFETIME_COMPLIANCE_C01_BASELINE.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_C01_BASELINE.md)
- [LIVESTOCK_LIFETIME_COMPLIANCE_C02_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_C02_DESIGN_PACKAGE.md)
- [LIV-C05_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/LIV-C05_DESIGN_PACKAGE.md)
- [packages/core_domain/decision.py](/C:/programing/Titan/packages/core_domain/decision.py)
- [packages/core_domain/evaluation.py](/C:/programing/Titan/packages/core_domain/evaluation.py)
- [packages/core_domain/decision_governance.py](/C:/programing/Titan/packages/core_domain/decision_governance.py)
- [packages/core_application/decision_service.py](/C:/programing/Titan/packages/core_application/decision_service.py)
- [packages/core_application/decision_governance_service.py](/C:/programing/Titan/packages/core_application/decision_governance_service.py)
- [packages/core_application/dossier_service.py](/C:/programing/Titan/packages/core_application/dossier_service.py)
- [packages/core_infrastructure/persistence/decision_governance.py](/C:/programing/Titan/packages/core_infrastructure/persistence/decision_governance.py)
- [apps/api/livestock_queries.py](/C:/programing/Titan/apps/api/livestock_queries.py)
- [tests/application/test_decision_governance_service.py](/C:/programing/Titan/tests/application/test_decision_governance_service.py)
- [tests/integration/test_decision_governance_postgresql.py](/C:/programing/Titan/tests/integration/test_decision_governance_postgresql.py)
- [tests/integration/test_livestock_api_leitura.py](/C:/programing/Titan/tests/integration/test_livestock_api_leitura.py)

## 4. Documentos de autoridade

- [AGENTS.md](/C:/programing/Titan/AGENTS.md)
- [VISION.md](/C:/programing/Titan/VISION.md)
- [DOMAIN.md](/C:/programing/Titan/DOMAIN.md)
- [ARCHITECTURE.md](/C:/programing/Titan/ARCHITECTURE.md)
- [DEVELOPMENT.md](/C:/programing/Titan/DEVELOPMENT.md)
- [docs/CHECKLIST_DE_IMPLEMENTACAO.md](/C:/programing/Titan/docs/CHECKLIST_DE_IMPLEMENTACAO.md)
- ADR-0048
- ADR-0052
- ADR-0053
- ADR-0054

## 5. Documentos auxiliares

- [LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md)
- [LIV-C05_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/LIV-C05_DESIGN_PACKAGE.md)
- [LIVESTOCK_STAGE_PACKAGE_TEMPLATE.md](/C:/programing/Titan/docs/plans/LIVESTOCK_STAGE_PACKAGE_TEMPLATE.md)

## 6. Análise

### 6.1 Architectural Question

What is the minimum authorized path that produces an official `Decision` without collapsing `Evaluation`, authority, review and emission?

### 6.2 Estado atual comprovado

O repositório já possui o núcleo principal da governança:

- `DecisionService.decide()` em [decision_service.py](/C:/programing/Titan/packages/core_application/decision_service.py) emite `Decision` oficial apenas quando:
  - a `Evaluation` é reproduzível;
  - a autoridade pertence à mesma `Organization`;
  - a `purpose` coincide;
  - o `DecisionAuthorityProfile` está ativo e vigente;
  - não há `approvals_required` pendentes;
  - a emissão automática não está bloqueada por `REVISAO_HUMANA_NECESSARIA`, `EVIDENCIA_CONFLITANTE` ou `VALIDACAO_EXTERNA_PENDENTE`.
- `DecisionGovernanceService` em [decision_governance_service.py](/C:/programing/Titan/packages/core_application/decision_governance_service.py) já implementa:
  - `create_proposal()`
  - `record_review()`
  - `emit_after_approval()`
  - `emit_after_approvals()`
  - `apply_override()`
  - `file_contestation()`
- A persistência PostgreSQL já existe em [decision_governance.py](/C:/programing/Titan/packages/core_infrastructure/persistence/decision_governance.py) para:
  - `decision_authority_profiles`
  - `decision_proposals`
  - `decision_reviews`
  - `decision_overrides`
  - `decision_contestations`
- O Dossier já carrega a trilha de governança quando fornecida, em [dossier_service.py](/C:/programing/Titan/packages/core_application/dossier_service.py).

### 6.3 Prova de cobertura de testes existente

Já há cobertura forte do núcleo:

- [test_decision_governance_service.py](/C:/programing/Titan/tests/application/test_decision_governance_service.py) cobre:
  - proposta derivada da `Evaluation`;
  - rejeição de `Evaluation` adulterada;
  - review de outra organização;
  - emissão humana com aprovação;
  - rejeição de `REJEITA` e `DEVOLVE`;
  - hash desatualizado;
  - múltiplas aprovações;
  - proibição de contar o mesmo revisor duas vezes.
- [test_decision_governance_postgresql.py](/C:/programing/Titan/tests/integration/test_decision_governance_postgresql.py) cobre roundtrip de proposal/review/decision/contestation em PostgreSQL.
- [test_livestock_api_leitura.py](/C:/programing/Titan/tests/integration/test_livestock_api_leitura.py) já cobre o portão de revisão humana na API:
  - quando a emissão automática é recusada, a resposta é `409`;
  - a API expõe `proposal_id`, `evaluation_id` e `proposal_result`;
  - a proposta fica persistida.

### 6.4 Lacuna residual comprovada

A lacuna não está mais no domínio central de governança. A lacuna remanescente está no fluxo oficial de produção:

- o caminho automático já sabe abrir `DecisionProposal` quando a emissão automática é recusada;
- porém o repositório ainda não comprova um fluxo oficial ponta a ponta para:
  - consultar proposta;
  - registrar uma ou mais `DecisionReview`;
  - emitir a `Decision` humana final;
  - materializar o Dossier governado dessa emissão;
  - validar esse caminho por API/roteiro executável.

Em outras palavras:

- o núcleo da ADR-0054 já existe;
- o caller oficial de produção para fechar o ciclo ainda é parcial.

### 6.5 Distinções conceituais obrigatórias

- `Evaluation` continua sendo execução técnica preservada, nunca conclusão oficial.
- `DecisionProposal` continua sendo fotografia do que o motor proporia, nunca `Decision`.
- `DecisionReview` continua sendo ato humano de aprovação, rejeição ou devolução, nunca reescrita da `Evaluation`.
- `DecisionAuthorityProfile` continua sendo a base da autoridade resolvida pelo servidor.
- `Decision` humana final continua sendo nova emissão, não mutação da proposta nem da review.
- O Dossier continua sendo apresentação auditável derivada da trilha acima.

### 6.6 Alternativas avaliadas

Alternativa A: considerar `LIV-C06` já concluído porque domínio, persistência e testes de núcleo existem.

- vantagem:
  - menor trabalho imediato.
- desvantagens:
  - conflita com o checklist, que ainda aponta lacuna de caller/fluxo oficial;
  - deixaria sem prova o fechamento ponta a ponta de produção.
- veredito:
  - rejeitada.

Alternativa B: implementar apenas endpoints/fluxos de produção sobre os conceitos já existentes.

- vantagem:
  - respeita reuse before creation;
  - usa domínio, persistência e Dossier já aprovados;
  - atende exatamente a lacuna residual comprovada.
- desvantagens:
  - exige delimitar com cuidado o menor recorte observável da API.
- veredito:
  - recomendada.

Alternativa C: introduzir novo conceito central de governança para “processo de decisão”.

- vantagem:
  - unificaria proposta, reviews e emissão sob um conceito agregador.
- desvantagens:
  - não há prova de insuficiência dos conceitos atuais;
  - amplia superfície de domínio sem necessidade comprovada;
  - exigiria gate arquitetural novo.
- veredito:
  - rejeitada.

### 6.7 Recomendação mínima

A recomendação mínima para `LIV-C06` é:

- não criar novo agregado ou entidade central;
- manter `DecisionProposal`, `DecisionReview`, `DecisionAuthorityProfile` e `Decision` como estão;
- implementar apenas o caller oficial que feche o ciclo:
  - localizar proposta;
  - registrar review humana;
  - emitir `Decision` humana via `emit_after_approval()` ou `emit_after_approvals()`;
  - produzir Dossier com seção `governance`;
  - responder por API sem colapsar os conceitos.

### 6.8 Contrato alvo mínimo

O contrato mínimo desta etapa deve permitir:

- entrada:
  - `proposal_id`
  - identificação do revisor/autoridade resolvida pelo servidor
  - conclusão da revisão
  - fundamentação humana
- processamento:
  - persistir `DecisionReview`
  - validar quantidade mínima de aprovações
  - emitir `Decision` humana quando o gate for satisfeito
  - persistir `Decision`
  - materializar `Dossier`
- saída:
  - `review_id`
  - `decision_id` quando emitida
  - `dossier_id` quando emitido
  - estado explícito quando a proposta ainda não tiver aprovações suficientes

### 6.9 Gate arquitetural

Há um gate adicional comprovado antes da implementação:

- o repositório ainda não possui um mecanismo explícito e aprovado para resolver a autoridade humana de emissão a partir do `OrganizationContext` real;
- `OrganizationContext` hoje entrega `user_id`, `actor_id`, `membership_id`, `role_ids` e `permission_codes`, mas não carrega um contrato de "esta combinação autoriza revisar e emitir decisão humana para esta `purpose`";
- qualquer implementação de endpoint oficial precisaria decidir:
  - qual permissão habilita review/emissão humana;
  - quais papéis recebem essa permissão;
  - como `DecisionAuthorityProfile.role_name`, `principal_reference`, `purpose` e `approvals_required` são resolvidos em produção;
  - se a mesma autoridade pode revisar e emitir no caminho mínimo, ou se a segregação exige perfis distintos.

Isso ultrapassa mero caller faltando e entra em decisão de autorização/autoridade.

Conclusão:

- a implementação não deve prosseguir silenciosamente antes de uma decisão humana explícita sobre a resolução de autoridade humana para `LIV-C06`.

## 7. Decisões

- `LIV-C06` não exige novo agregado para prosseguir.
- A modelagem central de governança é suficiente, mas o fluxo oficial continua bloqueado pela ausência de uma regra aprovada de resolução da autoridade humana em produção.
- O menor caminho conforme continua sendo reutilizar o núcleo existente, mas somente depois de fixar explicitamente a política de autoridade/permissão para review e emissão humana.
- Se a implementação exigir novo conceito central de governança, a execução deve parar e voltar para aprovação arquitetural.

## 7.1 Proposta mínima de resolução de autoridade humana

Proposta mínima para destravar a implementação sem alterar o modelo central:

- introduzir uma permissão explícita e exclusiva para executar o fluxo técnico de revisão/emissão:
  - `DECISION_REVIEW_EXECUTE`
- essa permissão não deve ser inferida de payload do cliente;
- o endpoint oficial de review/emissão deve continuar resolvendo autoridade a partir do `OrganizationContext` validado pelo servidor.

Distinção obrigatória:

- `Permission` autoriza a operação técnica do endpoint;
- `DecisionAuthorityProfile` continua sendo a única base para competência de revisão/emissão oficial;
- a implementação não deve sugerir que a autoridade nasce da permissão.

Resolução mínima proposta para o `DecisionAuthorityProfile` humano:

- `principal_reference`:
  - derivado de `contexto.actor_id`;
- `organization_id`:
  - derivado de `contexto.organization_id`;
- `purpose`:
  - copiada da `DecisionProposal` ou da `Evaluation` correspondente;
- `role_name`:
  - resolvido a partir do perfil compatível com a combinação entre `Organization`, `Purpose`, `Role`, `Permission` e validade;
  - a resolução nunca depende do “primeiro papel” do contexto;
- `emission_method`:
  - `HUMAN`;
- `approvals_required`:
  - `1` no caminho mínimo do MVP;
- `is_active`:
  - `true`;
- `valid_from` e `valid_to`:
  - opcionais, sem inventar regra temporal nova nesta etapa.

Regra mínima proposta de segregação:

- no caminho mínimo do MVP, o mesmo ator pode revisar e emitir;
- essa permissão deve ser explícita e aprovada humanamente;
- endurecimento posterior para dupla aprovação ou segregação forte pode ser feito depois, sem exigir novo conceito central.

Fluxo oficial mínimo proposto:

1. localizar `DecisionProposal`;
2. registrar `DecisionReview`;
3. se a conclusão for `APROVA`, resolver `DecisionAuthorityProfile` humano a partir do `OrganizationContext`;
4. executar `Current Proposal Verification`;
5. resolver a `Evaluation` corrente referenciada pela proposta;
6. resolver a `Policy` corrente exigida pelo fluxo de emissão, sem reescrever a trilha histórica;
7. emitir `Decision` via `emit_after_approval()`;
8. persistir `Decision`;
9. materializar `Dossier` com seção `governance`.

Gate temporal adicional obrigatório:

- `Current Proposal Verification` deve impedir emissão quando a proposta aprovada já não for a proposta corrente para aquela `Evaluation`/`purpose`;
- se existir `Evaluation` ou `DecisionProposal` mais recente e aplicável, a emissão da proposta anterior deve falhar fechado;
- a implementação não pode permitir reutilizar uma approval antiga sobre material superado.

Invariantes adicionais desta proposta:

- o cliente nunca escolhe `DecisionAuthorityProfile`;
- o cliente nunca escolhe autoridade por papel, nome de papel ou combinação declarada no payload;
- `REJEITA` e `DEVOLVE` não emitem `Decision`;
- `DecisionReview` permanece append-only e não reescreve `Evaluation` nem `DecisionProposal`;
- temporalidade precisa ser revalidada antes da emissão humana final;
- nenhuma entidade, agregado, enum central ou migration estrutural é introduzido por esta decisão mínima.

## 8. Riscos

- ampliar o escopo e acabar implementando contestação, override e UI completos de uma vez;
- permitir que o cliente escolha autoridade, em violação direta das ADRs;
- introduzir uma regra silenciosa de autorização humana sem aprovação explícita;
- tratar aprovação humana como edição da proposta, e não como trilha append-only;
- emitir `Decision` humana sem Dossier correspondente;
- considerar a etapa concluída sem roteiro executável de validação da API.

## 9. Critério de encerramento

O estágio `LIV-C06` é considerado pronto para implementação quando:

- [x] a `Architectural Question` estiver respondida;
- [x] a lacuna residual estiver localizada no caller/fluxo oficial, e não no domínio central;
- [x] a recomendação mínima reutilizando os conceitos atuais estiver registrada;
- [x] os gates que evitam colapso entre `Evaluation`, `Proposal`, `Review` e `Decision` estiverem explícitos;
- [x] a pendência específica de autoridade humana em produção estiver explicitamente registrada como bloqueio de implementação.

## 10. Dependências liberadas

Este artefato satisfaz o pré-requisito documental para:

- implementação futura de `LIV-C06`.

Observação:

- isso não autoriza `LIV-C07`;
- autorização humana continua necessária para qualquer etapa posterior.

## 11. Não conformidades

Nenhuma não conformidade documental nova encontrada.

Observações relevantes:

- o checklist continua apontando a ausência de caller/fluxo oficial completo como lacuna de produção, apesar de o núcleo de governança já existir e estar persistido;
- a análise desta execução acrescenta um detalhe material: a lacuna de caller vem acoplada à ausência de regra aprovada para resolver a autoridade humana em produção.

## 12. Limites

Este artefato não:

- implementa `LIV-C06`;
- escolhe silenciosamente a permissão ou o papel que autoriza a emissão humana;
- altera ADRs, `DOMAIN.md` ou `ARCHITECTURE.md`;
- cria migration;
- conclui a etapa sem evidência de API e validação executável;
- autoriza `LIV-C07`.

## 13. Próxima etapa

Próxima ação potencial:

- obter decisão humana explícita sobre:
  - aprovação ou rejeição da permissão `DECISION_REVIEW_EXECUTE`;
  - aprovação ou rejeição da resolução mínima proposta do `DecisionAuthorityProfile` humano a partir do `OrganizationContext`;
  - aprovação ou rejeição do caminho MVP em que o mesmo ator pode revisar e emitir.

Condição:

- somente depois dessa decisão a implementação de `LIV-C06` pode prosseguir;
- se o trabalho exigir novo conceito central, nova migration estrutural ou mudança de autoridade arquitetural adicional, a execução deve parar para nova decisão humana.
