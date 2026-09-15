# Market Supply — Decisão: piloto buyer-facing ou parque consciente

**Data:** 15 de setembro de 2026
**Tipo:** decisão de produto, não Discovery — o ciclo `IDEA → DISCOVERY → DECISION → SPEC → PLAN → BUILD`
já foi percorrido extensivamente para esta capacidade (NEXT-12, CUT A a F3.5V, ADRs 0069-0072). O que falta
não é engenharia; é a decisão que `docs/livestock/LIVESTOCK_CONTINUITY_ASSESSMENT.md` §8 já registrou como
prioridade 5, ainda não tomada.

---

## Contexto

Market Supply é a capacidade de um comprador (frigorífico) consultar, de forma agregada e sem identificar
indivíduos, se um conjunto de fornecedores tem oferta que atenda a um perfil de mercado — sem acessar dados
crus de nenhum produtor. Foi construída em dezenas de cortes incrementais (`docs/CHECKLIST_DE_IMPLEMENTACAO.md`,
seção NEXT-12), cada um pequeno, testado e documentado, culminando em **F3.5U**: um teste de integração
contra PostgreSQL real prova o fluxo completo (grant → população candidata autorizada → readiness →
privacidade → auditoria durável → resposta pública) com dados sintéticos, e **F3.5V**: uma primeira tela de
frontend (`apps/web/src/pages/MarketSupplyAggregate.tsx`) consumindo o contrato público.

## O que já está pronto e testado (verificado nesta sessão)

- Portão de autorização bilateral (`AuthorizationGrant`), com releitura fresca no instante do release para
  evitar corrida de revogação (TOCTOU-hardened, F-05).
- Portão de privacidade de agregação (coorte mínima, precisão geográfica, filtros excessivos, proteção
  contra differencing por consulta repetida) — `packages/livestock_application/market_supply_privacy.py`.
- Trilha de auditoria durável, owner-scoped, RLS-protegida, append-only.
- Idempotência semântica via o `IdempotencyService` do Core.
- Resolução de população candidata restrita ao escopo autorizado pelo grant (nunca lookup global de
  Animal).
- Payload público com schema allow-listed (nenhum ID individual, nenhuma estrutura fora do aprovado).
- Endpoint HTTP (`POST /v1/livestock/market-supply/aggregate-assessments`) atrás de **duas** feature
  flags independentes, ambas desligadas por padrão (confirmado agora em `apps/api/main.py:135` e
  `apps/api/livestock_market_supply.py:145`).

## O que falta — e não é código, é decisão

Três lacunas concretas, verificadas agora no código, nenhuma delas resolvível por "ligar a flag":

1. **Não existe mecanismo de opt-in do produtor.** ADR-0070 declara como princípio que "participação de
   produtor é opt-in por padrão", mas busquei em todo `packages/livestock_application/market_supply*.py` e
   em `apps/web/src/pages/MarketSupplyAggregate.tsx` e **não há nenhum fluxo onde um produtor consinta** em
   ter seus animais incluídos numa consulta agregada de um comprador. O mecanismo de autorização hoje
   depende de um `AuthorizationGrant` — mas quem cria esse grant, e se o produtor sabe que está concedendo
   acesso agregado (e não só compartilhamento de Policy contratual, o uso original desse mesmo grant em
   BuyerPolicy), não está desenhado.
2. **Nenhum perfil de privacidade de produção existe.** `load_aggregation_privacy_profile()`
   (`market_supply_privacy.py:101`) recusa rodar sem configuração explícita — de propósito, por decisão
   registrada em F3.5D ("sem defaults produtivos hardcoded"). Isso significa que decidir os números reais
   (tamanho mínimo de coorte, limite de precisão geográfica, janela de repeated-query) é uma decisão de
   privacidade/negócio que ainda não foi tomada, não um parâmetro técnico a preencher.
3. **Nenhuma permissão concedida por padrão.** `MARKET_SUPPLY.AGGREGATE_ASSESS` existe no catálogo mas não
   está em nenhum papel padrão (`apps/seed/*.py`, confirmado agora) — decisão deliberada de F3.5B. Quem
   receberia essa permissão (comprador? Um papel novo?) não foi decidido.

## Opções

**A — Comprometer-se com um piloto buyer-facing real.**
Exige, antes de qualquer código novo: (1) desenhar e construir o fluxo de opt-in do produtor — provavelmente
o maior pedaço de trabalho restante, porque é UX e semântica de consentimento, não só backend; (2) decidir
os valores reais do perfil de privacidade, com alguém que pense em termos de risco de reidentificação, não
só engenharia; (3) decidir quem recebe `MARKET_SUPPLY.AGGREGATE_ASSESS` e como esse acesso é solicitado/
aprovado; (4) só então ligar as duas feature flags em ambiente controlado com um comprador real.

