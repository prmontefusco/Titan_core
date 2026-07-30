# ADR-0048 — Arquitetura de decisões explicáveis e reproduzíveis

**Data:** 2026-07-29<br>
**Status:** ACEITA<br>
**Aceita em:** 2026-07-29<br>
**Base normativa:** `DOMAIN.md` v1.19 e ADRs aceitas até a ADR-0047<br>
**Escopo:** Titan Core<br>
**Relacionadas:** ADR-0046, ADR-0047, `TITAN_ARCHITECTURE_PRINCIPLES.md`

> **A confiança não é armazenada. Ela é demonstrada.**

---

## 1. Contexto

O Titan já possui uma linguagem normativa capaz de representar:

- `Source`;
- `Claim`;
- `Evidence`;
- `Event`;
- `Fact`;
- `Policy`;
- `Rule`;
- `Evaluation`;
- `DecisionProposal`;
- `Decision`;
- `DecisionReason`;
- `Dossier`;
- proveniência, temporalidade, autoridade e revisão.

Entretanto, a mera existência desses conceitos não determina, por si só, como devem ser coordenados para produzir uma decisão explicável, reproduzível e auditável.

Sem uma decisão arquitetural explícita, diferentes módulos podem:

- consultar diretamente entidades de uma vertical dentro de regras;
- produzir decisões sem snapshot suficiente;
- tratar `Fact` como verdade absoluta;
- misturar avaliação técnica com autoridade decisória;
- recalcular silenciosamente uma decisão histórica;
- usar a `Policy` vigente para explicar uma decisão tomada sob versão anterior;
- criar explicações textuais sem códigos estruturados;
- esconder lacunas, conflitos ou limitações;
- introduzir conceitos paralelos ao `DOMAIN.md`;
- acoplar o Core à pecuária ou a uma regulamentação específica.

Esta ADR estabelece a arquitetura normativa para coordenar os conceitos já definidos no `DOMAIN.md`.

Ela não cria uma segunda ontologia e não introduz uma entidade genérica `Assertion`.

---

## 2. Problema

O Titan precisa responder, de forma verificável:

1. Qual informação foi considerada?
2. De onde ela veio?
3. Quais evidências a sustentavam, contestavam ou contextualizavam?
4. Qual `Policy` e quais `Rules` foram aplicadas?
5. Qual base normativa foi utilizada?
6. Qual resultado técnico foi produzido?
7. Quem possuía autoridade para emitir a conclusão?
8. Por que a decisão foi tomada?
9. Quais lacunas, conflitos, restrições e incertezas permaneceram?
10. Como a avaliação pode ser tecnicamente reproduzida no futuro?

Essas respostas não podem depender:

- do estado atual do banco;
- da versão corrente da `Policy`;
- de consultas posteriores a serviços externos;
- de código específico de uma vertical;
- de memória institucional;
- de explicação manual não estruturada;
- de inferência sobre dados que não foram preservados.

---

## 3. Decisão

O Titan adotará uma arquitetura de decisão baseada na coordenação explícita da cadeia canônica:

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

Essa cadeia é complementada pelos insumos normativos:

```text
Policy
  + Rules
  + NormativeBasisSnapshot
  + versão do motor
  + contexto temporal
  + autoridade
             ↓
         Evaluation
             ↓
    DecisionProposal
             ↓
          Decision
             ↓
          Dossier
```

As setas representam navegabilidade de proveniência, dependência explicativa ou participação na avaliação. Elas não implicam que toda relação seja causal, temporal ou obrigatória.

A coordenação será realizada pelo `DecisionEngine`, conforme o significado normativo já definido no `DOMAIN.md`.

---

## 4. Princípio central

> Uma `Decision` é uma conclusão histórica contextualizada, produzida a partir de uma `Evaluation`; ela não é um atributo permanente da realidade.

Consequentemente:

- uma `Decision` nunca substitui `Fact`;
- uma `Decision` nunca altera a informação que avaliou;
- uma mudança de `Policy` não modifica decisões anteriores;
- nova informação não reabre silenciosamente avaliações históricas;
- revisão, reprodução, simulação e reavaliação são operações distintas;
- toda decisão deve preservar elementos suficientes para explicar seu resultado.

---

## 5. Limites desta ADR

