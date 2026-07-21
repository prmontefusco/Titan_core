# ADR 0016 — Decisões explicáveis, revisão humana e contestação
**Status:** Aceita  
**Data:** 21 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan transforma snapshots de informações, Evidences, Policies e RuleResults em conclusões auditáveis. Nem toda Evaluation permite uma Decision imediata: podem existir dados insuficientes, Evidence conflitante, validação pendente, autoridade humana obrigatória ou restrições operacionais.

Uma intervenção humana não pode alterar RuleResults, ocultar resultado anterior ou se apresentar como execução automática. Contestação, revisão, override, correção e reavaliação possuem semânticas diferentes.

## Problema

Definir:

- como explicar resultado técnico e Decision autorizada;
- quando o motor produz proposta em vez de Decision;
- como solicitar, avaliar e concluir revisão ou contestação;
- como registrar override sem reescrever fatos ou decisão original;
- como propagar impacto sem invalidar Dossier, Publication ou iniciar Recall automaticamente.

## Princípios

1. **Resultado não é decisão:** Evaluation descreve aplicação técnica; Decision é conclusão emitida por autoridade ou mecanismo autorizado.
2. **Explicação estruturada:** código, regra, Evidence, valor e limitação sustentam a mensagem humana.
3. **Histórico preservado:** revisão, override e reavaliação criam objetos novos e correlacionados.
4. **Autoridade delimitada:** papel, finalidade, escopo, validade e segregação são verificados pelo servidor.
5. **Incerteza explícita:** ausência, conflito ou pendência não são convertidos em aprovação ou rejeição.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Resultado booleano | Simplicidade | Oculta insuficiência, conflito, restrição e razão |
| Editar Decision após recurso | Visão corrente simples | Destrói história e prova da decisão original |
| Campo livre de justificativa | Flexibilidade | Não é testável, comparável ou reproduzível |
| Humano alterar RuleResult | Conveniência | Confunde execução da regra com autoridade decisória |
| Review e override versionados | Auditabilidade e clareza | Mais estados, autorizações e correlações |

## Decisão

Separar EvaluationOutcome, DecisionProposal, Decision, DecisionReview, DecisionChallenge, DecisionOverride e Reevaluation.

O DecisionEngine produz Evaluation determinística e pode produzir DecisionProposal. Decision oficial somente é emitida quando Policy, autoridade, evidências e aprovações exigidas estiverem satisfeitas.

Toda conclusão possui razões estruturadas. Intervenção humana cria novo registro e nunca altera Evidence, Fact, RuleResult, Evaluation ou Decision anteriores.

Os novos conceitos são candidatos arquiteturais e dependem de aprovação no `DOMAIN.md`.

## Gramática decisional consolidada

```text
Claim / Evidence
    ↓ ValidationAssessment
EvidenceAdmissibilityAssessment
    ↓ Evaluation
DecisionProposal
    ↓ DecisionAuthorityProfile / aprovação
Decision
    ↓ DecisionReview / DecisionChallenge / DecisionOverride
Reevaluation
    ↓ DecisionRelation
análise de impacto autorizada
```

Cada etapa responde a pergunta própria: o que foi alegado; qual material existe; como foi validado; se é admissível para a finalidade; o que as Rules produziram; o que foi proposto; quem possuía autoridade; qual Decision adquiriu efeito; se houve contestação ou exceção; o que mudou; e quais dependentes estão potencialmente afetados.

Uma etapa não substitui a anterior. A análise de impacto localiza possíveis efeitos e não constitui invalidação automática.

## EvaluationOutcome

Resultado técnico agregado da Evaluation antes da emissão de Decision.

Estados iniciais:

- `CONDICOES_SATISFEITAS`;
- `CONDICOES_NAO_SATISFEITAS`;
- `INFORMACAO_INSUFICIENTE`;
- `EVIDENCIA_CONFLITANTE`;
- `VALIDACAO_EXTERNA_PENDENTE`;
- `REVISAO_HUMANA_NECESSARIA`;
- `INDETERMINADO`.

EvaluationOutcome não autoriza operação, não publica conclusão e não substitui DecisionResult.

