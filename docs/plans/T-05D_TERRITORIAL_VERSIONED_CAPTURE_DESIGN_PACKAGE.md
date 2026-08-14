# T-05D — Territorialidade versionada e captura histórica

**Data:** 14 de agosto de 2026  
**Estado:** CORTE 1 IMPLEMENTADO — persistência/API/fontes reais permanecem fora  
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

Permanecem fora: migration, API pública, fonte real, adapter geodados,
Market Eligibility real, Dossier, VerificationBundle e alteração de Decisions.
