# ADR-0051 - Snapshot canonico, identidade criptografica e proveniencia

**Data:** 2026-07-29<br>
**Status:** ACEITA<br>
**Aceita em:** 2026-07-29<br>
**Base normativa:** `DOMAIN.md` v1.19 e ADRs aceitas ate ADR-0050<br>
**Escopo:** Titan Core<br>
**Relacionadas:** ADR-0048, ADR-0049, ADR-0050

---

## 1. Contexto

Uma `Evaluation` somente e reproduzivel se for possivel responder com precisao: **o que exatamente foi avaliado?**

Um hash de fatos isolados nao responde essa pergunta quando a interpretacao tambem depende de proveniencia, relacoes, politica, regras, fundamentacao normativa, finalidade, contexto autorizado, unidades ou tempos conhecidos. Um snapshot incompleto pode parecer integro e ainda assim permitir interpretacao diferente quando reproduzido.

O Snapshot e a fronteira entre a realidade registrada e sua interpretacao. Tudo antes do snapshot pertence ao dominio registrado; tudo depois pertence a avaliacao.

---

## 2. Problema

O Titan precisa garantir que duas avaliacoes possam demonstrar se usaram exatamente o mesmo universo de informacoes conhecidas e autorizadas, e se aplicaram a mesma semantica de avaliacao.

O problema inclui referencias de proveniencia que hoje podem existir no conteudo do fato sem participar de sua identidade criptografica. Alterar `source_reference`, `EvidenceReference`, relacao relevante ou representacao externa pode alterar a interpretacao reproduzivel; portanto, nao pode permanecer fora da identidade.

---

## 3. Decisao

Um Snapshot e uma declaracao imutavel, canonica, serializavel, identificavel, verificavel e reproduzivel da realidade conhecida e autorizada utilizada por uma avaliacao especifica. Ele nao e apenas colecao de objetos.

Qualquer elemento que possa alterar a interpretacao reproduzivel participa da identidade criptografica correspondente.

Esta ADR define duas identidades complementares:

- `snapshot_hash`: identifica o universo de informacoes, referencias, proveniencia e tempos disponibilizados para avaliacao;
- `context_hash`: identifica a semantica autorizada da avaliacao, incluindo finalidade, sujeito, politica, regras, fundamentacao, configuracao deterministica e projecao de autorizacao relevante.

`evaluation_hash`, `decision_hash` e hashes de artefatos posteriores sao derivados de identidades e resultados preservados, sem substituir `snapshot_hash` ou `context_hash`.

---

## 4. Escopo e nao objetivos

Esta ADR define composicao logica, identidade, canonicalizacao e proveniencia do snapshot de avaliacao.

Esta ADR nao define:

- algoritmo criptografico concreto;
- banco, tabela, documento ou armazenamento fisico;
- protocolo de serializacao fisica ou biblioteca especifica;
- significado completo dos tempos validos e de conhecimento;
- modelo geral de unidades e dimensionalidade;
- emissao de `Decision`, autoridade ou dossier;
- grafo fisico de proveniencia.

Esses assuntos permanecem para ADRs especializadas. Esta ADR define o contrato que elas devem preservar.

---

## 5. Composicao do snapshot

O snapshot de avaliacao contem, quando aplicavel e autorizado:

- `Facts`, `Claims`, `Evidences` e seus identificadores, versoes e conteudo ou digests necessarios;
- referencias de proveniencia, incluindo `source_reference`, `EvidenceReference` e origem declarada;
- relacoes, direcao, tipo, versao e referencias dos objetos relacionados;
- referencias estaveis de `Subject` e Organization quando delimitarem o material avaliado;
- instantes preservados relevantes;
- objetos externos referenciados;
- conteudo efetivamente entregue, inclusive campos removidos ou mascarados por redaction quando alterarem a informacao disponivel;
- metadados autorizados que possam alterar a interpretacao ou admissibilidade.

