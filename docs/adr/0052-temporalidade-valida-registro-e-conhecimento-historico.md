# ADR-0052 - Temporalidade valida, registro e conhecimento historico

**Data:** 2026-07-29<br>
**Status:** ACEITA<br>
**Aceita em:** 2026-07-29<br>
**Base normativa:** `DOMAIN.md` v1.19 e ADRs aceitas ate ADR-0051<br>
**Escopo:** Titan Core<br>
**Relacionadas:** ADR-0048, ADR-0049, ADR-0050, ADR-0051

---

## 1. Contexto

Uma informacao pode descrever corretamente um evento passado e ainda assim nao estar disponivel para uma decisao realizada naquele passado.

O Titan preserva representacoes aceitas sobre a realidade, e nao verdade material absoluta. Por isso, a temporalidade deve permitir responder separadamente: a que instante ou intervalo a informacao se refere, quando ela passou a produzir efeito e quando o Titan poderia legitimamente utiliza-la.

Sem essa separacao, uma avaliacao pode usar conhecimento recebido depois de sua emissao, uma correcao pode apagar a versao que era conhecida anteriormente, ou uma Policy pode ser escolhida apenas porque esta vigente hoje.

---

## 2. Problema

Os instantes abaixo possuem significados distintos e nao podem ser tratados como sinonimos:

- quando algo ocorreu ou foi observado;
- quando a informacao descreve a realidade ou produz efeito no dominio;
- quando uma fonte emitiu, enviou ou o Titan recebeu um registro;
- quando o Titan o registrou, aceitou ou passou a conhece-lo para determinada finalidade;
- quando uma correcao, substituicao ou revogacao foi produzida;
- quando uma `Evaluation` utilizou a representacao selecionada.

Exemplo:

```text
Vacinacao realizada:       10/01
Documento emitido:         11/01
Documento recebido:        20/01
Registrado no Titan:       21/01
Evaluation realizada:      15/01
```

Uma `Evaluation` feita em 15/01 nao pode usar o documento recebido em 20/01 para se apresentar como avaliacao baseada no conhecimento disponivel em 15/01, ainda que o documento descreva vacinacao ocorrida em 10/01.

---

## 3. Decisao

O Titan adota uma semantica temporal que distingue, no minimo, tempo valido e tempo de conhecimento.

- **tempo valido**: quando a representacao se refere a evento, observacao, estado ou efeito no dominio;
- **tempo de conhecimento**: quando a representacao entrou no universo que o Titan podia utilizar para uma finalidade e contexto delimitados.

Nenhuma reproducao historica pode utilizar informacao que nao estivesse disponivel no limite de conhecimento correspondente, mesmo que ela descreva fato anterior.

Toda selecao temporal para `Evaluation` declara explicitamente:

- `reference_time`: instante ou intervalo da realidade representada que a selecao examina;
- `knowledge_cutoff`: limite do conhecimento admissivel no contexto de Organization, audiencia, finalidade, autorizacao e escopo declarado;
- regra de selecao temporal, versao e finalidade;
- timezone, precisao, `TimeConfidence` e limitacoes quando aplicaveis.

`as_of` isolado nao possui semantica suficiente para reproducao historica. Onde o termo for mantido por compatibilidade, seu significado precisa ser associado explicitamente a `reference_time`, `knowledge_cutoff` ou ambos; ele nao pode ocultar essa distincao.

Esta ADR define semantica e contrato de selecao. Ela nao cria uma entidade generica persistida chamada `BitemporalSnapshot`, `KnowledgeTime` ou equivalente. Uma forma persistida nova exige decisao propria e alteracao formal do `DOMAIN.md`.

---

## 4. Escopo e nao objetivos

Esta ADR define:

- vocabulario e separacao dos eixos temporais;
- criterios para selecao historica de material, `Policy` e fundamentacao;
- efeito de informacao retroativa, correcao e conhecimento posterior;
- relacao entre selecao temporal, snapshot e operacoes historicas;
- representacao de instantes, intervalos, precisao e timezone.

Esta ADR nao define:

- banco de dados, indice, particionamento ou mecanismo fisico de versionamento;
- algoritmo de hash ou serializacao, definidos pela ADR-0051;
- uma fonte universal de tempo confiavel;
- semantica operacional especifica de cada vertical;
- retroatividade juridica ou validade legal automatica;
- migracao que invente tempos historicos sem evidencia.

---

## 5. Vocabulario temporal

