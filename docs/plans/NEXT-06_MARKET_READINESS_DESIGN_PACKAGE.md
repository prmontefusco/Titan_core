# NEXT-06 — Market Readiness e seleção de lote: Design Package

**Data:** 12 de agosto de 2026  
**Estado:** AGUARDANDO REVISÃO HUMANA  
**Escopo:** projeção operacional derivada para um perfil fictício de mercado; não cria nova elegibilidade, decisão ou autorização.

## 1. Objetivo

Permitir responder, para uma população explícita de animais:

> “Sob esta finalidade, Policy, `reference_time` e `knowledge_cutoff`, quantos animais têm uma conclusão Titan utilizável; quais não têm; quais ainda exigem informação ou reavaliação; e quais candidatos podem compor uma lista de tamanho solicitado?”

O resultado é uma **leitura operacional**. Não responde que uma operação foi autorizada, que um lote foi reservado, que um Animal passou a possuir um atributo `eligible`, nem que autoridade externa reconhecerá o resultado.

O primeiro caso permanece sintético:

```text
MARKET_TEST_A / STANDARD
Recognition boundary: INTERNAL_ONLY
Result boundary: MARKET_ELIGIBILITY_ASSESSMENT_NOT_EXPORT_AUTHORIZATION
```

## 2. Decisão proposta

**Introduzir um read model transitório de Application, derivado de Decisions/Evaluations imutáveis, e uma seleção determinística de candidatos sobre esse read model.**

Não criar nesta etapa:

- `MarketReadiness` ou `LotSelection` persistidos;
- nova `Decision`, `Evaluation`, Policy, Rule, Dossier ou motor de regras;
- campo de elegibilidade no Animal ou no `LivestockLot`;
- reserva, alteração de `LotMembership`, criação de lote comercial ou operação de venda;
- composição de Animal + estabelecimento + operação (NEXT-04);
- reavaliação em massa, fila ou impacto por mudança normativa (NEXT-07);
- API, migration, integração SISBOV/Odoo ou perfil de mercado real no Corte 1.

O núcleo deve consumir a mesma semântica já preservada por `Decision`, `Evaluation`, `FactSnapshot`, `NormativeBasisSnapshot`, coverage dimensional e `DecisionReason`. A projeção apenas as organiza para uso operacional.

**Invariante do Corte 1:** o NEXT-06 nunca reexecuta Rules nem reconsidera a correção semântica de uma `Decision` existente. Ele verifica somente identidade, contexto, anchors preservados e utilidade daquela conclusão para a projeção solicitada.

```text
Decisions imutáveis por Animal
          + contexto explícito
                    ↓
        MarketReadiness read model
                    ↓
  contagens, gaps agregados e candidatos
                    ↓
    seleção determinística (sem reserva)
```

## 3. Contexto de leitura obrigatório

Não existe readiness sem contexto. Toda consulta deve declarar ou resolver de maneira verificável:

| Campo | Papel |
|---|---|
| Organization | isolamento da população e das evidências |
| finalidade/perfil de mercado | pergunta normativa; nunca atributo do Animal |
| Policy exata e versão | regra sob a qual a conclusão é lida |
| `reference_time` | instante factual da pergunta |
| `knowledge_cutoff` | limite de conhecimento aceito |
| recognition boundary | limite de reconhecimento da conclusão |
| população | lista explícita de Animals ou membros vigentes de um lote existente |

Uma `Decision` só pode contribuir como **ATUAL** quando sua Evaluation possui o mesmo sujeito, finalidade, Policy/versão, `reference_time`, `knowledge_cutoff` e boundary requeridos. Uma Decision de contexto diferente não é reinterpretada, sobrescrita ou escolhida por “mais recente”.

Se uma Decision histórica existe, mas a Policy agora resolvida para o contexto é outra, a entrada é `REAVALIACAO_NECESSARIA`. Este é estado da projeção, não `DecisionResult` e não evidência de reprovação.

