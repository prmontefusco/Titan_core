# T-05D Corte 4 — API controlada e roteiro de validação territorial sintética

**Data:** 14 de agosto de 2026
**Estado:** IMPLEMENTADO em 14 de agosto de 2026 — API sintética controlada e roteiro executável
**Escopo:** Titan Livestock; ADR-0062; continuação dos Cortes 1, 2 e 3
**Pré-requisitos concluídos:** captura territorial temporal, persistência append-only e adapter sintético-realista

## Problema

Os Cortes 1 a 3 já provaram a semântica interna:

```text
payload sintético-realista
        ↓
SyntheticTerritorialCaptureAdapter
        ↓
TerritorialSourceCapture
        ↓
persistência append-only
        ↓
TemporalTerritorialCaptureReader
        ↓
FactSnapshot temporal
```

Ainda falta uma forma operacional controlada para semear e observar esse fluxo
durante testes manuais e, futuramente, durante a integração do frontend.

Sem um endpoint/roteiro, a validação fica presa a testes automatizados e inserts
internos. Isso reduz a utilidade prática do incremento, porque o usuário não
consegue acompanhar a captura territorial sintética como operação visível.

## Decisão proposta

Criar uma API HTTP controlada para registrar capturas territoriais sintéticas e
um roteiro executável em `apps/validacao`.

O Corte 4 continua sem fonte oficial, sem provider geodados real e sem conclusão
normativa.

A API deve aceitar apenas perfis sintético-realistas já implementados:

```text
PRODES_LIKE_TIMELINE
DETER_LIKE_TIMELINE
FUNAI_LIKE_OVERLAP
IBAMA_LIKE_OVERLAP
```

e sempre gravar material como `TERRITORIAL_TEST_SOURCE` em ambiente `SYNTHETIC`.

## Fronteira semântica

O endpoint responde:

> “Esta captura territorial sintética foi registrada e preservada para seleção
> temporal futura.”

Ele não responde:

> “A propriedade está conforme.”

Nem:

> “O animal é elegível.”

Nem:

> “PRODES, DETER, FUNAI, IBAMA ou autoridade externa reconheceram este resultado.”

## Endpoint proposto

```text
POST /v1/livestock/properties/{property_id}/territorial-captures/synthetic
```

Permissão sugerida:

```text
LIVESTOCK_TERRITORIAL_CAPTURE.SYNTHETIC_CREATE
LIVESTOCK_TERRITORIAL_CAPTURE.READ
```

Justificativa para permissão nova: registrar captura territorial sintética é
operação de escrita append-only com impacto em reconstrução histórica futura. Não
deve piggyback em permissão de leitura territorial atual.

Como a criação de permissão exige seed nova, o Corte 4 deve atualizar a
semeadura e o roteiro deve avisar que a API precisa ser subida com a operadora
nova.

## Request body proposto

```json
{
  "geometry_id": "uuid",
  "geometry_version": 1,
  "profile": "FUNAI_LIKE_OVERLAP",
  "request_scope": {
    "layer": "FUNAI_LIKE",
    "operation": "OVERLAP"
  },
  "response_payload": {
    "feature_count": 1,
    "property_area_hectares": 1000.0,
    "overlap_area_hectares": 42.0,
    "source_version_ids": ["FUNAI_TEST_2026_V1"]
  },
  "captured_at": "2026-03-01T00:00:00Z",
  "known_at": "2026-03-02T00:00:00Z",
  "source_valid_from": null,
  "source_valid_to": null,
  "limitations": []
}
```

Regras:

- `property_id` vem da rota e não pode divergir do corpo;
- `geometry_id` deve existir, pertencer à mesma Organization e apontar para a
  propriedade da rota;
- `geometry_version` deve coincidir com a geometria selecionada;
- `profile` deve ser um dos quatro perfis sintético-realistas;
- `captured_at`, `known_at`, `source_valid_from` e `source_valid_to` devem ser
  UTC;
- `known_at` não pode ser inferido pelo servidor a partir de `captured_at`;
- `request_scope` e `response_payload` devem ser objetos JSON limitados;
- payloads muito grandes devem ser recusados;
- o adapter calcula `request_scope_digest` e `response_digest`;
- a API não aceita `response_digest` do cliente.

## Response body proposto

```json
{
  "capture_id": "uuid",
  "property_id": "uuid",
  "geometry_id": "uuid",
  "geometry_version": 1,
  "source_profile_code": "TERRITORIAL_TEST_SOURCE",
  "source_environment": "SYNTHETIC",
  "source_layer": "TERRITORIAL_TEST_OVERLAP",
  "operation": "OVERLAP",
  "request_scope_digest": "sha256hex",
  "response_schema": "livestock.territorial.synthetic_capture_response",
  "response_schema_version": 1,
  "canonicalization_version": "TERRITORIAL_RESPONSE_SUMMARY_CANONICAL_JSON_V1",
  "response_digest": "sha256hex",
  "response_summary": {},
  "source_version_ids": [],
  "source_valid_from": null,
  "source_valid_to": null,
  "captured_at": "2026-03-01T00:00:00Z",
  "known_at": "2026-03-02T00:00:00Z",
  "recorded_at": "2026-03-02T00:00:00Z",
  "limitations": [
    "SYNTHETIC_TERRITORIAL_SOURCE",
    "NO_EXTERNAL_RECOGNITION_ASSERTED"
  ]
}
```

## Endpoint de leitura

Preferência do Corte 4:

```text
GET /v1/livestock/properties/{property_id}/territorial-captures
```

Filtros opcionais:

```text
source_layer
operation
limit
offset
```

O endpoint de leitura deve expor apenas material da Organization ativa e deve
retornar lista paginável. Se já houver receio de escopo, pode-se adiar filtros e
implementar apenas listagem por propriedade com limite fixo.

## Roteiro executável

Arquivo proposto:

```text
apps/validacao/captura_territorial_sintetica.py
```

O roteiro deve:

1. sondar ambiente, login, permissões e migration antes do primeiro passo;
2. descobrir a Organization ativa sem copiar ID manualmente;
3. criar propriedade fictícia;
4. criar geometria fictícia da propriedade via API existente;
5. registrar captura `FUNAI_LIKE_OVERLAP` com sobreposição positiva sintética;
6. listar capturas da propriedade e exibir digest/limitações;
7. registrar captura `PRODES_LIKE_TIMELINE`;
8. listar novamente e comprovar as duas capturas;
9. tentar `geometry_id` inexistente ou divergente e esperar 4xx;
10. explicar que nenhuma Evaluation/Decision/Dossier foi criada.

O roteiro deve suportar `--pausar`, mostrar requisição/resposta formatadas e
descrever por que cada passo existe.

## Testes mínimos

### Application/API

- POST feliz para `FUNAI_LIKE_OVERLAP` retorna 201 e body sem aceitar digest do
  cliente.
- POST feliz para `PRODES_LIKE_TIMELINE` preserva `source_version_ids`.
- `known_at` posterior a `captured_at` é aceito e preservado.
- `known_at` ausente gera 422.
- `geometry_id` inexistente gera 404.
- geometria de outra Organization gera 404/403 sem vazar existência.
- `geometry_version` divergente gera 409 ou 422.
- profile desconhecido gera 422.
- payload com `source_version_ids` ausente grava limitação, não inventa versão.
- GET lista somente capturas da Organization ativa.
- GET com Organization B não enxerga capturas da Organization A.
- POST não cria Fact, Evaluation, Decision, Dossier ou coverage.

### Persistência/RLS

Reaproveitar testes do Corte 2. O Corte 4 não deve relaxar RLS nem adicionar
UPDATE/DELETE.

### Roteiro

- `python -m uv run --locked python -m apps.validacao.captura_territorial_sintetica`
  executa com dados fictícios e sem IDs copiados manualmente.
- `--pausar` funciona.

## Fora de escopo

- fonte oficial;
- HTTP client externo;
- integração com `Titan_geodata`;
- secrets, tokens de fonte externa ou custo recorrente;
- consulta a PRODES, DETER, FUNAI, IBAMA ou MapBiomas reais;
- Market Eligibility real;
- nova Policy territorial;
- alteração de FactProvider além de eventual composição já existente;
- Evaluation, Decision, Dossier ou VerificationBundle;
- PDF;
- frontend.

## Riscos e controles

| Risco | Controle |
|---|---|
| Usuário interpretar captura como conformidade | response e roteiro repetem que é material sintético, não conclusão |
| Payload arbitrário virar DoS | limitar tamanho/profundidade de `request_scope` e `response_payload` |
| Cliente controlar digest | servidor calcula todos os digests |
| Cross-tenant por geometria | serviço valida propriedade/geometria na Organization ativa antes de salvar |
| Permissão antiga não conter nova ação | seed nova e aviso explícito no roteiro |
| API virar fonte real por acidente | rota e permissão usam `synthetic`; fonte real exige outro corte |

## Portão para implementação

Confirmar antes de código:

1. A API será controlada e exclusivamente sintética.
2. Nova permissão e seed são aceitáveis neste corte.
3. O roteiro `apps/validacao` faz parte do aceite.
4. Nenhuma fonte real, geodata real, Policy, Evaluation, Decision, Dossier ou
   VerificationBundle será alterado.

## Próximo corte provável

Depois do Corte 4, existem duas rotas possíveis:

1. **Corte 5A — frontend/manual QA:** consumir a API sintética no frontend para
   testar jornada humana com dados artificiais.
2. **Corte 5B — adapter geodata controlado:** desenhar integração com
   `Titan_geodata` ou outro provider real/simulado, com contrato próprio e sem
   segredo no código.

Sem caso normativo real, a rota mais segura é Corte 5A.

## Registro de execução do Corte 4

Implementado em 14 de agosto de 2026 com API exclusivamente sintética.

Entregas:

- permissão específica `LIVESTOCK_TERRITORIAL_CAPTURE.SYNTHETIC_CREATE`;
- permissão específica `LIVESTOCK_TERRITORIAL_CAPTURE.READ`;
- `POST /v1/livestock/properties/{property_id}/territorial-captures/synthetic`;
- `GET /v1/livestock/properties/{property_id}/territorial-captures?limit=50&offset=0`;
- validação de propriedade e geometria na Organization ativa;
- `geometry_version` divergente retornando `409 CONFLITO_DE_REFERENCIA`;
- servidor calculando `request_scope_digest`, `response_digest`,
  `recorded_at`, `capture_id`, Organization owner e metadados internos;
- resposta HTTP sem payload bruto e sem `response_payload`;
- teste de duas capturas com mesmo conteúdo e `response_digest` igual, mas
  `capture_id` distinto;
- roteiro executável `apps/validacao/captura_territorial_sintetica.py` com
  `--pausar`, preflight de migration/permissão, criação de propriedade,
  geometria, captura overlap, captura timeline, listagem e caso negativo.

Permanecem fora: fonte real, `Titan_geodata`, secrets, mercado real, Policy,
Evaluation, Decision, Dossier, VerificationBundle e frontend.