Os termos abaixo possuem significado normativo quando aplicaveis. Nem todo registro precisa possuir todos eles.

| Termo | Significado |
| --- | --- |
| `occurred_at` | Instante em que o evento alegado ou registrado ocorreu. |
| `observed_at` | Instante em que alguem ou algum sistema observou, mediu ou constatou a informacao. |
| `valid_from` | Inicio do intervalo em que a representacao e aplicavel ao dominio. |
| `valid_to` | Fim exclusivo do intervalo de validade; ausente indica fim ainda nao delimitado. |
| `effective_at` / `effective_from` | Instante em que ato, relacao, Policy ou efeito declarado passa a produzir efeito no escopo correspondente. |
| `received_at` | Instante em que o Titan ou integracao controlada recebeu material de fonte externa. |
| `recorded_at` | Instante em que o Titan persistiu o registro sob sua responsabilidade. |
| `accepted_at` | Instante em que material se tornou aceito ou admissivel para finalidade delimitada, quando esse julgamento existir. |
| `known_at` | Instante demonstravel a partir do qual a informacao podia integrar o universo de conhecimento utilizavel no contexto de selecao declarado. |
| `discovered_at` | Instante em que uma divergencia, fato ou evidencia ja existente foi descoberta pelo Titan ou Actor identificado. |
| `corrected_at` | Instante declarado em que o Actor ou a fonte produziu formalmente a correcao. |
| `superseded_at` | Instante em que uma versao deixou de ser a versao corrente por supersession explicita; nao apaga sua existencia historica. |
| `reference_time` | Instante ou intervalo da realidade representada que uma selecao ou avaliacao pretende examinar. |
| `knowledge_cutoff` | Limite maximo de `known_at` admissivel para uma selecao ou avaliacao. |
| `evaluation_emitted_at` | Instante em que uma `Evaluation` nova foi produzida ou registrada como conclusao tecnica. |

`recorded_at`, `received_at`, `accepted_at` e `known_at` podem coincidir em um caso concreto, mas essa igualdade deve ser registrada ou demonstrada; ela nunca e presumida apenas pela proximidade temporal.

`known_at` demonstra disponibilidade de conhecimento, mas nao implica automaticamente aceitacao, validade probatoria, admissibilidade normativa, suficiencia ou verdade material. Quando a `Policy` exigir material aceito, verificado ou admissivel, a selecao tambem considera `accepted_at`, estado de verificacao e demais condicoes aplicaveis.

`known_at` nao deve ser interpretado como atributo universal e absoluto do conteudo quando sua disponibilidade depender de Organization, audiencia, finalidade, autorizacao ou escopo. Nesses casos, o instante de conhecimento pertence a disponibilidade contextual demonstravel. O Core pode representa-la por projecao, relacao, evento ou contrato de selecao existente, sem promover nesta ADR uma nova entidade normativa. Uma mesma informacao pode possuir limites de conhecimento distintos para contextos distintos.

---

## 6. Selecao temporal historica

Uma selecao historica combina os dois eixos:

```text
material valido para reference_time
            +
material conhecido ate knowledge_cutoff
            -> material temporalmente elegivel
```

Conceitualmente, para um elemento com intervalo de validade e conhecimento demonstravel:

```text
valid_from <= reference_time < valid_to, quando valid_to existir
knowledge_available_at(material, Organization, purpose, authorization_scope) <= knowledge_cutoff
```

Eventos instantaneos podem ser selecionados por `occurred_at` ou `observed_at`, conforme o contrato da `Policy` ou da capacidade. Relacoes, estados e vigencias usam intervalo quando aplicavel. A regra de selecao deve declarar qual campo ou intervalo e relevante; o Titan nao escolhe silenciosamente o campo mais conveniente.

Quando `reference_time` for intervalo, a regra temporal declara a relacao exigida, como intersecao, cobertura integral, contencao, precedencia ou ocorrencia dentro do intervalo. Sobreposicao parcial nao equivale automaticamente a validade para todo o periodo.

Ausencia de tempo necessario, `TimeConfidence` insuficiente, sobreposicao nao resolvida ou lacuna material nao autoriza inferencia. A selecao deve registrar limitacao, produzir resultado inconclusivo quando a `Policy` assim determinar ou recusar a operacao antes da `Evaluation`.

---

## 7. Conhecimento posterior, fatos retroativos e correcoes

Informacao retroativa e informacao cujo tempo valido e anterior ao seu `known_at`. Ela pode participar de avaliacao posterior, mas nao reescreve o universo conhecido por avaliacao anterior.

