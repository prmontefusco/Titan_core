# ADR 0038 — Executor de workers e consumo de mensagens da Inbox

**Status:** Aceita  
**Data:** 22 de julho de 2026  
**Decisores:** fundador e responsável pela arquitetura do Titan

## Contexto

A ADR-0006 estabelece o modelo de comunicação assíncrona do Titan utilizando Transactional Outbox no PostgreSQL, entrega *pelo menos uma vez*, confirmação de publicação, consumo com acknowledgement posterior ao commit e idempotência obrigatória. A ADR-0029 formalizou o RabbitMQ 4.3.3 como Message Broker inicial para transporte local, mantendo o broker como transporte substituível e não autoritativo.

O Passo 4.8B entregou o publisher da Outbox broker-neutral e o adapter RabbitMQ em Infrastructure. O Passo 4.8C precisa definir a arquitetura do executor de workers (`apps/worker`), a estrutura do padrão Inbox no PostgreSQL, o isolamento por Organization, a máquina de estados de consumo, o tratamento de falhas e quarentena, e a concorrência entre consumidores.

## Requisitos e Princípios

1. **Opção A — Transação Única sem Lease Persistida:** O processamento pelo worker ocorre sob uma **única transação PostgreSQL atômica**. O estado `EM_PROCESSAMENTO` existe exclusivamente dentro da transação ativa; se o worker morrer ou a transação for abortada durante a execução, o PostgreSQL reverte toda a transação (`ROLLBACK`). Não existe recuperação, *takeover* ou expiração durável de lease; a concorrência é coordenada por locks e constraints da própria transação PostgreSQL.
2. **PostgreSQL como fonte autoritativa de resultados:** o PostgreSQL é a fonte autoritativa dos resultados de consumo, tentativas que alcançaram uma transição durável (`CONCLUIDA`, `AGUARDANDO_RETRY`, `EM_QUARENTENA`, `RECONCILIACAO_PENDENTE`), conflitos e quarentenas. Tentativas abruptamente interrompidas antes do commit revertem no banco e existem apenas na telemetria operacional e métricas do broker, sendo inferidas por redelivery posterior.
3. **Acknowledgement posterior ao commit durável:** a confirmação (`ack`) da mensagem no broker ocorre estritamente após o commit transacional bem-sucedido no PostgreSQL. Nenhuma mensagem é confirmada antes do commit durável do resultado ou controle correspondente.
4. **Separação entre Resultado da Operação e Resultado da Entrega:** a idempotência preserva o `ProcessingOutcome` da operação original (qualquer que seja: `SUCCESS`, `BUSINESS_REJECTION`, `NO_OP`, `AUTHORIZATION_REJECTED`). Reentregas pós-commit mantêm o resultado semântico original e registram um `DeliveryHandlingOutcome` separado (ex: `DUPLICATE_RECOVERED`).
5. **Validação pré-tenant e isolamento RLS:** a `RecordOwnerOrganization` alegada pelo envelope somente estabelece o contexto RLS após validação de assinatura, schema, contrato e autoridade do produtor. O contexto RLS é aplicado via `set_config('titan.current_organization_id', :org_id, true)` (`SET LOCAL`), garantindo que o contexto expire automaticamente ao término da transação.
6. **Distinção de participantes e restrição contratual de autorização:** a `ConsumerServiceIdentity` do worker executa o consumo. O `OriginalActor` é preservado como causa/origem auditável, mas não é impersonado como ator autenticado no instante do consumo. O `AuthorizationEvaluationMode` é restrito pelo contrato do tipo de mensagem e não pode ser alterado arbitrariamente pelo produtor.
7. **Atomicidade de Efeitos e Transação de Controle em Separado para Abortos:** Em conclusões normais, a escrita nos agregados, a Inbox e as novas mensagens da Outbox são persistidos na mesma transação. Quando uma falha transitória abortar a transação de processamento (`statement_timeout`, `lock_timeout`, `deadlock`), o worker executa `ROLLBACK` completo e abre uma **transação de controle separada** para registrar a tentativa, agendar o retry durável (`AGUARDANDO_RETRY`) e emitir a Outbox de reagendamento antes de enviar o `ACK`. Handlers possuem orçamentos estritos de tempo (`transaction_budget < shutdown_timeout`).
8. **Identidade semântica com objeto canônico estruturado:** a deduplicação combina `message_id` globalmente único e o `semantic_message_digest` (calculado via serialização canônica `titan-json-v1` em UTF-8 NFC sobre o objeto canônico completo do envelope e payload, evitando concatenações ambíguas). Mesmo `message_id` com digest divergente gera registro de conflito separado em quarentena em nova transação de controle, preservando a Inbox concluída original intacta.
9. **Retry autoritativo agendado com preservação de identidade:** o reagendamento de retry no PostgreSQL cria uma nova tentativa de transporte com `available_at` (preservando `message_id`, `semantic_operation_id` e `semantic_message_digest` originais) e emite `ack` na mensagem original. Se o PostgreSQL estiver indisponível, o worker aciona *circuit breaker* e suspende o consumo para evitar *hot loops* no broker.
10. **Quarentena autoritativa com minimização de dados:** a quarentena pré-tenant para mensagens não confiáveis é confirmada no PostgreSQL em transação global restrita antes do `ack` no broker. Registros pré-tenant passam por minimização estrita e utilizam papel técnico restrito sem contexto RLS de tenant.
11. **Fronteira formal de schemas:** a Inbox e a mensageria persistem no schema `core_messaging`. O schema `core_audit` permanece restrito a eventos históricos e evidências imutáveis.
12. **Graceful shutdown determinístico:** ao receber `SIGTERM` ou `SIGINT`, o worker interrompe novas capturas (`basic_cancel`), solicita o cancelamento e encerra a sessão PostgreSQL ao atingir o timeout de encerramento para forçar o rollback limpo, abstendo-se de enviar o `ack`.