`Policy`, `Rules`, `NormativeBasisSnapshot`, configuracao deterministica, tolerancias e projecao de autorizacao pertencem ao `context_hash`. A funcao semantica, tipo esperado e papel do `Subject`, o papel da Organization e a finalidade de avaliacao tambem pertencem ao `context_hash`. O mesmo campo nao e duplicado nas duas identidades sem justificativa explicita e contrato unico de canonicalizacao.

Campos observacionais que nao alteram o material avaliado nem a interpretacao, como identificador de tentativa, duracao fisica ou executor da tentativa, nao pertencem a nenhuma identidade semantica do snapshot.

---

## 6. Identidade criptografica

`snapshot_hash` e calculado sobre a representacao canonica do material avaliado. Ele permite afirmar que duas avaliacoes receberam o mesmo universo de informacoes e proveniencia relevantes.

`context_hash` e calculado sobre a representacao canonica da semantica de avaliacao:

- finalidade, papel e tipo esperado do `Subject`;
- papel semantico da Organization responsavel;
- `Policy` e `Rules` com versoes exatas;
- `NormativeBasisSnapshot` quando aplicavel;
- versao de motor, artefato, configuracao deterministica, unidades e tolerancias;
- politica de autorizacao, `FieldScope`, `Visibility`, `AccessPurpose` e projecao que tenham determinado os dados entregues;
- instantes e limitacoes que alterem aplicabilidade ou interpretacao.

`OrganizationContext` integral, tokens, credenciais, correlacao de requisicao e outros segredos nao entram no hash. Entra somente projecao minima, estavel e autorizada que possa alterar o universo de dados ou a interpretacao.

A presenca de dado sensivel em uma entrada hasheada nao torna sua divulgacao automaticamente segura. Exposicao de hashes, digests e referencias permanece sujeita a `Authorization`, `Visibility`, `FieldScope` e risco de enumeracao.

---

## 7. Canonicalizacao

Antes do hash, o Titan produz representacao canonica com regras explicitas:

- cada identidade declara tipo, dominio semantico, identificador de esquema e versao de canonicalizacao;
- campos possuem nomes, tipos e presenca definidos;
- campos ausentes e `null` sao distinguidos quando a semantica exigir;
- objetos usam ordem deterministica de campos;
- arrays representam conjunto ordenado por chave canonica ou sequencia semanticamente declarada;
- UUIDs, identificadores e referencias possuem representacao estavel;
- textos usam UTF-8 e normalizacao declarada;
- datas e instantes usam formato, timezone e precisao declarados;
- numeros usam representacao, escala e arredondamento definidos;
- mapas nao dependem da ordem do banco, API ou runtime;
- campos nao autorizados, secretos ou sem efeito interpretativo sao excluidos explicitamente.

Hash de JSON bruto, de resposta HTTP, de ordem de consulta ou de linha fisica de banco nao constitui canonicalizacao.

Hashes de natureza diferente usam separacao explicita de dominio e envelope versionado. O contrato nao escolhe algoritmo nesta ADR, mas impede que snapshot, contexto, avaliacao e decisao compartilhem entrada sem tipo e versao identificaveis.

---

## 8. Proveniencia

Claims, Evidences e relacoes nao entram por mera existencia no grafo. Participam somente quando forem entradas autorizadas da avaliacao ou quando sua referencia for necessaria para demonstrar proveniencia, admissibilidade, cobertura ou limitacao do material efetivamente avaliado.

Toda referencia que possa alterar significado, admissibilidade, confianca, autoria, origem, cobertura ou interpretacao participa da identidade criptografica.

Isso inclui, quando aplicavel:

- `source_reference` de um `Fact`;
- `EvidenceReference` e referencias de artefato-fonte;
- `RelationshipReference`, tipo e direcao de relacao;
- identidade, versao, digest, autoria e escopo de fonte externa;
- estado de verificacao, cobertura, limitacao ou redaction que tenha afetado o material entregue.