Ausência de Decision correspondente, snapshot normativo legado ausente, coverage insuficiente, `DecisionResult.INDETERMINADA`, contexto ambíguo ou requisito de outro sujeito produzem estado não conclusivo e razão explícita. Não entram como candidatos positivos.

## 4. Classificação da projeção

O read model separa resultado histórico, atualidade e utilidade operacional:

| Estado de readiness | Critério | Pode ser candidato no Corte 1? |
|---|---|---|
| `READY` | Decision `APROVADA`, contexto exato, coverage e base normativa preservadas, `INTERNAL_ONLY` | Sim |
| `NOT_READY` | Decision `REJEITADA` no contexto exato | Não |
| `CONDITIONED` | Decision `APROVADA_COM_RESTRICOES` ou dependência de outro sujeito | Não |
| `INDETERMINATE` | Decision indeterminada, ausência/gap material, coverage/snapshot insuficiente ou contexto não conclusivo | Não |
| `REASSESSMENT_REQUIRED` | conclusão histórica existe, mas não corresponde à Policy/contexto atualmente solicitado | Não |
| `NOT_EVALUATED` | não há Decision correspondente para o Animal | Não |

`READY` significa *ready for candidate selection under this Titan assessment context only*: a conclusão Titan individual satisfaz a Policy sintética no contexto pedido. Nunca equivale a `EXPORT_ALLOWED`, habilitação de estabelecimento, reconhecimento externo, reserva comercial ou autorização de operação.

Os motivos devem manter links ou identificadores para a `Decision`/`Evaluation` que os originaram; os gaps não são duplicados como entidades. A agregação por código só produz uma contagem e exemplos de referência, sem apagar a explicação individual.

## 5. Readiness de portfólio e de lote existente

Uma população pode ser:

1. uma coleção explícita de `animal_id`; ou
2. os membros vigentes de um `LivestockLot`, no instante da consulta.

O `LivestockLot` existente continua sendo somente agrupamento temporal de animais. A consulta não altera membership e não confere ao lote uma Decision nova. Para o primeiro corte, “readiness do lote” quer dizer a distribuição dos membros atuais sob um único contexto de mercado.

Saída conceitual:

```text
MarketReadinessReport
  context: profile, policy/version, reference_time, knowledge_cutoff, boundary
  population: total
  counts:
    READY / NOT_READY / CONDITIONED / INDETERMINATE /
    REASSESSMENT_REQUIRED / NOT_EVALUATED
  gap_summary:
    código, contagem, referências de animais
  entries:
    animal, readiness state, Decision/Evaluation refs, gaps/reasons
```

A lista `entries` é projeção de leitura; a quantidade agregada precisa sempre indicar o mesmo contexto que gerou cada entrada. É proibido somar Decisions de Policies, tempos, perfis ou boundaries diferentes como se descrevessem uma única readiness.

## 6. Seleção de candidatos

A seleção inicial recebe um `MarketReadinessReport` homogêneo e uma quantidade desejada. Ela:

- inclui apenas entradas `READY`;
- ordena de modo determinístico por identificador estável do Animal, salvo ordenação de negócio aprovada em incremento próprio;
- declara `selection_basis = STABLE_SUBJECT_ID`, versão `1`, para que mudança futura de algoritmo não altere silenciosamente o significado da lista;
- devolve até a quantidade solicitada, a quantidade disponível, a insuficiência quando houver e a mesma referência de contexto;
- explica por que cada incluído pode ser usado como candidato e por que os demais não entraram;
- não cria `LivestockLot`, não grava seleção, não reserva Animal e não realiza venda, transferência ou despacho.

Exemplo:

```text
Pedido: 500 candidatos para MARKET_TEST_A v1
Disponíveis READY: 487
Resultado: 487 candidatos, shortage = 13
Demais: 9 NOT_READY, 2 INDETERMINATE, 2 REASSESSMENT_REQUIRED
```

Uma seleção de 500 não é “lote de exportação”. Ela é uma proposta transitória de candidatos individuais para análise humana posterior. Caso se torne necessário relacionar Animal, estabelecimento, janela logística e operação, isso abre o NEXT-04 antes de qualquer materialização.

