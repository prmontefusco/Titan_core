# Integridade de Dados, Idempotência e Auditoria

Este documento especifica os mecanismos de garantia de integridade, controle idempotente de requisições e a corrente de auditoria criptográfica (*Hash Chain*) do **Titan Core**.

---

## 1. Idempotência Transacional no PostgreSQL (`IdempotencyService`)

### O que é?
Mecanismo que impede a duplicidade de execução de comandos ou transações financeiras/operacionais repetidas com a mesma chave de idempotência (`idempotency_key`).

### Para que serve?
Evitar efeitos colaterais duplicados (ex: cobranças duplas, criação duplicada de cadastros) em retentativas disparadas por falhas de rede ou cliques duplos do usuário.

### Como funciona?
O resultado da primeira execução com a chave de idempotência é armazenado na tabela `core_audit.idempotency_records` **dentro da mesma transação da operação**. Quando uma nova requisição com a mesma chave chega:
1. O Titan verifica o banco sob RLS.
2. Se já concluído, retorna o resultado salvo sem re-executar o handler.
3. Se a requisição anterior estiver ainda em processamento, aguarda ou bloqueia concorrência.

### Como utilizar no código Python:
```python
from packages.core_application.idempotency import IdempotencyService
from packages.core_infrastructure.persistence.idempotency import TransactionalIdempotencyRepository

idempotency_repo = TransactionalIdempotencyRepository(connection=db_connection)
service = IdempotencyService(repository=idempotency_repo)

# Executa comando garantindo idempotencia
result = service.execute(
    idempotency_key="pay_req_99812348",
    organization_id=org_id,
    operation=lambda: execute_payment_logic(),
)
```

---

## 2. Corrente de Hashes Criptográficos (*Hash Chain*)

### O que é?
Estrutura imutável de registro de auditoria onde cada novo evento gravado no sistema contém o hash SHA-256 do registro imediatamente anterior.

### Para que serve?
Garantir **irrefutabilidade e detecção de adulteração de histórico**. Se qualquer linha antiga do banco de dados for alterada ou apagada diretamente por um usuário privilegiado ou por invasão, o link do hash da cadeia será quebrado e detectado nas auditorias.

### Como funciona?
```
[Evento N-1] (Hash: 0x8a9f...)
       │
       ▼ (Calcula Hash SHA-256 combinando Evento N + Hash N-1)
[Evento N]   (Hash: 0x3b1c...)
       │
       ▼
[Evento N+1] (Hash: 0x7e2d...)
```

---

## 3. Checkpoints de Integridade de Estado (`IntegrityCheckpointService`)

### O que é?
Pontos de marcação de estado calculados periodicamente para validar a coerência global dos módulos do sistema.

### Para que serve?
Permitir a auditores internos/externos confirmar que o estado atual da base de dados corresponde exatamente à sequência histórica de eventos processados.

### Como utilizar:
```python
from packages.core_application.integrity_checkpoint import IntegrityCheckpointService
from packages.core_infrastructure.persistence.checkpoint import TransactionalCheckpointRepository

checkpoint_repo = TransactionalCheckpointRepository(connection=db_connection)
service = IntegrityCheckpointService(writer=checkpoint_repo)

# Registra um checkpoint de integridade para a organização
checkpoint = service.create(
    checkpoint_id=TypedId.new("checkpoint"),
    entries=(event_chain_entry,),
    observed_at=agora,
    producer_reference=producer_ref,
    correlation_id=correlation_id,
    causation_id=causation_id,
)

```

---

## 4. Concorrência Otimista com Registro de Versão

### O que é?
Controle de versão por entidade que impede sobrescritas cegas (*lost updates*) quando dois usuários ou sistemas editam a mesma entidade simultaneamente.

### Como funciona?
Cada entidade alterável possui a coluna `version`. Ao atualizar:
```sql
UPDATE core_identity.users
SET name = :name, version = version + 1
WHERE user_id = :user_id AND version = :expected_version;
```
Se o retorno de linhas afetadas for 0, o Titan dispara a exceção `OptimisticConcurrencyError` solicitando a recarga do recurso antes da tentativa.