Esta ADR:

- define a arquitetura de coordenação do processo decisório;
- fixa responsabilidades e invariantes;
- define fronteiras entre domínio, avaliação, autoridade e apresentação;
- orienta implementações futuras do `DecisionEngine`.

Esta ADR não:

- cria nova entidade genérica `Assertion`;
- altera o significado de `Fact`, `Evidence`, `Evaluation` ou `Decision`;
- define uma DSL de políticas;
- define armazenamento físico;
- escolhe framework, banco de dados ou linguagem;
- cria regras específicas para União Europeia, China, SISBOV ou qualquer mercado;
- determina emissão automática para todas as decisões;
- substitui o `DOMAIN.md`;
- exige que todas as capacidades sejam implementadas no mesmo incremento.

---

## 6. Responsabilidades arquiteturais

### 6.1 Domínio operacional

O domínio operacional registra acontecimentos, declarações, evidências, relações e informações aceitas dentro da linguagem da vertical.

Ele pode produzir ou referenciar:

- `Claim`;
- `Evidence`;
- `Event`;
- `Fact`;
- `UniversalRelation`;
- referências a `Subject`;
- projeções reconstruíveis.

O domínio operacional não:

- escolhe a `Policy` aplicável por conveniência;
- codifica regras de mercado dentro de entidades;
- produz `DecisionResult` diretamente;
- considera uma condição atendida apenas porque o estado atual parece favorável;
- interpreta base normativa específica no agregado.

Exemplo:

`TreatmentApplication` conhece medicamento, dose, datas, responsável e evidências associadas.

`TreatmentApplication` não decide se um animal está apto para determinado mercado.

### 6.2 Seleção de Policy

A seleção da `Policy` é uma responsabilidade explícita de aplicação.

Ela deve considerar, quando aplicável:

- finalidade;
- mercado;
- jurisdição;
- tipo de decisão;
- instante de referência;
- instante do conhecimento;
- `Subject`;
- Organization;
- versão e vigência;
- `NormativeBasis`;
- contexto contratual ou regulatório;
- restrições de autorização.

A ausência, ambiguidade ou conflito de `Policy` aplicável não deve ser resolvida por escolha silenciosa.

Deve produzir resultado indeterminado, revisão ou código normativo correspondente.

### 6.3 Coleta de informações

O `DecisionEngine` coleta apenas informações autorizadas e relevantes para o escopo da avaliação.

A coleta deve:

- respeitar `OrganizationContext`;
- respeitar `Authorization`, `Visibility`, `FieldScope` e classificação;
- preservar IDs e versões dos objetos considerados;
- distinguir informação presente, ausente, inacessível e não avaliada;
- preservar o instante de referência;
- preservar o instante do conhecimento;
- registrar exclusões relevantes;
- impedir consulta arbitrária da vertical pelas `Rules`.

A coleta não transforma automaticamente `Claim` em `Fact` nem `Evidence` em informação admissível.

### 6.4 Admissibilidade de Evidence

Quando a `Policy` exigir avaliação de admissibilidade, o uso de `Evidence` deve ser precedido ou acompanhado por `EvidenceAdmissibilityAssessment`.

A admissibilidade:

- é contextual à `Policy`, finalidade e `Evaluation`;
- não altera `VerificationStatus`;
- não declara verdade material;
- pode aceitar, restringir, rejeitar ou exigir revisão;
- deve preservar códigos de razão e limitações.

Uma `Evidence` tecnicamente íntegra pode ser inadmissível para determinada decisão.

Uma `Evidence` admissível não se torna verdade absoluta.

### 6.5 Execução de Rules

Cada `Rule` publicada é imutável e versionada.

Sua execução deve ser:

- determinística para entradas equivalentes;
- isolada de efeitos colaterais;
- limitada ao snapshot autorizado;
- independente de consultas mutáveis não registradas;
- identificável por código e versão;
- capaz de produzir `RuleResult`;
- capaz de registrar informação insuficiente ou conflito;
- incapaz de alterar objetos de origem.

Uma `Rule` não emite `Decision`.

Ela produz resultado técnico individual.

### 6.6 Evaluation

A `Evaluation` é o registro imutável da execução de uma `Policy` sobre um snapshot delimitado.

Toda `Evaluation` deve preservar ou referenciar, quando aplicável:

- `Organization`;
- `Subject`;
- finalidade;
- `Policy` e versão;
- `Rules` e versões;
- `NormativeBasisSnapshot`;
- `Claims`;
- `Facts`;
- `Evidences`;
- relações consideradas;
- `RuleResults`;
- `EvaluationOutcome`;
- instante de referência;
- instante do conhecimento;
- versão do motor;
- hash do snapshot;
- executor;
- lacunas;
- conflitos;
- exclusões;
- limitações.

A `Evaluation` não é alterada após sua criação.

Correção de informação, nova evidência, mudança de política ou mudança de motor produz outra operação formal, nunca mutação da avaliação original.

### 6.7 EvaluationOutcome

`EvaluationOutcome` representa o resultado técnico agregado antes da emissão da decisão.

Ele não:

- autoriza operação;
- publica conclusão;
- substitui `DecisionResult`;
- comprova autoridade;
- representa decisão oficial;
- deve ser apresentado como “aprovado” sem `Decision`.

Estados como informação insuficiente, evidência conflitante, validação pendente e revisão humana necessária devem permanecer explícitos.

### 6.8 DecisionProposal

Quando a emissão exigir revisão humana ou autorização adicional, o motor produz `DecisionProposal`.

A proposta:

- referencia exatamente uma `Evaluation`;
- preserva resultado proposto;
- preserva `DecisionReasons`;
- preserva restrições e ações;
- identifica autoridade e aprovações requeridas;
- não altera estado operacional;
- não é apresentada como decisão oficial;
- permanece imutável.

A proposta não pode ser promovida a `Decision` por simples mudança de status.

A emissão cria uma nova `Decision` vinculada à proposta.

### 6.9 Decision

Toda `Decision` deve derivar de exatamente uma `Evaluation`.

Ela deve preservar ou referenciar:

- `Subject`;
- finalidade;
- `Evaluation`;
- `Policy` e versão;
- `NormativeBasisSnapshot`;
- `RuleResults`;
- hash do snapshot;
- `DecisionResult`;
- `DecisionReasons`;
- ações;
- restrições;
- autoridade;
- método de emissão;
- aprovações;
- validade;
- correlação;
- momento;
- versão do motor;
- `Digest`.

Uma decisão histórica nunca é atualizada para refletir conhecimento posterior.

Mudanças produzem nova `Evaluation`, nova `Decision` e, quando aplicável, `DecisionRelation`.

### 6.10 DecisionReason

A explicação não será apenas texto livre.

Toda conclusão relevante deve possuir razões estruturadas por meio de `DecisionReason`.

Cada razão deve preservar, quando aplicável:

- código estável;
- `Rule`;
- condição avaliada;
- valor e unidade autorizados;
- condição esperada;
- `EvidenceReferences`;
- assessments utilizados;
- severidade contextual;
- ações recomendadas;
- limitações;
- mensagem humana.

O código é contrato.

A mensagem pode ser traduzida ou redigida para determinada audiência, mas não pode inverter, ampliar ou alterar a razão original.

### 6.11 Autoridade

Resultado técnico e autoridade decisória são conceitos distintos.

O `DecisionEngine` pode:

- produzir `Evaluation`;
- produzir `DecisionProposal`;
- emitir `Decision` automática somente quando autorizado.

A emissão deve respeitar `DecisionAuthorityProfile`.

O método deve distinguir:

- `AUTOMATICA_AUTORIZADA`;
- `HUMANA`;
- `HUMANA_ASSISTIDA`;
- `OVERRIDE_AUTORIZADO`.

Cargo, propriedade do registro, Membership ou autenticação isolada não comprovam autoridade decisória.

IA pode auxiliar na produção de `Claim`, extração, classificação ou proposta, mas não recebe autoridade por sua natureza técnica.

---

## 7. Snapshot e reprodutibilidade

### 7.1 Regra geral

Toda `Evaluation` deve ser vinculada a um snapshot delimitado e verificável.

O snapshot deve permitir identificar:

- quais objetos foram considerados;
- quais versões foram utilizadas;
- quais informações estavam ausentes;
- quais objetos estavam inacessíveis;
- quais dados foram excluídos;
- qual `Policy` foi aplicada;
- quais `Rules` foram executadas;
- qual base normativa foi utilizada;
- qual versão do motor executou a avaliação;
- quais instantes temporais foram considerados;
- quais hashes permitem verificar integridade.

