# ADR-0072 - Market Supply audit history visibility for differencing

**Data:** 2026-09-01  
**Estado:** ACCEPTED WITH CHANGES
**Escopo:** Titan Livestock Market Supply + Core audit/RLS usage

## Contexto

ADR-0069 define Market Supply Intelligence como analise nao regulatoria.
ADR-0070 define progressive disclosure com `aggregate-first, identity-last`.
ADR-0071 exige historico suficiente para semantic differencing antes de qualquer
API agregada cross-Organization.

O audit independente F-09 identificou dois riscos:

1. `audit_owner_organization_id` era fornecido pelo caller interno sem validacao.
2. A tabela `core_audit.market_supply_query_audit_records` usa RLS owner-only;
   se o endpoint F3.5 rodar exclusivamente sob contexto da Organization
   compradora, a busca de historico relacionado para differencing nao enxerga os
   audit records pertencentes aos produtores/contribuintes.

O primeiro risco ja foi fechado no codigo: `MarketSupplyAggregateGateRequest`
exige que `audit_owner_organization_id` seja igual a
`authorization_request.owner_organization_id`.

Resta decidir como uma futura API buyer-facing podera avaliar differencing usando
historico auditado sem liberar raw audit rows para a Organization compradora.

## Problema

Market Supply precisa combinar duas exigencias que puxam em direcoes opostas:

- privacy/differencing precisa consultar historico semanticamente relacionado;
- raw audit de Market Supply pode revelar ausencia, invisibilidade, supressao,
  revogacao, membership ou filtros sensiveis.

Permitir que o buyer leia diretamente `market_supply_query_audit_records` torna
o proprio audit um oracle. Por outro lado, rodar todo o workflow apenas sob o
contexto RLS do buyer pode deixar o historico vazio e neutralizar a protecao de
differencing.

## Decisao Proposta

Manter `MarketSupplyQueryAuditRecord` com RLS runtime owner-only por padrao.

F3.5 nao deve expor raw audit rows ao comprador. A avaliacao de differencing MUST
ser executada por pipeline de aplicacao mediado por contextos
owner/contributor-scoped. Qualquer servico ou role capaz de ler historico de
audit fora desses limites owner-scoped de RLS exige ADR separada e aprovacao
explicita de seguranca.

O comprador recebe somente a projecao publica uniforme resultante.

Em termos de fronteira:

```text
Buyer request context
  |
  v
Authorization / contribution resolution
  |
  v
Per-owner auditable evaluation context
  |
  v
Owner-scoped query history fingerprints
  |
  v
History completeness assessment
  |
  v
DisclosureDecision
  |
  v
Durable owner-owned AuditRecord
  |
  v
Uniform buyer public response
```

Essa decisao preserva:

- `DATA ACCESS != DATA CONTRIBUTION != DERIVED KNOWLEDGE != DISCLOSURE`;
- raw audit visibility diferente de disclosure agregado;
- owner-only RLS como default seguro;
- audit minimization;
- differencing baseado em historico real, nao em historico invisivel por RLS.

## Invariantes

- `audit_owner_organization_id` deve ser a owner Organization da autorizacao
  avaliada.
- Raw `MarketSupplyQueryAuditRecord` nao e payload buyer-facing.
- Buyer authorization para solicitar aggregate assessment nao implica permissao
  para ler raw audit history.
- Related query history usado por privacy/differencing deve vir de registros
  persistidos e visiveis ao contexto autorizado que os avalia.
- O resultado publico continua sendo `RELEASED` ou `NOT_RELEASED` conforme
  `DisclosureDecision` e resposta uniforme.
- Falha em obter historico requerido deve falhar fechado ou produzir
  `NOT_RELEASED`; nao deve liberar agregado como se nao houvesse historico.
- Uma decisao `RELEASED` exige cobertura demonstravelmente completa do historico
  de queries para o escopo requerido pelo privacy profile ativo.
- Incapacidade de demonstrar completude do historico requerido MUST falhar
  fechado, inclusive quando o historical reader executa sem erro mas retorna
  historico incompleto.
- Uma unica query buyer-facing pode envolver multiplas owner Organizations; cada
  contribuicao usada na decisao deve estar coberta por contexto auditavel de sua
  owner Organization e correlacionada a mesma assessment.