## 7. Reuso e conflito identificado

| Necessidade | Reuso permitido | Limite |
|---|---|---|
| conclusão individual | `Decision` e `Evaluation` Core | jamais reemitir ou alterar Decision histórica |
| contexto normativo | `NormativeBasisSnapshot` e seleção temporal do NEXT-02 | Policy ambígua/faltante é fail-closed |
| coverage e lacunas | snapshot e `DecisionReason` existentes | não criar `EligibilityGap` persistida |
| agrupamento de Animals | `LivestockLot` e memberships temporais | membership não é prova de elegibilidade |
| prova individual | Dossier do NEXT-05 | não criar Dossier agregado no NEXT-06 |

O repositório contém a matriz e endpoints comerciais anteriores da ADR-0044 (`MarketEligibilityMatrix`, `commercial_outlook` e `MarketProjectionStatus`). Eles são evidência útil de apresentação e de estados de projeção, mas **não são a base semântica do NEXT-06**: executam avaliações no caminho de leitura, incluem mercados reais legados e têm projeção comercial que pode transformar um `INDETERMINADO` por ausência de carência em `ELEGIVEL`. Tal transformação conflita com o princípio atual de que ausência de conhecimento não é conclusão positiva. Este Design Package não altera esse legado; impede apenas que ele seja ampliado ou reutilizado como fonte de `READY`.

## 8. Cortes propostos

### Corte 1 — read model puro e seleção determinística

- contratos transitórios de Application para entrada homogênea, entrada individual, relatório e seleção;
- derivação pura a partir de Decisions/Evaluations fornecidas, sem repositório, banco ou API;
- classificação fail-closed dos seis estados;
- agregação de gaps sem perder referências individuais;
- seleção de candidatos `READY`, estável e sem efeitos colaterais;
- testes unitários inteiramente sintéticos.

### Corte 2 — leitura controlada de população real

- somente após revisão, adaptar o relatório a repositórios existentes para Animals ou membros vigentes de um lote;
- resolver Policy temporal e contexto sem executar ou persistir avaliações novas em uma consulta de readiness;
- se houver endpoint, entregar OpenAPI, testes de integração, autorização e roteiro em `apps/validacao`;
- ainda sem criação/reserva de lote, Dossier agregado ou mercado real.

### Corte 3 — uso operacional posterior

- somente diante de caso concreto, decidir se uma seleção precisa persistir como intenção auditável;
- caso exija Animal + estabelecimento + operação, decompor e aprovar NEXT-04 antes;
- conectar cada Animal selecionado ao seu Dossier individual existente, sem fundir Dossiers;
- fila/reavaliação por mudança de Policy permanece NEXT-07.

## 9. Testes mínimos do Corte 1

1. duas Decisions `APROVADA` sob o mesmo `MARKET_TEST_A v1` geram duas entradas `READY` e contagem correta;
2. `REJEITADA`, `APROVADA_COM_RESTRICOES`, `INDETERMINADA` e ausência de Decision ficam em estados diferentes e não viram candidatos;
3. coverage de `treatment_history` ou `medication_classification` insuficiente preserva `INDETERMINATE`, sem concluir reprovação;
4. Decision de `MARKET_TEST_A v1` quando a consulta requer v2 vira `REASSESSMENT_REQUIRED`, sem mudar a Decision original;
5. mesma Decision para `MARKET_TEST_B` não contribui para `MARKET_TEST_A`;
6. boundary diferente ou snapshot normativo ausente não é ocultado como `READY`;
7. gaps são agregados por código, mas cada entrada mantém referências à causa original;
8. selecionar N candidatos retorna apenas `READY`, ordenação estável e shortage explícito;
9. seleção não cria/fecha `LotMembership`, Dossier, Evaluation ou Decision.
10. a mesma população em ordem de entrada distinta produz os mesmos candidatos na mesma ordem.

## 10. Fora do escopo e riscos preservados