O snapshot não precisa duplicar indiscriminadamente todos os payloads.

Pode utilizar referências estáveis, conteúdo canônico, Digests e material mínimo suficiente, conforme classificação, retenção e viabilidade técnica.

### 7.2 Tempo do fato e tempo do conhecimento

A avaliação deve distinguir:

- quando o acontecimento teria ocorrido;
- quando foi registrado;
- quando foi descoberto;
- quando passou a ser conhecido;
- quando a política era aplicável;
- quando a decisão foi emitida.

Conhecimento posterior não deve ser projetado sobre a avaliação original.

Uma reprodução histórica utiliza os elementos originais.

Uma reavaliação atual utiliza o contexto atual e produz novo registro.

### 7.3 Versão do motor

A versão do motor faz parte da reprodutibilidade.

Deve identificar, conforme aplicável:

- versão lógica;
- versão do runtime;
- digest do artefato executável;
- versão da DSL ou compilador;
- configuração determinística;
- tolerâncias numéricas;
- dependências relevantes.

Alteração do motor não modifica avaliações anteriores.

---

## 8. Operações posteriores à Decision

As operações abaixo são semanticamente distintas e não devem ser agrupadas sob um termo genérico como “replay”.

### 8.1 HistoricalReproduction

Reexecuta:

- snapshot original;
- `Policy` original;
- `Rules` originais;
- `NormativeBasisSnapshot` original;
- versão original do motor.

Seu objetivo é verificar reprodutibilidade técnica.

Não produz substituição automática da `Evaluation` ou `Decision`.

### 8.2 HistoricalComplianceAssessment

Produz nova avaliação sobre a correspondência de uma decisão histórica com a base considerada aplicável ao período.

Deve separar:

- conhecimento disponível originalmente;
- conhecimento descoberto posteriormente;
- interpretação normativa posterior;
- fontes recuperadas depois da decisão.

Não conclui automaticamente validade jurídica, culpa ou fraude.

### 8.3 CounterfactualSimulation

Aplica hipoteticamente outra `Policy`, `Rule`, base normativa ou conjunto de condições.

Seu resultado é simulação.

Não altera estado operacional nem afirma que aquele resultado existiu historicamente.

### 8.4 CurrentReevaluation

Avalia o contexto atual com fatos, evidências, políticas e regras atualmente aplicáveis.

Pode produzir nova `Evaluation` e nova `Decision`.

Deve preservar diferenças em relação às anteriores.

---

## 9. Dossier e explicabilidade

O `Dossier` é o snapshot auditável, imutável e, quando tecnicamente viável, autocontido da decisão ou do processo de conformidade.

Ele deve permitir compreender:

- o que foi avaliado;
- a proveniência das informações;
- a política e as regras aplicadas;
- a fundamentação normativa;
- os resultados individuais;
- o resultado agregado;
- a decisão emitida;
- as razões;
- as limitações;
- as revisões, relações ou overrides;
- a integridade do material.

O `Dossier` não é obrigatório em toda operação interna.

Quando emitido, não deve depender exclusivamente do estado futuro do banco para ser compreendido.

PDF é apenas uma representação do `Dossier`.

---

## 10. Explicação e autorização

A obrigação de explicabilidade não implica exposição irrestrita.

Toda apresentação de explicação deve respeitar:

- `Authorization`;
- `Visibility`;
- `FieldScope`;
- `AccessPurpose`;
- `DataClassification`;
- redaction;
- audiência;
- restrições de licença;
- limitações de exportação.

A versão redigida deve:

- preservar códigos de razão;
- não inverter a conclusão;
- não ocultar lacuna material de forma enganosa;
- indicar quando informações não podem ser apresentadas;
- distinguir “não considerado”, “inacessível”, “ausente” e “redigido”.

A explicação completa continua preservada dentro do escopo autorizado correspondente.

---

## 11. Invariantes

### I-01 — Derivação

Toda `Decision` referencia exatamente uma `Evaluation`.

### I-02 — Imutabilidade

`Evaluation`, `DecisionProposal`, `Decision`, `DecisionReason` e `Dossier` publicados são imutáveis.

