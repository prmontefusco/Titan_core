# Integração de Mensageria e Eventos (Outbox, Inbox e Governança)

Este documento descreve como funciona a camada de mensageria assíncrona do Titan Core, para que serve cada componente, como utilizá-los programaticamente e como sistemas externos devem integrar-se para enviar e receber mensagens de forma segura e resiliente.

---

## 1. Formato do Envelope Canônico (`IncomingMessageEnvelope`)

### O que é?
É o invólucro padrão (envelope) utilizado por todas as mensagens (comandos e eventos) que entram no Titan Core.

### Para que serve?
Garantir que todas as mensagens possuam rastreabilidade universal (correlação, causação, data/hora), autoridade declarada (produtor e ator humano) e payload tipado.

### Como funciona?
O envelope é uma estrutura imutável (`dataclass frozen`) contendo metadados de auditoria e um payload canônico (`CanonicalPayload`). O digest semântico da mensagem é calculado deterministicamente em UTF-8 NFC usando o serializador `titan-json-v1`.

### Estrutura do Envelope JSON para Integração:
```json
{
  "message_id": "outbox_message:d6146f37-08ed-42ab-8f76-1cb2c2291410",
  "organization_id": "f31bc184-feaa-4ec1-a690-3032683000e9",
  "kind": "COMMAND",
  "contract_type": "titan.billing.charge_customer",
  "contract_version": 1,
  "semantic_operation_id": "operation:a8134574-9d02-88d7-40bd-cd0f61831a39",
  "actor_reference": {
    "target_id": "user:177e5bd3-5dee-4415-84bc-ecb5167b2df1",
    "organization_id": "f31bc184-feaa-4ec1-a690-3032683000e9",
    "contract_version": 1
  },
  "producer_reference": {
    "target_id": "service:billing_app",
    "organization_id": "f31bc184-feaa-4ec1-a690-3032683000e9",
    "contract_version": 1
  },
  "timestamps": {
    "occurred_at": "2026-07-22T14:30:00Z",
    "recorded_at": "2026-07-22T14:30:01Z"
  },
  "correlation_id": "correlation:764baf21-4014-4fb2-ac86-2756838ca3d1",
  "causation_id": "command:98d7cef5-13f2-4786-a613-e98f6e31b3a3",
  "auth_evaluation_mode": "SERVICE_AUTHORITY_ONLY",
  "purpose": "FINANCIAL_CHARGE",
  "classification": "PROTECTED",
  "payload": {
    "schema": "titan.billing.charge",
    "version": 1,
    "value": {
      "customer_id": "cust_99812",
      "amount_cents": 15000,
      "currency": "BRL"
    }
  }
}
```

---

## 2. Padrão Outbox Transacional & Reconciliação

### O que é?
Garantia de que eventos e comandos sejam gravados no banco de dados **na mesma transação** da alteração de estado do negócio e posteriormente publicados no broker (RabbitMQ).

### Para que serve?
Evita o problema de "duas fases" onde o banco grava o estado mas o broker cai antes de publicar a mensagem, resultando em perda de eventos.

### Como utilizar na aplicação?
```python
from packages.core_application.outbox import OutboxPublisherService

# Publica mensagem gravando estado PENDENTE na tabela core_audit.outbox_messages
publisher_service.publish(
    connection=db_connection,
    envelope=envelope,
)
```

### Reconciliação Operacional da Outbox
Se um trabalhador cair enquanto segura uma mensagem gravada (`CLAIMED`), o serviço de reconciliação descobre e libera *leases* expiradas:
```python
from packages.core_application.outbox import OutboxReconciliationService
from packages.core_infrastructure.persistence.outbox import TransactionalOutboxReconciliationRepository

repo = TransactionalOutboxReconciliationRepository(connection=db_connection)
service = OutboxReconciliationService(repository=repo)
report = service.run()
print(f"Claims expirados liberados: {report.released_claims_count}")
```

---

## 3. Inbox Transacional & Deduplicação

### O que é?
Garantia de processamento idempotente no lado consumidor da mensagem.

### Resultados de Processamento (`ConsumerReceipt`):
1. **`PROCESSED`**: Mensagem nova processada e confirmada com sucesso.
2. **`DUPLICATE_RECOVERED`**: Re-entrega exata (mesmo `message_id` e mesmo digest). Não re-executa a aplicação e retorna os efeitos/decisões salvas previamente.
3. **`CONFLICT_DETECTED`**: Mensagem re-entregue com mesmo `message_id` porém digest alterado. Preserva a mensagem concluída original e grava o evento forense em `core_messaging.inbox_conflicts`.

### Exemplo de Handler Consumidor:
```python
from packages.core_application import IncomingMessageEnvelope, ProcessingOutcome

class CustomerBillingHandler:
    def handle(self, envelope: IncomingMessageEnvelope) -> tuple[ProcessingOutcome, str | None, str | None]:
        # Lógica de negócio protegida sob RLS
        return (
            ProcessingOutcome.SUCCESS,
            f"charge_id:{envelope.message_id.value}",
            "decision:approved",
        )
```

---

## 4. Quarentena & Replay Auditado por Operador

### Quarentena Pré-Tenant (`untrusted_message_quarantine`)
Mensagens corrompidas ou enviadas por produtores não autorizados são gravadas em quarentena sem abrir transação no modelo de domínio.

### Como solicitar Replay Auditado:
Operadores humanos podem inspecionar a quarentena e autorizar um novo processamento com justificativa obrigatória:

```python
from packages.core_application.inbox import InboxQuarantineService, ReplayRequest
from packages.core_infrastructure.persistence.inbox import TransactionalInboxQuarantineRepository
from packages.shared_kernel import TypedId, UniversalReference, OrganizationId

quarantine_repo = TransactionalInboxQuarantineRepository(connection=db_connection)
service = InboxQuarantineService(repository=quarantine_repo)

# 1. Listar mensagens retidas na quarentena
quarantined_list = service.list_quarantined(limit=10)

# 2. Solicitar Replay informando Operador e Justificativa
operator_ref = UniversalReference(
    target_id=TypedId(entity_type="user", value=user_id_uuid),
    organization_id=OrganizationId(org_id_uuid),
    contract_version=1,
)

request = ReplayRequest(
    quarantine_id=quarantined_list[0].quarantine_id,
    operator_actor_reference=operator_ref,
    reason="Contrato de integração corrigido no gateway de pagamentos",
)

result = service.replay(request)
print(f"Status do Replay: {result.status}") # REQUEUED
```

---

## 5. Como Integrar um Sistema Externo ao Worker Daemon (`apps/worker`)

### Passos para Enviar Mensagem de um Sistema Externo:
1. Conectar ao RabbitMQ na URL de AMQP.
2. Serializar o payload de acordo com a especificação JSON do envelope canônico `IncomingMessageEnvelope`.
3. Publicar na fila `titan.outbox` (ou routing key configurada).
4. O Worker Daemon (`python -m apps.worker.main`) consumirá a mensagem, aplicará as validações pré-tenant, executará a transação RLS no PostgreSQL e confirmará o ACK no RabbitMQ.
