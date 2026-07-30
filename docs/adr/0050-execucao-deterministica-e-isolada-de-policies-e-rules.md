# ADR-0050 - Execucao deterministica e isolada de Policies e Rules

**Data:** 2026-07-29<br>
**Status:** ACEITA<br>
**Aceita em:** 2026-07-29<br>
**Base normativa:** `DOMAIN.md` v1.19 e ADRs aceitas ate ADR-0049<br>
**Escopo:** Titan Core<br>
**Relacionadas:** ADR-0036, ADR-0048, ADR-0049

---

## 1. Contexto

Uma regra pode possuir codigo aparentemente deterministico e ainda produzir resultados nao reproduziveis se consultar estado mutavel, depender de servicos externos, usar tempo corrente, aleatoriedade nao controlada, configuracao nao versionada ou informacoes que nao pertencam ao snapshot autorizado.

Portanto, determinismo no Titan nao e apenas propriedade do algoritmo. E propriedade do conjunto formado por codigo, entradas, contexto, dependencias, versoes, unidades, tolerancias e ambiente de execucao.

As ADRs 0048 e 0049 definem, respectivamente, a decisao explicavel e a selecao de politica. Esta ADR define o contrato que impede cada vertical ou runtime de executar suas regras com semantica diferente, acesso oculto ao sistema ou efeitos colaterais nao auditaveis.

---

## 2. Problema

O Titan precisa garantir que uma `Rule`:

- execute somente sobre informacao autorizada e preservada;
- produza resultado tecnico distinto de decisao oficial;
- trate ausencia, conflito e falha tecnica sem converte-los em nao conformidade;
- seja reproduzivel com as mesmas entradas, versoes e tolerancias;
- nao altere o dominio que esta avaliando;
- permita localizar regra, contexto, entrada, runtime e resultado depois da execucao.

Sem esse contrato, uma mesma `Policy` pode ser avaliada de maneiras incompativeis por modulos distintos, destruindo explicabilidade, auditabilidade e reproducao historica.

---

## 3. Decisao

Toda execucao de `Policy` e `Rule` no Titan devera obedecer a contrato arquitetural deterministico e auditavel, independentemente do mecanismo concreto de execucao.

O contrato e composto, no minimo, por:

- `RuleExecutionContext` delimitado;
- snapshot autorizado e imutavel;
- versao exata de `Policy` e `Rule`;
- versao do motor ou runtime;
- unidades, precisao, arredondamento e tolerancias declarados;
- limites de recursos;
- proibicao de efeitos externos nao registrados;
- `RuleResult` tecnico estruturado ou falha tecnica explicitamente classificada;
- evidencia estruturada e correlacionavel de toda tentativa de execucao, materializada como recibo persistido quando exigido pelo mecanismo ou caso de uso;
- rastreabilidade entre regra, entradas e resultado.

Uma `Rule` nao consulta livremente o sistema nem toma `Decision`. Ela recebe contexto delimitado, executa de forma deterministica e produz resultado tecnico estruturado.

---

## 4. Escopo e nao objetivos

Esta ADR define semantica, entradas, saidas, limites e invariantes de execucao.

Esta ADR nao define:

- formato de bytecode;
- runtime Wasm, compilador ou ABI;
- linguagem de autoria de regras;
- armazenamento fisico de modulos;
- detalhes de wasmtime, wasmer ou outro runtime;
- DSL de `RuleCondition`;
- estrategia de snapshot canonico ou temporalidade bitemporal completas;
- emissao de `Decision`, autoridade ou revisao humana.

Esses assuntos pertencem a ADR-0036, ADR-0048, ADRs futuras especializadas ou a implementacoes que cumpram este contrato.

---

## 5. Relacao com a ADR-0036

A ADR-0036 decidiu adotar WebAssembly Sandbox como mecanismo especializado para execucao segura, imutavel e historicamente reproduzivel de politicas normativas.

Esta ADR nao substitui, revoga ou reduz essa decisao. A ADR-0050 define o contrato geral que toda execucao de `Policy` e `Rule` deve cumprir. A ADR-0036 define uma implementacao aprovada desse contrato para regras normativas compiladas em Wasm.

Em caso de conflito:

- prevalece esta ADR quanto a semantica de execucao, entradas e resultados;
- prevalece a ADR-0036 quanto ao mecanismo Wasm ja aceito;
- qualquer incompatibilidade deve ser resolvida por nova ADR, nunca por interpretacao silenciosa.

---

## 6. RuleExecutionContext

`RuleExecutionContext` e contrato de aplicacao delimitado para uma execucao, nao nova entidade normativa persistida do Core nesta fase.

Ele deve fornecer somente:

- identificadores e versoes de `Policy` e `Rule`;
- `Subject`, finalidade e Organization autorizados;
- snapshot autorizado, seu hash e referencias permitidas;
- instante de referencia e instantes de conhecimento disponiveis no escopo;
- configuracao deterministica, unidades, precisao e tolerancias;
- versao do motor, runtime ou artefato executavel;
- limites de tempo, memoria, entrada e saida;
- correlacao e metadados necessarios para recibo.

O contexto nao fornece conexao de banco, cliente HTTP, relogio corrente, gerador aleatorio, sistema de arquivos, segredo, token ou capacidade de alterar objetos de origem.

---

## 7. Entradas autorizadas e dependencias

Toda dependencia capaz de alterar resultado deve estar:

- incorporada ao snapshot; ou
- versionada, congelada e identificada no contexto; ou
- proibida para aquela execucao.

Consultas a banco, rede, servico externo, configuracao de ambiente e estado global sao proibidas durante a execucao, salvo se o resultado dessas consultas ja estiver representado e autorizado no contexto.

Uma `Rule` nao interpreta payload interno de vertical fora dos contratos de fatos e referencias entregues. O resolvedor de fatos e o `DecisionEngine` permanecem responsaveis por preparar o contexto antes da execucao.

---

## 8. Determinismo temporal e aleatoriedade

Tempo corrente nao e entrada valida. Uma regra usa somente instantes preservados no `RuleExecutionContext`.

Aleatoriedade e proibida. Se um caso excepcional exigir simulacao probabilistica, a semente, algoritmo, versao e finalidade devem ser explicitamente definidos em ADR propria; esse caso nao pode se apresentar como execucao normativa deterministica.

Mesmo codigo, mesmas entradas, mesmas versoes, mesma configuracao e mesmas tolerancias produzem resultado equivalente dentro das tolerancias declaradas.

---

## 9. Unidades, precisao e tolerancias

Unidade, escala, precisao, arredondamento, intervalo de tolerancia e metodo de comparacao fazem parte do contrato de execucao quando um valor numerico participar do resultado.

Conversao implicita, arredondamento dependente de runtime ou comparacao de ponto flutuante sem tolerancia declarada sao proibidos. Falta de unidade, dimensao incompativel ou tolerancia ausente produz informacao insuficiente ou falha de contrato, conforme a natureza do problema; nunca resultado negativo silencioso.

Enquanto nao houver contrato numerico canonico, uma `Rule` numerica deve declarar a representacao utilizada, como inteiro escalado, decimal de precisao definida ou outro formato aprovado. Uso de ponto flutuante nativo do runtime, por si so, nao demonstra reproducao entre mecanismos distintos.

---

## 10. RuleResult e resultado tecnico

`RuleResult` permanece o resultado individual normativo ja definido no `DOMAIN.md`: `ATENDIDA`, `NAO_ATENDIDA`, `PENDENTE`, `NAO_APLICAVEL` ou `INDETERMINADA`.

Ausencia de informacao deve ser representada como `PENDENTE` ou `INDETERMINADA`, conforme contrato deterministico da versao da regra; essa escolha nao pertence ao runtime nem ao executor. Em termos gerais, `PENDENTE` indica informacao requerida que pode ser legitimamente complementada no fluxo previsto, enquanto `INDETERMINADA` indica impossibilidade de concluir com o conjunto autorizado de informacoes ou ambiguidade nao resolvida.

Quando uma `Rule` detectar conflito relevante em suas entradas, ela produz `RuleResult.INDETERMINADA` acompanhado de codigo estruturado que identifique o conflito. A agregacao pode produzir `EvaluationOutcome.EVIDENCIA_CONFLITANTE`, conforme a `Policy` versionada. A `Rule` nunca produz diretamente um `EvaluationOutcome`.

`NAO_ATENDIDA` significa condicao avaliavel que falhou. Ela nao representa timeout, erro de runtime, entrada invalida, limite de recurso ou violacao do contrato de execucao.

---

## 11. Falha tecnica e classificacao de execucao

Falha tecnica e distinta de resultado normativo. Categorias tecnicas minimas sao:

- `SUCCESS`;
- `TIMEOUT`;
- `RESOURCE_LIMIT`;
- `INVALID_INPUT`;
- `RUNTIME_ERROR`;
- `CONTRACT_VIOLATION`;
- `UNSUPPORTED_VERSION`.

Nesta fase, essas categorias descrevem o contrato tecnico e o conteudo de recibos ou erros de aplicacao; elas nao criam novo enum persistido do Core. Sua persistencia generica exige definicao formal no `DOMAIN.md`.