## Alternativas Consideradas

### Opção A — Transação Única sem Lease Persistida (Adotada)

- RabbitMQ entrega a mensagem ao worker em `apps/worker`;
- worker efetua a validação pré-tenant (envelope, produtor, assinatura e contrato de autorização) antes da transação de tenant;
- inicia transação PostgreSQL atômica (`SET LOCAL` + aquisição transacional da Inbox + Application handler + escrita nos agregados + Outbox + marcação `CONCLUIDA`);
- commit da transação PostgreSQL;
- `ack` enviado ao RabbitMQ após o commit.
- *Vantagens:* modelo de concorrência e idempotência simples e robusto. Se o worker cair antes do commit, o PostgreSQL executa `ROLLBACK` completo e zero estado durável permanece. Se cair após o commit e antes do `ack`, a reentrega encontra `status = CONCLUIDA` e recupera o resultado sem reexecutar o handler de domínio.

### Opção B — Claim Persistido com Lease e Fencing Token

- exige registrar `EM_PROCESSAMENTO` em transação 1, obter `claim_generation`/`fencing_token`, renovar heartbeat em transações intermediárias e validar o token na transação 2 de commit do efeito;
- *Desvantagens:* adiciona complexidade e estados transitórios desnecessários para os handlers de domínio atuais, que executam dentro dos limites temporais de uma única transação PostgreSQL.

## Decisão

Adotar a **Opção A (Transação Única sem Lease Persistida)** com worker nativo Python (`apps/worker`), porta de consumo `MessageConsumerPort` na Application, adapter `RabbitMQPikaConsumer` na Infrastructure e schema **`core_messaging`** no PostgreSQL.

### Fluxo Atômico de Consumo e Transações de Controle

