# ADR-0061 - Selecao normativa temporal antes de Market Eligibility

**Status:** ACEITA
**Data:** 13 de agosto de 2026
**Decisor:** responsavel pelo produto e arquitetura do Titan

## Contexto

O Core ja possui `NormativeBasisSnapshot` tipado, imutavel, persistido na
`Evaluation` e incorporado ao `context_hash`. A selecao temporal de `Policy`
tambem ja falha fechada por `reference_time` e `knowledge_cutoff`.

Entretanto, o caminho de `MarketEligibilityService` ainda pode avaliar uma
Policy sem fornecer fotografia normativa. `Rule.normative_source` e apenas texto
descritivo legado: nao identifica instrumento, versao, dispositivo, digest,
aprovacao, vigencia ou conhecimento. Promove-lo implicitamente a fundamento
normativo criaria uma afirmacao que o Titan nao consegue provar.

## Decisao

Uma Evaluation independente de Market Eligibility somente podera ser emitida
quando uma fonte de aplicacao entregar exatamente um `NormativeBasisSnapshot`
tipado e elegivel para a Policy, Rules, finalidade, `reference_time` e
`knowledge_cutoff` da avaliacao.

A selecao devera ser exposta por uma porta de Application. A implementacao
concreta devera consultar material normativo persistido e versionado, ou perfil
interno controlado explicitamente classificado como `INTERNAL_TEST`. Ela deve:

- selecionar somente base conhecida ate o `knowledge_cutoff`;
- respeitar intervalo semiaberto de validade/aplicabilidade;
- recusar ausencia, sobreposicao, conflito ou tempo nao demonstravel;
- preservar no snapshot a base, referencias, digests, aprovacao e limitacoes;
- nunca derivar base de `Rule.normative_source`, versao de Policy ou texto livre.

Enquanto a porta nao possuir fonte concreta, Market Eligibility deve retornar
indeterminacao controlada e nao persistir Evaluation ou Decision. O fallback
farmacologico que tambem emite Evaluation sem fotografia normativa devera ser
alinhado ao mesmo portao no corte de implementacao.

## Consequencias

- Evaluations historicas ja persistidas permanecem imutaveis e continuam
  declarando a limitacao legada quando nao possuem snapshot.
- Nenhuma migration, mercado real, integracao externa ou taxonomia normativa e
  introduzida por esta ADR.
- O primeiro adapter pode servir somente o caso ficticio aprovado, desde que o
  perfil, conteudo sintetico, digests, aprovacao e limites sejam dados
  controlados - nunca inferencias a partir de Rule.
- O corte de implementacao deve incluir testes de ausencia, ambiguidade, base
  publicada apos o cutoff, mudanca de digest e persistencia na Evaluation.

## Alternativas rejeitadas

- Construir snapshot a partir de `Rule.normative_source`: texto livre nao e
  referencia normativa verificavel.
- Reutilizar a Policy como se fosse NormativeBasis: mistura interpretacao
  executavel e sua fundamentacao.
- Manter Evaluation positiva sem snapshot: impede explicar integralmente qual
  base normativa foi aplicada.
- Criar agora modelo universal completo de instrumento normativo: amplia o
  dominio sem o primeiro caso controlado de fonte e autoria.
