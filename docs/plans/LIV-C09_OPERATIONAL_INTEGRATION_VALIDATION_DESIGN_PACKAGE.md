# LIV-C09_OPERATIONAL_INTEGRATION_VALIDATION_DESIGN_PACKAGE

Status: APROVADA
Template version: 1
Artifact ID: `LIV-C09-DP-v1`
Parent plan version: `1.2`
Extension proposal: `1.0`
Stage: `LIV-C09`
Date: `2026-08-04`
Derived from:

- [LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md)
- Stage `LIV-C08`
- [LIV-C08_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/LIV-C08_DESIGN_PACKAGE.md)

## 1. Objetivo

Definir um pacote de validacao operacional para a integracao outbound ja implementada, comprovando que o fluxo `fato sanitario -> outbox -> publicacao -> consumer/worker -> acknowledgement tecnico -> reconciliacao` se comporta de forma idempotente, auditavel, isolada por `Organization` e sem transferir autoridade sanitaria ao ERP.

## 2. Escopo

Este artefato cobre:

- validacao operacional da fronteira outbound ja existente;
- provas de idempotencia, retry, resultado desconhecido, replay operacional e reconciliacao;
- observabilidade minima e diagnostico do fluxo assincrono;
- limites formais para impedir que o ERP ou o worker sejam tratados como fonte de verdade sanitaria.

Este artefato nao cobre:

- novas regras sanitarias ou de mercado;
- novo contrato inbound ERP -> Titan;
- ampliacao do dominio Livestock;
- escolha de um ERP real, credenciais, deploy externo ou rollout produtivo;
- alteracao de `DOMAIN.md`, `ARCHITECTURE.md` ou ADRs existentes sem nova aprovacao.

## 3. Entradas

- [AGENTS.md](/C:/programing/Titan/AGENTS.md)
- [VISION.md](/C:/programing/Titan/VISION.md)
- [DOMAIN.md](/C:/programing/Titan/DOMAIN.md)
- [ARCHITECTURE.md](/C:/programing/Titan/ARCHITECTURE.md)
- [DEVELOPMENT.md](/C:/programing/Titan/DEVELOPMENT.md)
- [docs/CHECKLIST_DE_IMPLEMENTACAO.md](/C:/programing/Titan/docs/CHECKLIST_DE_IMPLEMENTACAO.md)
- [docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md)
- [docs/plans/LIV-C08_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/LIV-C08_DESIGN_PACKAGE.md)
- [docs/adr/0006-entrega-assincrona-com-outbox-e-message-broker.md](/C:/programing/Titan/docs/adr/0006-entrega-assincrona-com-outbox-e-message-broker.md)
- [docs/adr/0038-executor-de-workers-e-consumo-da-inbox.md](/C:/programing/Titan/docs/adr/0038-executor-de-workers-e-consumo-da-inbox.md)
- [docs/adr/0029-rabbitmq-como-message-broker-inicial.md](/C:/programing/Titan/docs/adr/0029-rabbitmq-como-message-broker-inicial.md)
- [packages/livestock_application/erp_outbox.py](/C:/programing/Titan/packages/livestock_application/erp_outbox.py)
- [packages/livestock_application/treatment_service.py](/C:/programing/Titan/packages/livestock_application/treatment_service.py)
- [packages/core_application/outbox.py](/C:/programing/Titan/packages/core_application/outbox.py)
- [packages/core_application/inbox.py](/C:/programing/Titan/packages/core_application/inbox.py)
- [packages/core_infrastructure/persistence/outbox.py](/C:/programing/Titan/packages/core_infrastructure/persistence/outbox.py)
- [packages/core_infrastructure/persistence/inbox.py](/C:/programing/Titan/packages/core_infrastructure/persistence/inbox.py)
- [packages/core_infrastructure/rabbitmq.py](/C:/programing/Titan/packages/core_infrastructure/rabbitmq.py)
- [packages/core_infrastructure/rabbitmq_consumer.py](/C:/programing/Titan/packages/core_infrastructure/rabbitmq_consumer.py)
- [apps/worker/main.py](/C:/programing/Titan/apps/worker/main.py)
- [apps/worker/config.py](/C:/programing/Titan/apps/worker/config.py)
- [tests/integration/test_outbox_postgresql.py](/C:/programing/Titan/tests/integration/test_outbox_postgresql.py)
- [tests/integration/test_outbox_reconciliation_postgresql.py](/C:/programing/Titan/tests/integration/test_outbox_reconciliation_postgresql.py)
- [tests/integration/test_inbox_postgresql.py](/C:/programing/Titan/tests/integration/test_inbox_postgresql.py)
- [tests/integration/test_inbox_postgresql_flow.py](/C:/programing/Titan/tests/integration/test_inbox_postgresql_flow.py)
- [tests/integration/test_inbox_quarantine_postgresql.py](/C:/programing/Titan/tests/integration/test_inbox_quarantine_postgresql.py)
- [tests/integration/test_worker_e2e.py](/C:/programing/Titan/tests/integration/test_worker_e2e.py)