```text
                  RabbitMQ (Transporte)
                            │ (entrega mensagem)
                            ▼
     Worker (`apps/worker` via `RabbitMQPikaConsumer`)
                            │ 1. Valida envelope, tipo, versão, perfil e semantic_message_digest
                            │ 2. Valida autoridade do produtor e modo de autorização do contrato (pré-tenant)
                            │    └─ Se falhar: BEGIN (Global) -> insere untrusted_message_quarantine + Outbox -> COMMIT -> ACK.
                            ▼
               PostgreSQL (Transação Única de Processamento)
                            ├── 3. SET LOCAL titan.current_organization_id = %s
                            ├── 4. Aquisição atômica em core_messaging.inbox_messages (INSERT ... ON CONFLICT DO NOTHING)
                            │      ├─ Se CONCLUIDA + mesmo digest: recupera ProcessingOutcome original e grava HandlingOutcome = DUPLICATE_RECOVERED -> COMMIT -> ACK
                            │      ├─ Se CONCLUIDA + digest diferente: abre Transação de Controle -> insere inbox_conflicts (HandlingOutcome = CONFLICT_DETECTED) + Outbox -> COMMIT -> ACK
                            │      └─ Se AGUARDANDO_RETRY: transição condicional (status = 'AGUARDANDO_RETRY' AND available_at <= NOW() AND digest = digest_registrado)
                            ├── 5. Invoca Application Handler (escrita nos agregados sob orçamento de tempo)
                            ├── 6. Grava novas mensagens na Outbox (para e-mails, webhooks ou integrações externas)
                            └── 7. Atualiza InboxMessage para status = 'CONCLUIDA', completion_result_code = ProcessingOutcome
                            ▼
              ┌─────────────┴─────────────┐
        Sucesso (COMMIT)            Falha Transitória (Abort/Rollback)
              │                                   │
              ▼                                   ▼
        ACK (RabbitMQ)              Transação de Controle Separada
                                          ├── Grava inbox_delivery_attempts (RETRY_SCHEDULED)
                                          ├── Atualiza InboxMessage (status = AGUARDANDO_RETRY, available_at)
                                          └── Insere Outbox de reagendamento
                                          ▼
                                    COMMIT (Controle) ──> ACK (RabbitMQ)
                                          │ (se a transação de controle falhar)
                                          ▼
                                    SEM ACK ──> Pausa Consumo ──> Redelivery
```

---

## Estrutura do Schema `core_messaging`

A persistência do mecanismo de mensageria assíncrona aloca-se estritamente no schema **`core_messaging`**:

1. **`core_messaging.inbox_messages`**: estado operacional atual das mensagens atribuídas às Organizations.
2. **`core_messaging.inbox_delivery_attempts`**: histórico append-only de tentativas concluídas e tratamentos de entrega.
3. **`core_messaging.inbox_conflicts`**: registro de tentativas de entrega com `message_id` idêntico e `semantic_message_digest` divergente.
4. **`core_messaging.untrusted_message_quarantine`**: quarentena técnica global para mensagens cuja assinatura, produtor ou Organization não puderam ser validados (acessível exclusivamente por `ConsumerServiceIdentity` sem contexto RLS ativo).
5. **`core_messaging.outbox_messages`**: mensagens transacionais pendentes de publicação.

---

## Aquisição Atômica e Matriz de Comportamento na Inbox

A aquisição atômica utiliza `INSERT INTO core_messaging.inbox_messages (...) VALUES (...) ON CONFLICT (message_id) DO NOTHING RETURNING message_id`.

Se a inserção não retornar linha (registro existente), o worker consulta a Inbox sob a seguinte **Matriz de Comportamento**:

| Estado Encontrado | Digest Recebido vs Registrado | Comportamento do Worker |
|---|---|---|
| **`CONCLUIDA`** | Idêntico | Preserva o `ProcessingOutcome` original (qualquer que seja); grava `inbox_delivery_attempts` com `handling_result = DUPLICATE_RECOVERED` e envia o `ACK`. |
| **`CONCLUIDA`** | Divergente | Preserva a Inbox original intacta; grava `inbox_conflicts` com `handling_result = CONFLICT_DETECTED` e notificação na Outbox em transação de controle separada, enviando o `ACK`. |
| **`AGUARDANDO_RETRY`** | Idêntico | Reassume a mensagem **somente se** `status = 'AGUARDANDO_RETRY' AND available_at <= NOW() AND digest = digest_registrado` sob bloqueio transacional. Se `available_at > NOW()`, a mensagem redundante é tratada conforme a política de transporte sem reexecutar o handler. |
| **`EM_QUARENTENA`** | Idêntico | Recupera o estado de quarentena, grava tentativa como `QUARANTINED` e envia o `ACK`. |
| **`RECONCILIACAO_PENDENTE`** | Idêntico | Não reexecuta o handler de domínio sem intervenção do processo de reconciliação. |
| **`EM_PROCESSAMENTO`** | — | Protegido pela própria transação concorrente no PostgreSQL; worker aguarda o término do bloqueio de linha/chave primária. |