Correcao, `SupersessionRelation`, nova evidencia ou conflito resolvido preservam o registro e a versao anteriormente conhecidos. Exemplo:

```text
Fact v1
  known_at: 10/01
  conteudo: peso 500 kg

Fact v2
  known_at: 15/01
  conteudo: peso 450 kg
  supersedes: Fact v1
```

Uma reproducao com `knowledge_cutoff` em 12/01 encontra `Fact v1`. Uma reavaliacao atual pode considerar `Fact v2`, desde que a selecao, a finalidade e a `Policy` aplicavel estejam declaradas.

Nenhuma informacao posterior altera silenciosamente `Evaluation`, `Decision`, `Snapshot` ou `Dossier` historicos. Ela pode produzir novo snapshot, nova `Evaluation`, nova `Decision`, relacao explicita de revisao ou uma das operacoes formais desta ADR.

---

## 8. Intervalos, precisao e timezone

Intervalos temporais usam convencao semiaberta: `[inicio, fim)`. O inicio e inclusivo; o fim, quando existir, e exclusivo. Vigencia sem fim conhecido possui `valid_to` ausente, e nao uma data artificial distante.

Instantes usados em comparacao sao normalizados em UTC, com precisao declarada. O valor local, timezone e offset originais permanecem preservados quando influenciarem interpretacao, prova ou reproducao.

Uma data sem hora nao e convertida silenciosamente em instante UTC. Ela preserva granularidade, calendario e localidade ou jurisdicao aplicavel. Quando uma `Policy` exigir instante e a conversao nao estiver definida por contrato controlado, existe limitacao temporal, nao um horario presumido.

Eventos instantaneos possuem instante e precisao declarados. Intervalos sobrepostos, lacunas e ordens temporalmente impossiveis devem permanecer visiveis para a `Policy`, para a regra ou para revisao humana; nao sao resolvidos por ordem de persistencia.

---

## 9. Policy, regra e fundamentacao normativa

A vigencia do material avaliado, da `Policy` e da `NormativeBasis` sao resolvidas separadamente.

A selecao temporal de `Policy`, `Rule` e `NormativeBasis` tambem considera separadamente seu intervalo de vigencia ou efeito, instante de publicacao, registro ou conhecimento admissivel, eventual retroatividade expressamente declarada e finalidade da operacao historica.

Uma `Evaluation` historica combina somente:

- informacoes temporalmente elegiveis para `reference_time` e `knowledge_cutoff`;
- `Policy` publicada e aplicavel segundo a ADR-0049;
- `Rules` exatas da `Policy` selecionada;
- `NormativeBasisSnapshot` correspondente, quando aplicavel;
- autorizacao e projecao que permitiram o material entregue.

Uma `Policy` pode ser eficaz para periodo anterior ao instante em que foi publicada ou conhecida. Essa retroatividade nao autoriza sua inclusao em `HistoricalReproduction` de decisao que nao a conhecia. Ela pode participar de `HistoricalComplianceAssessment` posterior somente quando a finalidade, a base normativa e a regra de selecao declararem expressamente o uso retrospectivo.

Policy vigente hoje nao substitui automaticamente a Policy aplicavel no instante historico. Base normativa descoberta, atualizada ou reinterpretada depois tambem nao pode ser apresentada como fundamento conhecido na decisao original.

---

## 10. Operacoes historicas

As operacoes da ADR-0048 recebem semantica temporal explicita:

### 10.1 HistoricalReproduction

Reexecuta o snapshot, `Policy`, `Rules`, `NormativeBasisSnapshot`, contexto e versao de motor originais. Usa o `knowledge_cutoff` e a selecao preservados originalmente; nao consulta conhecimento posterior para completar lacunas.

Se o snapshot original estiver preservado, a reproducao nao reconstrui material a partir do estado atual. Se ele nao estiver suficientemente preservado, o resultado deve declarar a limitacao, sem afirmar reproducao integral.

### 10.2 HistoricalComplianceAssessment

Produz nova `Evaluation` sobre periodo historico declarado. Deve informar separadamente `reference_time`, `knowledge_cutoff`, `Policy` e `NormativeBasis` utilizados. Conhecimento posterior somente participa quando a finalidade da operacao o declarar expressamente; nesse caso, o resultado nao se apresenta como decisao originalmente disponivel.

### 10.3 CurrentReevaluation

