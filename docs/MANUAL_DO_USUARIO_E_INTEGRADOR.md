# Manual do Usuário e do Integrador — Titan Core

> **Público-alvo:** Desenvolvedores, arquitetos, auditores e gestores que precisam compreender, utilizar ou integrar sistemas externos à plataforma Titan Core.
> **Pré-requisito presumido:** Nenhum conhecimento prévio da plataforma Titan.

---

## SUMÁRIO

1. [O que é o Titan Core? (Visão Geral Didática)](#1-o-que-é-o-titan-core-visão-geral-didática)
2. [Conceitos Fundamentais e Arquitetura](#2-conceitos-fundamentais-e-arquitetura)
3. [Guia Módulo por Módulo: Para que serve e Como usar](#3-guia-módulo-por-módulo-para-que-serve-e-como-usar)
   - [3.1 Mensageria Assíncrona & Resiliência (Outbox, Inbox e Quarentena)](#31-mensageria-assíncrona--resiliência-outbox-inbox-e-quarentena)
   - [3.2 Segurança, Multitenancy e Isolamento RLS](#32-segurança-multitenancy-e-isolamento-rls)
   - [3.3 Integridade, Idempotência e Auditoria (Hash Chain)](#33-integridade-idempotência-e-auditoria-hash-chain)
   - [3.4 Evidências, Criptografia, Anexos e Proveniência](#34-evidências-criptografia-anexos-e-proveniência)
   - [3.5 Políticas, Regras, Fatos e Decisões Explicáveis](#35-políticas-regras-fatos-e-decisões-explicáveis)
   - [3.6 Governança Humana (Propostas, Overrides e Contestações)](#36-governança-humana-propostas-overrides-e-contestações)
   - [3.7 Genealogia e Projeções Temporais](#37-genealogia-e-projeções-temporais)
   - [3.8 Não Conformidades, Recall e Dossiê PDF Verificável](#38-não-conformidades-recall-e-dossiê-pdf-verificável)
   - [3.9 Verificação Externa por Terceiros (Offline e API)](#39-verificação-externa-por-terceiros-offline-e-api)
   - [3.10 Operação Offline e Admissão de Dispositivos](#310-operação-offline-e-admissão-de-dispositivos)
   - [3.11 Resiliência de Borda e Proteção de Dados (Rate Limiting e Log Redaction)](#311-resiliência-de-borda-e-proteção-de-dados-rate-limiting-e-log-redaction)
4. [Guia de Integração para Sistemas Externos (Passo a Passo)](#4-guia-de-integração-para-sistemas-externos-passo-a-passo)
5. [Cenário Prático Completo em Python (End-to-End)](#5-cenário-prático-completo-em-python-end-to-end)

---

## 1. O que é o Titan Core? (Visão Geral Didática)

### 1.1 A Metáfora do Cartório Digital Indestrutível
Imagine que você administra uma organização e precisa provar a um auditor, cliente ou órgão fiscal que determinado lote de produto ou operação financeira cumpriu **todas as leis e regras de qualidade vigentes**.

Em sistemas tradicionais, registros podem ser editados no banco por engano, logs podem ser perdidos, e decisões de aprovação muitas vezes ficam registradas como um simples booleano (`status = "APROVADO"`), sem explicar *quem* aprovou, *quais regras* foram checadas, *quais documentos* provam a conformidade e *qual era a lei exata* no dia da transação.

O **Titan Core** resolve isso atuando como um **cartório digital criptográfico e motor de decisões normativas**. Ele registra dados de forma imutável, avalia regras de forma matemática e determinística e produz decisões autoexplicativas que qualquer pessoa consegue verificar sem depender do Titan.

---

### 1.2 Os 4 Princípios Invioláveis do Titan Core

1. **O Core não conhece nenhuma vertical de negócio:**
   O núcleo do Titan é totalmente agnóstico. Ele não sabe o que é um bovino, uma nota fiscal ou um prontuário médico. Ele entende apenas *Entidades*, *Fatos*, *Regras*, *Evidências* e *Relações*. Cada setor de negócio (ex: pecuária, finanças, saúde) é acoplado via portas de integração.
2. **Nada é sobrescrito e nada é apagado (Imutabilidade Append-Only):**
   No Titan não existe `DELETE` ou `UPDATE` destrutivo sobre registros de auditoria e domínio. Se um documento for revogado, uma decisão contestada ou uma regra corrigida, o Titan grava um **novo registro histórico** apontando para o anterior, mantendo a linha do tempo intacta.
3. **Dado ausente nunca é acusação sem prova (Lacuna é pendência, não reprovação):**
   Se uma informação necessária para avaliar uma regra não estiver presente no sistema, o Titan declara o resultado como `PENDENTE` ou `INDETERMINADO`. Ele nunca assume que a ausência de um comprovante significa que a pessoa descumpriu a regra.
4. **Nenhuma decisão sem justificativa:**
   Toda decisão gerada pelo Titan traz uma lista obrigatória de razões com códigos normativos e ações corretivas. Uma decisão "muda" é rejeitada pelo próprio banco de dados.

---

## 2. Conceitos Fundamentais e Arquitetura

### 2.1 Multitenancy e Isolamento RLS (`OrganizationId`)
O Titan é multi-tenant: múltiplos clientes ou filiais compartilham o mesmo banco de dados com isolamento total.
- **Como funciona?** O isolamento é garantido nativamente pelo PostgreSQL através do **Row-Level Security (RLS)**.
- **O que isso significa na prática?** Cada tabela possui uma política de segurança que exige a definição da variável de sessão `titan.organization_id`. Mesmo que um desenvolvedor escreva um SQL sem cláusula `WHERE`, o banco esconde automaticamente as linhas de outras organizações.

### 2.2 Identidade Universal (`UniversalReference` e `TypedId`)
Para identificar qualquer elemento no sistema de forma inequívoca em qualquer microsserviço ou sistema externo:
- **`TypedId`**: Identificador composto pelo tipo lógico e um UUID v4.
  *Exemplo:* `TypedId(entity_type="user", value=UUID("..."))`
- **`UniversalReference`**: Tríade universal contendo `(target_id, organization_id, contract_version)`. Indica exatamente a qual organização e versão de contrato aquele recurso pertence.

---

## 3. Guia Módulo por Módulo: Para que serve e Como usar

---

### 3.1 Mensageria Assíncrona & Resiliência (Outbox, Inbox e Quarentena)

#### Para que serve?
Garantir que mensagens trocadas entre sistemas não sejam perdidas caso a rede oscile ou um serviço caia.

#### Como funciona?
- **Padrão Outbox (Envio Garantido):** Em vez de enviar uma mensagem direto ao RabbitMQ e arriscar a conexão cair, a aplicação grava a alteração no banco e a mensagem na tabela `core_audit.outbox_messages` **na mesma transação**. Um serviço de background (Worker) lê e publica no broker.
- **Padrão Inbox (Deduplicação Consumidora):** Quando uma mensagem chega, o consumidor verifica se ela já foi processada.
  - `PROCESSED`: Mensagem nova processada com sucesso.
  - `DUPLICATE_RECOVERED`: Re-entrega de mensagem idêntica. Devolve o resultado salvo sem re-executar o código.
  - `CONFLICT_DETECTED`: Re-entrega com o mesmo ID porém conteúdo alterado (tentativa de adulteração ou erro). Preserva o original e registra o conflito forense.
- **Quarentena Pré-Tenant:** Mensagens corrompidas ou sem autorização válida são isoladas em quarentena sem afetar o banco do cliente. Um operador pode solicitar o `ReplayRequest` fornecendo justificativa.

#### Exemplo de Uso em Python:
```python
from packages.core_application.outbox import EventOutboxService, OutboxPublisherService
from packages.core_infrastructure.persistence.outbox import TransactionalOutboxWriter

# 1. Anexa o evento de domínio e a mensagem na transação do banco
outbox_service = EventOutboxService(writer=TransactionalOutboxWriter(connection=db_connection))
outbox_service.append(event=domain_event, message=outbox_message)

# 2. Worker publica no RabbitMQ
publisher_service = OutboxPublisherService(
    repository=outbox_repo,
    publisher=rabbitmq_publisher,
    publisher_id="worker_01",
)
publisher_service.publish_once()
```

---

### 3.2 Segurança, Multitenancy e Isolamento RLS

#### Para que serve?
Garantir que a sessão do banco esteja estritamente limitada à organização do usuário autenticado.

#### Como usar em Python:
```python
from packages.core_application.organization_context import OrganizationContextService
from packages.shared_kernel import OrganizationId

org_id = OrganizationId.from_string("f31bc184-feaa-4ec1-a690-3032683000e9")

# Injeta a variável de sessão RLS na conexão PostgreSQL ativa
OrganizationContextService.apply_context(connection=db_connection, organization_id=org_id)
```

---

### 3.3 Integridade, Idempotência e Auditoria (Hash Chain)

#### Para que serve?
- **Idempotência (`IdempotencyService`):** Evita cobranças ou cadastros duplicados quando o usuário clica duas vezes no botão de enviar.
- **Cadeia de Hashes (*Hash Chain*):** Cada evento de auditoria grava o hash SHA-256 da linha anterior. Se alguém alterar o banco manualmente, a corrente se quebra e a adulteração é detectada.
- **Checkpoints (`IntegrityCheckpointService`):** Marcações periódicas que selam o estado do sistema.

#### Exemplo de Uso em Python:
```python
from packages.core_application.idempotency import IdempotencyService
from packages.core_infrastructure.persistence.idempotency import TransactionalIdempotencyRepository

service = IdempotencyService(repository=TransactionalIdempotencyRepository(connection=db_connection))

# Executa ação de forma idempotente
resultado = service.execute(
    idempotency_key="REQUISICAO_PAGAMENTO_99812",
    organization_id=org_id,
    operation=lambda: realizar_pagamento(),
)
```

---

### 3.4 Evidências, Criptografia, Anexos e Proveniência

#### Para que serve?
Armazenar laudos, PDFs, imagens e dados brutos que comprovem uma operação.
- **Níveis de Confiança (`ConfidenceTier`):** Distingue declarações não verificadas (`INFORMED`) de sistemas protegidos (`HARDENED_SYSTEM`) ou atestações criptográficas (`CRYPTOGRAPHICALLY_ATTESTED`).
- **Assinatura Digital (`KeyManagementService`):** Permite assinar evidências usando algoritmos criptográficos sem expor chaves privadas.
- **Anexos (`DocumentService`):** Armazena arquivos binários validando obrigatoriamente o hash SHA-256 no upload e no download.
- **Proveniência (`ProvenanceService`):** Permite navegar o grafo: `Source → Evidence → DomainEvent` (responde "de onde veio isso?" e "o que isso originou?").

#### Exemplo de Uso em Python:
```python
from packages.core_application.evidence_service import EvidenceService
from packages.core_domain.evidence import ConfidenceLevel, ConfidenceTier, Source, SourceType

evidence_service = EvidenceService(repository=evidence_repo)

# 1. Registra a evidência com hash SHA-256 do conteúdo
evidencia = evidence_service.register_evidence(
    organization_id=org_id,
    source=Source(source_id=TypedId.new("source"), source_type=SourceType.DOCUMENT),
    author_reference=autor_ref,
    content=bytes_do_laudo,
    confidence_level=ConfidenceLevel(
        tier=ConfidenceTier.DOCUMENTED,
        reason="Laudo oficial assinado por responsável técnico.",
    ),
)
```

---

### 3.5 Políticas, Regras, Fatos e Decisões Explicáveis

#### Como funciona o fluxo de decisão?
```
Políticas e Regras (Norma) + Fatos do Cliente (Snapshot) ──► Evaluation ──► Decision Explicável
```

1. **`PolicyService`**: Define a política normatizada e seu ciclo de vida (`DRAFT → PUBLISHED → SUPERSEDED / REVOKED`).
2. **`RuleService`**: Adiciona regras à política com severidade (`INFO`, `WARNING`, `CRITICAL`, `BLOCKING`) e condições declarativas (`RuleCondition`).
3. **`FactProviderPort`**: Porta pela qual a aplicação fornece o `FactSnapshot` (fotografia imutável dos fatos no instante da avaliação).
4. **`RuleEvaluationEngine`**: Executa o motor determinístico.
5. **`PolicyEvaluationService`**: Agrega os resultados das regras em um objeto `Evaluation`. Se houver contradições entre fatos ativos, o `EvidenceInconsistencyDetector` (ADR-0035) eleva o resultado para `EVIDENCIA_CONFLITANTE`.
6. **`DecisionService`**: Converte a `Evaluation` em uma `Decision` pública (`APROVADA`, `REJEITADA`, `APROVADA_COM_RESTRICOES` ou `INDETERMINADA`), acompanhada das razões normativas obrigatórias (`DecisionReason`).

#### Exemplo de Uso em Python:
```python
from packages.core_application.decision_service import DecisionService
from packages.core_application.evaluation_service import PolicyEvaluationService, RuleEvaluationEngine

# 1. Avalia a política sobre o snapshot de fatos
eval_service = PolicyEvaluationService(engine=RuleEvaluationEngine())
avaliacao = eval_service.evaluate_policy(
    policy=politica_publicada,
    rules=regras_da_politica,
    snapshot=snapshot_de_fatos,
    purpose="LICENCIAMENTO_OPERACIONAL",
)

# 2. Emite a decisão explicável
decisao = DecisionService().decide(avaliacao)
print("Resultado da Decisão:", decisao.result.value)
for razao in decisao.reasons:
    print("Razão:", razao.code.value, "-", razao.message)
```

---

### 3.6 Governança Humana (Propostas, Overrides e Contestações)

#### Para que serve? (ADR-0016)
Permitir que operadores ou fiscais humanos intervenham em decisões automatizadas sem violar a auditabilidade.

- **`DecisionProposal`**: Criada quando a avaliação resulta em `REVISAO_HUMANA_NECESSARIA`.
- **`DecisionOverride`**: Intervenção manual autorizada por um perfil credenciado (`DecisionAuthorityProfile`). Exige obrigatoriamente uma justificativa em texto. A decisão original permanece gravada e intacta.
- **`ContestationRecord`**: Registro formal de recurso ou contestação submetido pela parte afetada.

#### Exemplo de Uso em Python:
```python
from packages.core_application.decision_governance_service import DecisionGovernanceService
from packages.core_domain.decision_governance import DecisionAuthorityProfile

governance = DecisionGovernanceService()

# Aplica uma intervenção autorizada (Override)
override = governance.apply_override(
    original_decision=decisao_original,
    authority_profile=perfil_autoridade_fiscal,
    new_result=DecisionResult.APROVADA_COM_RESTRICOES,
    mandatory_reason="Aprovado mediante apresentação de laudo físico complementar validado.",
)
```

---

### 3.7 Genealogia e Projeções Temporais

#### Para que serve?
- **Relação Universal (`UniversalRelation`):** Registrar vínculos temporais entre entidades (ex: transformação de insumo em lote, associação de pessoas a empresas) com histórico completo.
- **Projeções Reconstruíveis (`ProjectionRebuildService`):** Estruturas de leitura otimizadas criadas a partir do histórico. Podem ser apagadas e reconstruídas a qualquer momento sem perder informação.

---

### 3.8 Não Conformidades, Recall e Dossiê PDF Verificável

#### 1. Não Conformidades (`NonConformityService`)
Acompanha pendências ou falhas até sua resolução:
`DETECTADA → CLASSIFICADA → ATRIBUIDA → EM_CORRECAO → PRONTA_PARA_REAVALIACAO → ENCERRADA`.
A transição para `ENCERRADA` exige uma nova `Evaluation` que comprove que a falha foi sanada.

#### 2. Recall (`RecallService`)
Realiza travessia em largura no grafo de genealogia para localizar todos os sujeitos e decisões **potencialmente afetados** por um problema. Se atingir um limite de busca ou ciclo, o resultado é explicitamente marcado com `RecallGap` (`is_conclusive = False`).

#### 3. Dossiê Autocontido e Gerador de PDF Verificável (`SoftwareDossierPdfAdapter` - Passo 7.8)
Copia todas as políticas, regras, fatos, evidências e decisões em um pacote imutável e gera uma representação em **PDF A4 estilizado**, contendo cabeçalho, tabelas normativas, assinatura digital e um **QR Code de verificação**:

```python
from packages.core_application.dossier_service import DossierService
from packages.core_infrastructure.pdf import SoftwareDossierPdfAdapter

# Gera o documento PDF assinado com QR Code
pdf_adapter = SoftwareDossierPdfAdapter()
dossier_service = DossierService(pdf_port=pdf_adapter)

pdf_representation = dossier_service.generate_pdf(
    dossier=dossier_objeto,
    signing_provider=signing_provider,
    key_id=chave_identificador,
)

# Salva o arquivo PDF no disco
with open("dossier_oficial.pdf", "wb") as f:
    f.write(pdf_representation.pdf_bytes)
```

---

### 3.9 Verificação Externa por Terceiros (Offline e API)

#### Para que serve?
Permitir que um auditor ou parceiro receba uma decisão e confirme se ela é legítima **sem precisar acessar o banco de dados do Titan**.

1. **`VerificationBundle`**: Pacote contendo o dossiê, assinaturas e certificados.
2. **`BundleVerifier`**: Verificador puro (offline, sem banco, sem rede). Avalia 8 dimensões de integridade e devolve um veredito (`VALIDA`, `INVALIDA`, `INDETERMINADA`, `NAO_APLICAVEL`, `NAO_EXECUTADA`).
3. **API Publica (`POST /v1/verification/bundles`)**: Endpoint público para verificação externa via HTTP.

---

### 3.10 Operação Offline e Admissão de Dispositivos

#### Para que serve? (Passo 7.9 / ADR-0021)
Permitir que dispositivos em campo (smartphones, coletores sem internet) capturem operações e as sincronizem quando a conexão retornar.

- **`OfflineOperation`**: Envelope append-only da intenção. O digest da intenção (`intent_digest`) é calculado apenas sobre o comando e dados, ignorando IDs locais ou relógio, o que permite idempotência perfeita no reenvio.
- **`OfflineSession` & `OfflineCapabilityProfile`**: Credenciais e escopos de operação autorizados offline com prazo de expiração.
- **`DeviceTrustAssessment`**: Avaliação de postura de segurança do dispositivo (rejeita dispositivos com root/jailbreak ou score baixo).
- **`EvaluatesDeviceTrustAndSession`**: Porta de admissão rigorosa no servidor.
- **`LocalPreview`**: Prévia in-memory gerada no dispositivo para simular o resultado antes do envio (`service.generate_local_preview(operation)`).

---

### 3.11 Resiliência de Borda e Proteção de Dados (Rate Limiting e Log Redaction)

#### Para que serve? (ADR-0039)
- **Limitação de Taxa HTTP 429 (`InMemoryRateLimiter`):** Protege as APIs contra ataques de negação de serviço (DDoS) ou requisições desordenadas, devolvendo o status HTTP 429 e o cabeçalho `Retry-After`.
- **Mascaramento de Logs (`RedactingLogFormatter`):** Sanitiza automaticamente todas as mensagens emitidas nos logs do sistema, substituindo senhas, tokens JWT (`Bearer`), chaves privadas e API keys pela tag `[REDACTED_SECRET]`.

---

## 4. Guia de Integração para Sistemas Externos (Passo a Passo)

Para integrar uma aplicação externa (gateway, ERP, app mobile) ao Titan Core, siga este fluxo:

### Passo 1: Autenticação HTTP via OIDC / JWT
Envie o token de acesso obtido no provedor de identidade no cabeçalho HTTP:
```http
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Passo 2: Envio de Comandos/Eventos via Mensageria (RabbitMQ / Outbox)
Envie o payload JSON formatado no envelope canônico `IncomingMessageEnvelope` para a fila `titan.outbox`:

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
    "occurred_at": "2026-07-23T14:30:00Z",
    "recorded_at": "2026-07-23T14:30:01Z"
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

## 5. Cenário Prático Completo em Python (End-to-End)

Abaixo está um script Python autocontido que demonstra a execução integrada das principais funcionalidades do Titan Core:

```python
"""Exemplo de fluxo completo no Titan Core."""

from datetime import UTC, datetime
from uuid import uuid4

from packages.core_application.decision_service import DecisionService
from packages.core_application.dossier_service import DossierService
from packages.core_application.evaluation_service import PolicyEvaluationService, RuleEvaluationEngine
from packages.core_domain.decision import DecisionReason, DecisionReasonCode, DecisionResult, compute_decision_hash
from packages.core_domain.dossier import Dossier
from packages.core_domain.evaluation import Evaluation, EvaluationOutcome, RuleResult, RuleResultStatus, compute_evaluation_hash
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.policy import Policy, PolicyStatus
from packages.core_domain.rule import Rule, SeverityLevel
from packages.core_infrastructure.crypto import SoftwareKeyProvider, SoftwareSigningProvider
from packages.core_infrastructure.pdf import SoftwareDossierPdfAdapter
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

# 1. Identificação da Organização e Sujeito
org_id = OrganizationId(uuid4())
subject_id = TypedId(entity_type="lote", value=uuid4())
policy_id = TypedId(entity_type="policy", value=uuid4())
rule_id = TypedId(entity_type="rule", value=uuid4())
now = datetime.now(UTC)

# 2. Criação do Snapshot de Fatos
fact = Fact.create(
    fact_type="certidao.sanitaria",
    payload={"status": "VALIDA"},
    observed_at=now,
)
snapshot = FactSnapshot(
    organization_id=org_id,
    target_id=subject_id,
    as_of=now,
    facts=(fact,),
    snapshot_hash="a" * 64,
)

# 3. Política e Regra
policy = Policy(
    policy_id=policy_id,
    organization_id=org_id,
    code="POL_SANIDADE",
    name="Política de Sanidade",
    description="Regras sanitárias de exportação",
    version=1,
    status=PolicyStatus.PUBLISHED,
)
rule = Rule(
    rule_id=rule_id,
    policy_id=policy_id,
    organization_id=org_id,
    code="REGRA_CERTIDAO",
    name="Certidão Válida",
    description="Exige certidão válida",
    version=1,
    severity=SeverityLevel.BLOCKING,
    normative_source="Instrução Normativa 01",
    required_evidence_types=(),
    conditions=(),
)

# 4. Avaliação e Decisão
engine = RuleEvaluationEngine()
eval_service = PolicyEvaluationService(engine=engine)
evaluation = eval_service.evaluate_policy(
    policy=policy,
    rules=(rule,),
    snapshot=snapshot,
    purpose="EXPORTACAO",
)

decisao = DecisionService().decide(evaluation)
print(f"Decisão Gerada: {decisao.result.value}")

# 5. Geração de Dossiê e Representação PDF Assinada com QR Code
dossier = Dossier.build(
    decision=decisao,
    evaluation=evaluation,
    policy=policy,
    rules=(rule,),
)

key_provider = SoftwareKeyProvider()
signing_provider = SoftwareSigningProvider(key_provider=key_provider)
key_id = TypedId.new("key")

pdf_adapter = SoftwareDossierPdfAdapter()
dossier_service = DossierService(pdf_port=pdf_adapter)

pdf_representation = dossier_service.generate_pdf(
    dossier=dossier,
    signing_provider=signing_provider,
    key_id=key_id,
)

print(f"PDF Gerado com sucesso! Tamanho: {len(pdf_representation.pdf_bytes)} bytes.")
print(f"Payload do QR Code de verificação: {pdf_representation.verification_qr_payload}")
```
