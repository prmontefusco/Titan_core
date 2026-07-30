# Titan Architecture Specification (TAS)

## Volume I: Titan Architecture Principles

**Versão:** 1.0<br>
**Status:** ACEITO COMO DOCUMENTO NORTEADOR<br>
**Autor:** Titan Architecture Board<br>
**Base normativa de elaboração:** `DOMAIN.md` v1.19<br>
**Compatibilidade:** ADRs aceitas até ADR-0055

> **"A confiança não é armazenada. Ela é demonstrada."**

> **Status de uso:** este documento passa a orientar a interpretação arquitetural
> do Titan a partir de 2026-07-29. Ele não substitui `DOMAIN.md`,
> `ARCHITECTURE.md`, `DEVELOPMENT.md` nem as ADRs aceitas; funciona como
> especificação complementar e norteadora compatível com esses documentos.

---

## Prefácio

O Titan não nasceu para registrar dados.

O Titan nasceu para preservar a confiança.

Toda organização que depende de conformidade regulatória precisa provar que uma decisão tomada hoje poderá ser explicada amanhã. Registrar informações, por si só, não resolve esse problema. Planilhas, ERPs e bancos de dados registram informações. O que normalmente falta é responder, de modo verificável: **por que esta decisão foi tomada?**

O Titan existe para responder essa pergunta. Seu objetivo não é apenas armazenar registros. É preservar declarações, fatos aceitos, evidências, regras e decisões de modo que possam ser examinados, explicados e, quando aplicável, reproduzidos.

---

## 1. Missão

A missão do Titan é transformar informações auditáveis, evidências e critérios explícitos em decisões contextualizadas, explicáveis e reproduzíveis.

O Titan não substitui especialistas, veterinários, auditores ou autoridades regulatórias. Ele fornece uma base objetiva para que suas decisões possam ser compreendidas, verificadas e reproduzidas dentro do escopo, das evidências e das políticas que as fundamentaram.

---

## 2. Visão

O Titan pretende tornar-se uma plataforma genérica para sistemas que exigem confiança regulatória.

Embora sua primeira aplicação seja a cadeia pecuária, seus princípios não dependem desse domínio. Eles podem orientar capacidades em alimentos, agricultura, florestas, carbono, logística, indústria, saúde e em qualquer ambiente onde decisões precisem ser justificadas por evidências.

---

## 3. Escopo e não objetivos

Este volume define princípios arquiteturais, critérios de interpretação e restrições que orientam as decisões estruturais do Titan.

Este documento não:

- define entidades adicionais do domínio;
- substitui o `DOMAIN.md`;
- altera ADRs aceitas;
- especifica banco de dados, framework, linguagem ou protocolo;
- constitui backlog ou plano de implementação;
- determina que todas as capacidades aqui descritas sejam implementadas no mesmo incremento;
- transforma princípios filosóficos em conceitos persistentes sem decisão arquitetural própria.

---

## 4. O problema da confiança

A maior parte dos sistemas atuais responde: **o que aconteceu?**

Poucos conseguem responder: **como sabemos que isso aconteceu?**

Menos ainda conseguem responder: **por que essa decisão foi tomada?**

O Titan trata essas perguntas como níveis distintos de conhecimento. Integridade não é veracidade material. Uma informação pode ter origem, autoria, sequência e conteúdo verificáveis sem que a plataforma afirme que ela representa a realidade de forma absoluta.

O Titan não presume verdade. Ele preserva as condições pelas quais uma declaração, um fato aceito, uma avaliação ou uma decisão pode ser examinada e justificada.

---

## 5. Cadeia canônica de proveniência e decisão

O modelo conceitual canônico do Titan é:

```text
Source
  ↓
Claim
  ↓
Evidence
  ↓
Event
  ↓
Fact
  ↓
Evaluation
  ↓
Decision
  ↓
Dossier
```

Essa cadeia representa o caminho canônico de proveniência e explicação do Titan. Ela não é uma pipeline rígida em que todos os objetos devem obrigatoriamente existir em toda situação.

As setas representam navegabilidade de proveniência e dependência explicativa; não implicam que toda relação seja temporal, causal ou de derivação direta.

Quando aplicável:

- uma `Evidence` pode sustentar, contestar ou contextualizar diretamente um `Event`, `Fact`, `Evaluation` ou `Decision`;
- um `Fact` pode derivar de diferentes combinações de `Claim`, `Source` e `Evidence`;
- um `Event` não precisa necessariamente nascer de uma `Claim`;
- uma `Evaluation` pode existir sem produzir uma `Decision` oficial, quando houver revisão humana;
- um `Dossier` é um snapshot de auditoria, e não uma etapa obrigatória de toda operação.