- Differencing nao pode consultar apenas owners presentes na query atual quando
  o privacy profile exigir historico semanticamente relacionado mais amplo.
- Desabilitar a API de Market Supply nao remove a capacidade interna autorizada
  de auditar/verificar registros historicos.

## Alternativas

### A. Buyer-visible raw audit rows

Permitir RLS bilateral ou requester-visible em
`market_supply_query_audit_records`.

Beneficio: endpoint buyer poderia consultar historico diretamente.

Risco: transforma audit em oracle de membership, supressao, revogacao e
differencing. Contraria o principio `aggregate-first, identity-last`.

Status: rejeitada para F3.5.

### B. Owner-only raw audit + application-mediated differencing

Manter audit owner-only e permitir que o pipeline interno avalie historico por
owner/contribuinte autorizado, retornando apenas a resposta publica uniforme ao
buyer.

Beneficio: preserva RLS conservador, permite differencing real e evita raw audit
buyer-facing.

Risco: F3.5 precisa orquestrar multiplos contextos autorizados com cuidado,
incluindo rechecagem de revogacao antes do release.

Status: aceita para F3.5.

### C. Dedicated audit/security role with broad read

Criar role operacional para ler todo historico de Market Supply e alimentar a
avaliacao de privacy.

Beneficio: simplifica consulta de historico.

Risco: cria nova superficie privilegiada, exige governanca de credenciais,
observabilidade, segregacao e retenção. Pode ser apropriado futuramente, mas e
mais amplo que o necessario para o primeiro F3.5.

Status: adiada; exige decisao operacional separada se escolhida.

### D. Store buyer-owned duplicate audit records

Persistir uma copia owner-owned e outra buyer-owned de cada query.

Beneficio: buyer context enxerga seu proprio historico.

Risco: duplica audit, aumenta risco de divergencia, amplia superficie de
metadata sensivel e complica revogacao/retencao.

Status: rejeitada para F3.5.

## Consequencias

- O schema atual owner-only continua valido.
- F3.5 precisa tratar Candidate Population como composicao de contribuicoes
  owner-scoped, nao como consulta global executada sob o buyer.
- O repositório de audit pode continuar retornando apenas fingerprints para
  differencing, sem payload sensivel.
- F3.5 deve correlacionar query global, contribuicoes owner-scoped,
  `DisclosureDecision` e resposta publica por uma mesma assessment/correlation,
  sem exigir nesta ADR que existam N registros fisicos duplicados.
- API buyer-facing futura continua bloqueada ate existir orquestracao
  produtiva testada para contextos owner-scoped e grants aprovados.
- Testes de F3.5 devem provar que historico de differencing e considerado mesmo
  quando raw audit rows nao sao visiveis ao buyer.

## Gates Automatizados Necessarios

- buyer nao consegue ler raw `MarketSupplyQueryAuditRecord` owner-owned;
- owner consegue ler seu audit record;
- workflow interno consegue alimentar `previous_queries` com fingerprints
  owner-scoped;
- workflow interno demonstra completude do historico requerido pelo privacy
  profile ativo antes de qualquer `RELEASED`;
- query relacionada que passaria isoladamente e bloqueada por differencing;
- falha, indisponibilidade ou incompletude do historical query reader gera
  `NOT_RELEASED` ou erro interno fail-closed, nunca `RELEASED`;
- query multi-owner nao pode produzir resultado publicavel quando qualquer
  contribuicao usada pela assessment nao possui cobertura auditavel owner-scoped;
- audit record de non-release e persistido antes da resposta publica;
- resposta publica nao revela se o bloqueio veio de RLS, historico,
  differencing, revogacao ou ausencia.

## Mudancas Exigidas no Aceite

1. Alternativa B aceita para F3.5.
2. Nenhuma role/servico com leitura ampla de audit e autorizado por esta ADR.
3. Completude do historico requerido vira invariante explicito de release.
4. Correlacao multi-owner entre query, contribuicoes, audit context,
   `DisclosureDecision` e resultado publico deve ser verificavel.
5. Historico requerido ausente ou incompleto produz `NOT_RELEASED` ou falha
   fechada, nunca `RELEASED`.

## Decisoes Humanas Necessarias

Nenhuma decisao humana adicional permanece nesta ADR. F3.5 ainda possui gates
proprios no release package, incluindo permission, fonte produtiva da Candidate
Population, privacy profile e contrato HTTP.
