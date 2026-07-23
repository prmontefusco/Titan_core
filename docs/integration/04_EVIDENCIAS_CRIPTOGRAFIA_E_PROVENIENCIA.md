# Evidências, Criptografia e Proveniência

Este documento especifica como o **Titan Core** registra evidências imutáveis, assina artefatos criptograficamente, armazena documentos com verificação de integridade e permite navegar pela cadeia de proveniência que sustenta cada afirmação.

A regra que atravessa todo o marco: **nada é sobrescrito e nada é apagado**. Contestar, revogar ou corrigir sempre produz um registro novo que preserva o anterior.

---

## 1. Evidence — registro imutável

### O que é?
Registro imutável usado para sustentar, contestar ou contextualizar um Fato, Evento, relação, avaliação ou decisão. Preserva fonte, autoria, hash do conteúdo, nível de confiança, período de validade e histórico de verificações.

### Para que serve?
Permitir que qualquer conclusão do sistema aponte para o material que a sustenta. Sem evidência rastreável, uma decisão é apenas uma afirmação.

### Como funciona?
A Evidence é criada com o hash SHA-256 do conteúdo calculado no momento do registro. O conteúdo pode ser verificado depois: se o material for adulterado, o hash deixa de conferir. A Evidence nunca é alterada — verificações e revogações são registros adicionais anexados a ela.

### Como utilizar no código Python:
```python
from packages.core_application.evidence_service import EvidenceService
from packages.core_domain.evidence import ConfidenceLevel, ConfidenceTier, Source, SourceType
from packages.core_infrastructure.persistence.evidence import TransactionalEvidenceRepository

service = EvidenceService(repository=TransactionalEvidenceRepository(connection=db_connection))

evidence = service.register_evidence(
    organization_id=org_id,
    source=Source(source_id=TypedId.new("source"), source_type=SourceType.DOCUMENT),
    author_reference=author_ref,
    content=documento_em_bytes,
    confidence_level=ConfidenceLevel(
        tier=ConfidenceTier.DOCUMENTED,
        reason="Laudo emitido por laboratório credenciado.",
    ),
)
```

### Níveis de confiança (`ConfidenceTier`)
`INFORMED`, `DOCUMENTED`, `VERIFIED_SOURCE`, `HARDENED_SYSTEM`, `CRYPTOGRAPHICALLY_ATTESTED`.

Confiança é **separada de integridade**: um documento íntegro pode ter origem apenas declarada, e o sistema não confunde as duas coisas.

---

## 2. Gestão de chaves e assinatura (`KeyManagementService`)

### O que é?
Registro do ciclo de vida das chaves criptográficas — ativação, rotação e revogação — e assinatura de artefatos por meio de portas substituíveis.

### Para que serve?
Permitir assinatura verificável sem acoplar o Core a nenhum fornecedor. HSM, KMS ou TSA são detalhes de infraestrutura e **não aparecem no domínio**.

### Como funciona?
`KeyProviderPort`, `SigningProviderPort` e `TrustValidatorPort` definem os contratos; a infraestrutura fornece as implementações. Registrar uma nova chave para o mesmo propósito **rotaciona automaticamente** a anterior, que passa ao estado `ROTATED` e continua verificando assinaturas históricas.

> **Chaves privadas nunca são gravadas** em banco, log ou código. O registro guarda apenas a impressão digital da chave pública.

### Como utilizar no código Python:
```python
from packages.core_application.crypto import KeyManagementService
from packages.core_infrastructure.persistence.crypto import TransactionalKeyRegistryRepository

service = KeyManagementService(
    registry=TransactionalKeyRegistryRepository(connection=db_connection)
)

chave = service.register_key(
    organization_id=org_id,
    purpose="Assinatura de Documentos",
    public_key_fingerprint="sha256:...",
)

# Comprometimento: bloqueia novas assinaturas sem apagar o histórico
service.revoke_key(key_id=chave.key_identifier.key_id, reason="Vazamento em auditoria.")
```

### Estados da chave (`KeyState`)
`ACTIVE`, `ROTATED`, `REVOKED`.