Referencias de origem sao canonicalizadas segundo sua funcao. Identidade, versao, digest, autoria e escopo participam quando relevantes. Localizador fisico substituivel participa somente se sua mudanca alterar verificabilidade, admissibilidade ou material disponivel.

Alterar referencia semanticamente relevante exige novo `snapshot_hash`, mesmo quando o payload visivel do fato nao mudar.

---

## 9. Objetos externos

Objeto externo, como PDF, imagem, bundle ou resposta de fonte, nao precisa ser copiado integralmente para o snapshot quando classificacao, retencao ou viabilidade impedirem isso.

O snapshot preserva material minimo suficiente para identifica-lo e verificar seu papel, como:

- identificador estavel;
- tipo e versao;
- digest e algoritmo quando disponivel;
- origem e referencia autorizada;
- instante relevante;
- escopo, cobertura e limitacoes;
- assinatura ou estado de verificacao quando influentes.

Objeto externo sem identidade verificavel suficiente pode ser registrado como limitacao e participar somente quando a `Policy` permitir. Ele impede alegacao de reproducao criptografica integral daquele objeto; digest opcional silencioso nao e permitido.

---

## 10. Relacao com temporalidade

O snapshot preserva os instantes que participaram da selecao e da interpretacao. Esta ADR nao define o significado completo de tempo do fato, registro, descoberta ou conhecimento.

A ADR-0052 definira a semantica desses tempos. Ate la, nenhuma implementacao pode usar tempo corrente ou projetar conhecimento posterior sem que o instante utilizado esteja explicitamente representado no snapshot ou contexto.

---

## 11. Hashes derivados

```text
material avaliado canonico  -> snapshot_hash
semantica de avaliacao      -> context_hash
snapshot_hash + context_hash + RuleResults + outcome + metadados semanticos proprios da Evaluation
                           -> evaluation_hash
evaluation_hash + DecisionReasons + resultado + emissao
                           -> decision_hash
decisao e componentes exportados
                           -> dossier_hash
```

Cada hash responde pergunta diferente. A versao do motor ja participa de `context_hash` e nao e duplicada como entrada independente de `evaluation_hash`. Nenhum hash posterior permite omitir, reconstruir por inferencia ou substituir a identidade do snapshot original.

---

## 12. Invariantes

1. Mesmo material canonico, mesma proveniencia relevante, mesmo dominio e mesma versao de canonicalizacao produzem mesmo `snapshot_hash`.
2. Alterar elemento que influencie interpretacao reproduzivel produz nova identidade correspondente.
3. Alterar ordem fisica de banco, mapa ou conjunto nao altera hash canonico.
4. Campos nao autorizados ou sem efeito interpretativo nao participam da identidade semantica.
5. `source_reference` e outras referencias semanticamente relevantes participam de `snapshot_hash`.
6. Politica, regra, fundamentacao e configuracao deterministica participam de `context_hash`.
7. Segredos, tokens e metadados observacionais nao participam de identidades semanticas.
8. Snapshot nao depende de ordem de consulta, resposta HTTP ou estado futuro do banco.
9. Objeto externo relevante possui referencia, versao ou digest, escopo e limitacoes suficientes.
10. Nova informacao produz novo snapshot ou nova avaliacao; nao altera identidade historica existente.
11. Tipo, dominio semantico, identificador de esquema e versao de canonicalizacao participam da identidade criptografica.
12. Conteudo removido ou mascarado por redaction altera `snapshot_hash` quando afetar a informacao entregue.
13. Politica de autorizacao e projecao que causaram redaction participam de `context_hash` quando necessarias a reproducao.
14. Elemento relacionado nao entra por mera existencia; entra somente quando utilizado ou necessario a proveniencia.
15. Localizador fisico de fonte nao se confunde com identidade semantica da fonte.
16. Entradas sensiveis hasheadas continuam sujeitas a controle de exposicao.

