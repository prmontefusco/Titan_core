# T-05D — Territorialidade versionada e captura histórica

**Data:** 14 de agosto de 2026  
**ADR status:** PROPOSTA para a trilha T-05D  
**T-05D Corte 1:** IMPLEMENTED_AS_EXPERIMENT, com fonte sintética e sem persistência  
**T-05D Corte 2:** IMPLEMENTED_APPEND_ONLY_PERSISTENCE, sem API pública e sem fonte real
**Escopo:** Titan Livestock; reconstrução histórica territorial da ADR-0062  
**Relacionadas:** ADR-0026, ADR-0041, ADR-0052, ADR-0058, ADR-0062

## Problema

Os serviços territoriais atuais (`TerritorialTimelineService`,
`TerritorialOverlapService` e `EnvironmentalEmbargoService`) respondem leituras
atuais. Eles usam a geometria vigente da propriedade e consultam o provider de
geodados no momento da chamada. Isso é correto para exploração operacional, mas
não é suficiente para uma Evaluation histórica.

Uma consulta territorial atual não prova o que o provider externo apresentava em
um corte anterior. Se o Titan consultar PRODES, DETER, FUNAI ou embargo hoje para
reproduzir uma avaliação de ontem, ele pode responder a pergunta errada.

O T-05D precisa transformar material territorial externo em fotografia
verificável, selecionável por `reference_time` e `knowledge_cutoff`, sem fazer
uma abstração universal prematura para todas as fontes externas.

## Fronteiras existentes

`PropertyGeometry` já resolve a geometria do imóvel: é uma versão imutável do
perímetro/camada do próprio CAR, com digest, `captured_at`, `imported_at`,
`response_digest` e `layer_version`.

Essa geometria não é camada territorial externa. O próprio domínio já afirma que
PRODES, DETER, FUNAI, MapBiomas e embargos existem independentemente do imóvel.
Portanto, T-05D não deve guardar PRODES/FUNAI dentro de `PropertyGeometry`.

`ExternalSourceCaptureArtifact` já estabelece um padrão útil: captura
source-neutral, append-only, com digest, parser, outcome, projeção revisável e
limitações. Porém o contrato atual está restrito ao `SISBOV_SIMULATOR_LOCAL` e a
recursos `ANIMAL`, `GTA` e `MOVEMENT`. Ele não deve ser deformado para
territorialidade sem um contrato aprovado.

## Decisão proposta

Criar um primeiro contrato Livestock de captura territorial versionada, inicialmente
sintético, capaz de preservar uma resposta territorial como material histórico
verificável.

O contrato deve responder:

- qual propriedade e qual geometria foram usadas;
- qual fonte/camada territorial foi consultada;
- qual escopo foi perguntado;
- qual conteúdo ou resumo canonizado foi recebido;
- qual digest identifica a resposta;
- qual versão/identidade da camada externa foi declarada;
- quando a captura ocorreu;
- quando o Titan passou a conhecer a captura;
- qual intervalo ou referência temporal a fonte declara;
- quais limitações impedem tratar a captura como prova mais forte.

O primeiro corte não deve decidir mercado real, não deve consultar fontes reais,
não deve alterar `Decision`/`Dossier` históricos e não deve promover leitura atual
de geodados a evidência histórica.

## Modelo conceitual

Nome de trabalho:

`TerritorialSourceCapture`

Campos conceituais mínimos:

```text
capture_id
organization_id
property_id
geometry_id
geometry_version
source_profile_code
source_environment
source_name
source_layer
operation
request_scope_digest
response_digest
response_summary
response_schema
response_schema_version
canonicalization_version
source_version_ids[]
source_valid_from?
source_valid_to?
captured_at
known_at
recorded_at
limitations[]
```

`captured_at` é quando a consulta/captura ocorreu.  
`known_at` é quando o Titan pode usar essa captura em reconstrução histórica.  
`recorded_at` é persistência/auditoria interna.  
Nenhum desses campos deve ser inferido retroativamente em backfill.

`response_digest` identifica conteúdo sob contrato canônico explicitamente
versionado: `response_schema`, `response_schema_version` e
`canonicalization_version` declaram como `response_summary` foi canonizado antes
do SHA-256. Ele nunca é hash da serialização incidental do JSONB, de uma resposta
HTTP bruta ou de bytes externos não preservados. Se um adapter futuro precisar
provar bytes originais da fonte, a captura territorial deverá referenciar um
SourceArtifact/Document protegido que preserve esses bytes; `response_summary`
continuará sendo a interpretação estruturada minimizada da captura.