## 4. Documentos de autoridade

- [VISION.md](/C:/programing/Titan/VISION.md)
- [DOMAIN.md](/C:/programing/Titan/DOMAIN.md)
- [ARCHITECTURE.md](/C:/programing/Titan/ARCHITECTURE.md)
- [DEVELOPMENT.md](/C:/programing/Titan/DEVELOPMENT.md)
- [docs/adr/0006-entrega-assincrona-com-outbox-e-message-broker.md](/C:/programing/Titan/docs/adr/0006-entrega-assincrona-com-outbox-e-message-broker.md)
- [docs/adr/0038-executor-de-workers-e-consumo-da-inbox.md](/C:/programing/Titan/docs/adr/0038-executor-de-workers-e-consumo-da-inbox.md)
- [docs/adr/0029-rabbitmq-como-message-broker-inicial.md](/C:/programing/Titan/docs/adr/0029-rabbitmq-como-message-broker-inicial.md)

## 5. Documentos auxiliares

- [docs/CHECKLIST_DE_IMPLEMENTACAO.md](/C:/programing/Titan/docs/CHECKLIST_DE_IMPLEMENTACAO.md)
- [docs/MANUAL_DO_USUARIO_E_INTEGRADOR.md](/C:/programing/Titan/docs/MANUAL_DO_USUARIO_E_INTEGRADOR.md)
- [docs/integration/01_MENSAGERIA_E_EVENTOS.md](/C:/programing/Titan/docs/integration/01_MENSAGERIA_E_EVENTOS.md)
- [docs/REQUISITOS_DE_PRODUCAO.md](/C:/programing/Titan/docs/REQUISITOS_DE_PRODUCAO.md)

## 6. Analise

### 6.1 Questao arquitetural

How can Titan validate the operational behavior of the outbound ERP boundary without turning operational transport states into sanitary domain authority?

### 6.2 Estado atual comprovado

O repositorio ja possui quase toda a infraestrutura tecnica necessaria para a validacao operacional:

- `OutboxMessage`, `OutboxPublisherService` e `OutboxReconciliationService` ja existem no Core em [packages/core_application/outbox.py](/C:/programing/Titan/packages/core_application/outbox.py).
- `TransactionalOutboxMessageWriter`, `TransactionalEventOutboxRepository`, `OutboxPublicationStateRepository` e reconciliacao persistida ja existem em [packages/core_infrastructure/persistence/outbox.py](/C:/programing/Titan/packages/core_infrastructure/persistence/outbox.py).
- O consumer transacional, a deduplicacao de `Inbox`, a quarentena e o replay operacional ja existem em [packages/core_application/inbox.py](/C:/programing/Titan/packages/core_application/inbox.py) e [packages/core_infrastructure/persistence/inbox.py](/C:/programing/Titan/packages/core_infrastructure/persistence/inbox.py).
- O worker executavel e a configuracao centralizada ja existem em [apps/worker/main.py](/C:/programing/Titan/apps/worker/main.py) e [apps/worker/config.py](/C:/programing/Titan/apps/worker/config.py).
- O contrato outbound minimo do `LIV-C08` ja nasce do tratamento em [packages/livestock_application/erp_outbox.py](/C:/programing/Titan/packages/livestock_application/erp_outbox.py) e [packages/livestock_application/treatment_service.py](/C:/programing/Titan/packages/livestock_application/treatment_service.py).

