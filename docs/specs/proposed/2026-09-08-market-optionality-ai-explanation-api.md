# SPEC: Contrato de API e UI para AI Explanation de Market Optionality

- **Nível:** CRITICAL
- **Estado:** proposta
- **Decisão de Discovery:** PROCEED
- **Owner de produto:** Titan Core + Titan Livestock
- **Data:** 2026-09-08

## Problema e usuário

Produtores pecuários e operadores internos precisam compreender o status de preservação de opções de mercado (`MarketOptionAssessment`) de animais sob sua gestão sem depender de interpretação manual de códigos normativos complexos.

O Titan já possui o pipeline seguro de AI Explanation (com payload minimizado, deterministic guard, fallback canônico e audit durável sob RLS), mas **nenhum endpoint HTTP ou tela expõe essa capacidade**, preservando os portões de governança de ADR-0074 e ADR-0075 (`POLICY_GATE: User-Visible API/UI Contract`).

Esta SPEC define o primeiro contrato visível da API e UI para AI Explanation, garantindo que o texto gerado permaneça não decisional, estritamente owner-scoped e protegido contra exfiltração de dados ou quebra de invariantes.

## Contexto e objetivo

- Expor a explicação por IA exclusivamente como camada de apresentação transitória e não decisional sobre o `MarketOptionAssessment` de um `subject` (Animal).
- Implementar o padrão canônico do Titan de liberação gradual:
  1. SPEC aprovada;
  2. Permission explícita no catálogo de Livestock sem concessão automática a papéis de comprador;
  3. Router HTTP feature-flagged (`TITAN_MARKET_OPTIONALITY_AI_EXPLANATION_API_ENABLED=false` por padrão);
  4. Cabeçalhos rígidos anti-cache (`Cache-Control: no-store`, `Pragma: no-cache`);
  5. Roteiro de validação manual executável em `apps/validacao/`;
  6. Frontend em `apps/web` consumindo estritamente a projeção pública sanitizada.

## Fora de escopo

- Explicações buyer-facing ou relatórios agregados de mercado com IA (permanecem proibidos sob ADR-0074/0075).
- Consultas cross-tenant ou visibilidade multi-owner.
- Streaming ou entrega parcial de texto não validado pelo guard.
- Persistência de prompt bruto, texto de erro ou payload do provider.
- Criação de novas Policies, Evaluations, Decisions, Dossiers ou VerificationBundles via IA.
- Previsão de preços, elegibilidade futura ou recomendações zootécnicas/veterinárias.

## Invariantes e Regras de Negócio

1. **Owner-only:** A rota opera sob o contexto da Organization dona do Animal. Animais de outra Organization recebem `404` uniforme ou `403`.
2. **Saída Canônica como Base e Fallback:** A IA não é executada sem que exista um `MarketOptionAssessment` canônico prévio do animal. Se o provider falhar, o guard rejeitar ou a gravação de audit falhar, a API retorna o resumo canônico estruturado com `release_disposition: "NOT_RELEASED"`.
3. **Audit antes de Release:** Nenhum texto gerado por IA é devolvido no corpo da resposta HTTP sem que um `ai_explanation_audit_records` correspondente tenha sido persistido com sucesso na transação.
4. **Coordenadas Temporais Obrigatórias:** `reference_time` e `knowledge_cutoff` devem ser informados em UTC.
5. **Anti-cache:** Respostas contendo explicações devem incluir `Cache-Control: no-store` e `Pragma: no-cache`.
6. **Feature Flag Default-off:** Com a flag desligada, a rota não é registrada no OpenAPI e responde `404` uniforme.

## Contrato HTTP Proposto

### Endpoint
`POST /v1/livestock/animals/{animal_id}/market-optionality/explanation`

### Headers Obrigatórios
- `Authorization: Bearer <token>`
- `X-Titan-Organization-Id: <uuid>`
- `Idempotency-Key: <string>` (opcional / recomendado para correlação)

### Request Body
```json
{
  "policy_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "policy_version": 1,
  "market_purpose": "EU_DEFORESTATION_REGULATION_BEEF",
  "reference_time": "2026-09-08T12:00:00Z",
  "knowledge_cutoff": "2026-09-08T12:00:00Z"
}
```

### Response Body (200 OK — Released)
```json
{
  "subject_id": "animal:3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "market_purpose": "EU_DEFORESTATION_REGULATION_BEEF",
  "policy_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "policy_version": 1,
  "reference_time": "2026-09-08T12:00:00Z",
  "knowledge_cutoff": "2026-09-08T12:00:00Z",
  "canonical_state": "OPTION_OPEN",
  "reversibility": "NOT_APPLICABLE",
  "release_disposition": "RELEASE_APPROVED",
  "explanation_text": "Resumo sanitizado em português aprovado pelo guard.",
  "canonical_fallback": {
    "summary": "Resumo canônico baseado exclusivamente nas regras vigentes.",
    "reason_codes": ["SANITARY_CONFORMANCE_VERIFIED"]
  },
  "audit_id": "ai_explanation_audit:9ba65f64-5717-4562-b3fc-2c963f66afb1"
}
```

### Response Body (200 OK — Not Released / Fallback)
```json
{
  "subject_id": "animal:3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "market_purpose": "EU_DEFORESTATION_REGULATION_BEEF",
  "policy_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "policy_version": 1,
  "reference_time": "2026-09-08T12:00:00Z",
  "knowledge_cutoff": "2026-09-08T12:00:00Z",
  "canonical_state": "OPTION_OPEN",
  "reversibility": "NOT_APPLICABLE",
  "release_disposition": "NOT_RELEASED",
  "explanation_text": null,
  "canonical_fallback": {
    "summary": "Resumo canônico baseado exclusivamente nas regras vigentes.",
    "reason_codes": ["SANITARY_CONFORMANCE_VERIFIED"]
  },
  "audit_id": "ai_explanation_audit:9ba65f64-5717-4562-b3fc-2c963f66afb1"
}
```

## Critérios de Aceite

1. **Permission no Catálogo:** `LIVESTOCK.MARKET_OPTION.EXPLAIN` cadastrada em `packages/livestock_application/authorization.py`, sem concessão padrão a `FRIGORIFICO` ou compradores.
2. **Isolamento de Tenant:** Tentativas de consultar animais de outra organização retornam `404` uniforme.
3. **Fail-Closed em Falha de Audit:** Falha de banco na gravação de audit retorna resposta sem texto liberado (`explanation_text: null`).
4. **Proteção HTTP:** Resposta sempre acompanhada de `Cache-Control: no-store` e `Pragma: no-cache`.
5. **Superfície Pública Congelada:** `tests/api/test_core_public_surface.py` atualizado para testar rota oculta quando flag desligada e exposta apenas quando flag ligada.
6. **Roteiro de Validação:** Entregue script executável em `apps/validacao/market_optionality_ai_explanation_api.py`.
7. **Frontend (UI):** Componente em `apps/web` consumindo o endpoint, apresentando claramente o status não decisional e o fallback canônico quando o texto de IA não estiver disponível.
