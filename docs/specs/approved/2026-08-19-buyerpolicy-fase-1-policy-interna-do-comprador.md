# BuyerPolicy — Fase 1: Policy interna do comprador (`INTERNAL_ONLY`)

- **Nível:** CRITICAL
- **Estado:** proposta
- **Decisão de Discovery:** PROCEED (para Fase 0), condicionado à aceitação da
  ADR-0064
- **Owner de produto:** Founder / Product Owner
- **Data:** 2026-08-19

> Esta SPEC **não autoriza implementação**. Ela registra os critérios de aceite da
> Fase 1 para quando a ADR-0064 for formalmente aceita e a SPEC promovida a
> `approved/`. Nenhuma API, migration, capability ou UI é criada por este
> documento.

## Problema e usuário

Uma Organization compradora (ex.: frigorífico) possui critérios internos de
elegibilidade — próprios, não regulatórios — para aceitar um lote ou animal já
visível a ela. Hoje não há forma governada de declarar esse critério sem
misturá-lo a uma Policy regulatória (ADR-0049) ou criar lógica particular fora do
Titan. A Discovery de 2026-08-15 e a ADR-0064 concluíram que o mecanismo genérico
de `Policy`/`Rule` (ADR-0038/ADR-0043) já cobre essa necessidade; falta apenas
declarar e testar a fronteira do primeiro incremento seguro.

## Contexto e objetivo

A ADR-0064 decide que a Fase 1 (`BuyerPolicy`) é: `Policy` própria da Organization
compradora, `RuleIdentity`s exclusivamente `source_type=INTERNAL_POLICY`,
avaliação restrita a sujeitos/Facts já visíveis à própria Organization, resultado
como `Evaluation` isolada com boundary `INTERNAL_ONLY` explícito, nunca fundida com
`MarketEligibilityPurpose`/`MarketProfile` (ADR-0044).

Resultado observável esperado: uma Organization compradora consegue criar,
publicar, adotar e avaliar sua própria Policy interna reutilizando
`/v1/rule-governance` e o serviço de avaliação já existentes, com o resultado
claramente rotulado como interno e isolado de qualquer outra Organization.

**Nota de vocabulário (ver ADR-0064 §3):** "Organization compradora" é o papel de
negócio que motivou esta capacidade, não um tipo técnico. Nenhum mecanismo do
Titan distingue hoje uma Organization compradora de qualquer outra; as
`RULE_GOVERNANCE_*` já existentes são concedidas por `Role`/`Permission` dentro do
`OrganizationContext` de cada Organization, sem noção de segmento comercial.
Portanto, esta SPEC implementa um padrão disponível a **qualquer** Organization
com essas permissions sobre seus próprios dados — não introduz nem pressupõe um
gate exclusivo de "comprador". Restringir formalmente quem pode publicar
BuyerPolicy é questão de produto adiada (ADR-0064 §23), fora do escopo desta SPEC.

## Fora de escopo

- `RuleSourceType.CONTRACT` / critério bilateral pactuado entre Organizations;
- qualquer `Sharing`, `AuthorizationGrant`, `AccessPurpose` ou `FieldScope` novos;
- avaliação de dado de qualquer Organization além da que possui a Policy;
- `DecisionProposal`, `Decision` ou `DecisionAuthorityProfile` de BuyerPolicy;
- composição/agregação entre Policy regulatória e BuyerPolicy;
- sujeitos ou fact types além dos já usados pela elegibilidade Livestock;
- DSL livre de autoria, importação/integração externa de critério;
- tela de produto (UI); esta SPEC cobre apenas contrato técnico/API;
- alteração de `DOMAIN.md` ou `ARCHITECTURE.md`.

## Comportamento e regras de negócio

1. Uma Organization compradora cria uma `RuleIdentity` própria com
   `source_type=INTERNAL_POLICY`, usando `RULE_GOVERNANCE_CRIAR` sob seu próprio
   `OrganizationContext` — caminho já existente em `/v1/rule-governance`.
2. Publica uma `RuleVersion` usando apenas templates/fact types Livestock já
   autorizados (reaproveita `RuleCondition` existente) via
   `RULE_GOVERNANCE_PUBLICAR`.
3. Cria e publica sua própria `Policy` (`organization_id` = compradora) e registra
   `RuleAdoption` via `RULE_GOVERNANCE_ADOTAR`.
4. **Antes de aceitar publicação/adoção**, o sistema verifica que todas as
   `RuleIdentity`s referenciadas pelas `RuleVersion`s adotadas por aquela `Policy`
   declaram `source_type=INTERNAL_POLICY`. Mistura de origem é rejeitada com
   motivo explícito, não silenciosamente aceita.
5. A Organization compradora aciona avaliação da sua Policy sobre um sujeito já
   autorizadamente visível a ela (mesma Organization proprietária dos Facts).
   Produz uma `Evaluation` isolada da matriz regulatória.
6. A resposta técnica da `Evaluation` de BuyerPolicy inclui, de forma explícita:
   origem (`INTERNAL_POLICY`), boundary (`INTERNAL_ONLY`), Organization
   proprietária da Policy e Organization ativa no pedido.
7. Nenhuma outra Organization consegue listar, ler, avaliar ou inferir a
   existência da Policy, das Rules, da Evaluation ou das razões de outra
   Organization compradora.