Produz nova `Evaluation` no presente utilizando o conhecimento admissivel no momento da reavaliacao. O `knowledge_cutoff` corresponde ao corte de conhecimento atual capturado explicitamente.

`reference_time` permanece correspondente ao periodo ou estado que se pretende examinar, podendo ser atual ou historico. `evaluation_emitted_at`, `reference_time` e `knowledge_cutoff` nao sao presumidos como o mesmo instante.

A `Policy`, as `Rules` e a `NormativeBasis` utilizadas devem ser declaradas. A operacao informa se aplica semantica normativa atual, semantica normativa historica ou outra composicao expressamente autorizada. Relogio corrente nao entra implicitamente na execucao.

### 10.4 CounterfactualSimulation

Usa premissas hipoteticas explicitamente identificadas, inclusive tempos, conhecimento, `Policy`, `Rules` ou fundamentacao alternativos. Nao altera estado operacional e nao se apresenta como resultado historico existente.

Essas operacoes nao compartilham silenciosamente o mesmo `as_of`, snapshot ou corte de conhecimento.

---

## 11. Relacao com snapshot e identidade

A ADR-0052 resolve selecao temporal. A ADR-0051 canonicaliza e preserva o resultado dessa selecao.

Todo snapshot criado para `Evaluation` deve preservar, no minimo:

- `reference_time` e `knowledge_cutoff`;
- versoes e referencias selecionadas;
- tempos validos, de conhecimento contextual e de emissao que justificam inclusao, exclusao, limite ou lacuna relevante;
- regra temporal, contrato e versao utilizados na selecao;
- precisao, timezone, `TimeConfidence` e limitacoes materialmente relevantes.

Esses elementos participam de `snapshot_hash` ou `context_hash` conforme a fronteira definida pela ADR-0051. A selecao temporal nao depende da ordem do banco, do horario em que a consulta foi executada ou do relogio corrente nao preservado.

---

## 12. Invariantes

1. Tempo valido nao se confunde com tempo de conhecimento.
2. Informacao conhecida depois de `knowledge_cutoff` nao participa de reproducao anterior.
3. Correcao, supersession ou nova evidencia nao apagam a versao anteriormente conhecida.
4. Toda selecao historica declara `reference_time` e `knowledge_cutoff`.
5. Tempo corrente nao e utilizado implicitamente em selecao, execucao ou reproducao.
6. Novo conhecimento produz nova versao, novo snapshot, nova avaliacao ou relacao explicita; nunca reescreve a identidade historica.
7. Avaliacao historica preserva regra temporal, versao e limitacoes usadas.
8. Fact retroativo nao reescreve `Decision` historica.
9. Vigencia de `Policy` e `NormativeBasis` e resolvida separadamente da vigencia do material.
10. Datas, precisao, timezone e intervalo possuem representacao canonica.
11. Data sem hora nao recebe horario ou timezone presumidos.
12. Ausencia de `known_at` historico permanece desconhecida ou aproximada explicitamente; nunca e apresentada como certeza reconstruida.
13. Conhecimento e autorizacao sao correlacionados quando a informacao somente era utilizavel sob escopo, audiencia ou Organization especificos.
14. Ordem de persistencia nao resolve conflito, sobreposicao, lacuna ou contradicao temporal.
15. Disponibilidade de conhecimento contextual nao e reduzida automaticamente a `known_at` global.
16. Vigencia retroativa nao equivale a conhecimento retroativo.
17. `HistoricalReproduction` nao utiliza `Policy` ou `NormativeBasis` desconhecida no contexto original.
18. Avaliacao retrospectiva com norma posterior declara explicitamente essa finalidade.
19. `evaluation_emitted_at`, `reference_time` e `knowledge_cutoff` sao instantes semanticamente distintos.
20. Conhecimento nao implica aceitacao ou admissibilidade normativa.
21. Se `reference_time` for intervalo, a relacao temporal exigida e declarada pela regra de selecao.

---

## 13. Fluxo de referencia

```text
Facts, Claims, Evidences, Events e versoes
        -> filtro por tempo valido
        -> filtro por tempo de conhecimento
        -> selecao temporal autorizada
        -> Snapshot canonico (ADR-0051)
        -> RuleExecutionContext (ADR-0050)
        -> Evaluation
        -> Decision
```

---

## 14. Estado atual e transicao

O Core atual ja possui partes do vocabulario temporal: `observed_at` em `Fact`, `occurred_at` e `recorded_at` em `RecordTimestamps`, `as_of` em `FactSnapshot`, e campos especializados de correcao, importacao e vertical.

