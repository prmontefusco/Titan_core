# Sincronização e Operação Offline

Este documento especifica como o **Titan Core** recebe operações capturadas sem conexão, revalida cada uma e produz efeito oficial ou recusa explicável.

> **Estado:** cobre o passo **7.9**, que implementa a **ADR-0021** e a seção 19 do `DOMAIN.md`.

Dois princípios atravessam o marco:

1. **Offline captura, não cria autoridade.** Desconexão não amplia Permission, grant, Membership, Purpose ou Policy.
2. **Sincronização é por operação.** Sucesso do lote nunca oculta resultado individual.

---

## 1. O envelope (`OfflineOperation`)

### O que é?
Envelope append-only de uma intenção capturada sem conexão, com identidade semântica, chave de idempotência, Device, Actor, relógio alegado, sequência local, dependências e conteúdo mínimo.

```python
from packages.core_domain.synchronization import DeviceClockReading, OfflineOperation, TimeConfidenceLevel

operacao = OfflineOperation(
    operation_id=TypedId.new("offline_operation"),
    organization_id=org_id,
    device_reference=device,
    actor_reference=actor,
    semantic_identity="vertical.comando:discriminador",
    idempotency_key="captura-0000001",
    operation_type="vertical.comando",
    contract_version=1,
    local_sequence=1,
    clock=DeviceClockReading(
        client_observed_at=agora,
        claimed_occurred_at=momento_do_fato,
        timezone_name="America/Sao_Paulo",
        confidence=TimeConfidenceLevel.SINCRONIZADO_COM_SERVIDOR,
        last_server_contact_at=ultimo_contato,
    ),
    payload=CanonicalPayload(schema="vertical.comando", version=1, value={...}),
    depends_on=(),
)
```

Segredo, token e credencial **não integram o conteúdo** — a proibição é herdada de `CanonicalPayload`.

### O digest da intenção, e por que ele ignora o envelope
```python
digest = operacao.intent_digest
```

`compute_intent_digest` cobre Organization, identidade semântica, tipo, versão do contrato e payload. Ele **deliberadamente ignora** OperationId, sequência local, relógio e tentativa.

> São justamente esses campos que mudam entre retomadas do mesmo comando. Incluí-los faria a mesma intenção parecer diferente a cada reenvio e destruiria a idempotência.

Consequência prática: a mesma intenção recapturada pelo Device, com outro OperationId e outro relógio, produz **o mesmo digest**.

---

## 2. O relógio do Device permanece alegação

| Nível de `TimeConfidence` | Exige |
|---|---|
| `SINCRONIZADO_COM_SERVIDOR` | último contato com o servidor declarado |
| `MONOTONICO_LOCAL` | continuidade monotônica declarada |
| `APENAS_RELOGIO_LOCAL` | — |
| `INDETERMINADO` | — (produz conflito na sincronização) |

**Nenhum nível transforma relógio de cliente em prova temporal.** O mais alto apenas declara que houve contato recente com o servidor.

```python
primeira.precedes(segunda)   # True/False dentro da mesma continuidade
primeira.precedes(outra)     # None — continuidade diferente
```

`precedes` devolve `None` fora da mesma continuidade monotônica. Continuidade perdida ou relógio civil não sustentam precedência, e afirmar ordem nesse caso seria inventar prova.

---

## 3. O lote e seu manifesto (`SynchronizationBatch`)

```python
lote = SynchronizationBatch.create(
    organization_id=org_id,
    device_reference=device,
    operations=(primeira, segunda),
    created_at_device=agora,
)
```

O manifesto declara, por operação: identificador, identidade semântica, digest da intenção, posição física e dependências. `inspect` confronta o declarado com o recebido e devolve **todos** os defeitos, não apenas o primeiro — o cliente precisa corrigir o lote inteiro, não descobrir um problema por retomada.

| Defeito | Detecta |
|---|---|
| `OPERACAO_AUSENTE` | declarada e não recebida |
| `OPERACAO_NAO_DECLARADA` | recebida e não declarada |
| `OPERACAO_DUPLICADA` | recebida duas vezes |
| `DIGEST_DIVERGENTE` | conteúdo alterado |
| `IDENTIDADE_SEMANTICA_DIVERGENTE` | intenção trocada |
| `ORGANIZATION_DIVERGENTE` / `DEVICE_DIVERGENTE` | origem trocada |
| `SEQUENCIA_FORA_DA_FRONTEIRA` | sequência local fora do intervalo declarado |

**Integridade do lote não substitui integridade individual, e posição física não cria causalidade.**

---

## 4. A recepção (`SynchronizationService`)

```python
from packages.core_application.synchronization_service import SynchronizationService

servico = SynchronizationService(
    repository=TransactionalSynchronizationRepository(connection=db_connection),
    effect_handler=aplicar_efeito_oficial,      # produz o efeito e devolve as referências
    device_admission=avaliador_de_device,       # opcional; padrão é permissivo
)
resultado_do_lote = servico.receive_batch(lote, operacoes, recebido_em)
```

### O handler de efeito oficial
```python
def aplicar_efeito_oficial(op: OfflineOperation) -> tuple[UniversalReference, ...]:
    ...
    return (referencia_do_objeto_criado,)
```

| Exceção do handler | Resultado |
|---|---|
| `OfficialEffectRejected(*codigos)` | `REJEITADA` |
| `OfficialEffectConflict(motivo, estado, alternativas)` | `CONFLITANTE` |
| `OfficialEffectResultUnknown(estado)` | `RESULTADO_DESCONHECIDO` |

Devolver tupla vazia é erro de programação: `ACEITA` sem referência não seria recuperável nem auditável.