## DecisionProposal

Proposta imutável derivada de Evaluation, destinada a emissão automática autorizada ou revisão humana.

Preserva Evaluation, outcome, resultado proposto, DecisionReasons, ações, restrições, autoridade requerida, aprovações requeridas, validade proposta, motor, instante e limitações.

Proposal não é Decision, não altera State e não pode ser apresentada externamente como decisão oficial. Expiração ou rejeição não altera Evaluation.

## DecisionResult

Resultado controlado da Decision emitida:

- `APROVADA`;
- `REJEITADA`;
- `APROVADA_COM_RESTRICOES`;
- `INDETERMINADA`.

Resultados específicos de vertical pertencem a perfis próprios e não ao Core. `REVISAO_NECESSARIA` é estado do processo, não DecisionResult final.

## DecisionReason

Razão estruturada e versionada de EvaluationOutcome, DecisionProposal, Decision ou review.

Preserva código estável em português, Rule e versão, condição, campo afetado, valor observado e unidade quando permitido, condição esperada, EvidenceReferences, ValidationAssessments, severidade contextual, ações, limitações e mensagem humana.

Código é contrato; mensagem pode ser traduzida. Mensagem não amplia o que código, Rule e Evidence sustentam. Redaction pode gerar representação autorizada sem alterar a razão original.

## Decision

Decision referencia Evaluation e, quando aplicável, DecisionProposal aprovada.

Além do contrato existente, preserva DecisionResult, DecisionReasons, autoridade emissora, capacidade, Organization atuante, método de emissão, aprovações, restrições, validade, correlação com Decision anterior e status de publicação.

Método de emissão inicial: `AUTOMATICA_AUTORIZADA`, `HUMANA`, `HUMANA_ASSISTIDA` ou `OVERRIDE_AUTORIZADO`.

`HUMANA_ASSISTIDA` identifica assistência automatizada e não a apresenta como decisão puramente humana. Decision emitida é imutável; nova conclusão recebe novo ID.

## DecisionAuthorityProfile

Perfil versionado que define quem pode emitir, revisar, contestar, aprovar override ou publicar determinada Decision.

Preserva finalidade, DecisionType, Organization, Roles ou grants aplicáveis, Permission, competência declarada, Evidence, nível de autenticação, segregação de funções, limites, validade e aprovações.

Membership, cargo declarado, client claim ou RecordOwnerOrganization não comprovam autoridade isoladamente. O servidor resolve o perfil.

## DecisionReview

Caso imutavelmente identificado que coordena revisão de Evaluation, DecisionProposal ou Decision.

Preserva objeto revisado, motivo, escopo, solicitante, OrganizationContext, autoridade requerida, revisor, estado, prazos, Evidence adicional, conflitos, atividades, conclusão e correlação.

Estados iniciais: `ABERTA`, `EM_TRIAGEM`, `AGUARDANDO_EVIDENCIA`, `EM_ANALISE`, `DECIDIDA`, `ENCERRADA`, `CANCELADA`.

Transições são controladas. Cancelamento não apaga submissões. Concorrência, múltiplas revisões e reabertura seguem Policy explícita.

## DecisionChallenge

Contestação imutável apresentada por Actor ou Organization autorizada contra escopo específico de Evaluation ou Decision.

Preserva fundamento, DecisionReasons contestadas, Evidence, resultado pretendido, representação, prazo, DataClassification e limitações.

Challenge não suspende, revoga ou invalida Decision automaticamente. Efeito provisório exige Policy e decisão autorizada separadas.

## ReviewEvidenceSubmission

Submissão imutável de Evidence ou referência durante review.

Preserva remetente, capacidade, Source, Provenance, instante, finalidade, DataContract, classificação, validação e admissibilidade. Anexo não se torna Evidence aceita automaticamente.

Nova Evidence pode exigir ValidationAssessment e nova Evaluation. Revisor não altera snapshot original.

## ReviewAssessment

Avaliação imutável do material e das questões de uma DecisionReview.