---

## Máquina de Estados e Resultados da Inbox

### Estados Operacionais (`status`)

- **`EM_PROCESSAMENTO`**: estado estritamente transacional ativo durante a sessão PostgreSQL corrente (não durável pós-falha).
- **`AGUARDANDO_RETRY`**: falha transitória registrada; reagendamento durável aguarda janela `available_at`.
- **`CONCLUIDA`**: processamento transacional finalizado e commitado (com sucesso ou rejeição de negócio esperada).
- **`EM_QUARENTENA`**: mensagem confiável de tenant com falha técnica permanente ou limite de retries exaurido.
- **`RECONCILIACAO_PENDENTE`**: estado durável criado por processo posterior de reconciliação quando a consulta pós-falha encontra condição incompatível.

### Separação de Resultados: Operação vs Tratamento da Entrega

1. **`ProcessingOutcome`** (Resultado semântico da operação original em `completion_result_code`):
   - **`SUCCESS`**: efeito de negócio executado e commitado com sucesso.
   - **`BUSINESS_REJECTION`**: a regra de domínio foi executada e produziu uma rejeição esperada e auditável (ex: animal já removido do lote). Processamento considerado concluído sem encaminhamento para a DLQ.
   - **`NO_OP`**: instrução recebida que não exigiu alteração de estado.
   - **`AUTHORIZATION_REJECTED`**: comando ou instrução rejeitada por regra de autorização no momento da execução.

2. **`DeliveryHandlingOutcome`** (Resultado do tratamento da entrega em `inbox_delivery_attempts.handling_result`):
   - **`PROCESSED`**: primeira execução concluída com sucesso.
   - **`DUPLICATE_RECOVERED`**: reentrega pós-commit detectada; resultado original preservado e retornado sem reexecução.
   - **`RETRY_SCHEDULED`**: falha transitória registrada e retry durável reagendado.
   - **`CONFLICT_DETECTED`**: conflito de digest registrado em `inbox_conflicts`.
   - **`QUARANTINED`**: mensagem enviada à quarentena.

---

## Identidade Semântica e Objeto Canônico (`titan-json-v1`)

O `semantic_message_digest` utiliza serialização canônica `titan-json-v1` em UTF-8 NFC sobre a estrutura do objeto canônico completo (evitando concatenações diretas de strings ambíguas):

```json
{
  "canonical_profile": "titan-json-v1",
  "message_id": "...",
  "message_type": "...",
  "schema_version": "...",
  "semantic_operation_id": "...",
  "producer_identity": "...",
  "record_owner_organization_id": "...",
  "authorization_evaluation_mode": "...",
  "purpose": "...",
  "authorization_decision_reference": "...",
  "payload": {}
}
```

Digest: `SHA-256(canonical_utf8_bytes)`. Metadados mutáveis de transporte (contadores de redelivery, routing keys) não integram o digest semântico.

---

## Isolamento RLS, Participantes e Restrição de Autorização

### Validação Pré-Tenant e Minimização de Dados na Quarentena

1. O worker valida o envelope, assinatura e autorização da `ProducerServiceIdentity` para emitir mensagens no escopo da `RecordOwnerOrganization` alegada.
2. O `AuthorizationEvaluationMode` declarado é validado contra o contrato registrado para o `message_type` e `schema_version`. O produtor não pode escolher um modo mais permissivo do que o exigido pelo contrato.
3. Se a validação pré-tenant falhar, o worker grava a quarentena em uma transação global restrita:
   ```text
   BEGIN;
     INSERT INTO core_messaging.untrusted_message_quarantine (
         received_at, alleged_producer, alleged_organization, message_id,
         received_bytes_digest, rejection_reason_code, sanitized_routing_metadata
     ) VALUES (...);
     INSERT INTO core_messaging.outbox_messages (...) VALUES (...);
   COMMIT;
   ```
   Após o `COMMIT` bem-sucedido, o worker envia o `ACK` da mensagem original no RabbitMQ. O payload bruto não é armazenado por padrão, sendo sanitizado para proteger o sistema contra conteúdo sensível ou malicioso.