### 6.3 Lacuna remanescente

A lacuna principal nao e mais de modelagem de dominio. A lacuna e de prova operacional integrada:

- ainda falta consolidar uma evidencia unica de que o contrato outbound Livestock percorre todo o ciclo assincrono previsto pelas ADRs;
- ainda falta provar de forma executavel que `RESULTADO_DESCONHECIDO`, retry, deduplicacao, quarentena e reconciliacao nao degradam a autoridade sanitaria do Titan;
- ainda falta transformar a fronteira implementada em um roteiro operacional auditavel para evolucao futura de ERP real.

### 6.4 Principios obrigatorios desta etapa

- reutilizacao antes de criacao;
- derivacao antes de persistencia adicional;
- estado operacional nao e estado de dominio sanitario;
- `ack` tecnico nao e prova de aplicacao;
- `worker` nao substitui `Actor` original;
- nenhuma falha operacional pode promover conformidade silenciosa;
- o recebimento pela `Inbox` comprova apenas que o consumidor Titan ou adaptador local aceitou o envelope de forma idempotente; nao comprova, isoladamente, que o ERP executou ou confirmou a operacao;
- todo acknowledgement deve declarar emissor, escopo e significado; nenhum ack pode ser interpretado alem da fase que efetivamente comprova;
- qualquer ampliacao para inbound autoritativo exige nova governanca arquitetural.

### 6.5 Alternativas avaliadas

#### Alternativa A - Considerar o `LIV-C08` suficiente sem etapa operacional dedicada

Impacto:

- reduz trabalho imediato;
- deixa a fronteira sem prova integrada completa;
- aumenta o risco de acoplamento acidental quando a integracao real com ERP comecar.

Conclusao:

- rejeitada.

#### Alternativa B - Criar etapa documental e tecnica separada de validacao operacional

Impacto:

- preserva a separacao entre modelagem de dominio e endurecimento operacional;
- permite provar `retry`, `unknown`, `quarantine`, `replay` e `reconciliation` com foco proprio;
- reduz o risco de que o ERP ganhe autoridade por interpretacao operacional equivocada.

Conclusao:

- recomendada.

### 6.6 Escopo tecnico minimo recomendado

O `LIV-C09` deve validar no minimo:

- emissao do comando outbound do tratamento;
- claim/publicacao/aceite/resultado desconhecido na outbox;
- consumo idempotente por `Inbox`;
- repeticao segura da mesma mensagem;
- isolamento entre duas `Organizations`;
- quarentena e replay autorizados quando o envelope ou o handler falharem;
- reconciliacao de claims expirados e mensagens pendentes;
- roteiro executavel de validacao manual sem copiar identificadores a mao.

### 6.7 Semantica minima de acknowledgements

O `LIV-C09` deve separar conceitualmente, mesmo sem criar novos enums nesta etapa:

- `MESSAGE_ACCEPTED_BY_BROKER`: comprova apenas aceite do broker;
- `MESSAGE_ACCEPTED_BY_CONSUMER`: comprova apenas que o consumer/adaptador aceitou o envelope de forma idempotente;
- `DELIVERY_ATTEMPTED`: comprova tentativa tecnica de entrega externa;
- `DELIVERY_CONFIRMED`: comprova apenas a confirmacao tecnica prevista no contrato externo;
- `DELIVERY_REJECTED`: comprova rejeicao tecnica ou contratual definitiva;
- `DELIVERY_OUTCOME_UNKNOWN`: comprova incerteza operacional reconciliavel, nunca sucesso implicito.