### I-03 — Versionamento

Toda `Evaluation` referencia versões exatas de `Policy`, `Rules`, base normativa e motor.

### I-04 — Snapshot

Toda `Evaluation` possui snapshot delimitado, identificável e verificável.

### I-05 — Explicabilidade

Toda `Decision` possui razões estruturadas suficientes para explicar seu resultado dentro do escopo autorizado.

### I-06 — Autoridade

Nenhuma `Decision` oficial é emitida sem autoridade resolvida e método de emissão registrado.

### I-07 — Separação

`EvaluationOutcome` não é `DecisionResult`.

### I-08 — Não mutação da origem

O processo decisório não altera `Claims`, `Evidences`, `Events`, `Facts` ou relações de origem.

### I-09 — Conhecimento posterior

Nova informação não modifica silenciosamente avaliação ou decisão histórica.

### I-10 — Indeterminação explícita

Ausência, conflito, ambiguidade, indisponibilidade ou falta de autoridade não são convertidos silenciosamente em aprovação ou rejeição.

### I-11 — Independência vertical

O `DecisionEngine` não importa entidades concretas de verticais nem interpreta seus payloads internos.

### I-12 — Determinismo

Entradas equivalentes, versões equivalentes e configuração equivalente produzem resultado técnico equivalente dentro das tolerâncias declaradas.

### I-13 — Proveniência navegável

Deve ser possível navegar da `Decision` até seus insumos e, conforme autorização, dos insumos às decisões que os utilizaram.

### I-14 — Policy publicada

Uma `Policy` publicada não é alterada; evolução gera nova versão.

### I-15 — Explicação não textual apenas

Mensagem humana isolada não substitui `DecisionReason` estruturada.

### I-16 — Sem Assertion genérica implícita

A implementação não cria entidade genérica `Assertion` sem ADR aceita e alteração formal do `DOMAIN.md`.

---

## 12. Fluxo de referência

```text
1. Receber finalidade e Subject
2. Resolver OrganizationContext e Authorization
3. Selecionar Policy aplicável
4. Resolver Rules e NormativeBasisSnapshot
5. Delimitar snapshot e instantes
6. Coletar Claims, Facts, Evidences e relações autorizadas
7. Avaliar admissibilidade e conflitos quando aplicável
8. Executar Rules
9. Produzir RuleResults
10. Agregar EvaluationOutcome
11. Persistir Evaluation imutável
12. Produzir DecisionReasons e resultado proposto
13. Produzir e persistir DecisionProposal quando houver revisão ou aprovação adicional
14. Resolver DecisionAuthorityProfile, método de emissão e aprovações para eventual Decision
15. Produzir e persistir Decision somente quando a autoridade estiver resolvida
16. Produzir representações explicativas autorizadas
17. Emitir Dossier quando aplicável
```

Nenhuma etapa autoriza leitura ou emissão apenas por aparecer neste fluxo. `DecisionProposal` não exige autoridade emissora de `Decision`; a emissão de `Decision`, inclusive automática, somente ocorre depois da resolução da autoridade e das aprovações exigidas.

---

## 13. Exemplo conceitual: elegibilidade de um lote

O domínio pecuário pode registrar:

- aplicações de medicamentos;
- datas;
- doses;
- prescrições;
- movimentações;
- identificações;
- documentos;
- evidências;
- eventos de transformação.

O domínio não grava diretamente:

```text
eligible_for_eu = true
```

Para determinada finalidade, o `DecisionEngine`:

1. seleciona a `Policy` correspondente;
2. identifica as `Rules`;
3. delimita o lote e o período;
4. coleta informações e evidências autorizadas;
5. avalia carência, substâncias, rastreabilidade e lacunas;
6. registra `RuleResults`;
7. produz `EvaluationOutcome`;
8. produz proposta ou decisão autorizada;
9. registra razões e limitações;
10. permite emitir `Dossier`.

Uma atualização futura da política não altera a decisão anterior.

Ela pode motivar nova avaliação conforme a operação formal aplicável.

---

## 14. Alternativas rejeitadas

### 14.1 Decisão como campo mutável da entidade

Exemplo:

```text
animal.eligible = true
```

Rejeitada porque:

- perde contexto;
- oculta política e versão;
- não preserva razões;
- confunde estado com conclusão;
- dificulta reprodução;
- favorece sobrescrita silenciosa.

Projeções operacionais podem existir, mas devem derivar de decisões identificadas e não substituir o histórico.

### 14.2 Rules consultando diretamente bancos das verticais

Rejeitada porque:

- acopla o Core;
- impede snapshot confiável;
- introduz resultados não determinísticos;
- dificulta testes;
- contorna autorização;
- torna a proveniência opaca.

### 14.3 Explicação gerada apenas por IA

Rejeitada porque:

- texto não é contrato;
- pode omitir ou inventar razões;
- não garante correspondência com regras;
- não é suficiente para auditoria.

IA pode transformar razões estruturadas em linguagem humana, desde que preserve códigos, escopo, limitações e autorização.

### 14.4 Atualizar Decision quando novas evidências aparecem

Rejeitada porque viola histórico, temporalidade e reprodutibilidade.

Nova evidência pode gerar impacto, revisão, reavaliação ou nova decisão.

### 14.5 Usar sempre a Policy mais recente

Rejeitada porque destrói a capacidade de explicar decisões históricas.

Cada avaliação referencia versão exata.

### 14.6 Criar entidade genérica Assertion agora

Rejeitada porque o `DOMAIN.md` não define `Assertion` como entidade genérica do Core.

Asserções especializadas permanecem em seus contextos próprios.

---

## 15. Consequências positivas

- decisões auditáveis;
- reprodução técnica;
- separação entre domínio e regulamentação;
- políticas versionadas;
- explicações estruturadas;
- suporte a revisão humana;
- indeterminação explícita;
- capacidade de avaliar o mesmo fato sob mercados diferentes;
- preservação do conhecimento histórico;
- menor acoplamento entre Core e verticais;
- base para dossiês verificáveis;
- capacidade de evolução sem reescrever passado.

---

## 16. Custos e consequências negativas

- maior volume de registros;
- necessidade de snapshots e hashes;
- mais complexidade temporal;
- necessidade de versionar políticas e motor;
- aumento da disciplina necessária para autoria de regras;
- necessidade de distinguir avaliação, proposta e decisão;
- maior esforço de testes determinísticos;
- necessidade de preservar explicações e autorização;
- dificuldade adicional para consultas operacionais simples.

Esses custos são aceitos porque a finalidade do Titan exige auditabilidade e confiança demonstrável.

---

## 17. Riscos

### 17.1 Snapshot incompleto

Mitigação:

- contratos explícitos;
- hashes;
- testes de completude;
- códigos para lacunas;
- reprodução periódica.

### 17.2 Política ambígua

Mitigação:

- seleção explícita;
- resultado indeterminado;
- revisão;
- `NormativeBasisSnapshot`.

### 17.3 Regra não determinística

Mitigação:

- sandbox;
- proibição de dependência externa mutável;
- versionamento do motor;
- testes de reprodutibilidade.

### 17.4 Explicação divergente do resultado

Mitigação:

- `DecisionReason` estruturada;
- geração textual derivada;
- testes entre `RuleResult`, resultado e razão.

### 17.5 Vazamento de informações na explicação

Mitigação:

- redaction por audiência;
- `FieldScope`;
- classificação;
- autorização específica;
- auditoria de acesso.

### 17.6 Acoplamento à vertical

Mitigação:

- contratos genéricos;
- referências tipadas;
- adaptadores;
- testes de dependência arquitetural.

---

## 18. Estado atual e transição

O Titan já possui implementações parciais de `FactSnapshot`, `RuleResult`, `Evaluation`, `DecisionReason`, `Decision`, persistência append-only e matriz de elegibilidade de mercado. Elas preservam resultados e razões estruturadas, mas ainda não constituem, isoladamente, uma implementação integral desta ADR.

Em particular, o caminho atual:

- pode emitir `Decision` diretamente a partir de `Evaluation`, sem resolver `DecisionAuthorityProfile`, método de emissão ou aprovações;
- não produz necessariamente `DecisionProposal` quando a avaliação exigir revisão humana;
- possui snapshot com instante de referência, mas ainda não representa genericamente todos os instantes de registro e conhecimento exigidos por esta ADR;
- preserva `source_reference` no conteúdo do fato, mas o hash atual do snapshot deve passar a cobrir essa proveniência antes de ser tratado como identidade completa do material avaliado.

