# LIV-C08_DESIGN_PACKAGE

Status: PROPOSTO
Template version: 1
Artifact ID: `LIV-C08-DP-v1`
Plan version: `1.2`
Stage: `LIV-C08`
Date: `2026-08-04`
Derived from:

- [LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md)
- Stage `LIV-C08`

## 1. Objetivo

Definir o contrato minimo de integracao ERP para a vertical Livestock sem transferir ao ERP qualquer autoridade sobre `Evidence`, `Fact`, `Evaluation`, `Decision` ou sobre o historico sanitario vitalicio.

## 2. Escopo

Este artefato cobre:

- a fronteira conceitual entre evento sanitario do Titan e efeito administrativo externo no ERP;
- o reaproveitamento da infraestrutura existente de `Transactional Outbox`, publicacao, idempotencia e reconciliacao;
- o contrato tecnico minimo de mensagem, acknowledgement e estado operacional;
- limites explicitos para evitar que o ERP seja tratado como fonte de verdade sanitaria.

Este artefato nao cobre:

- integracao real com Odoo;
- escolha final de broker, executor, topologia ou deployment;
- inbound ERP -> Titan com autoridade de dominio;
- novas regras sanitarias, novas policies ou novas decisions;
- implementacao de fila, retry distribuido ou observabilidade completa alem do contrato minimo.

## 3. Entradas

- [AGENTS.md](/C:/programing/Titan/AGENTS.md)
- [VISION.md](/C:/programing/Titan/VISION.md)
- [DOMAIN.md](/C:/programing/Titan/DOMAIN.md)
- [ARCHITECTURE.md](/C:/programing/Titan/ARCHITECTURE.md)
- [DEVELOPMENT.md](/C:/programing/Titan/DEVELOPMENT.md)
- [docs/CHECKLIST_DE_IMPLEMENTACAO.md](/C:/programing/Titan/docs/CHECKLIST_DE_IMPLEMENTACAO.md)
- [docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md)
- [docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md)
- [docs/adr/0006-entrega-assincrona-com-outbox-e-message-broker.md](/C:/programing/Titan/docs/adr/0006-entrega-assincrona-com-outbox-e-message-broker.md)
- [packages/core_application/outbox.py](/C:/programing/Titan/packages/core_application/outbox.py)
- [packages/core_infrastructure/persistence/outbox.py](/C:/programing/Titan/packages/core_infrastructure/persistence/outbox.py)
- [packages/core_infrastructure/persistence/migrations/versions/20260722_0014_create_outbox_publication_state.py](/C:/programing/Titan/packages/core_infrastructure/persistence/migrations/versions/20260722_0014_create_outbox_publication_state.py)
- [apps/worker/main.py](/C:/programing/Titan/apps/worker/main.py)
- [apps/worker/config.py](/C:/programing/Titan/apps/worker/config.py)
- [tests/infrastructure/test_outbox_persistence_contract.py](/C:/programing/Titan/tests/infrastructure/test_outbox_persistence_contract.py)
- [tests/infrastructure/test_rabbitmq_publisher.py](/C:/programing/Titan/tests/infrastructure/test_rabbitmq_publisher.py)
- [tests/application/test_outbox_reconciliation.py](/C:/programing/Titan/tests/application/test_outbox_reconciliation.py)

## 4. Documentos de autoridade

- [VISION.md](/C:/programing/Titan/VISION.md)
- [DOMAIN.md](/C:/programing/Titan/DOMAIN.md)
- [ARCHITECTURE.md](/C:/programing/Titan/ARCHITECTURE.md)
- [DEVELOPMENT.md](/C:/programing/Titan/DEVELOPMENT.md)
- [docs/adr/0006-entrega-assincrona-com-outbox-e-message-broker.md](/C:/programing/Titan/docs/adr/0006-entrega-assincrona-com-outbox-e-message-broker.md)
- [docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md)

## 5. Documentos auxiliares

- [docs/CHECKLIST_DE_IMPLEMENTACAO.md](/C:/programing/Titan/docs/CHECKLIST_DE_IMPLEMENTACAO.md)
- [docs/MANUAL_DO_USUARIO_E_INTEGRADOR.md](/C:/programing/Titan/docs/MANUAL_DO_USUARIO_E_INTEGRADOR.md)
- [docs/integration/01_MENSAGERIA_E_EVENTOS.md](/C:/programing/Titan/docs/integration/01_MENSAGERIA_E_EVENTOS.md)
- [docs/CORTE_MVP_BACKEND.md](/C:/programing/Titan/docs/CORTE_MVP_BACKEND.md)

## 6. Analise

### 6.1 Questao arquitetural

What is the minimum ERP contract that preserves Titan as the sole authority over sanitary facts?

### 6.2 Estado comprovado do repositorio

O repositorio ja possui a infraestrutura minima necessaria para uma fronteira outbound sem criar um novo modelo de integracao:

- `OutboxMessage` ja e contrato tecnico versionado com `message_id`, `kind`, `contract_type`, `contract_version`, `actor_reference`, `producer_reference`, `correlation_id`, `causation_id`, `idempotency_key`, `payload` e `classification` em [packages/core_application/outbox.py](/C:/programing/Titan/packages/core_application/outbox.py).
- `OutboxPublisherService` ja separa `ACEITA_PELO_BROKER`, `RESULTADO_DESCONHECIDO` e `REJEITADA_PELO_BROKER`, sem confundir aceite tecnico com processamento concluido, em [packages/core_application/outbox.py](/C:/programing/Titan/packages/core_application/outbox.py).
- O estado operacional de publicacao e separado da `OutboxMessage` original em `core_audit.outbox_publication_state` e `core_audit.outbox_publication_attempts`, com RLS por `record_owner_organization_id`, em [packages/core_infrastructure/persistence/outbox.py](/C:/programing/Titan/packages/core_infrastructure/persistence/outbox.py) e na migration [20260722_0014_create_outbox_publication_state.py](/C:/programing/Titan/packages/core_infrastructure/persistence/migrations/versions/20260722_0014_create_outbox_publication_state.py).
- A reconciliacao operacional ja existe e libera claims expirados sem alterar a `OutboxMessage` original, em [packages/core_application/outbox.py](/C:/programing/Titan/packages/core_application/outbox.py), [packages/core_infrastructure/persistence/outbox.py](/C:/programing/Titan/packages/core_infrastructure/persistence/outbox.py) e [apps/worker/main.py](/C:/programing/Titan/apps/worker/main.py).
- O adaptador RabbitMQ ja preserva publicacao confirmada, erro roteavel e resultado desconhecido, em [tests/infrastructure/test_rabbitmq_publisher.py](/C:/programing/Titan/tests/infrastructure/test_rabbitmq_publisher.py).

### 6.3 Distincoes obrigatorias

- Fato sanitario: continua pertencendo ao Titan e ao seu dominio/aplicacao aprovados.
- Evento de integracao ERP: e derivado de um fato ou decisao ja produzidos no Titan; nao os substitui.
- Acknowledgement tecnico: prova apenas recepcao/publicacao/processamento tecnico conforme o contrato; nao prova aplicacao sanitaria, elegibilidade, conformidade ou decisao.
- Estado operacional de entrega: pertence a `Outbox`/publisher/reconciliacao; nao pertence ao dominio sanitario.
- Operacao administrativa no ERP: pode refletir um desdobramento administrativo externo, mas nao cria automaticamente `Evidence`, `Fact`, `Evaluation` ou `Decision` no Titan.

### 6.4 Alternativas avaliadas

#### Alternativa A - Chamada sincrona ERP no fluxo principal

Descricao:

- o caso de uso sanitario chamaria o ERP diretamente antes de concluir a operacao.

Aderencia:

- baixa aderencia a ADR-0006 e ao plano.

Impacto:

- acopla disponibilidade externa ao fluxo autoritativo do Titan;
- mistura efeito sanitario com efeito administrativo;
- dificulta retry, resultado desconhecido e reconciliacao;
- torna mais provavel tratar erro do ERP como erro do fato sanitario.

Conclusao:

- rejeitada.

#### Alternativa B - Reutilizar exclusivamente a infraestrutura existente de Outbox para publicar contrato outbound de integracao

Descricao:

- o Titan continua produzindo o fato, evaluation, decision e dossier internamente;
- um `IntegrationEvent` ou `Command` versionado e publicado pela Outbox dispara o efeito administrativo externo;
- publicacao, retry e reconciliacao usam a infraestrutura ja aceita.

Aderencia:

- alta aderencia a ADR-0006, ao plano `LIV-C08` e ao principio de reutilizacao antes de criacao.

Impacto:

- menor superficie nova;
- preserva isolamento por Organization;
- preserva ack tecnico separado de efeito de negocio;
- mantem historico e reprodutibilidade do Titan independentes do ERP.

Conclusao:

- recomendada como opcao minima.

#### Alternativa C - Criar agregado ou modulo ERP especializado como fonte central da integracao

Descricao:

- introduzir um novo agregado persistente ou um dominio proprio de "ERP Integration" antes de provar insuficiencia da Outbox.

Aderencia:

- nao demonstrada.

Impacto:

- amplia superficie de dominio sem prova;
- arrisca duplicar estado operacional ja existente;
- cria pressao para modelar autoridade externa cedo demais.

Conclusao:

- rejeitada neste estagio.

### 6.5 Regra de decisao aplicada

A solucao preferida e a que:

- introduz a menor superficie de dominio;
- preserva as semanticas ja aceitas de `OutboxMessage`, `ack` tecnico e reconciliacao;
- nao cria fonte de verdade concorrente ao Titan;
- mantem compatibilidade com integracoes futuras, incluindo ERP, SISBOV e certificadoras;
- permite evolucao de contrato sem hardcode de um produto especifico.