Ainda nao existe semantica uniforme para `known_at`, `knowledge_cutoff`, selecao bitemporal, correcoes historicamente selecionaveis ou reproducao estrita de conhecimento. O `FactSnapshot` atual usa `as_of` unico e seu hash ainda esta em transicao para o contrato canonico da ADR-0051.

A transicao deve:

- acrescentar tempos e contratos somente quando houver evidencia e necessidade aprovada;
- preservar registros legados sem alegar corte de conhecimento que nao possa ser demonstrado;
- distinguir tempo observado, ocorrido, recebido, registrado, aceito e conhecido;
- introduzir selecao temporal antes de depender dela para emitir `Decision` historica;
- criar testes que provem que conhecimento posterior nao entra em reproducao anterior.

Nenhuma migracao pode preencher `known_at` historico por inferencia silenciosa a partir de `recorded_at`, timestamp de banco ou horario de arquivo. Quando houver aproximacao operacional autorizada, ela deve ser marcada com origem, metodo, `TimeConfidence` e limitacao.

---

## 15. Alternativas rejeitadas

### 15.1 Usar somente `occurred_at`

Rejeitada porque nao informa quando o Titan conheceu ou podia usar a informacao.

### 15.2 Usar somente `recorded_at`

Rejeitada porque registro interno nao descreve necessariamente quando o evento ocorreu, quando a fonte o emitiu ou quando se tornou admissivel.

### 15.3 Tratar `as_of` como sinonimo universal de tempo

Rejeitada porque esconde a diferenca entre realidade representada e conhecimento disponivel.

### 15.4 Recalcular avaliacoes historicas com estado atual

Rejeitada porque projeta conhecimento posterior sobre decisao anterior e viola reproducao historica.

### 15.5 Corrigir registros sobrescrevendo versoes anteriores

Rejeitada porque elimina o universo conhecido no instante original e impede auditoria.

### 15.6 Inferir horario de data parcial ou timezone ausente

Rejeitada porque cria certeza temporal artificial e pode alterar aplicabilidade de regra ou Policy.

---

## 16. Criterios de conformidade

Uma implementacao esta conforme esta ADR quando:

- distingue explicitamente tempo valido, disponibilidade de conhecimento contextual e emissao da avaliacao;
- exige `reference_time` e `knowledge_cutoff` para selecao historica;
- nao permite que reproducao historica use material conhecido posteriormente;
- preserva correcao, supersession e versao anteriormente conhecida;
- resolve vigencia e conhecimento de material, `Policy` e `NormativeBasis` de forma separada;
- preserva regra temporal, timezone, precisao e limitacoes relevantes no snapshot conforme ADR-0051;
- nao usa relogio corrente ou `as_of` ambiguo de modo implicito;
- trata ausencia ou baixa confianca temporal como limitacao, nao como certeza;
- cobre em testes fato retroativo, correcao posterior, disponibilidade diferente por Organization, norma retroativa, data parcial, timezone, intervalo semiaberto e reproducao sem conhecimento posterior.

---

## 17. Questoes adiadas

- forma persistida e API do contrato de selecao temporal;
- fonte de tempo confiavel, sincronizacao e prova externa de relogio;
- politica de retencao e disposicao para historico temporal;
- regras de negocio especializadas para precisao, calendario e retroatividade de cada vertical;
- relacionamento entre corte de conhecimento, `FieldScope`, redaction e compartilhamento em implementacao concreta.

Essas questoes nao autorizam interpretacao silenciosa contraria aos invariantes desta ADR.

---

## 18. Proximas ADRs registradas

Depois da aceitacao e da implementacao incremental desta ADR, a sequencia arquitetural prevista e:

1. **ADR-0053 - Autoridade decisoria e emissao de Decision**
2. **ADR-0054 - DecisionProposal, revisao humana e override**
3. **ADR-0055 - Dossier verificavel e validacao independente**

Elas permanecem planejadas. Esta ADR nao antecipa seus modelos persistidos, APIs ou implementacoes.

---

## 19. Consequencias

O Titan passa a tratar tempo como parte da demonstracao de confianca, e nao como metadado conveniente. Isso aumenta disciplina de captura, versionamento e teste, mas impede que informacao descoberta hoje seja apresentada como conhecimento disponivel ontem.

Uma decisao pode continuar sendo explicada anos depois nao apenas pelo que avaliou, mas por qual representacao conhecida e autorizada da realidade estava disponivel no instante relevante.