### Participantes e Referência Verificável de Autorização

Para mensagens com `AuthorizationEvaluationMode = AT_ACCEPTANCE`, o envelope carrega obrigatoriamente a estrutura verificável:
- `authorization_decision_reference`
- `authorization_policy_version`
- `accepted_at`
- `accepting_service_identity`
- `authorization_context_digest`

O worker verifica se essa referência existe, corresponde à operação e Organization, e foi emitida por autoridade aceitável antes de executar o handler.

---

## Retry com Transação de Controle e Incerteza de Commit

### Retries com Transação de Controle Separada

Em caso de `TRANSIENT_TECHNICAL_FAILURE` que aborta a transação de processamento (ex: `statement_timeout`, `lock_timeout`, `deadlock`):
1. O PostgreSQL executa `ROLLBACK` completo da transação de processamento.
2. O worker abre uma **nova transação de controle** no PostgreSQL:
   ```text
   BEGIN;
     INSERT INTO core_messaging.inbox_delivery_attempts (..., handling_result) VALUES (..., 'RETRY_SCHEDULED');
     UPDATE core_messaging.inbox_messages SET status = 'AGUARDANDO_RETRY', available_at = :next_time WHERE message_id = :id;
     INSERT INTO core_messaging.outbox_messages (...) VALUES (...); -- Reagendamento com available_at
   COMMIT;
   ```
3. O reagendamento **preserva integralmente** o `message_id`, `semantic_operation_id` e `semantic_message_digest` originais, atribuindo apenas um `outbox_message_id` técnico para a publicação de transporte.
4. Efetua `COMMIT` da transação de controle e envia o `ACK` da mensagem original no RabbitMQ.
5. Se a transação de controle também falhar: o worker não envia o `ACK`, aciona *circuit breaker*, desativa a escuta e permite a redelivery do broker.

### Incerteza de Commit (`RECONCILIACAO_PENDENTE`)

`RECONCILIACAO_PENDENTE` é um estado durável criado por um processo posterior de reconciliação quando a consulta pós-falha encontra condição incompatível. Se a conexão for perdida durante o envio do `COMMIT`:
1. O worker **não envia o ACK** ao RabbitMQ.
2. Ao reconectar, antes de reexecutar o handler, o worker consulta `core_messaging.inbox_messages` por `message_id` e `semantic_message_digest`.
3. Se constar como `CONCLUIDA`, conclui que o `COMMIT` anterior foi bem-sucedido, envia o `ACK` pendente e encerra sem reexecutar.
4. Se ausente, permite a reexecução na nova transação.

---

## Orçamento Transacional, Graceful Shutdown e Prefetch

### Orçamento Transacional do Handler

Handlers executados sob a Opção A possuem orçamentos transacionais estritos (`statement_timeout`, `lock_timeout`, `handler_timeout`). O orçamento transacional normal deve satisfazer:
$$\text{transaction\_budget} < \text{shutdown\_timeout}$$
Processos longos, distribuídos ou CPU-intensivos são proibidos dentro da transação única, devendo ser divididos em etapas ou regidos por futura decisão de claim e fencing.

### Graceful Shutdown

1. Ao receber `SIGTERM` ou `SIGINT`, o worker entra em estado `DRAINING` e executa `basic_cancel` no canal AMQP.
2. Aguarda a finalização da transação PostgreSQL da mensagem em processamento.
3. Se o `shutdown_timeout` for atingido sem conclusão, o worker solicita o cancelamento da operação e encerra a sessão PostgreSQL — forçando o banco a abortar e reverter qualquer transação ainda não confirmada — e **não envia o ACK**.
4. Operações AMQP no adapter respeitam o modelo de concorrência do client `pika`.

### Prefetch

- Workers de processo único fixam `prefetch_count = 1`, garantindo que o trabalhador não reserve mais mensagens do que pode finalizar concorrentemente.