Uma falha tecnica impede a producao de `RuleResult` conclusivo. O caso de uso deve preservar classificacao, correlacao, entradas identificaveis e limitacoes, sem apresenta-la como conformidade ou nao conformidade.

---

## 12. Isolamento e efeitos colaterais

Execucao de regra e livre de efeitos colaterais. Ela nao cria, modifica ou remove `Claims`, `Evidences`, `Events`, `Facts`, relacoes, `Policies`, `Rules`, `Evaluations` ou `Decisions`.

Persistir `RuleResult`, `Evaluation` e recibos e responsabilidade do caso de uso externo a regra. Log tecnico nao pode carregar payload sensivel, segredo ou dado nao autorizado; auditoria deve registrar somente material permitido e necessario.

---

## 13. Limites de recursos

Limites semanticamente deterministicos fazem parte do contrato reproduzivel, como:

- quantidade maxima de instrucoes ou combustivel do runtime;
- quantidade maxima de operacoes;
- profundidade maxima de avaliacao ou recursao;
- memoria logica;
- tamanho de entrada e saida;
- quantidade maxima de regras ou itens processados.

Limites operacionais dependentes do ambiente, como wall-clock timeout, prazo do processo, cancelamento por indisponibilidade ou limite do orquestrador, protegem a infraestrutura, mas nao integram por si sos a identidade semantica do resultado.

Exceder limite deterministico gera classificacao tecnica identificavel no contexto reproduzivel. Quando um limite operacional interromper a tentativa, o sistema registra falha tecnica sem produzir conclusao normativa. Reproducao posterior pode executar novamente o mesmo contexto, preservando a observacao da falha anterior sem substitui-la.

---

## 14. Recibo e rastreabilidade

Toda tentativa de execucao deve deixar evidencia estruturada, correlacionavel e auditavel. A equivalencia entre recibos considera os elementos semanticos:

- `Policy`, `Rule` e versoes;
- hash e identificadores do contexto e snapshot;
- versao do motor, runtime ou artefato;
- configuracao deterministica, unidades, tolerancias e limites deterministicos;
- `RuleResult` ou falha tecnica classificada;
- hash da saida e limitacoes semanticas.

Identificador da tentativa, executor, inicio, termino, duracao, infraestrutura e falhas operacionais sao metadados observacionais. Eles podem variar entre execucoes e nao integram, por si sos, a identidade semantica do resultado reproduzido.

Quando Wasm Sandbox for utilizado, `NormativeExecutionReceipt` da ADR-0036 e o registro imutavel que materializa esse recibo. Outros mecanismos devem fornecer evidencia equivalente dentro dos contratos vigentes, sem criar objeto autoritativo paralelo. Ausencia de recibo persistido nao autoriza execucao opaca.

---

## 15. Tratamento de erro, ausencia e conflito

```text
Condicao avaliavel violada                    -> RuleResult.NAO_ATENDIDA
Informacao exigida ausente                     -> PENDENTE ou INDETERMINADA, conforme contrato da Rule
Conflito detectado pela Rule                   -> RuleResult.INDETERMINADA com codigo estruturado
Conflito agregado pela Policy                  -> EvaluationOutcome.EVIDENCIA_CONFLITANTE
Rule valida, fora do escopo concreto do Subject -> RuleResult.NAO_APLICAVEL
Rule ou Policy fora da vigencia resolvida      -> CONTRACT_VIOLATION, INVALID_INPUT ou interrupcao anterior
Timeout, runtime ou limite excedido            -> falha tecnica classificada
Entrada ou contrato invalido                   -> falha tecnica classificada
```

Nenhuma linha dessa tabela autoriza transformar falha tecnica em conclusao regulatoria. A agregacao em `EvaluationOutcome` permanece responsabilidade da `Policy` e do motor de avaliacao.

---

## 16. Invariantes

1. Uma `Rule` executa somente sobre `RuleExecutionContext` delimitado.
2. Nenhuma `Rule` consulta diretamente banco, rede, relogio corrente, sistema de arquivos ou servico externo nao representado no contexto.
3. Mesmas entradas, versoes e configuracao produzem resultado equivalente dentro das tolerancias declaradas.
4. Ausencia de informacao nao e resultado negativo.
5. Erro tecnico nao e falha regulatoria.
6. Conflito de evidencia nao e resolvido silenciosamente pela `Rule`.
7. Toda execucao produz `RuleResult` estruturado ou falha tecnica explicitamente classificada.
8. Unidades, precisao, arredondamento e tolerancias pertencem ao contrato.
9. Toda dependencia que altere resultado e versionada, congelada ou incorporada ao snapshot.
10. A execucao nao altera objetos de origem.
11. O recibo permite verificar regra, entrada, runtime e saida semanticamente, preservando observacoes operacionais separadas dentro do escopo autorizado.
12. O mecanismo Wasm da ADR-0036 cumpre estes invariantes quando utilizado.
13. Metadados observacionais de uma tentativa nao alteram a identidade semantica da execucao reproduzida.
14. O runtime nao escolhe livremente entre `PENDENTE` e `INDETERMINADA`.
15. Rule fora da vigencia ou aplicabilidade resolvida nao e executada como regra normalmente selecionada.