---

## 13. Fluxo de referencia

```text
Facts, Claims, Evidences, Relationships e proveniencia autorizada
        -> Canonical Snapshot
        -> snapshot_hash

Policy, Rules, NormativeBasisSnapshot e configuracao deterministica
        -> Canonical Evaluation Context
        -> context_hash

snapshot_hash + context_hash
        -> RuleExecutionContext
        -> Evaluation
        -> Decision
        -> Dossier
```

O caso de uso preserva a associacao entre as duas identidades. A regra recebe contexto delimitado conforme ADR-0050; ela nao recompila o snapshot, consulta banco ou decide quais referencias ignorar.

---

## 14. Estado atual e transicao

O Core atual possui `FactSnapshot` e `snapshot_hash`, mas a representacao hasheada ainda nao cobre integralmente referencias de proveniencia, relacoes, contexto autorizado, temporalidade completa ou canonicalizacao formal. `source_reference`, em particular, deve passar a alterar a identidade do snapshot.

A transicao deve ocorrer sem reescrever `Evaluations` e `Decisions` existentes. Novas versoes de snapshot e hash devem declarar contrato e versao de canonicalizacao. Leituras historicas distinguem a identidade legada da identidade conforme esta ADR, sem afirmar equivalencia onde ela nao puder ser demonstrada.

T1 da ADR-0048 e implementacao inicial obrigatoria desta decisao. T2 e ADR-0052 completarao a dimensao temporal.

---

## 15. Alternativas rejeitadas

### 15.1 Hash do JSON bruto

Rejeitada porque ordem de chaves, campos omitidos, formatacao e biblioteca podem alterar bytes sem alterar semantica.

### 15.2 Hash de linha ou estado do banco

Rejeitada porque estrutura fisica, ordem de consulta e estado posterior nao definem o universo autorizado de avaliacao.

### 15.3 Hash de resposta da API

Rejeitada porque representacao de transporte, audiencia e paginacao nao substituem contexto e proveniencia da avaliacao.

### 15.4 Hash somente de Facts

Rejeitada porque omite evidencia, origem, relacoes, objetos externos e semantica de avaliacao que podem alterar resultado.

---

## 16. Criterios de conformidade

Uma implementacao esta conforme esta ADR somente se:

- produz serializacao canonica independente de banco, API e runtime;
- calcula `snapshot_hash` sobre material e proveniencia relevantes;
- calcula `context_hash` sobre semantica e projecao autorizada relevantes;
- muda identidade quando `source_reference` ou outra referencia relevante mudar;
- muda `snapshot_hash` quando redaction alterar o conteudo entregue;
- declara tipo, dominio, esquema e versao de canonicalizacao para cada identidade;
- exclui segredos e metadados observacionais das identidades semanticas;
- controla exposicao de hashes e referencias sensiveis;
- preserva versoes, digests, limitacoes e referencias externas necessarias;
- testa igualdade para mesma semantica e desigualdade para toda mudanca relevante;
- nao reescreve snapshots, avaliacoes ou decisoes historicas.

---

## 17. Questoes adiadas

Permanecem para ADRs ou incrementos proprios:

- algoritmo de hash, dominio de separacao e rotacao;
- especificacao formal de serializacao canonica;
- modelo de unidades, dimensionalidade e representacao decimal;
- semantica completa de temporalidade bitemporal;
- armazenamento fisico e indexes;
- Merkle trees, checkpoints, assinatura e verificacao independente de conjuntos;
- formato de dossie e verificacao offline.

---

## Conclusao

O Snapshot e a fronteira entre a realidade registrada e sua interpretacao.

Quando a identidade criptografica cobre material, proveniencia e contexto relevantes, o Titan pode demonstrar nao apenas que uma avaliacao existiu, mas exatamente qual representacao conhecida e autorizada da realidade ela recebeu.
