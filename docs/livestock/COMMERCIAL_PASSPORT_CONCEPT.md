# Commercial Passport Concept

**Data:** 2026-09-11
**Status:** Conceito aprovado para planejamento; sem implementacao F1-F7.
**Owner:** Titan Livestock.

## Definicao

Commercial Passport / Passaporte Comercial e uma projection/application view em Titan Livestock que responde, para o produtor:

- para onde posso vender;
- onde quase consigo vender;
- por que nao consigo;
- o que falta;
- quantos animais/lotes/populacoes estao aptos;
- quando bloqueios temporarios podem deixar de bloquear, quando essa informacao for derivavel.

CommercialPassport != Decision.

CommercialPassport != MarketEligibility.

Commercial Passport compoe multiplas avaliacoes, decisoes e projections ja existentes. Ele nao e fonte de verdade e nao duplica historico de animal, propriedade, movimento, tratamento, GTA, evidencia ambiental ou outro fato operacional.

## Cadeia conceitual

```text
Source Facts
-> Evidence
-> FactSnapshot
-> Policies / Requirements
-> Evaluations
-> Decisions
-> dynamic Commercial Passport
```

Quando houver emissao formal ou compartilhamento:

```text
dynamic Commercial Passport
-> immutable issued snapshot
-> Dossier
-> VerificationBundle
```

Consulta dinamica nao emite Dossier nem VerificationBundle.

## Estrutura conceitual

```text
CommercialOpportunity
-> Property readiness
-> Population eligibility
-> Reasons / gaps / limitations
```

### CommercialOpportunity

Representa uma oportunidade comercial avaliada em Livestock. Pode corresponder futuramente a:

- mercado/pais/bloco;
- programa;
- comprador;
- protocolo privado;
- certificacao;
- janela de entrega;
- requisito de peso;
- requisito de idade;
- quantidade;
- geografia/logistica;
- protocolo privado buyer-specific.

Esses elementos permanecem em Livestock. Nem todo requisito comercial e regulatorio.

### Property readiness

Avalia se a propriedade satisfaz requisitos da oportunidade comercial que pertencem ao nivel da propriedade, da Organization ou de evidencias documentais/ambientais/operacionais.

PROPERTY READINESS e diferente de ANIMAL / LOT / POPULATION ELIGIBILITY.

Uma propriedade pode estar pronta para determinado mercado e ainda possuir animais inelegiveis.

Animais podem possuir evidencias validas mesmo quando ha requisitos incompletos da propriedade.

Nao colapsar essas dimensoes em um unico status.

### Population eligibility

Resume elegibilidade de animais, lotes ou populacoes para a mesma oportunidade comercial. Deve preservar contagens por estado e limitacoes, sem revelar detalhes nao autorizados em contextos externos.

## Requirement reasoning

Requirement reasoning deve existir antes do Passport completo.

Estados canonicos iniciais em Livestock:

- `SATISFIED`: requisito aplicavel foi atendido pelo material avaliado.
- `MISSING`: a evidencia ou dado exigido nao foi fornecido ou nao existe no material conhecido.
- `UNKNOWN`: o Titan nao consegue concluir com o conhecimento disponivel; pode haver fonte indisponivel, coverage insuficiente, intervalo nao reconstruivel ou ambiguidade.
- `FAILED`: requisito aplicavel foi avaliado e nao foi atendido.
- `NOT_APPLICABLE`: requisito nao se aplica ao subject/contexto avaliado.
- `BLOCKED`: requisito ou condicao impede a oportunidade no contexto atual, mesmo que outros requisitos estejam satisfeitos.

Distincoes obrigatorias:

- `MISSING != UNKNOWN`: ausencia de evidencia exigida nao e o mesmo que indeterminacao por incerteza.
- `FAILED != MISSING`: falha exige avaliacao negativa; missing e lacuna de material.
- `BLOCKED != FAILED`: blocker e uma condicao impeditiva para a oportunidade; pode ser temporaria ou derivada de regra comercial.
- `NOT_APPLICABLE` nao reduz readiness.
- Unknown nao deve virar false.
- Missing evidence nao deve virar non-compliance.

## Readiness

Readiness nao e um unico score.

A representacao principal deve ser derivavel por requisitos:

```text
satisfied_count
missing_count
unknown_count
failed_count
not_applicable_count
blocked_count
applicable_requirement_count
blocking_requirement_count
```

Um percentual pode existir como projection secundaria, desde que totalmente derivavel e documentado. Exemplo: requisitos satisfeitos sobre requisitos aplicaveis, excluindo `NOT_APPLICABLE`.

SCORE != DECISION.

Um unico blocker pode tornar uma oportunidade indisponivel mesmo com alto percentual derivado.

## Status de alto nivel

O Passport pode apresentar uma classificacao operacional para UX, mas ela nao substitui requirement reasoning. Nomes finais devem ser definidos em F1/F2, mas a semantica deve preservar:

- oportunidade pronta/disponivel;
- parcialmente pronta;
- indisponivel por blocker/falha;
- desconhecida/indeterminada;
- nao avaliada.

Essa classificacao e projection de Livestock, nao `DecisionResult` do Core.

## Formal issuance

Separar:

- dynamic passport projection;
- formal issued passport snapshot.

Projection dinamica e recomputavel e usada para experiencia operacional.

Issued snapshot e evento formal, imutavel, reproduzivel e potencialmente compartilhavel. Deve reutilizar Dossier e VerificationBundle existentes. Nao criar mecanismo paralelo.

## Privacidade e disclosure

Commercial Passport pertence ao produtor/Organization.

Nao criar endpoint publico que revele identidade de produtor, propriedade, localizacao precisa, inventario, quantidade de animais, compliance ou lacunas de compliance.

Disclosure externo deve passar por authorization/grant apropriado. Quando aplicavel ao Market Supply, preservar:

```text
authorization
-> population
-> disclosure
-> aggregate
-> audit
```

## Limites

Commercial Passport nao e:

- passaporte governamental;
- certificado oficial;
- autorizacao de exportacao;
- decision regulatoria;
- MarketEligibility individual;
- score financeiro;
- marketplace;
- matching comprador-produtor.
