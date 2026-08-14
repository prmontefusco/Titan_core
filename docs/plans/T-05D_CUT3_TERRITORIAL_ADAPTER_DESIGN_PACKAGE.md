# T-05D Corte 3 — Adapter territorial sintético-realista

**Data:** 14 de agosto de 2026
**Estado:** PROPOSTO — aguardando revisão antes de código
**Escopo:** Titan Livestock; ADR-0062; continuidade do T-05D Corte 1/2
**Pré-requisitos concluídos:** captura territorial sintética em memória e persistência append-only em `core_audit.territorial_source_captures`

## Problema

O Titan já consegue preservar uma fotografia territorial sintética, persistir o
material de forma append-only e selecioná-lo por `reference_time` e
`knowledge_cutoff`.

Ainda falta provar o ponto operacional seguinte: como uma resposta territorial
parecida com fonte real entra no contrato `TerritorialSourceCapture` sem virar
conclusão normativa, sem consultar a fonte atual durante reprodução histórica e
sem codificar um mercado real prematuramente.

Não existe ainda um caso normativo real fechado. Portanto, o Corte 3 deve usar
um adapter sintético-realista: artificial o bastante para não alegar integração
oficial, mas parecido o bastante com PRODES/DETER/FUNAI/IBAMA para deixar poucos
passos entre o teste e um adapter futuro.

## Decisão proposta

Implementar um adapter application-level para uma fonte territorial controlada:

```text
TERRITORIAL_TEST_SOURCE
```

com perfis sintético-realistas de resposta:

```text
PRODES_LIKE_TIMELINE
DETER_LIKE_TIMELINE
FUNAI_LIKE_OVERLAP
IBAMA_LIKE_OVERLAP
```

Esses nomes não afirmam origem oficial. Eles apenas testam formatos de captura
que imitam as perguntas materiais esperadas:

- timeline anual de desmatamento/alerta;
- sobreposição territorial com camada protegida ou restritiva;
- versão declarada da camada;
- escopo da geometria consultada;
- resumo canonizado e limitado;
- limitações explícitas.

O adapter deve produzir `TerritorialSourceCapture` e opcionalmente persistir via
`TransactionalTerritorialSourceCaptureRepository`. Ele não decide
`SEM_RESTRICAO`, não avalia mercado, não cria `Evaluation`, não emite `Decision`
e não altera `Dossier`.

## Fronteira semântica

O Corte 3 responde:

> “Como uma resposta territorial controlada é normalizada e preservada como
> material histórico selecionável?”

Ele não responde:

> “Esta fazenda é elegível para determinado mercado?”

Nem:

> “A fonte oficial reconhece esta conclusão?”

A conclusão normativa continua pertencendo a Policy/Evaluation/Decision. A
captura territorial é apenas material de entrada.

## Contrato de entrada do adapter

O adapter deve receber uma solicitação explícita com:

```text
organization_id
property_id
geometry_id
geometry_version
source_profile_code = TERRITORIAL_TEST_SOURCE
source_environment = SYNTHETIC
source_layer
operation
request_scope
captured_at
known_at
source_valid_from?
source_valid_to?
response_payload
limitations[]
```

`request_scope` deve ser minimizado e canonizado antes do digest. Campos
sugeridos:

```text
property_id
geometry_id
geometry_version
layer
operation
reference_geometry_digest?
requested_years?
requested_buffer_meters?
```

O `request_scope_digest` não deve depender da ordem incidental de chaves JSON.

## Contrato canônico de resposta

O Corte 3 deve manter o contrato já aprovado:

```text
response_schema = livestock.territorial.synthetic_capture_response
response_schema_version = 1
canonicalization_version = TERRITORIAL_RESPONSE_SUMMARY_CANONICAL_JSON_V1
```

O `response_digest` deve ser SHA-256 do `response_summary` canonizado sob esse
contrato. Ele não é hash de resposta HTTP bruta, nem do JSONB físico, nem de
ordem incidental de serialização.

### Timeline-like

Resumo mínimo:

```text
{
  "profile": "PRODES_LIKE_TIMELINE",
  "layer": "PRODES_LIKE",
  "operation": "TIMELINE",
  "property_area_hectares": 1000.0,
  "years": [
    {
      "year": 2024,
      "feature_count": 1,
      "source_area_hectares": 12.5,
      "overlap_area_hectares": 4.2,
      "source_version_ids": ["PRODES_TEST_2024_V1"]
    }
  ]
}
```