---

## 17. Fluxo de referencia

```text
Policy selecionada
        -> Snapshot autorizado
        -> Rules versionadas
        -> RuleExecutionContext
        -> RuleResults ou falhas tecnicas classificadas
        -> EvaluationOutcome
```

O caso de uso de avaliacao, coordenado pelo `DecisionEngine` quando fizer parte de fluxo decisorio, resolve o contexto, aciona o mecanismo de execucao, persiste resultados e agrega a `Evaluation`. O executor de regras nao seleciona `Policy`, nao coleta informacao livremente, nao persiste objetos de dominio e nao emite `Decision`.

---

## 18. Testes de reprodutibilidade

Toda implementacao do contrato deve possuir testes que comprovem:

- mesmas entradas e versoes produzem o mesmo `RuleResult` e recibo semanticamente equivalente;
- alteracao de fato, referencia, unidade, tolerancia ou versao altera o contexto identificavel;
- consulta externa, relogio corrente ou estado global nao participa da execucao;
- ausencia, conflito e falha tecnica produzem categorias distintas;
- timeout e limite de recurso nao produzem `NAO_ATENDIDA`;
- metadados observacionais podem variar sem alterar a equivalencia semantica do recibo;
- a regra nao altera objetos de origem;
- reproducao historica usa o mesmo contexto preservado, nao configuracao corrente.

---

## 19. Estado atual e transicao

O Core ja possui `RuleEvaluationEngine`, `PolicyEvaluationService`, `RuleResult`, `EvaluationOutcome`, snapshot de fatos, hashes e `DecisionService`. Essas capacidades sao implementacao parcial do contrato: usam fatos fornecidos pelo snapshot e agregam resultados tecnicos, mas ainda nao oferecem recibo uniforme, limites executaveis, temporalidade completa, hash de proveniencia e separacao formal de falha tecnica.

A transicao deve preservar `RuleResults` e `Evaluations` historicos. Novas capacidades devem introduzir o contrato por incrementos separados, especialmente em conjunto com T1 e T2 da ADR-0048 e as ADRs 0051 e 0052 propostas.

---

## 20. Alternativas rejeitadas

### 20.1 Cada vertical define seu proprio executor

Rejeitada porque fragmenta semantica de ausencia, conflito, erro e reproducao.

### 20.2 Rule consulta diretamente banco ou servico externo

Rejeitada porque torna a entrada invisivel, mutavel e nao reproduzivel.

### 20.3 Excecao tecnica equivale a nao conformidade

Rejeitada porque confunde defeito operacional com condicao normativa avaliada.

### 20.4 Reabrir a decisao Wasm

Rejeitada porque a ADR-0036 ja decidiu o mecanismo especializado. Esta ADR apenas define o contrato que ele deve cumprir.

---

## 21. Criterios de conformidade

Uma implementacao esta conforme esta ADR somente se:

- executa regras sobre contexto delimitado e snapshot autorizado;
- bloqueia I/O e dependencias mutaveis nao registradas;
- preserva versoes, tolerancias e limites relevantes;
- distingue resultado normativo de falha tecnica;
- nao executa como selecionada `Rule` fora da vigencia ou aplicabilidade resolvida;
- preserva recibo ou evidencia equivalente;
- distingue limites deterministicos de limites operacionais;
- nao altera objetos de origem;
- possui testes de determinismo e reproducao;
- cumpre a ADR-0036 quando executar politica normativa em Wasm.

---

## 22. Questoes adiadas

Permanecem para ADRs ou incrementos proprios:

- representacao persistida generica de classificacao tecnica de execucao;
- serializacao canonica completa do snapshot e de suas referencias;
- modelo de unidades e dimensionalidade;
- tolerancias por dominio e por jurisdicao;
- DSL de autoria de regras;
- limites concretos por runtime e perfil operacional;
- armazenamento e verificacao independente de recibos fora de Wasm.

---

## Conclusao

Determinismo nao e apenas executar o mesmo algoritmo. E impedir que qualquer elemento nao preservado participe silenciosamente do resultado.

Com este contrato, toda regra do Titan pode ser examinada como funcao de contexto delimitado, versoes identificadas e entradas auditaveis, independentemente do runtime que a execute.