8. Revogar ou substituir a `RuleVersion`/`Policy` é prospectivo: `Evaluation`s
   históricas não são reescritas; nova avaliação após revogação relata ausência
   explícita de Policy aplicável, nunca reaproveita versão anterior
   silenciosamente.

## Critérios de aceite

1. Uma Policy do comprador é distinguível de Policy regulatória na resposta
   técnica, com origem e boundary legíveis (ADR-0064 Decisão 2 e 4).
2. Publicação/adoção de `Policy` com `RuleIdentity`s de `source_type` heterogêneo
   é rejeitada com motivo estruturado (ADR-0064 Invariante 3).
3. Nenhuma capability nova de autorização é introduzida; apenas
   `RULE_GOVERNANCE_CRIAR/PUBLICAR/ADOTAR/LER` e a capability de avaliação já
   existente (nomeada explicitamente nesta SPEC durante o PLAN).
4. Nova versão ou revogação de `RuleVersion`/`Policy` não reescreve `Evaluation`
   histórica.
5. Uma Organization não consegue criar, listar, avaliar ou inferir dado da Policy
   de outra Organization sem relacionamento autorizado (que não existe nesta
   fase).
6. `Evaluation` de BuyerPolicy nunca aparece em resposta de
   `MarketEligibilityPurpose`/matriz da ADR-0044, e vice-versa.
7. `Evaluation` preserva Policy/Rules/versões/snapshot/tempos exigidos pelos
   contratos já vigentes (ADR-0048/ADR-0050/ADR-0051).
8. O roteiro em `apps/validacao` demonstra: caso positivo, caso negativo, negação
   segura para Organization sem relação, isolamento entre comprador A e comprador
   B, rejeição por mistura de origem, e comportamento pós-revogação.
9. Resposta a acesso fora do escopo da Organization solicitante é uma negação
   segura e explícita — nunca uma falha silenciosa nem uma lista vazia ambígua —
   mas **não distingue**, para quem não tem acesso, recurso inexistente de
   recurso existente porém invisível (`DOMAIN.md` P-198, `ARCHITECTURE.md`,
   ADR-0027). O código de status exato segue o contrato já vigente em
   `/v1/rule-governance`: `403`/`PERMISSAO_AUSENTE` quando falta `Permission` no
   próprio `OrganizationContext` do solicitante (não revela nada sobre um
   recurso específico), e `404`/`RECURSO_NAO_ENCONTRADO` uniforme quando o
   recurso pedido está fora do `organization_id` do solicitante — o mesmo código
   usado hoje para recurso genuinamente inexistente. Esta SPEC não introduz um
   terceiro sinal que diferencie "existe mas não é seu" de "não existe".

## Plano técnico

A preencher no PLAN, após aprovação desta SPEC. Deve, no mínimo:

- nomear a capability de avaliação reaproveitada (ADR-0064 §9/§21.1) e confirmar
  que já aceita `organization_id` não-operador;
- desenhar o teste de homogeneidade de `source_type` por Policy adotada — local
  mais provável: `rule_governance_service.py` (validação antes de
  publicar/adotar) ou `market_eligibility`/serviço de avaliação equivalente;
- confirmar o contrato de resposta técnica que expõe boundary/origem — provável
  extensão de resposta de `/v1/rule-governance` ou de um endpoint de avaliação
  próprio, a decidir no PLAN sem introduzir rota fora do padrão REST já em uso
  (ADR-0027);
- não introduzir migration nova a menos que a verificação de homogeneidade exija
  índice ou consulta que hoje não existe — decisão do PLAN, não desta SPEC;
- impacto em tenancy: nenhum, por construção (sem travessia de Organization).

## Verificação e observabilidade

- testes automatizados: positivo, negativo (Rule não atendida), mistura de
  origem rejeitada, negação segura (404 uniforme) entre Organizations sem
  relação, revogação prospectiva, ausência pós-revogação;
- roteiro manual/API em `apps/validacao` cobrindo os cenários do critério de
  aceite 8;
- nenhum log ou trace deve conter payload de Fact ou Evidence além de
  identificadores opacos e códigos, conforme `ARCHITECTURE.md` (Governança e
  ciclo de vida de dados).

## Documentação afetada

- ADR-0064 (esta SPEC depende da sua aceitação formal);
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`, somente quando houver entrega
  efetivamente implementada e validada (não nesta etapa de Discovery/SPEC);
- possível nota em `DOMAIN.md` apenas se o PLAN revelar necessidade de formalizar
  `recognition_boundary` — não antecipado por esta SPEC (ver ADR-0064 §21).

## Riscos, alternativas e perguntas abertas

Riscos herdados da Discovery (mistura semântica, autoria sem governança) são
mitigados pelos invariantes da ADR-0064 e pelos critérios de aceite 1–2 acima.

Perguntas ainda abertas para o PLAN, não bloqueantes para aprovar esta SPEC:

1. Nome exato da capability de avaliação a reaproveitar (ADR-0064 §9).
2. Se a verificação de homogeneidade de origem deve ocorrer na publicação da
   `RuleVersion`, na adoção pela `Policy`, ou em ambas (defesa em profundidade).
3. Formato exato do campo de boundary na resposta técnica (string controlada vs.
   enum específico) — deve ser decidido no PLAN sem exigir migration de
   `DOMAIN.md`.

Esta SPEC só pode ser promovida a `approved/` após a ADR-0064 mudar de `PROPOSTA`
para `ACEITA`.