---

## Retenção Operacional

- A política de retenção da Inbox é calculada dinamicamente:
  $$\text{Janela de Retenção} > \text{Maior horizonte de reintrodução (incluindo backups e DLQ)} + \text{margem operacional}$$
- Nenhuma limpeza de registros operacionais da Inbox pode ocorrer enquanto uma mensagem puder ser reintroduzida legitimamente no ecossistema Titan.

---

## Consequências

| Tipo | Consequências |
|---|---|
| **Positivas** | Transação única atômica sem vazamento de leases; transação de controle separada para salvar retries pós-rollback; isolamento RLS seguro via `SET LOCAL`; preservação do resultado de conclusão original em caso de digest divergente; separação entre resultado da operação e resultado da entrega; quarentena pré-tenant isolada com minimização de dados; retry durável com preservação da identidade semântica. |
| **Negativas** | Necessidade de manter tabelas de suporte (`inbox_delivery_attempts`, `inbox_conflicts`, `untrusted_message_quarantine`) em `core_messaging`; restrição de handlers a transações de curta duração. |

---

## Riscos e Controles

| Risco | Controle |
|---|---|
| Transação de processamento abortada por timeout/lock | PostgreSQL executa `ROLLBACK` completo; worker abre nova transação de controle para gravar retry e enviar `ACK` |
| Reentrega de mensagem com digest alterado | Preserva `inbox_messages` como `CONCLUIDA` original e registra conflito em `inbox_conflicts` com `CONFLICT_DETECTED` em transação de controle |
| Envelope com Organization não autorizada | Validação pré-tenant grava em `untrusted_message_quarantine` em transação global minimizada antes do `ACK` |
| Produtor tentando burlar modo de autorização | Modo declarado no envelope validado contra a regra registrada para o `message_type` e `schema_version` |
| Side-effects externos executados inline | Proibidos no handler; emitidos via Outbox dentro da mesma transação do consumidor |
| Hot loop por falha de banco no retry | Circuit breaker no worker e pausa de consumo quando o PostgreSQL está indisponível |
| Re-agendamento de retry alterar identidade | Retry cria nova tentativa de transporte com `available_at`, preservando `message_id` e `semantic_message_digest` originais |
| Incerteza de commit (`COMMIT` enviado e conexão desfeita) | Reconexão consulta Inbox antes de reexecutar; se `CONCLUIDA`, envia o `ACK` pendente |
| Timeout de graceful shutdown atingido | Fechamento forçado da conexão PostgreSQL induz rollback automático; mensagem fica sem `ACK` para redelivery |
| Handler demorado travar o banco | Orçamento transacional estrito (`statement_timeout < shutdown_timeout`) por perfil operacional |

---

## Verificação Automatizada

Os testes do Passo 4.8C devem cobrir:

1. **Transação Única e Aborto:** worker sofrendo `statement_timeout` resultando em rollback completo no PostgreSQL e gravação do retry durável via transação de controle separada.
2. **Reentrega pós-commit:** mensagem reentregue após commit recuperando o `ProcessingOutcome` original da Inbox, registrando `DUPLICATE_RECOVERED` em `inbox_delivery_attempts` e enviando `ACK` sem invocar o handler.
3. **Digest divergente:** mensagem com `message_id` existente e digest alterado gravando registro em `inbox_conflicts` com `CONFLICT_DETECTED` em transação de controle sem modificar a Inbox concluída original.
4. **Validação pré-tenant e autorização:** envelope com assinatura/produtor inválido ou `AuthorizationEvaluationMode` incompatível sendo enviado à quarentena pré-tenant minimizada sem acionar `SET LOCAL`.
5. **Isolamento RLS:** confirmação de que `SET LOCAL` expira com o commit/rollback e não vaza para a próxima execução da conexão.
6. **Preservação de identidade no retry:** confirmação de que o reagendamento de retry preserva o `message_id` e o `semantic_message_digest` originais.
7. **Aquisição atômica e concorrência:** dois workers recebendo simultaneamente o mesmo `message_id` resolvendo por `INSERT ... ON CONFLICT DO NOTHING`.