Uma visão complementar da decisão é:

```text
Source → Claim → Evidence → Event → Fact
                                      │
Policy + Rules +                       │
NormativeBasisSnapshot ────────────────┤
                                      ↓
                                 Evaluation
                                      ↓
                                  Decision
                                      ↓
                                   Dossier
```

`Policy`, `Rules` e, quando aplicável, `NormativeBasisSnapshot` são insumos da `Evaluation`; não são uma etapa posterior a um `Fact`. Quando houver fundamentação normativa, a `Evaluation` preserva o `NormativeBasisSnapshot` correspondente, e não apenas uma referência mutável à fundamentação corrente.

---

## 6. Princípios fundamentais

### I. Truth over Convenience

A fidelidade ao registro, à proveniência e às limitações conhecidas possui prioridade sobre a conveniência operacional.

O Titan não afirma possuir a verdade objetiva. Ele preserva o que foi declarado, aceito, contestado, avaliado e decidido, com origem, contexto, validade e confiança explícitos.

### II. Historical Records Are Immutable

Registros históricos de eventos, evidências, fatos aceitos, políticas publicadas, avaliações e decisões não são reescritos silenciosamente.

A aceitação de um `Fact` não o transforma em verdade absoluta. Correções, novas evidências, revogações e mudanças de contexto produzem novos registros, avaliações ou relações, preservando o anterior e seu efeito histórico.

### III. Trust Requires Evidence

Nenhuma conclusão confiável decorre apenas da existência de um registro. A confiança deve ser demonstrada por origem, evidências, proveniência, critérios explícitos e avaliações reproduzíveis.

### IV. Every Decision Must Be Explainable

Nenhuma decisão pode existir sem elementos que permitam explicar, quando aplicável:

- quais `Claims`, `Facts`, relações e evidências foram considerados;
- quais políticas, regras e bases normativas foram aplicadas;
- qual avaliação produziu o resultado;
- quais razões, limitações, exceções e incertezas influenciaram a conclusão;
- qual autoridade, método e instante contextualizaram a decisão.

Nenhuma `Decision` pode ser registrada sem `DecisionReasons`, referências, snapshots e demais elementos suficientes para explicá-la dentro de seu escopo. A explicação apresentada a cada audiência permanece sujeita a `Authorization`, `Visibility`, `FieldScope`, `DataClassification` e redaction, sem alterar ou inverter a razão original.

### V. Decisions Are Contextual and Historically Preserved

Decisões são conclusões históricas contextualizadas; não são atributos permanentes da realidade.

O Titan preserva decisões, mas não as confunde com fatos. Toda `Decision` permanece vinculada à `Evaluation`, à `Policy`, às `Rules`, ao snapshot das informações consideradas, à fundamentação normativa aplicável, ao motor e ao contexto temporal que produziram seu resultado.

Mudanças em `Policies`, `Rules`, `Evidences`, `Sources` ou conhecimento não reescrevem nem recalculam silenciosamente decisões históricas. Conforme a finalidade e a autorização aplicáveis, podem produzir `HistoricalReproduction`, `HistoricalComplianceAssessment`, `CounterfactualSimulation`, `CurrentReevaluation`, nova `Evaluation`, nova `Decision` ou relações explícitas entre decisões, preservando a história anterior.

---

## 7. O domínio representa registros sobre a realidade, não a realidade absoluta

O domínio representa declarações, eventos, evidências, relações e informações aceitas sobre a realidade, sempre dentro de origem, contexto, finalidade, validade e confiança delimitados. Ele não presume acesso direto ou definitivo à realidade material.

O domínio operacional de uma vertical não incorpora diretamente regras de mercado, jurisdição ou regulamentação. O Titan Core fornece os conceitos genéricos necessários para representar `Policies`, `Rules`, `NormativeReferences`, `NormativeBasis` e `Evaluations`. O conteúdo regulatório concreto, sua aplicabilidade e seus perfis pertencem às políticas, aos perfis aprovados e às capacidades especializadas correspondentes.

Por exemplo, `TreatmentApplication` pode conhecer medicamento, dose, data e responsável. Não deve conhecer União Europeia, China, SISBOV ou USDA.

Essa separação permite que a mesma realidade registrada seja avaliada sob políticas distintas, em jurisdições e mercados diferentes, sem reescrever sua história.