Todo adapter deve declarar como `known_at` é demonstrado. No
`TERRITORIAL_TEST_SOURCE`, ele é controlado artificialmente pelos testes. Em
fontes reais, pode coincidir com a resposta de uma consulta síncrona, mas isso
precisa ser regra do adapter, não conveniência de implementação.

`source_valid_from` e `source_valid_to` representam somente o intervalo temporal
que a própria fonte/camada afirma que aquele conteúdo descreve, quando essa
semântica existir. Eles não representam vigência do registro Titan, vigência da
geometria do imóvel ou versão de dataset por inferência. Se a fonte não declarar
intervalo de validade, ambos permanecem nulos e a limitação correspondente deve
ser explícita quando material.

## Corte 1 — Fonte territorial sintética

Implementar somente uma fonte artificial:

`TERRITORIAL_TEST_SOURCE`

Camadas sintéticas:

- `TERRITORIAL_TEST_TIMELINE`
- `TERRITORIAL_TEST_OVERLAP`

Ela permite testar a semântica sem misturar interpretação de PRODES, DETER,
FUNAI ou IBAMA.

O Corte 1 deve ser puro de application/domain quando possível:

- sem API pública;
- sem migration se o contrato puder ser provado em memória;
- sem fonte real;
- sem Market Eligibility real;
- sem PDF, VerificationBundle ou Dossier novo.

O resultado esperado é um leitor temporal capaz de produzir fatos sintéticos
somente a partir de capturas territorialmente admissíveis.

Fact types propostos para o teste:

```text
livestock.territorial.test_timeline
livestock.territorial.test_overlap
```

Esses facts devem preservar `capture_id`, `geometry_id`, `geometry_version`,
`response_digest`, `source_version_ids`, `known_at` e `limitations`.

## Corte 2 — Persistência append-only

Somente após o Corte 1 ser aprovado, persistir o contrato como tabela
append-only com RLS explícito `SELECT`/`INSERT`, sem `UPDATE`/`DELETE`.

Critérios mínimos:

- tenant coerente entre capture, propriedade e geometria;
- índice por Organization, propriedade, fonte, camada, operação e `known_at`;
- payload/resumo limitado para evitar DoS;
- digest obrigatório para resposta material;
- `known_at` obrigatório para novas capturas;
- linhas legadas inexistentes, sem backfill.

### Corte 2 — pacote de implementação proposto

**Estado:** IMPLEMENTADO em 14 de agosto de 2026 — persistência append-only sintética.

O Corte 2 deve persistir exatamente o contrato sintético já provado no Corte 1,
sem ampliar para fonte real e sem expor API pública. A migration prevista será a
próxima da cadeia Alembic, criando uma única tabela append-only:

```text
core_audit.territorial_source_captures
```

Ownership do schema: embora `TerritorialSourceCapture` permaneça conceito
Livestock e não seja promovido ao Core, o projeto já define em
`packages/livestock_infrastructure/persistence/metadata.py` que as tabelas da
vertical vivem fisicamente em `core_audit`, com `titan.module_owner=livestock`.
Portanto, `core_audit` aqui é armazenamento técnico/auditável compartilhado, não
generalização conceitual do contrato para o Core. Caso o projeto introduza no
futuro um schema físico `livestock_audit`, essa tabela é candidata natural a
migração; isso exigiria ADR/migration própria.

Colunas propostas:

```text
capture_id uuid primary key
record_owner_organization_id uuid not null
property_id uuid not null
geometry_id uuid not null
geometry_version integer not null
source_profile_code varchar(120) not null
source_environment varchar(40) not null
source_name varchar(120) not null
source_layer varchar(120) not null
kind varchar(40) not null
operation varchar(80) not null
request_scope_digest varchar(64) not null
response_schema varchar(160) not null
response_schema_version integer not null
canonicalization_version varchar(120) not null
response_digest varchar(64) not null
response_summary jsonb not null
source_version_ids jsonb not null
source_valid_from timestamptz null
source_valid_to timestamptz null
captured_at timestamptz not null
known_at timestamptz not null
recorded_at timestamptz not null
limitations jsonb not null
```

Constraints mínimas:

- `geometry_version >= 1`;
- `source_valid_to IS NULL OR source_valid_from IS NULL OR source_valid_to > source_valid_from`;
- `request_scope_digest` e `response_digest` com 64 caracteres hexadecimais;
- `response_schema` obrigatório e não vazio;
- `response_schema_version >= 1`;
- `canonicalization_version = 'TERRITORIAL_RESPONSE_SUMMARY_CANONICAL_JSON_V1'`
  no Corte 2;
- `source_environment = 'SYNTHETIC'` no Corte 2;
- `source_profile_code = 'TERRITORIAL_TEST_SOURCE'` no Corte 2;
- `kind IN ('TIMELINE', 'OVERLAP')`;
- `(kind, source_layer)` coerente com as camadas sintéticas;
- FK simples para `core_identity.organizations`;
- FK composta para `rural_properties` por `(record_owner_organization_id, property_id)`;
- FK composta para `property_geometries` por
  `(record_owner_organization_id, geometry_id)`.

Se `property_geometries` ainda não possuir `UNIQUE(record_owner_organization_id,
geometry_id)`, o Corte 2 deve adicioná-la explicitamente antes da FK composta.
Essa constraint não muda semântica de dados; apenas torna o tenant owner parte da
integridade referencial, repetindo o padrão usado no hardening de capturas
externas da ADR-0058.

RLS:

- habilitar RLS e `FORCE ROW LEVEL SECURITY`;
- criar uma policy `FOR SELECT USING (...)`;
- criar uma policy `FOR INSERT WITH CHECK (...)`;
- não criar policy `FOR ALL`;
- não criar policy para `UPDATE` ou `DELETE`.

O predicado deve seguir o padrão:

```sql
record_owner_organization_id =
NULLIF(current_setting('titan.organization_id', true), '')::uuid
```

Repositório:

```text
TransactionalTerritorialSourceCaptureRepository
```

Responsabilidades:

- `save(capture)`;
- `list_by_property(organization_id, property_id)`;
- mapear JSONB de volta para `MappingProxyType`/tuplas imutáveis via domínio;
- não recalcular nem substituir `known_at`, `captured_at` ou digest;
- ordenar leitura por `(known_at, captured_at, capture_id)`.

Testes mínimos do Corte 2:

- round-trip PostgreSQL preserva `response_summary`, digest, versões, intervalos,
  `response_schema`, `response_schema_version`, `canonicalization_version`,
  `captured_at`, `known_at`, `recorded_at` e limitações;
- digest recalculado a partir do contrato canônico versionado de
  `response_summary` confere com `response_digest`, sem depender da serialização
  física do JSONB;
- Organization A não lista captura da Organization B sob RLS;
- role restrita com grants amplos consegue `SELECT`/`INSERT`, mas `UPDATE` e
  `DELETE` retornam `rowcount == 0`;
- FK composta rejeita captura que aponta para propriedade ou geometria de outra
  Organization;
- `TemporalTerritorialCaptureReader` usando o repositório PostgreSQL mantém os
  testes T0/T1/T2 do Corte 1;
- `alembic check` não detecta divergência após a migration.

Fora de escopo do Corte 2:

- API pública;
- roteiro manual em `apps/validacao`;
- adapter PRODES, DETER, FUNAI, IBAMA, MapBiomas ou geodados real;
- integração com `TerritorialTimelineService` ou `TerritorialOverlapService`
  atuais;
- mercado real, Dossier, VerificationBundle ou alteração de Decisions.

## Corte 3 — Adapters reais

Adapters para PRODES, DETER, FUNAI ou IBAMA só entram depois de um caso real
concreto ou artificialmente controlado com contrato equivalente ao real.

Cada adapter deve declarar:

- fonte e camada;
- operação;
- identidade de versão da camada, quando disponível;
- forma canônica do resumo;
- limitações conhecidas da fonte;
- se a resposta representa timeline, overlap ou embargo.

O adapter não decide conformidade. Ele apenas captura e normaliza material.

## Invariantes

1. `PropertyGeometry` é geometria do imóvel; não é camada territorial externa.
2. Consulta territorial atual nunca responde uma reprodução histórica.
3. Captura territorial não é Decision, Evaluation, Dossier ou autorização.
4. Ausência de captura elegível não equivale a ausência de restrição.
5. Um resultado `SEM_RESTRICAO` só pode existir quando uma captura elegível
   afirmou isso para o escopo e camada consultados.