### Overlap-like

Resumo mínimo:

```text
{
  "profile": "FUNAI_LIKE_OVERLAP",
  "layer": "FUNAI_LIKE",
  "operation": "OVERLAP",
  "feature_count": 1,
  "property_area_hectares": 1000.0,
  "overlap_area_hectares": 42.0,
  "overlap_ratio": 0.042,
  "source_version_ids": ["FUNAI_TEST_2026_V1"]
}
```

Valores ausentes não devem ser inventados. Se a fonte controlada não declarar
área, versão ou intervalo, o adapter deve preservar a ausência e declarar
limitação correspondente.

## `known_at`

No Corte 3, `known_at` continua artificial e controlado por teste.

Regra:

```text
known_at = instante em que o Titan recebeu/admitiu aquela captura sintética
```

Não pode ser derivado de `source_valid_from`, ano do dado, data de camada ou
`captured_at` por conveniência. Um teste deve provar:

```text
source_valid_from = 2024-01-01
captured_at       = 2026-03-01
known_at          = 2026-03-02
knowledge_cutoff  = 2026-03-01

=> captura não participa
```

## `source_valid_from/to`

Esses campos significam somente o intervalo que a própria camada declara
descrever.

Exemplos:

- timeline anual 2024: `[2024-01-01, 2025-01-01)`;
- camada de sobreposição sem intervalo declarado: ambos nulos;
- dataset publicado como versão vigente a partir de 2026-01-01: somente se essa
  semântica estiver explícita no payload controlado.

Eles não substituem `known_at` e não representam vigência da conclusão Titan.

## Limitações obrigatórias

Toda captura do Corte 3 deve declarar pelo menos uma limitação que deixe claro o
caráter sintético:

```text
SYNTHETIC_TERRITORIAL_SOURCE
NO_EXTERNAL_RECOGNITION_ASSERTED
```

Limitações adicionais esperadas:

```text
SOURCE_INTERVAL_NOT_DECLARED
SOURCE_VERSION_DECLARED_BY_TEST_FIXTURE
RAW_SOURCE_BYTES_NOT_PRESERVED
GEOMETRY_ACCURACY_NOT_REEVALUATED
```

`limitations` não são gaps normativos. Elas limitam o que a captura permite
afirmar.

## Persistência

O adapter pode salvar a captura pelo repositório do Corte 2.

Persistir não transforma a captura em fonte normativa, Decision, Evidence
admissível universal ou autorização externa. Persistência apenas preserva o
material para seleção temporal posterior.

## Testes mínimos

1. Adapter timeline-like produz `TerritorialSourceCapture` com digest canônico
   estável e `source_version_ids` preservados.
2. Reordenar chaves do payload de entrada não altera `response_digest`.
3. Alterar valor material do resumo altera `response_digest`.
4. Captura com `known_at` posterior ao cutoff não participa da leitura temporal.
5. `source_valid_from/to` não substituem `known_at`.
6. Overlap-like com `feature_count = 0` não vira automaticamente conclusão
   normativa; apenas preserva a resposta.
7. Payload sem versão declarada gera limitação, não versão inventada.
8. Persistência round-trip preserva o resultado do adapter.
9. Duas Organizations permanecem isoladas pelo repositório/RLS já existente.

## Fora de escopo

- PRODES, DETER, FUNAI, IBAMA, MapBiomas ou provider real;
- HTTP client externo;
- secrets, tokens, autenticação de fonte externa ou custo recorrente;
- API pública;
- roteiro manual em `apps/validacao`;
- Market Eligibility real;
- alteração de Policy, Evaluation, Decision, Dossier ou VerificationBundle;
- prova jurídica de conformidade territorial;
- reconhecimento externo.

## Portão para implementação

Antes de código, confirmar:

1. O Corte 3 usa apenas fonte sintética-realista.
2. O adapter cria material histórico, não conclusão normativa.
3. `known_at` permanece explícito e não derivado de validade da fonte.
4. `response_digest` continua preso ao contrato canônico versionado.
5. Persistência pode ser usada, mas API pública e fonte real ficam fora.

## Próximo corte provável

Depois do Corte 3, o caminho natural é o Corte 4:

```text
API interna/controlada + roteiro apps/validacao + seed fictício
```

Esse corte permitiria ensaio manual durante o frontend sem ainda afirmar mercado
real ou integração oficial.