Preserva escopo, DecisionReasons examinadas, Evidence admitida e rejeitada, conflitos, Policy, autoridade, análise, recomendações, divergências, limitações e ReasonCodes.

Resultados iniciais: `MANTER`, `REAVALIAR`, `OVERRIDE_ELEGIVEL`, `EVIDENCIA_ADICIONAL_NECESSARIA`, `INDETERMINADO`.

ReviewAssessment não é nova Decision.

## DecisionOverride

Autorização excepcional e imutável para emitir nova Decision que diverge do resultado técnico ou da Decision anterior dentro de escopo delimitado.

Preserva AuthorityProfile, Actor, justificativa, Evaluation, RuleResults não atendidos, DecisionReasons, Evidence, risco aceito, condições, escopo, validade, aprovações, Decision substituída e nova Decision.

Override não altera RuleResult, não declara que condição foi satisfeita e não corrige dado. É proibido sem autoridade explícita e justificativa estruturada.

Expiração encerra novos efeitos dentro do perfil, mas não reescreve uso histórico. Pode iniciar reavaliação, nunca reversão automática.

## Reevaluation

Solicitação e execução correlacionadas que produzem nova Evaluation com snapshot, Evidence, Policy, Rules e motor explicitamente identificados.

Motivos iniciais: `NOVA_EVIDENCIA`, `CORRECAO`, `CONFLITO_RESOLVIDO`, `VALIDACAO_CONCLUIDA`, `POLITICA_ATUALIZADA`, `REVISAO`, `OVERRIDE_EXPIRADO`, `REAVALIACAO_AUTORIZADA`.

`VALIDACAO_CONCLUIDA` registra somente o evento desencadeador. A conclusão pode ser positiva, negativa, parcial ou indeterminada e não implica Evidence verificada ou admissível.

Reevaluation distingue HistoricalReproduction, HistoricalComplianceAssessment, CounterfactualSimulation e CurrentReevaluation. Somente operação autorizada pode produzir nova Decision.

## Relação entre decisões

DecisionRelation liga decisões sem substituir a original.

Tipos iniciais: `CONFIRMA`, `SUBSTITUI_PARA_NOVOS_EFEITOS`, `RESTRINGE`, `REVOGA_PARA_NOVOS_EFEITOS`, `RESULTA_DE_REVISAO`, `RESULTA_DE_OVERRIDE`, `RESULTA_DE_REAVALIACAO`.

Relação preserva escopo, instante efetivo, autoridade, Evidence e razões. “Substitui” não apaga validade ou efeitos históricos anteriores.

## Efeito provisório

Suspensão, restrição ou manutenção provisória durante review é decisão própria, autorizada e temporal.

Preserva objeto, efeito, fundamento, risco, autoridade, início, expiração, condições e ReasonCodes. Ausência de decisão provisória mantém o comportamento definido pela Policy; não presume suspensão ou continuidade.

## Impacto e downstream

Nova Review, Challenge, Evidence, Override ou Decision pode iniciar análise autorizada por Provenance.

A análise localiza State, NonConformities, Dossiers, Publications, Sharings, integrações, Decisions dependentes e objetos de Recall potencialmente afetados.

`POTENCIALMENTE_AFETADO` não significa inválido, fraude, culpa ou recall obrigatório. Comunicação, republicação, revogação, ação corretiva e Recall exigem decisões próprias.

## Explicação pública e interna

Decision mantém explicação completa classificada. Representações interna, contratual, regulatória e pública aplicam Authorization, FieldScope, DisclosureAudience, DataContract e redaction.

Explicação reduzida informa resultado, códigos, escopo e limitações sem revelar Evidence protegida. Redaction não pode inverter conclusão nem ocultar restrição material.

## Automação e assistência

DecisionEngine registra versão, configuração, Policy, inputs e Digests necessários à reprodução. Resultado equivalente exige entradas e versões equivalentes.

Modelo estatístico ou IA pode apoiar triagem, extração ou recomendação somente conforme Policy, DataContract e Provenance. Sua saída é Claim ou resultado derivado, não autoridade decisória automática.

Revisor humano deve poder examinar informações materiais e registrar conclusão própria. Clique formal sem acesso ao contexto não transforma automação em revisão significativa.