**B — Parque consciente.**
Documentar que a capacidade está pronta e testada, mas que não há demanda validada de comprador nem decisão
de privacidade que a sustente — e não tocar mais nela até que uma delas apareça. `docs/product/
MARKET_SUPPLY_INTELLIGENCE_CONCEPT.md` já carrega o status "NOT AUTHORIZED FOR PRODUCTION" desde 28/08/2026;
esta opção apenas reconhece que isso continua verdadeiro.

**C — Piloto muito mais estreito, sem opt-in genérico.**
Em vez de um mecanismo de opt-in reutilizável, pedir consentimento manual e específico para um piloto único
com um comprador e um punhado de produtores já conhecidos (ex.: os mesmos produtores/CAR de MS já usados
nas validações territoriais). Evita construir UX de opt-in genérica antes de saber se há demanda real —
mas ainda exige decisão de privacidade (item 2) e de permissão (item 3), e o consentimento "manual" precisa
de registro auditável equivalente, não pode ser verbal.

## Trade-offs

| Opção | A favor | Contra |
|---|---|---|
| A — piloto completo | Sinaliza compromisso comercial; usa tudo que já foi construído | Maior esforço restante é justamente o que não foi feito ainda (opt-in real); risco de construir UX de consentimento sem comprador confirmado |
| B — parque | Nenhum risco novo; reconhece honestamente a falta de demanda validada (coerente com NR-8: GTA/PNIB foram identificados como wedge melhor que Market Supply) | Abandona um investimento de engenharia real; capacidade fica "pronta e esquecida" |
| C — piloto estreito | Testa demanda real com esforço mínimo de opt-in | Ainda exige as decisões 2 e 3; consentimento manual auditável não é trivial de improvisar com qualidade |

## Recomendação

Não tenho base para recomendar A, B ou C com confiança — é uma decisão comercial (existe comprador
interessado? existe pressão para provar essa capacidade agora?) que depende de informação que não está no
repositório. O que registro com confiança, a partir do código: **nenhuma das três opções está a uma "ligar
a flag" de distância.** A opção mais barata de testar sem comprometer arquitetura é C, mas mesmo ela exige
decisão humana sobre privacidade (item 2) antes de qualquer linha de código nova.

## Decisão necessária

1. A, B ou C acima (ou nenhuma — manter como está e revisitar depois).
2. Se A ou C: quem decide os valores do perfil de privacidade (item 2) — isso não deveria ser uma escolha
   de engenharia.
3. Se A ou C: existe already um comprador/produtor reais para o piloto, ou isso ainda depende de validação
   comercial fora deste repositório?

---

## Decisão tomada em 15/09/2026

**Opção C (piloto estreito) escolhida como direção**, mas com as duas perguntas de acompanhamento
respondidas de um jeito que impede o início de SPEC/BUILD agora:

- **Contraparte real:** ainda não existe comprador nem produtores identificados — depende de validação
  comercial fora deste repositório.
- **Decisor de privacidade:** ainda não definido quem decide os valores reais do perfil.

**Consequência, por `AGENTS.md` ("nunca criar abstração para necessidade futura sem uso atual"):**
desenhar ou construir o mecanismo de consentimento manual/auditável agora seria exatamente essa abstração
especulativa — não há comprador, não há produtor, não há valores de privacidade para o mecanismo servir.
Diferente de GTA (reaproveita capacidade já existente, usável por qualquer operador hoje), o piloto estreito
de Market Supply **depende estruturalmente** de uma contraparte real para ter qualquer uso.

**Estado resultante: PARQUEADO COM DIREÇÃO DEFINIDA, não DEFER genérico.** A diferença importa: não é "não
sabemos o que fazer" (isso seria B) — é "sabemos que quando a validação comercial confirmar comprador e
produtores, e alguém for designado para decidir privacidade, a Opção C é o caminho, e o código para o
piloto estreito de consentimento manual pode começar direto em SPEC, sem nova Discovery."

**Gatilho explícito para retomar:** (1) comprador e ao menos um produtor real confirmados fora deste
repositório, **e** (2) uma pessoa/processo designado para decidir os valores do perfil de privacidade. Os
dois precisam existir antes de reabrir esta frente — nenhuma implementação é autorizada por este registro
até lá.