Mesmo `DELIVERY_CONFIRMED` nao tem autoridade para alterar o fato sanitario original registrado no Titan.

### 6.8 Idempotencia em duas fronteiras

Esta etapa deve provar duas idempotencias distintas:

- idempotencia interna: a mesma mensagem nao pode ser processada duas vezes pelo consumer/adaptador local;
- idempotencia externa: a mesma solicitacao nao pode produzir dois efeitos administrativos no ERP ou no conector externo.

Regra minima:

- retry apos `DELIVERY_OUTCOME_UNKNOWN` reutiliza a mesma identidade idempotente;
- nova intencao operacional legitima recebe nova identidade;
- timeout apos efeito externo, mas antes do ack, deve permanecer reconciliavel sem duplicar efeito.

### 6.9 Isolamento operacional por Organization

O `LIV-C09` deve provar mais do que ausencia de vazamento de leitura:

- mensagem da Organization A nao pode ser claimed por worker restrito a B;
- ack ou replay de B nao pode concluir mensagem de A;
- a mesma `idempotency_key` em Organizations diferentes nao pode colidir;
- metricas, consultas e operacoes de quarentena/replay nao podem revelar identificadores de outro tenant;
- a identidade operacional efetiva deve ser tratada, conceitualmente, como `organization_id + message_id`, ainda que `message_id` seja globalmente unico.

### 6.10 Quarentena, replay e imutabilidade

Replay, liberacao de quarentena e reconciliacao manual sao atos operacionais auditaveis:

- exigem permissao especifica;
- nao alteram o `TreatmentApplication` original;
- nao editam silenciosamente o payload historico;
- registram solicitante, motivo, mensagem, tentativa, instante, resultado e correlacao com o incidente.

Se uma correcao do conteudo for necessaria, ela deve produzir nova mensagem ou novo fluxo explicito, nunca sobrescrever o envelope historico.

### 6.11 Caminho formal para `DELIVERY_OUTCOME_UNKNOWN`

O `LIV-C09` deve demonstrar um caminho explicito de saida para resultado desconhecido, reutilizando os conceitos do Core quando possivel:

| Estado observado | Proxima acao permitida |
|---|---|
| publicacao nao iniciada | retry |
| broker confirmou | aguardar consumer/adaptador |
| consumer processou envelope | aguardar resultado externo conforme contrato |
| resultado externo desconhecido | reconciliar antes de retry destrutivo |
| rejeicao permanente | quarentena |
| duplicata | recuperar resultado anterior |
| claim expirado | liberar e reprocessar |

### 6.12 Observabilidade minima esperada

Esta etapa deve produzir ou consolidar evidencias para:

- quantidade de mensagens pendentes da outbox;
- quantidade de claims expirados liberados;
- quantidade de mensagens em `RESULTADO_DESCONHECIDO`;
- quantidade de duplicatas recuperadas pela inbox;
- quantidade de mensagens em quarentena;
- correlacao entre `message_id`, `correlation_id`, `causation_id` e a aplicacao de tratamento original.

Regra adicional:

- metricas agregadas sem payload;
- logs e traces sem medicamento, animal, dose ou dados pessoais;
- uso de `message_id`, `correlation_id` e codigos sanitizados;
- nenhuma falha operacional deve duplicar o dominio sanitario em logs.

## 7. Decisoes

- A proxima frente recomendada apos `LIV-C08` e um `LIV-C09` separado, focado exclusivamente em validacao operacional da integracao.
- Essa etapa deve permanecer fora do plano `LIV-C01` a `LIV-C08`, porque seu objetivo nao e ampliar semantica sanitaria, e sim provar comportamento operacional.
- A etapa deve preferir testes e roteiros executaveis sobre nova modelagem.
- Qualquer necessidade de novo agregado, nova tabela de dominio, nova autoridade inbound ou reinterpretacao de fatos sanitarios deve interromper a execucao e gerar `PLAN_CHANGE_REQUEST`.