### 6.6 Contrato minimo recomendado

O contrato minimo deve ser outbound e tecnico:

- origem: evento sanitario ou decisao ja consolidada no Titan;
- forma: `OutboxMessage` classificada como `INTEGRATION_EVENT` ou `COMMAND`, conforme a intencao do consumidor;
- identificacao: `message_id`, `contract_type`, `contract_version`, `correlation_id`, `causation_id`, `idempotency_key`;
- isolamento: `organization_id` preservada de ponta a ponta;
- payload: apenas referencia ou snapshot minimo autorizado do fato/decisao que motiva o efeito administrativo externo;
- retorno tecnico esperado: `ACEITA_PELO_BROKER`, `RESULTADO_DESCONHECIDO` ou `REJEITADA_PELO_BROKER`;
- recepcao do ERP: se existir, deve ser tratada como acknowledgement tecnico ou status operacional externo, nunca como prova sanitaria.

### 6.7 Invariantes confirmados para implementacao

- baixa de estoque no ERP nao prova aplicacao;
- conclusao de tarefa no ERP nao prova manejo;
- Titan e ERP permanecem desacoplados em nivel de tabela, ORM e banco;
- confirmacao tecnica do ERP nao altera, autoriza nem substitui o fato sanitario original registrado no Titan;
- nenhuma operacao administrativa proveniente do ERP gera automaticamente `Evidence`, `Fact`, `Evaluation` ou `Decision`;
- nenhuma nova entidade, aggregate, tabela ou conceito transversal deve ser criada enquanto `OutboxMessage` e seu estado operacional forem suficientes.

## 7. Decisoes

- A recomendacao minima do `LIV-C08` e reutilizar a infraestrutura existente de `Transactional Outbox`, publisher e reconciliacao para publicar o contrato outbound ERP.
- O contrato deve nascer fora do dominio sanitario central, na fronteira Application/Infrastructure, como desdobramento tecnico de um fato ou decisao ja produzidos pelo Titan.
- O ERP nao recebera autoridade para criar, corrigir, confirmar ou reinterpretar automaticamente semantica sanitaria.
- Qualquer necessidade de inbound autoritativo, novo agregado de integracao, nova tabela de dominio ou mudanca em `DOMAIN.md` exigira `PLAN_CHANGE_REQUEST`.

## 8. Riscos

- confundir acknowledgement tecnico com confirmacao de negocio do ERP;
- expandir o payload alem do minimo necessario e vazar conteudo protegido;
- introduzir acoplamento a Odoo ou a um broker especifico no contrato publico;
- criar retry/reconciliacao paralelos fora da infraestrutura de Outbox;
- aceitar retorno ERP como prova sanitaria por conveniencia operacional.

## 9. Criterio de encerramento

O estagio `LIV-C08` e considerado concluido quando:

- [ ] a fronteira outbound ERP estiver explicitamente definida como derivada do Titan, nao autoritativa;
- [ ] o contrato usar a infraestrutura existente de `OutboxMessage`, publicacao e reconciliacao, salvo prova contraria documentada;
- [ ] acknowledgement tecnico e efeito sanitario estiverem separados no desenho e nos testes;
- [ ] nenhuma autoridade sanitaria do ERP estiver implicita em contrato, estado ou retorno tecnico;
- [ ] nenhuma pendencia restante deste estagio exigir nova decisao humana antes da implementacao.

## 10. Dependencias liberadas

Este artefato satisfaz o pre-requisito documental para a implementacao minima de `LIV-C08`.

Observacao:

- satisfazer pre-requisito nao autoriza execucao de etapa posterior;
- a implementacao ainda deve permanecer restrita a `LIV-C08`.

## 11. Nao conformidades

- Nenhuma nao conformidade documental nova foi encontrada neste estagio.
- Permanece a necessidade de evitar leitura equivocada de autorizacoes amplas antigas; por isso a autorizacao humana especifica de `LIV-C08` foi registrada em nova entrada append-only do status.

## 12. Limites

Este artefato nao:

- implementa integracao real com ERP;
- escolhe Odoo, RabbitMQ, topologia ou executor definitivos;
- autoriza automaticamente qualquer etapa posterior;
- cria autoridade inbound do ERP;
- altera `DOMAIN.md`, `ARCHITECTURE.md`, ADRs ou contratos centrais ja aceitos.

## 13. Proxima etapa

A proxima etapa potencial e a implementacao minima de `LIV-C08`, restrita a:

- produzir o contrato outbound versionado na fronteira Application/Infrastructure;
- registrar estado operacional usando a Outbox existente;
- adicionar testes focados em contrato, idempotencia, isolamento e nao autoridade do ERP.

Essa proxima etapa depende de execucao explicita e nao autoriza qualquer estagio posterior automaticamente.