---

## 8. Separação entre fato, evidência e interpretação

O Titan distingue rigorosamente informação, sustentação e interpretação.

Um `Fact` é uma representação aceita de uma informação para uma finalidade delimitada. Pode derivar de `Claims`, `Sources` e `Evidences`, preservando origem, contexto, validade e confiança. Sua aceitação não o transforma em verdade material.

Uma `Evidence` é um registro imutável que sustenta, contesta ou contextualiza outros objetos. Uma `Policy` e suas `Rules` interpretam informações dentro de uma finalidade, escopo e versão. Uma `Decision` registra a conclusão resultante de uma `Evaluation`.

Interpretações podem mudar. Registros históricos e suas relações não são apagados para acomodar a interpretação posterior.

### Sobre assertions

Nesta versão da TAS, o termo `assertion` não designa uma entidade genérica adicional do Titan Core entre `Evidence` e `Policy`.

Afirmações produzidas pelo Titan devem conservar `AssertionType` e `AssertionScope` quando aplicáveis. Tipos concretos de asserção pertencem às respectivas capacidades ou verticais. A criação de uma abstração genérica `Assertion` exige decisão arquitetural própria e alteração formal do `DOMAIN.md`.

---

## 9. O tempo possui dois eixos

Toda decisão relevante depende, no mínimo, de dois tempos distintos:

- **tempo do fato:** quando o acontecimento teria ocorrido ou produzido efeito;
- **tempo do conhecimento:** quando a informação, evidência, fonte, regra ou contexto tornou-se conhecido, registrado ou utilizável para a avaliação.

Essa distinção impede que conhecimento posterior seja projetado silenciosamente sobre uma decisão histórica. Toda arquitetura do Titan deve preservar os instantes necessários para distinguir o que ocorreu do que se sabia em cada momento.

---

## 10. O verdadeiro produto do Titan

O Titan não vende rastreabilidade como fim em si mesma. Rastreabilidade é um meio.

O produto do Titan é confiança reproduzível: a capacidade de demonstrar como uma declaração foi recebida, como uma informação foi sustentada, qual política a avaliou, que decisão foi produzida e quais limites permanecem conhecidos.

---

## 11. Linguagem e autoridade normativa

O `DOMAIN.md` é a fonte normativa central da linguagem de domínio do Titan. ADRs aceitas registram decisões estruturais e podem alterar ou especializar essa linguagem de forma explícita. A TAS organiza princípios, interpretações e critérios arquiteturais; ela não cria silenciosamente novos conceitos de domínio.

```text
DOMAIN.md e ADRs aceitas
    ↓ definem linguagem e decisões estruturais
TAS
    ↓ organiza princípios e critérios de interpretação
Guias de implementação
    ↓ orientam a execução sem criar conceitos normativos
Código
    ↓ implementa os documentos acima
```

Em caso de divergência terminológica ou semântica entre a TAS e o `DOMAIN.md`, prevalece o `DOMAIN.md`, salvo quando uma ADR aceita determinar explicitamente sua alteração. A divergência deve ser resolvida documentalmente antes da implementação.

---

## 12. Regra editorial para arquitetura e ADRs futuras

Nenhum documento da Titan Architecture Specification deve começar por tecnologia. Cada documento começa pelo problema de negócio e pelo problema filosófico que a tecnologia, quando necessária, resolve.

Toda ADR futura deve responder obrigatoriamente:

1. Que problema de negócio e de confiança resolve?
2. Qual princípio arquitetural preserva?
3. Quais invariantes cria, preserva ou altera?
4. Como preserva auditabilidade?
5. Como preserva reprodutibilidade?
6. Como preserva o tempo do fato e o tempo do conhecimento?
7. Como preserva explicabilidade?
8. Como se alinha à linguagem normativa do `DOMAIN.md`?

Se uma ADR não puder responder a essas perguntas, ela deve ser revisada antes de orientar implementação.

---

## 13. Conclusão

O Titan não pretende ser apenas um software de rastreabilidade. Pretende ser uma plataforma de confiança.

Sua responsabilidade é permitir que, anos depois, seja possível responder:

- o que foi declarado, registrado ou aceito;
- como essa informação foi sustentada;
- qual decisão foi tomada;
- por que ela foi tomada;
- quais limites e incertezas eram conhecidos;
- e como sua avaliação pode ser reproduzida dentro do contexto histórico aplicável.

> **A confiança não é armazenada. Ela é demonstrada.**