## Offline

Captura de Challenge ou Evidence pode ser permitida offline por perfil. Emissão de Decision oficial, conclusão de review, efeito provisório e override são `ONLINE_REQUIRED` ou `FORBIDDEN_OFFLINE` conforme Policy.

Sincronização revalida identidade, autoridade, prazo, Policy, Decision vigente, concorrência, DataContract e Evidence. Submissão rejeitada permanece auditável.

## Fronteiras arquiteturais

Domain define resultados, razões, autoridade, review, challenge, override, relações e invariantes. Não conhece API, banco, workflow engine ou interface.

Application coordena seleção de Policy, Evaluation, proposta, autorização, review, reavaliação, emissão, impacto e publicação.

Infrastructure persiste registros, entrega notificações e executa adapters. Não decide resultado, autoridade, override ou efeito provisório.

Presentation coleta solicitações e apresenta explicações autorizadas. Cliente não fornece resultado, AuthorityProfile, Permission ou status confiáveis.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Decisões reproduzíveis; revisão auditável; override explícito; contestação sem perda histórica |
| Negativas | Mais estados; autorização fina; concorrência de reviews; necessidade de explicações e notificações |

## Riscos e controles

| Risco | Controle |
|---|---|
| Proposal apresentada como Decision | Tipos e contratos separados |
| Revisor alterar resultado técnico | RuleResults imutáveis e nova Decision |
| Override virar atalho | AuthorityProfile, Evidence, validade e segregação |
| Contestação suspender tudo | Efeito provisório como decisão separada |
| Explicação revelar dados | Representações autorizadas e redaction testada |
| Automação disfarçada de revisão | Método de emissão e acesso material registrados |

## Verificação automatizada

Testes futuros devem cobrir:

- Decision emitida sem Evaluation ou autoridade aplicável;
- Proposal apresentada como decisão oficial;
- DecisionReason sem código, Rule, Evidence ou limitação exigida;
- RuleResult, Evaluation ou Decision histórica alterada;
- review com transição inválida, concorrência ou reabertura não autorizada;
- challenge suspendendo Decision sem efeito provisório;
- override sem competência, justificativa, validade ou aprovação;
- expiração de override reescrevendo história;
- nova Evidence usada sem validação e admissibilidade;
- redaction invertendo conclusão ou ocultando restrição material;
- IA ou cliente escolhendo resultado ou autoridade;
- ação downstream ou Recall iniciado automaticamente.

## Critérios de aceitação

A ADR pode ser aceita quando:

- EvaluationOutcome, DecisionProposal, DecisionResult e estado de review forem distintos;
- DecisionReason for estruturada, versionada, traduzível e autorizável;
- Decision oficial exigir AuthorityProfile e aprovações aplicáveis;
- review, challenge, evidence submission e assessment preservarem histórico;
- override não alterar Facts, Evidences, RuleResults ou Decision anterior;
- reavaliação produzir novos objetos e declarar contexto utilizado;
- relações entre decisões delimitarem efeitos novos e históricos;
- efeitos provisórios dependerem de decisão própria;
- impacto não produzir invalidação, sanção ou Recall automático;
- automação, assistência e decisão humana forem identificadas;
- offline, privacidade, Provenance e DataContract forem preservados;
- API, frontend, schema, migration e workflow permanecerem fora da decisão.

## O que esta ADR não decide

Esta ADR não escolhe:

- tela, formulário, notificação, SLA ou workflow engine;
- schema, tabela, API, fila, worker ou implementação do motor;
- autoridade jurídica concreta, prazo recursal ou procedimento regulatório;
- resultados específicos de vertical, fraude, sanção ou Recall obrigatório.

## Plano de reversão

Antes da implementação, esta proposta pode ser substituída. Depois da adoção, mudança preserva Evaluations, Proposals, Decisions, Reasons, AuthorityProfiles, Reviews, Challenges, submissions, assessments, overrides, relações e efeitos históricos.

Reversão não transforma Proposal em Decision, apaga contestação, remove override ou reescreve resultado anterior.
