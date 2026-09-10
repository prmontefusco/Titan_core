# SPEC: Frontend — Fluxo Operacional de Animal

- **Nível:** STANDARD
- **Estado:** proposta
- **Decisão de Discovery:** PROCEED
- **Owner de produto:** Founder / Product Owner
- **Data:** 2026-09-10

## Problema e usuário

O Titan Livestock já possui backend, API e telas iniciais para animais, timeline,
tratamentos, elegibilidade, explicação comercial, lotes, governança e revisão. A
experiência atual ainda funciona mais como conjunto de telas técnicas do que como
um fluxo operacional guiado para validar a tese central do produto.

O usuário afetado neste primeiro corte é o operador Livestock autenticado que
precisa responder, a partir de um animal concreto:

- quem é o animal e em qual contexto operacional ele está;
- qual histórico relevante existe;
- quais avaliações/elegibilidades estão disponíveis;
- por que uma conclusão comercial foi emitida ou recusada;
- quais lacunas ou próximos passos aparecem sem o frontend inventar autoridade.

## Contexto e objetivo

Esta frente pertence ao Titan agora porque a rodada de correções da auditoria
adversarial foi encerrada e o frontend existente já tem base suficiente para virar
produto piloto incremental.

O objetivo é transformar o caminho de consulta de animal em uma experiência
operacional coesa, usando capacidades reais já entregues, sem criar regras de
negócio no navegador e sem ampliar autorização.

Resultado observável: um usuário autenticado consegue buscar um animal, entrar no
seu detalhe, entender identidade/status/contexto, navegar para timeline,
tratamento, elegibilidade/matriz/explicação comercial e retornar ao fluxo sem se
perder nem depender de conhecimento técnico da API.

## Fora de escopo

- dashboard geral da plataforma;
- landing page ou marketing;
- Organization switcher;
- capability/navigation manifest server-side;
- editor visual de Policies/Rules;
- Market Supply como fluxo principal inicial;
- ZKP, HTML/Wasm, VerificationBundle offline ou capacidades futuras;
- mudança em backend, contratos públicos, migrations, RBAC, RLS ou autorização;
- criação de decisão, avaliação, regra, fato ou elegibilidade no frontend;
- autosave offline ou formulário complexo novo.

## Comportamento e regras de negócio

O frontend deve permanecer apresentação e integração:

- autorização continua sendo decisão do backend;
- ausência de dado aparece como ausência, lacuna ou estado vazio, nunca como
  conclusão positiva;
- respostas `401`, `403`, `404`, `409` e `422` preservam estados distintos na UI;
- `OrganizationContext` fixo atual deve continuar visível quando relevante, sem
  sugerir troca livre de Organization;
- timelines devem preservar a semântica da fonte exposta pela API, sem fundir
  eventos heterogêneos em uma narrativa universal;
- explicações comerciais devem exibir conclusão, limitações e motivos recebidos
  da API, sem reinterpretar o resultado.

## Critérios de aceite

1. A página de busca de animais orienta o usuário para localizar um animal e
   diferencia carregando, vazio, erro, não autorizado e resultado encontrado.
2. A página de detalhe do animal apresenta identidade, propriedade/origem,
   status operacional, links de ação relevantes e contexto de Organization sem
   parecer uma tela técnica crua.
3. A navegação para timeline, tratamento, elegibilidade, matriz/explicação
   comercial e retorno ao detalhe é previsível e preserva o foco operacional do
   animal.
4. Estados de erro e autorização usam os componentes existentes de estado sempre
   que aplicável, sem duplicação visual desnecessária.
5. Nenhuma regra de elegibilidade, autorização, decisão ou explicação é duplicada
   no navegador.
6. O fluxo passa em testes automatizados de React/Vitest para os cenários
   principais e negativos.
7. O build, lint e testes do frontend passam.

## Plano técnico

- Reusar `apps/web/src/pages/AnimalSearch.tsx`,
  `apps/web/src/pages/AnimalDetail.tsx`,
  `apps/web/src/pages/AnimalTimeline.tsx`,
  `apps/web/src/pages/AnimalEligibility.tsx`,
  `apps/web/src/pages/CommercialExplanation.tsx`,
  `apps/web/src/pages/TreatmentForm.tsx` e componentes existentes.
- Reusar `ApplicationShell`, `DetailPage`, `AsyncStates` e padrões já criados no
  design package `docs/plans/TITAN_UI_ARCHITECTURE_V1_DESIGN_PACKAGE.md`.
- Criar componentes pequenos somente quando houver consumidor concreto dentro do
  fluxo de animal. Não criar design system genérico.
- Não alterar endpoints nem contratos de API no primeiro corte. Se a UX revelar
  lacuna de contrato, registrar nova decisão antes de implementar backend.
- Manter `RequestOptions` com `renewAccessToken` e o retry OIDC já implementado.
- Não adicionar dependência frontend sem justificativa e atualização deliberada
  do manifesto.

## Verificação e observabilidade

- `npm run test` em `apps/web`;
- `npm run build` em `apps/web`;
- `npm run lint` em `apps/web`;
- testes de página para busca, detalhe, navegação para timeline/elegibilidade e
  estados `401/403/404`;
- quando o corte virar BUILD, validar manualmente no navegador com API local e
  Keycloak, usando dados fictícios/semeados.

Não há nova observabilidade backend neste corte. Logs, auditoria e correlação
continuam nos serviços existentes.

## Documentação afetada

- esta SPEC deve mover para `approved/` quando aceita;
- o plano técnico detalhado pode nascer em `docs/plans/` somente após aprovação;
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md` deve ser atualizado quando o corte de
  frontend for efetivamente entregue e verificado.

## Riscos, alternativas e perguntas abertas

### Opções consideradas

1. **Começar por dashboard geral.** Rejeitada para este corte: alto risco de
   apresentar métricas sem jornada operacional validada.
2. **Começar por Market Supply.** Deferida: é valioso, mas carrega risco maior de
   privacidade, agregação, interpretação comercial e autorização.
3. **Começar pelo fluxo de animal.** Recomendado: usa capacidades reais já
   existentes, mostra a tese do Titan e mantém o escopo demonstrável.

### Trade-offs

- O fluxo de animal entrega menos impacto comercial agregado que Market Supply,
  mas reduz risco de overengineering e valida o núcleo narrativo do produto.
- Não criar Organization switcher limita a experiência multi-tenant, mas evita
  simular autorização que o backend ainda não expõe como contrato de navegação.
- Manter somente componentes concretos reduz velocidade aparente de construção de
  UI genérica, mas preserva simplicidade e revisabilidade.

### Recomendação

Prosseguir com um primeiro corte de BUILD focado em acabamento e coesão do fluxo:

`AnimalSearch → AnimalDetail → AnimalTimeline / AnimalEligibility / CommercialExplanation / TreatmentForm`.

### Decisão necessária

Product Owner deve aprovar se este fluxo de animal é o primeiro produto piloto de
frontend. Sem esse aceite, a SPEC permanece proposta e não autoriza implementação.
