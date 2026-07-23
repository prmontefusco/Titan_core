# Genealogia, Relações Temporais e Projeções Reconstruíveis

Este documento especifica como o **Titan Core** registra vínculos entre sujeitos ao longo do tempo e como monta estruturas de leitura descartáveis a partir dos registros imutáveis.

> **Estado:** o Marco 7 está em andamento. Este documento cobre os passos **7.1** e **7.2**. Não conformidades, recall, dossiê, pacote de verificação e sincronização serão acrescentados conforme forem entregues.

---

## 1. Relação universal e temporal (`UniversalRelation`)

### O que é?
Vínculo genérico, temporal e auditável entre dois sujeitos, registrando origem, destino, tipo, período de validade, Organization responsável, Evento criador, evidências, confiança e quantidade opcional.

### Para que serve?
Formar a genealogia: responder de onde veio, para onde foi, quando, em qual quantidade, qual evento criou o vínculo e quais evidências o sustentam.

### Como funciona?

**O tipo da relação é um nome canônico livre, não um enum.** O Core não conhece os vínculos de nenhuma vertical; um conjunto fechado obrigaria o núcleo a mudar toda vez que uma vertical precisasse de um vínculo novo.

```python
relation_type="transformacao"   # válido
relation_type="composicao"      # válido
relation_type="Composição"      # rejeitado: precisa ser canônico minúsculo
```

**Temporalidade:** relação sem início declarado vale desde sempre; sem fim, vale indefinidamente.

```
t0                    t0+10d                 t0+30d
│                       │                       │
├── relação A (vigente) ┤
                        ├── relação B (vigente) ──────►
```

Consultar em `t0+5d` devolve A; consultar em `t0+20d` devolve B.

### Como utilizar no código Python:
```python
from decimal import Decimal

from packages.core_application.relation_service import RelationService
from packages.core_domain.evidence import ConfidenceLevel, ConfidenceTier
from packages.core_domain.relations import UniversalRelation
from packages.core_infrastructure.persistence.relations import TransactionalRelationRepository

service = RelationService(
    repository=TransactionalRelationRepository(connection=db_connection)
)

relacao = service.register_relation(
    UniversalRelation.create(
        organization_id=org_id,
        source_reference=origem,
        target_reference=destino,
        relation_type="transformacao",
        created_at=agora,
        confidence=ConfidenceLevel(
            tier=ConfidenceTier.DOCUMENTED, reason="Nota fiscal anexada."
        ),
        valid_from=agora,
        quantity=Decimal("120.500"),
        unit="kg",
        created_by_event=event_id,
        evidence_references=(referencia_da_evidencia,),
    )
)
```

### Consulta temporal e navegação
```python
# Prospectiva: para onde este sujeito aponta, na data X
saindo = service.list_outgoing_at(org_id, origem, at_time=data_x)

# Retrospectiva: quem aponta para este sujeito, na data X
entrando = service.list_incoming_at(org_id, destino, at_time=data_x)

# Sem instante: histórico completo
tudo = service.list_outgoing_at(org_id, origem)
```

### Encerrar não apaga
```python
service.close_relation(relacao.relation_id, ended_at=data_de_encerramento)
```
O vínculo passa a ter fim declarado e **continua respondendo consultas em instantes anteriores**. Genealogia nunca é perdida.

### Regras de integridade
- **Quantidade usa `Decimal`, nunca `float`** (coerente com o kernel de serialização), nunca é negativa e **sempre exige unidade declarada**. Quantidade sem unidade não significa nada num dossiê.
- **A relação não liga um sujeito a ele mesmo** (exceto o tipo `supersession`).
- **A relação não atravessa Organizations**: origem ou destino em outra Organization é recusado no domínio, e a travessia é bloqueada por `CrossOrganizationTraversalDenied` **antes** de consultar o repositório.

> Travessia de grafo é uma leitura poderosa. Sem fronteira explícita, seguir arestas viraria caminho de vazamento entre tenants — por isso a negação é explícita, e não silenciosa.

---

## 2. Projeções reconstruíveis (`ProjectionRebuildService`)

### O que é?
Estrutura de leitura derivada de eventos e relações, que indexa **quem aponta para cada referência**.

### Para que serve?
Responder rapidamente "quais registros citam este sujeito?" sem varrer o histórico inteiro a cada consulta.

### Como funciona?

A projeção **não é fonte de verdade e não contém regra de negócio própria**. Ela apenas organiza para leitura o que os registros imutáveis já declararam. Por isso descartá-la e reconstruí-la é operação normal, não perda de dado.

```
core_audit.domain_events ──┐
                           ├──► reference_projection (descartável)
core_audit.relations ──────┘
```

Papéis indexados (`ReferenceRole`): `AGGREGATE`, `ACTOR`, `SOURCE` (de eventos); `RELATION_SOURCE`, `RELATION_TARGET` (de relações).

### Reconstrutibilidade estrutural
A chave primária da tabela é **o próprio conteúdo derivado**, sem identificador sorteado. Reconstruir produz linhas idênticas, e comparar duas reconstruções é exato em vez de aproximado.

O digest ignora o instante de reconstrução — ele descreve a execução, não o conteúdo. Incluí-lo faria duas reconstruções idênticas parecerem diferentes.

### Como utilizar no código Python:
```python
from packages.core_application.projection_service import ProjectionRebuildService
from packages.core_infrastructure.persistence.projections import (
    PostgresProjectionSource, TransactionalProjectionRepository,
)

service = ProjectionRebuildService(
    source=PostgresProjectionSource(connection=db_connection),
    repository=TransactionalProjectionRepository(connection=db_connection),
)

digest = service.rebuild(org_id)                 # reconstrói do zero
apontando = service.list_referencing(org_id, alvo)  # referências reversas
```

### Detectar projeção defasada
```python
if not service.is_consistent_with_sources(org_id):
    service.rebuild(org_id)
```
`is_consistent_with_sources()` compara o gravado com o que as fontes produziriam agora, **sem gravar nada**.

### Ordem estável
As entradas são ordenadas por chave total antes de gravar, de modo que o conteúdo derivado não dependa da ordem em que o banco devolveu as linhas.

---

## 3. Notas de integração

- **Isolamento**: `core_audit.relations` e `core_audit.reference_projection` aplicam RLS por Organization.
- **Reconstrução é segura**: apagar a projeção não afeta eventos nem relações. O teste de integração do Core faz exatamente isso — apaga somente a projeção, reconstrói e confirma conteúdo idêntico com a fonte histórica intacta.
- **Índices**: as relações são indexadas por origem e por destino dentro da Organization, sustentando navegação nos dois sentidos.