## 8. Riscos

- confundir sucesso de publicacao com sucesso de negocio;
- validar apenas o caminho feliz e deixar `RESULTADO_DESCONHECIDO` sem prova;
- deixar o replay operacional crescer para replay de dominio sem governanca;
- acoplar observabilidade ou configuracao do worker a detalhes de um ERP especifico;
- executar integracao real cedo demais e mascarar fragilidades locais.

## 9. Criterio de encerramento

O estagio `LIV-C09` e considerado concluido quando:

- [ ] existir prova executavel do fluxo `treatment -> outbox -> publication -> inbox -> worker outcome`;
- [ ] os cenarios de duplicata, quarentena, replay e reconciliacao estiverem cobertos por testes ou roteiro executavel equivalente;
- [ ] a separacao entre `ack` tecnico e autoridade sanitaria permanecer explicita em codigo, testes e documentacao;
- [ ] a validacao manual nao depender de copia manual de identificadores;
- [ ] o significado de cada ack estiver declarado e testado;
- [ ] aceite pela `Inbox` nao estiver apresentado como confirmacao do ERP;
- [ ] idempotencia interna e externa estiverem testadas separadamente;
- [ ] timeout apos efeito externo nao produzir operacao duplicada;
- [ ] `RESULTADO_DESCONHECIDO` possuir caminho explicito de reconciliacao;
- [ ] replay e quarentena exigirem autoridade operacional e deixarem auditoria;
- [ ] mensagens e estados operacionais permanecerem isolados por `Organization`;
- [ ] logs, metricas e traces nao capturarem payload sanitario sensivel;
- [ ] falha definitiva de integracao nao alterar nem remover o `TreatmentApplication` original;
- [ ] nenhuma pendencia remanescente deste estagio exigir nova decisao humana para o comportamento minimo.

## 10. Dependencias liberadas

Este artefato prepara a proxima etapa de endurecimento operacional da integracao outbound.

Observacao:

- satisfazer este pre-requisito nao autoriza implementacao automatica;
- qualquer execucao futura ainda depende de aprovacao humana explicita.

## 11. Nao conformidades

- Nenhuma nao conformidade documental nova foi encontrada.
- Permanece a ausencia de uma etapa formal no plano original para validacao operacional pos-contrato; este artefato existe justamente para cobrir essa lacuna sem reescrever o plano anterior.

## 12. Limites

Este artefato nao:

- implementa o `LIV-C09`;
- escolhe um ERP real;
- muda a autoridade do Titan;
- autoriza automaticamente um novo ciclo de implementacao;
- altera ADRs, `DOMAIN.md` ou `ARCHITECTURE.md`.

## 13. Proxima etapa

A proxima etapa potencial e criar uma autorizacao explicita para `LIV-C09` e, somente depois, implementar:

- testes integrados focados no contrato outbound Livestock;
- roteiro executavel em `apps/validacao`;
- endurecimento observavel do worker/outbox/inbox para o fluxo ERP.

Cenarios E2E obrigatorios para essa proxima etapa:

- publicacao e consumo normais;
- mesma mensagem publicada duas vezes;
- worker cai antes de registrar conclusao;
- ERP executa, mas a resposta se perde;
- retry apos resultado desconhecido;
- ERP rejeita definitivamente o contrato;
- envelope invalido vai para quarentena;
- replay autorizado resolve a mensagem;
- replay nao autorizado e recusado;
- claim expira e e liberado pela reconciliacao;
- Organization B tenta consultar ou operar mensagem da A;
- mensagem duplicada retorna resultado anterior sem repetir o efeito;
- falha prolongada do ERP nao afeta a persistencia sanitaria do Titan;
- metricas e logs nao contem payload;
- reinicio do worker preserva estado e continuidade.

Essa proxima etapa depende de aprovacao humana posterior e nao pode ser liberada automaticamente.
