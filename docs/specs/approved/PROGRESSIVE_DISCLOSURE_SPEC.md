# SPEC: Progressive Disclosure and Data Sharing

- **Nível:** CRITICAL
- **Estado:** aprovada como baseline arquitetural; BUILD/CUT F nao autorizado
- **Decisão de Discovery:** PROCEED para SPEC/DESIGN ONLY; ADR-0070 aceita; produção exige nova autorização de CUT F
- **Owner de produto:** Founder / Product Owner
- **Data:** 2026-08-28

## Problema e usuário

Market Supply Intelligence só é útil se compradores conseguirem ver capacidade agregada. Ao mesmo tempo, Organization é boundary de isolamento e relação comercial não concede acesso ao rebanho, Animal, propriedade, evidência, Evaluation ou Dossier.

## Contexto e objetivo

Esta SPEC propõe o desenho de progressive disclosure: visão agregada autorizada, intenção comercial, seleção candidata e disclosure detalhado sob escopo explícito. Não cria consent model, grant novo, API ou cross-tenant access.

## Fora de escopo

- implementação de grants, consentimentos ou data-sharing contracts;
- endpoint de agregação;
- acesso a Animal, Dossier ou Evidence de outra Organization;
- revogação implementada;
- exportação, redistribuição, inferência ou IA sobre dados compartilhados;
- CUT F.

## Comportamento e regras de negócio

Princípio aprovado: aggregate-first, identity-last.

Ausência de grant válido nega acesso. Relação comercial, Policy compartilhada, identificador conhecido, contrato buyer/supplier, existência de `CommercialDemand` ou participação na mesma supply network não implicam autorização.

Purposes iniciais aceitos:

- `MARKET_SUPPLY_AGGREGATE_ASSESSMENT`: autoriza somente superfície agregada aprovada.
- `MARKET_SUPPLY_CANDIDATE_DISCLOSURE`: autoriza disclosure detalhado apenas após contexto comercial/candidate-selection explícito e dentro de FieldScope/GrantScope.

Aggregate assessment nunca escala silenciosamente para candidate disclosure.

Fase A futura: visão agregada autorizada, com FieldScope mínimo, sem identificar produtores, propriedades, animais ou evidências.

Fase B futura: `CommercialDemand` aprovado, seleção candidata e disclosure detalhado apenas para sujeitos autorizados.

Nenhuma fase pode nascer de relação entre Organizations sem AuthorizationGrant/GrantAssessment/Purpose/Scope aplicáveis.

Produtor participa por opt-in explícito por padrão. O primeiro design deve privilegiar autorização limitada por buyer Organization, purpose, CommercialDemand/contexto, Policy/version, GrantScope, FieldScope, `valid_from` e `valid_until`.

Revogação é prospectiva: bloqueia novas consultas, reexecuções, novos relatórios e novo disclosure detalhado após sua eficácia. Material previamente entregue legitimamente não é apagado da história, mas não prova autorização atual.

Exportação e redistribuição são `DENY BY DEFAULT`.

`AggregationPrivacyPolicy` ou nome equivalente é conceito arquitetural aceito. Ele deve suportar pisos mínimos configuráveis e avaliação dinâmica de risco; não deve hard-codear threshold universal arbitrário.

Estágios mínimos de disclosure:

- Aggregate stage: comprador recebe somente informação agregada autorizada.
- Producer/property stage: disclosure posterior de produtor/propriedade mediante autorização.
- Candidate group stage: disclosure de lote/grupo selecionado.
- Individual animal stage: disclosure individual apenas quando finalidade, autorização e FieldScope justificarem.
- Evidence/artifact stage: Evidence, Dossier e VerificationBundle seguem mecanismos próprios.

## Critérios de aceite

- O design declara que ausência de grant nega.
- O design separa aggregate visibility de subject detail disclosure.
- O design preserva P-172, P-179, P-180, P-196, P-198 e P-200.
- Revogação prospectiva e exportação deny-by-default estão aceitas.
- O design exige controles contra reidentificação/differencing antes de API agregada cross-Organization.
- O threat model cobre filtros, pequenos grupos, consultas repetidas, diferença entre consultas, tempo, geografia e combinação de atributos.

## Plano técnico

Nenhum BUILD autorizado. Uma implementação futura exigirá ADR aceita, SPEC aprovada e plano para:

- AccessPurpose `MARKET_SUPPLY_AGGREGATE_ASSESSMENT` e `MARKET_SUPPLY_CANDIDATE_DISCLOSURE`;
- GrantScope;
- FieldScope de agregado e detalhe;
- audit tier e DataAccessRecord;
- resposta uniforme para inexistente/invisível;
- query model com isolamento e limiares;
- roteiro executável em `apps/validacao`.

## Verificação e observabilidade

Verificação desta SPEC: revisão documental. Verificação futura: testes de autorização, RLS, ausência de vazamento por agregação, revogação, purpose mismatch, FieldScope e auditoria.

## Documentação afetada

- `docs/plans/PROGRESSIVE_DISCLOSURE_DATA_SHARING_DESIGN_PACKAGE.md`
- `docs/adr/0070-progressive-disclosure-e-visibilidade-agregada.md`

## Riscos, alternativas e perguntas abertas

Riscos: reidentificação por filtros, inferência por repeated queries, vazamento de existência, autorização parcial apresentada como integral.

Decisões resolvidas pelo Product Owner:

- Dois AccessPurposes iniciais separados.
- Participação de produtor é opt-in por padrão.
- Reuso/composição de Core Authorization antes de qualquer consent model Livestock.
- Revogação é prospectiva.
- Exportação/redistribuição é deny-by-default.
- AggregationPrivacyPolicy é conceito aceito, sem threshold global arbitrário.

HUMAN REVIEW restante:

- Autorizar CUT F e cada API/persistência concreta.
- Aprovar FieldScope/GrantScope técnicos.
- Aprovar perfil concreto de AggregationPrivacyPolicy e audit tier antes de produção cross-Organization.