6. Captura conhecida depois do `knowledge_cutoff` não participa.
7. Fim de intervalo é exclusivo quando a fonte declarar intervalo.
8. Divergência de digest, versão desconhecida ou escopo ambíguo falha fechada.
9. Read models territoriais atuais podem continuar existindo, mas não alimentam
   avaliação histórica sem fotografia preservada.
10. O primeiro corte usa fonte sintética para provar semântica, não mercado real.

## Matriz mínima de testes

- Duas Organizations com propriedades e geometrias distintas.
- Captura T0 conhecida T0 entra em snapshot com cutoff T0.
- Captura T0 conhecida T2 não entra em snapshot com cutoff T1.
- Captura posterior ao `reference_time` não entra.
- Captura com digest divergente ou escopo diferente falha fechada.
- Duas capturas conflitantes para o mesmo escopo/camada/corte produzem
  indeterminação, não escolha por ordem do banco.
- Geometria atual alterada depois não reescreve fato produzido por captura que
  apontava para versão anterior.
- Ausência de captura produz lacuna/limitação, não `SEM_RESTRICAO`.
- Fonte sintética de timeline e overlap preserva IDs/digests no FactSnapshot.

## Fora de escopo

- Integração oficial PRODES, DETER, FUNAI, IBAMA ou MapBiomas.
- Autorização de exportação, reconhecimento externo ou mercado real.
- Alterar `PropertyGeometry` para guardar camadas territoriais.
- Backfill de capturas antigas.
- API pública, migration e roteiro manual no Corte 1.
- PDF, Dossier, VerificationBundle ou mudança em Decision histórica.

## Portão para implementação

Antes de código do Corte 1, confirmar:

1. a primeira fonte será sintética;
2. `PropertyGeometry` permanecerá somente como geometria do imóvel;
3. a captura territorial será prova de material consultado, não conclusão
   normativa;
4. ausência de captura elegível deverá resultar em indeterminação/lacuna;
5. nenhum adapter real ou migration será criado no primeiro corte.

## Registro de execução do Corte 1

Implementado em 14 de agosto de 2026 com fonte exclusivamente sintética
`TERRITORIAL_TEST_SOURCE`.

Entregas:

- `TerritorialSourceCapture` como fotografia territorial imutável em memória;
- `TemporalTerritorialCaptureReader` com seleção por `reference_time` e
  `knowledge_cutoff`;
- facts sintéticos `livestock.territorial.test_timeline` e
  `livestock.territorial.test_overlap`;
- integração opcional no `LivestockFactProvider` temporal estrito, usando somente
  propriedade derivada por movimentos;
- testes artificiais para posterioridade, cutoff, conflito, ausência e
  preservação de IDs/digests no snapshot.

Permanecem fora neste corte: API pública, fonte real, adapter geodados,
Market Eligibility real, Dossier, VerificationBundle e alteração de Decisions.

## Registro de execução do Corte 2

Implementado em 14 de agosto de 2026 como persistência exclusivamente sintética
do contrato já provado no Corte 1.

Entregas:

- migration `20260814_0075_create_territorial_source_captures.py`, criando
  `core_audit.territorial_source_captures`;
- tabela append-only com RLS explícito somente para `SELECT` e `INSERT`, sem
  policy `FOR ALL` e sem policy para `UPDATE`/`DELETE`;
- FKs compostas por `record_owner_organization_id` para propriedade e geometria,
  impedindo que uma captura aponte para material de outra Organization;
- constraints de ambiente sintético, perfil `TERRITORIAL_TEST_SOURCE`, camada,
  operação, digest, canonicalização e intervalo temporal declarado pela fonte;
- repositório `TransactionalTerritorialSourceCaptureRepository`, preservando
  `captured_at`, `known_at`, `recorded_at`, digest, versões da fonte,
  limitações e resumo canonizado;
- teste PostgreSQL com duas Organizations, role restrita sem `BYPASSRLS`,
  round-trip, bloqueio efetivo de `UPDATE`/`DELETE`, FK cross-tenant e leitura
  temporal pelo `TemporalTerritorialCaptureReader`.

Permanecem fora: API pública, roteiro manual em `apps/validacao`, fonte real,
adapter geodados, Market Eligibility real, Dossier, VerificationBundle e
alteração de Decisions.