### Ordem de processamento
O serviço processa **por dependência declarada**, não pela ordem física. A operação dependente enviada fisicamente antes da origem é aceita depois dela.

### Os sete resultados individuais

| Estado | Quando |
|---|---|
| `ACEITA` | efeito oficial produzido, com referência recuperável |
| `REJEITADA` | recusado pelo servidor; a captura permanece preservada |
| `DUPLICADA` | outra captura da mesma intenção sob a mesma chave |
| `CONFLITANTE` | chave divergente, ciclo, relógio insuficiente, versão ou autorização alterada |
| `DEPENDENCIA_PENDENTE` | dependência ausente, recusada ou em conflito |
| `EM_QUARENTENA` | Device não admitido a produzir efeito neste instante |
| `RESULTADO_DESCONHECIDO` | falha após o commit e antes da resposta |

### Idempotência e retomada

| Situação | Comportamento |
|---|---|
| Mesma operação reenviada | recupera o próprio resultado, com `RESULTADO_RECUPERADO` nos códigos |
| Mesma intenção, outro envelope | `DUPLICADA`, com as referências do efeito original |
| Mesma chave, **intenção diferente** | `CONFLITANTE` — **nunca** recupera nem associa o resultado anterior |

Associar o resultado anterior a uma intenção diferente devolveria ao cliente a confirmação de um comando que ele não enviou.

**Só `DEPENDENCIA_PENDENTE` e `EM_QUARENTENA` são reavaliados no reenvio.** Os demais são recuperados — inclusive `RESULTADO_DESCONHECIDO`, porque reprocessá-lo poderia repetir um efeito que talvez já exista.

> **A tentativa é da operação, não do lote.** A mesma captura pode ser reenviada em lotes diferentes, e o histórico append-only por tentativa perderia a decisão nova se ela recomeçasse do um.

### Conflito nunca é resolvido silenciosamente
Não existe last-write-wins, maior timestamp do Device nem último lote recebido. Todo `SynchronizationConflict` carrega motivo, estado observado e alternativas.

| Motivo | Significado |
|---|---|
| `IDEMPOTENCY_KEY_COM_INTENCAO_DIVERGENTE` | mesma chave, outra intenção |
| `DEPENDENCIA_CICLICA` | dependências formam ciclo |
| `MANIFESTO_DIVERGENTE_ENTRE_RETOMADAS` | mesmo BatchId, outro manifesto |
| `RELOGIO_INSUFICIENTE` | confiança temporal indeterminada |
| `VERSAO_DIVERGENTE` / `AUTORIZACAO_ALTERADA` | estado atual incompatível |

Manifesto alterado entre retomadas é **recusa estrutural do lote**, não conflito por operação: aceitar o lote novo permitiria substituir capturas já enviadas preservando o mesmo BatchId.

---

## 5. O resultado agregado (`SynchronizationBatchResult`)

| Estado | Quando |
|---|---|
| `RECEBIDO` | registrado na chegada |
| `PROCESSADO` | todas aceitas ou duplicadas |
| `PROCESSADO_PARCIALMENTE` | há resultado não aceito ou lacuna |
| `EM_RECONCILIACAO` | há resultado desconhecido |
| `RESULTADO_INDETERMINADO` | todos desconhecidos |
| `REJEITADO_ESTRUTURALMENTE` | manifesto não confere; nada foi examinado |
| `VALIDADO_PARCIALMENTE` | declarado e **não produzido** nesta implementação |

**O agregado conta e resume; nunca substitui nem reduz a precisão dos resultados individuais**, que permanecem recuperáveis por `OperationId`.

---

## 6. Persistência e garantias no banco

Três tabelas em `core_audit`, todas com RLS e `FORCE ROW LEVEL SECURITY`:

- `offline_operations` — os envelopes, preservados mesmo quando recusados;
- `synchronization_results` — append-only por `(operation_id, attempt)`;
- `synchronization_batches` — manifesto, tentativas e resultado agregado.

Três invariantes do domínio são **repetidas como `CHECK`**, de modo que nem escrita direta em SQL as viole:

```sql
status <> 'ACEITA' OR jsonb_array_length(produced_references) > 0
(status = 'CONFLITANTE') = (conflict IS NOT NULL)
status <> 'RESULTADO_DESCONHECIDO' OR reconciliation_deadline IS NOT NULL
```

### Por que não existe `UNIQUE (organization, idempotency_key)`
A segunda captura com a mesma chave e intenção divergente precisa ser **preservada** para virar conflito explicável. Uma constraint ali apagaria a captura em vez de explicá-la.

### Releitura
`get_operation` devolve `StoredOfflineOperation`, com o payload em bytes canônicos. A releitura **não** reconstrói `CanonicalPayload`: o contrato do passo 2.4 impede construir payload a partir de bytes arbitrários, e a persistência não é exceção.

---

## 7. Notas de integração

- **Fora do escopo deste passo, deliberadamente:** `OfflineCapabilityProfile`, `OfflineSession`, `OfflineAuthorizationSnapshot`, `DeviceTrustAssessment` e `LocalPreview` não foram antecipados.
- **A admissão do Device é uma porta explícita** (`DeviceAdmissionPort`), hoje com implementação permissiva (`AlwaysAdmitsDevice`). Ela existe para que o `DeviceTrustAssessment` futuro entre sem alterar o serviço: quem não avalia Device declara isso, em vez de não ter onde avaliar.
- **Rejeição não prova fraude** e não apaga a captura. Vínculo encerrado, grant revogado ou Policy alterada podem impedir a aceitação sem eliminar a evidência de que a captura ocorreu.
- **O Domain não conhece** banco local, sistema operacional, MDM, push, protocolo de transporte ou SDK de plataforma.