### Assinar uma Evidence
A assinatura exige que o `EvidenceService` receba o provedor e o registro de chaves — sem eles, `sign_evidence` levanta `RuntimeError` em vez de assinar silenciosamente com um padrão implícito:

```python
from packages.core_domain.crypto import CryptographicProfile
from packages.core_infrastructure.crypto import SoftwareSigningProvider

service = EvidenceService(
    repository=TransactionalEvidenceRepository(connection=db_connection),
    signing_provider=SoftwareSigningProvider(),
    key_registry=TransactionalKeyRegistryRepository(connection=db_connection),
)

assinada = service.sign_evidence(
    evidence_id=evidence.evidence_id,
    profile=CryptographicProfile.INSTITUTIONAL_SIGNATURE,
)
```

### Resultado da verificação
A validação nunca devolve um booleano solto. Ela distingue `VÁLIDA`, `INVÁLIDA` e `INDETERMINADA`, informando perfil, algoritmo, chave, instante e escopo. Material ausente produz `INDETERMINADA` — nunca é tratado como falha nem como sucesso.

---

## 3. Documentos e anexos (`DocumentService`)

### O que é?
Armazenamento de arquivos binários com cálculo e validação obrigatórios de hash SHA-256 na subida e na descida.

### Para que serve?
Garantir que o arquivo entregue hoje é exatamente o que foi registrado na origem, mesmo que o armazenamento seja externo ou tenha sido migrado.

### Como funciona?
No upload, o hash é calculado e gravado junto ao anexo. No download, o hash é recalculado sobre o conteúdo recuperado e comparado. **Divergência levanta `ValueError` e o conteúdo não é entregue** — o registro do anexo permanece intacto para investigação.

### Como utilizar no código Python:
```python
from packages.core_application.document_service import DocumentService
from packages.core_infrastructure.persistence.evidence import TransactionalAttachmentRepository
from packages.core_infrastructure.storage import SoftwareBlobStorage

service = DocumentService(
    storage=SoftwareBlobStorage(),
    repository=TransactionalAttachmentRepository(connection=db_connection),
)

anexo = service.upload_attachment(
    organization_id=org_id,
    filename="laudo_veterinario.pdf",
    content_type="application/pdf",
    content=conteudo_em_bytes,
)

anexo, conteudo = service.download_attachment(anexo.attachment_id)
```

O `BlobStoragePort` é substituível: trocar armazenamento local por objeto na nuvem não altera domínio nem aplicação.

---

## 4. Proveniência navegável (`ProvenanceService`)

### O que é?
Navegação imutável e bidirecional entre Fonte, Evidência e Evento de domínio.

### Para que serve?
Responder "de onde veio isto?" e "o que isto originou?" sem depender de conhecimento tácito de quem operou o sistema.

### Como funciona?
```
Source ──────► Evidence ──────► DomainEvent
   ▲               ▲                 │
   └───────────────┴─────────────────┘
              (navegação reversa)
```

O traço é montado a partir dos registros imutáveis e devolve nós e arestas tipados (`ProvenanceNode`, `ProvenanceEdge`, `ProvenanceTrace`).

### Como utilizar no código Python:
```python
from packages.core_application.provenance_service import ProvenanceService

service = ProvenanceService(
    evidence_repository=evidence_lookup,
    event_repository=event_lookup,
)

trace = service.trace_from_evidence(evidence_id)   # o que esta evidência sustenta
trace = service.trace_from_source(source_id)       # tudo que nasceu desta fonte
trace = service.trace_from_event(event_id)         # o que sustenta este evento
```

---

## 5. Notas de integração

- **Isolamento**: todas as tabelas deste marco (`core_audit.evidences`, `evidence_verifications`, `key_registry`, `attachments`) aplicam RLS por Organization. Uma Organization nunca enxerga material de outra.
- **Revogação não apaga**: revogar uma Evidence registra motivo, autor e instante, preservando o conteúdo original e as verificações já feitas.
- **Verificação é registro, não estado**: cada verificação vira uma linha em `evidence_verifications` com resultado `VERIFIED`, `REJECTED` ou `INCONCLUSIVE`.