- mercados reais, interpretação normativa externa e qualquer alegação de exportação;
- SISBOV, GTA, integração governamental, simulador, API externa e Odoo;
- escala, paginação, cache, processamento assíncrono e recomputação em massa;
- ranking por preço, raça, peso, propriedade, logística ou preferência comercial;
- composição com estabelecimento, certificadora, propriedade ou operação;
- persistência da matriz/readiness, reserva e emissão de documento agregado.

O risco operacional principal é confundir uma lista de candidatos com autorização de operação. O contrato, nomes, estados e testes devem manter explicitamente a fronteira `MARKET_ELIGIBILITY_ASSESSMENT_NOT_EXPORT_AUTHORIZATION`.

## 11. Portão para autorizar somente o Corte 1

Antes de código, confirmar:

1. `MARKET_TEST_A` sintético e `INTERNAL_ONLY` são o único caso do corte;
2. readiness é read model transitório, sem tabela, migration, endpoint ou efeitos de escrita;
3. `READY` exige Decision positiva e contexto exato, sem inferência a partir da matriz/commercial projection legada;
4. `REASSESSMENT_REQUIRED`, `INDETERMINATE` e `NOT_EVALUATED` jamais entram na seleção positiva;
5. seleção é determinística e não cria/reserva/modifica lote;
6. nenhum Dossier agregado, mercado real, SISBOV/Odoo ou composição de operação entra no corte.

Com essas confirmações, o próximo passo será implementar exclusivamente o Corte 1 e revisar seu resultado antes de conectar qualquer consulta persistida.

## 12. Aprovação e registro de execução

**Design aprovado em 12 de agosto de 2026. Autorização: somente Corte 1.** A revisão formalizou que readiness verifica correspondência contextual e anchors, mas não reexecuta Rules nem reinterpreta coverage; também tornou a estratégia de seleção explícita e versionável (`STABLE_SUBJECT_ID`/v1).

**CORTE 1 CONCLUÍDO EM 12 DE AGOSTO DE 2026.** `packages/livestock_application/market_readiness.py` introduz contratos transitórios de Application para contexto, entrada, relatório, resumo limitado de gaps e seleção sem escrita. `MarketReadinessService` classifica somente a utilidade da Decision existente em `READY`, `NOT_READY`, `CONDITIONED`, `INDETERMINATE`, `REASSESSMENT_REQUIRED` ou `NOT_EVALUATED`; Policy/finalidade/tempos incompatíveis exigem reavaliação, e snapshot normativo ou boundary não preservados permanecem indeterminados. A seleção inclui apenas `READY`, ordena por ID estável e declara `STABLE_SUBJECT_ID`/v1. Nenhum Rule, coverage, Decision ou lote é recalculado, emitido ou alterado.

**CORTE 2 CONCLUÍDO EM 12 DE AGOSTO DE 2026.** `MarketReadinessPopulationReader` adapta os leitores já existentes de Decision/Evaluation a uma população explícita de Animals ou aos membros vigentes de um `LivestockLot` no `reference_time`. Ele não resolve Policy, executa Rules, persiste readiness nem altera membership: fornece à projeção somente a única Decision/Evaluation que corresponde exatamente ao contexto. Ausência de Decision continua `NOT_EVALUATED`; Decision histórica não correspondente segue para `REASSESSMENT_REQUIRED`; mais de uma Decision exatamente correspondente é erro explícito e fail-closed, nunca escolha por “mais recente”. Nenhuma API, migration, Dossier agregado, lote comercial, reserva, mercado real ou integração externa foi criada.

## 13. Contratos respeitados

- **ADR-0041:** mercado é finalidade contextual, Decision histórica é imutável e composição de sujeitos exige desenho próprio.
- **ADR-0044:** matriz é derivação, e seus estados de projeção não se confundem com `DecisionResult`.
- **NEXT-01:** coverage é dimensional; ausência não prova negativo.
- **NEXT-02:** Policy e base normativa dependem de `reference_time` e `knowledge_cutoff`.
- **NEXT-03:** competência de Source, emissão de Decision e reconhecimento externo permanecem fronteiras distintas.
- **NEXT-05:** Dossier é individual e ancorado em uma Decision; readiness não cria segundo Dossier.