Essas limitações não autorizam reescrever `Evaluations` ou `Decisions` já registradas. Elas permanecem registros históricos segundo os contratos sob os quais foram emitidas.

Até a conclusão das Fases 1, 3 e 4, nenhuma nova capacidade regulatória deve declarar conformidade integral com esta ADR nem apresentar uma emissão automática como `Decision` oficial quando depender de autoridade humana, de aprovação adicional ou de tempo do conhecimento ainda não preservado.

Cada incremento de transição deve:

- manter a leitura dos registros históricos existentes;
- criar novos registros para novos efeitos, sem mutação retroativa;
- identificar explicitamente o método e o nível de conformidade da emissão;
- acrescentar testes de proveniência, temporalidade, autoridade e distinção entre proposta e decisão.

---

## 19. Critérios de conformidade

Uma implementação está conforme esta ADR somente se:

- não grava decisão regulatória como atributo autoritativo mutável da entidade;
- toda decisão referencia avaliação imutável;
- toda avaliação referencia versões exatas;
- existe snapshot verificável cujo hash cobre os fatos e suas referências de proveniência relevantes;
- o snapshot distingue o instante de referência dos instantes de registro e conhecimento requeridos pelo escopo;
- razões são estruturadas;
- autoridade é registrada;
- indeterminação é representada;
- nova informação não reescreve história;
- regras não consultam diretamente entidades internas de verticais;
- reproduções, simulações e reavaliações são operações distintas;
- explicações respeitam autorização;
- o Core permanece independente das verticais;
- nenhuma entidade genérica `Assertion` foi introduzida implicitamente.

---

## 20. Sequência de implementação recomendada

A implementação deverá ocorrer incrementalmente:

### Fase 1 — Contratos e snapshot

- contrato de entrada da avaliação;
- seleção de `Policy`;
- snapshot canônico, incluindo referências de proveniência relevantes;
- hash que cubra o conteúdo canônico e a proveniência do snapshot;
- representação explícita de tempo de referência, registro e conhecimento quando aplicável;
- versão do motor.

### Fase 2 — Rule execution

- executor determinístico;
- `RuleResult`;
- `EvaluationOutcome`;
- testes de equivalência.

### Fase 3 — Evaluation

- persistência imutável;
- proveniência;
- temporalidade;
- lacunas e conflitos.

### Fase 4 — DecisionProposal e Decision

- autoridade;
- métodos de emissão;
- aprovações;
- `DecisionReason`;
- `DecisionRelation`.
- transição do caminho automático existente para `DecisionProposal` ou `Decision` autorizada.

### Fase 5 — Dossier

- composição;
- autorização;
- exportação;
- verificação independente.

### Fase 6 — Operações históricas

- `HistoricalReproduction`;
- `HistoricalComplianceAssessment`;
- `CounterfactualSimulation`;
- `CurrentReevaluation`.

A ordem não transforma itens futuros em requisito do primeiro incremento.

---

## 21. Questões adiadas

Permanecem para ADRs próprias:

- contrato uniforme de integração das verticais;
- mecanismo de descoberta e seleção de providers;
- DSL de `Policy` e `Rule`;
- sandbox WebAssembly;
- serialização canônica do snapshot;
- estrutura física do Evidence Graph;
- estratégia de cache;
- formato do `Dossier`;
- protocolo público de verificação;
- governança de publicação de políticas;
- composição entre múltiplas políticas;
- distribuição e assinatura de bundles normativos.

---

## 22. Conclusão

O Titan não trata uma decisão como verdade armazenada.

Ele registra uma conclusão contextualizada e preserva os elementos necessários para demonstrar:

- quais informações foram consideradas;
- quais evidências estavam disponíveis;
- quais regras foram aplicadas;
- qual base normativa foi utilizada;
- qual resultado técnico foi produzido;
- quem possuía autoridade;
- quais limitações permaneceram;
- como a avaliação pode ser reproduzida.

Essa arquitetura transforma rastreabilidade em confiança demonstrável sem confundir integridade, evidência, fato aceito, avaliação e decisão.

> **O Titan preserva decisões; não as confunde com fatos.**
