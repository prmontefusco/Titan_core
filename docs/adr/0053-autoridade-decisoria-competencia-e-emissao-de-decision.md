# ADR-0053 - Autoridade decisoria, competencia e emissao de Decision

**Data:** 2026-07-29<br>
**Status:** ACEITA<br>
**Aceita em:** 2026-07-29<br>
**Base normativa:** `DOMAIN.md` v1.19 e ADRs aceitas ate ADR-0052<br>
**Escopo:** Titan Core<br>
**Relacionadas:** ADR-0048, ADR-0049, ADR-0050, ADR-0051, ADR-0052

---

## 1. Contexto

Uma avaliacao pode ser tecnicamente conclusiva e ainda nao possuir autoridade para produzir efeito oficial.

As ADRs anteriores definem como o Titan seleciona `Policy`, executa `Rules`, preserva material e proveniencia, e separa tempo valido de conhecimento disponivel. Falta definir a fronteira entre uma conclusao tecnica e o ato que a torna uma `Decision` oficial.

Sem essa fronteira, `EvaluationOutcome = CONDICOES_SATISFEITAS` pode ser confundido com `DecisionResult = APROVADA`, e um Actor com acesso tecnico pode emitir conclusao fora de sua competencia institucional, territorial, temporal ou regulatoria.

---

## 2. Problema

Uma `Evaluation` e resultado tecnico registrado da execucao de uma `Policy` e suas `Rules`. Uma `Decision` e conclusao historica emitida sob autoridade, com responsabilidade, efeito e limites declarados.

Mesmo uma `Evaluation` tecnicamente conclusiva pode exigir autoridade humana, mandato organizacional, escopo territorial, competencia regulatoria, dupla aprovacao, segregacao de funcoes, condicao pendente ou revisao obrigatoria antes de produzir `Decision` oficial.

Autenticacao, `Membership`, `Role`, `Permission`, ownership de registro ou acesso a API nao demonstram isoladamente competencia decisoria.

---

## 3. Decisao

O Titan distingue resultado tecnico de ato decisorio.

Uma `Evaluation` nao se converte automaticamente em `Decision`. Toda `Decision` deve ser emitida por autoridade identificavel, competente, autorizada e valida para finalidade, tipo de decisao, Organization, Subject, `Policy`, escopo e instante correspondentes.

A proibicao de conversao automatica significa que resultado tecnico nao produz `Decision` por implicacao. Uma `Decision` pode ser emitida automaticamente somente por fluxo autoritativo explicito, apos resolucao de perfil, competencia, delegacao, elegibilidade e demais pre-condicoes.

O conceito normativo aplicavel e `DecisionAuthorityProfile`, perfil versionado resolvido pelo servidor. Esta ADR consolida seu uso como pre-condicao de emissao e nao cria uma entidade generica paralela de autoridade.

Autoridade e competencia sao demonstradas por perfil aplicavel, origem identificavel, escopo, vigencia, evidencia, autenticacao e requisitos de aprovacao ou segregacao. Nenhuma dessas dimensoes e inferida apenas por cargo textual, claim externa, acesso ao sistema ou ordem de processamento.

Autoridade para emitir uma `Decision` nao implica automaticamente autoridade para executar, impor ou obter reconhecimento externo de seus efeitos. Efeitos operacionais, contratuais, regulatorios ou externos dependem de contrato, integracao, autoridade e capacidade proprios.

---

## 4. Escopo e nao objetivos

Esta ADR define:

- separacao entre `Evaluation`, `DecisionProposal` e `Decision`;
- competencia, escopo, vigencia e origem da autoridade decisoria;
- responsabilidade dos papois envolvidos na emissao;
- requisitos para emissao automatica, humana, assistida e override autorizado;
- responsabilidade do `DecisionEngine` na coordenacao de emissao;
- tratamento de ausencia, expiracao e violacao de autoridade;
- preservacao historica e relacoes entre decisoes.

Esta ADR nao define:

- o fluxo detalhado de `DecisionProposal`, revisao humana, aprovacao ou override, reservado para ADR-0054;
- taxonomia persistida adicional de metodos ou erros alem dos conceitos ja definidos no `DOMAIN.md`;
- regras de competencia especificas de mercado, jurisdicao ou vertical;
- assinatura criptografica, formato de recibo ou verificacao independente do `Dossier`, reservados para ADR-0055;
- conclusao juridica automatica sobre validade legal, culpa ou responsabilidade.

---

## 5. Papeis na emissao

Os papeis abaixo sao semanticamente distintos. Podem ser exercidos pela mesma pessoa, Organization ou `ServiceIdentity` somente quando `Policy`, perfil de autoridade e segregacao permitirem.

| Papel | Responsabilidade |
| --- | --- |
| `Evaluator` | Produz ou coordena o resultado tecnico da `Evaluation`. Pode ser motor, sistema, Actor humano ou mecanismo aprovado. Nao recebe autoridade decisoria por isso. |
| `DecisionAuthority` | Papel semantico exercido por identidade ou referencia existente que possui competencia demonstravel para autorizar determinada `Decision` em escopo delimitado. E resolvido pelo `DecisionAuthorityProfile` aplicavel. |
| `DecisionIssuer` | Actor ou mecanismo que executa materialmente a emissao e registra o ato. Pode agir em nome de autoridade distinta, sem se tornar sua fonte. |
| `DecisionOwner` | Organization ou papel institucional responsavel pela custodia, governanca e ciclo de vida da `Decision` no Titan. Nao atribui automaticamente responsabilidade juridica, autoridade regulatoria, competencia para emitir ou poder para alterar decisao historica. |

Esses papeis sao contratos de interpretacao da emissao. Esta ADR nao cria novas entidades persistidas chamadas `Evaluator`, `DecisionAuthority`, `DecisionIssuer` ou `DecisionOwner`; a forma de representacao usa os conceitos normativos existentes e os perfis especializados aprovados.

---

## 6. DecisionAuthorityProfile e origem da competencia

Toda emissao oficial resolve `DecisionAuthorityProfile` publicado, versionado e aplicavel. O servidor, e nao o cliente, resolve perfil, versao, autoridade e metodo aplicaveis ao caso.

O perfil delimita, no minimo, quando aplicavel:

- Organization responsavel e audiencia autorizada;
- finalidade e tipo de `Decision`;
- Subject, categoria, operacao, unidade, territorio ou jurisdicao;
- `Policy`, perfil de mercado ou contexto normativo permitido;
- `Role`, grant, capacidade ou Actor elegivel;
- nivel de risco, condicoes, limites quantitativos e restricoes;
- periodo de validade e instante de verificacao;
- autenticacao, evidencias de competencia, segregacao e aprovacoes exigidas;
- origem da autoridade, limitacoes e revogacao ou supersession aplicaveis.

A origem da competencia deve ser identificavel e pode derivar de norma, contrato, delegacao, papel organizacional, mandato, procedimento interno aprovado ou autoridade externa reconhecida. A origem nao precisa transformar qualquer desses elementos em verdade juridica absoluta; ela precisa permitir auditar por que aquela autoridade foi aceita para a finalidade delimitada.

---

## 7. Metodos de emissao

O `DOMAIN.md` ja distingue `AUTOMATICA_AUTORIZADA`, `HUMANA`, `HUMANA_ASSISTIDA` e `OVERRIDE_AUTORIZADO`. Esta ADR usa esses metodos e nao cria enum paralelo.

### 7.1 AUTOMATICA_AUTORIZADA

Uma `Decision` automatica somente pode ser emitida quando `Policy` e `DecisionAuthorityProfile` autorizarem explicitamente delegacao ao mecanismo identificado, e quando:

- a `Evaluation` for elegivel para emissao;
- nao houver revisao, aprovacao, conflito, incerteza ou validacao externa impeditiva;
- contexto, escopo, vigencia e material exigidos estiverem completos;
- risco e finalidade permitirem automacao;
- a delegacao, o mecanismo, as versoes e o recibo forem rastreaveis.

O sistema nao possui autoridade propria. Ele exerce autoridade delegada, limitada e verificavel.

O `DecisionIssuer` material da emissao automatica deve ser `ServiceIdentity` ou identidade tecnica equivalente, autenticada e vinculada a artefato, versao de servico, ambiente e delegacao autorizados. Nome logico de componente, como `DecisionEngine`, isoladamente nao demonstra identidade do emissor.

### 7.2 HUMANA

Emissao humana registra quem decidiu, em nome de qual Organization ou autoridade atuou, qual `DecisionAuthorityProfile` foi resolvido, qual `Evaluation` utilizou, quais limitacoes conhecia, qual fundamento adotou, escopo, instante, validade e metodo de emissao.

### 7.3 HUMANA_ASSISTIDA

Assistencia automatizada pode organizar material, executar `Rules` ou propor resultado, mas nao pode ser apresentada como decisao puramente humana. A autoridade humana, a intervencao realizada e as limitacoes do mecanismo permanecem explicitas.

### 7.4 OVERRIDE_AUTORIZADO

Override exige competencia e fundamento adicionais definidos pelo perfil e pelas regras aplicaveis. Ele nao apaga `Evaluation`, proposta, resultado tecnico ou decisao anterior. Seu procedimento detalhado e reservado para ADR-0054.

---

## 8. Elegibilidade, escopo e competencia temporal

Antes de emitir `Decision`, o `DecisionEngine` verifica se a `Evaluation` e elegivel, resolve autoridade e valida:

- finalidade, tipo e resultado proposto;
- Organization, Subject, audiencia, jurisdicao e territorio;
- `Policy`, `Rules`, `NormativeBasisSnapshot` e perfil aplicaveis;
- escopo autorizado, condicoes, risco e limites;
- vigencia da autoridade, delegacao, mandato e perfil no instante efetivo de emissao da `Decision` (`decision_issued_at` conceitual);
- delegacao, autenticacao, capacidade, aprovacao e segregacao exigidas;
- restricoes, redactions e limitacoes que possam impedir emissao oficial.

Validade da autoridade no instante da `Evaluation` nao substitui sua validade no instante de emissao da `Decision`. `decision_issued_at`, `evaluation_emitted_at`, `reference_time` e `knowledge_cutoff` podem ser distintos e permanecem semanticamente declarados conforme ADR-0052. A semantica temporal aplica-se a autoridade, delegacao, mandato, perfil, aprovacao, `Policy` e fundamentacao utilizados.

---

## 9. DecisionEngine

O `DecisionEngine` atua como coordenador de emissao. Ele verifica pre-condicoes, resolve o perfil de autoridade, valida escopo e vigencia, aplica a regra de emissao, materializa a `Decision` autorizada e registra rastreabilidade.

O `DecisionEngine` nao cria competencia decisoria, nao presume delegacao, nao transforma `EvaluationOutcome` em `DecisionResult` por conveniencia e nao substitui autoridade humana ou externa exigida.

Ele tambem nao importa entidades de vertical nem interpreta payloads operacionais fora dos contratos autorizados, conforme ADR-0048.

---

## 10. Revisao, aprovacao e segregacao

Uma `Decision` nao e emitida quando revisao ou aprovacao obrigatoria estiver pendente. Nesses casos, a `Evaluation` permanece historica e pode originar `DecisionProposal`, sem ser apresentada como conclusao oficial.

Separacao de funcoes e aplicada quando exigida por `Policy`, mandato, `DecisionAuthorityProfile` ou contexto regulatorio. Quem produziu `Evidence`, solicitou operacao, executou `Evaluation` ou possui interesse material nao recebe automaticamente permissao para revisar, aprovar ou emitir.

A modelagem de propostas, filas de revisao, multiaprovacao, recusas, contestacoes e override pertence a ADR-0054. Esta ADR somente estabelece que esses requisitos bloqueiam emissao oficial ate serem satisfeitos por autoridade valida.

---

## 11. Falha de autoridade e emissao recusada

Ausencia ou invalidade de autoridade nao produz `Decision` oficial. O sistema registra resultado estruturado da tentativa, limitacao ou encaminhamento para revisao conforme o fluxo aplicavel.

Codigos tecnicos ou de razao podem incluir, sem criar enumeracao persistida nova nesta ADR:

- `AUTHORITY_NOT_FOUND`;
- `AUTHORITY_EXPIRED`;
- `AUTHORITY_OUT_OF_SCOPE`;
- `REVIEW_REQUIRED`;
- `SEGREGATION_VIOLATION`;
- `EVALUATION_NOT_ELIGIBLE`.

Esses codigos nao convertem falha de autoridade em resultado regulatorio negativo. A `Evaluation` e suas razoes permanecem distintas da ausencia de competencia para emitir `Decision`.

---

## 12. Identidade e conteudo da Decision

Toda `Decision` preserva diretamente ou por referencias imutaveis, dentro do escopo autorizado, os elementos decisorios, autoritativos e operacionais necessarios. Metadados observacionais nao se confundem com o conteudo semantico da decisao.

O conteudo decisorio inclui:

- `Evaluation`, `evaluation_hash`, snapshot, `DecisionReasons` e `DecisionResult`;
- Subject, finalidade, `Policy`, Rules e `NormativeBasisSnapshot` aplicaveis;
- `decision_issued_at`, validade, condicoes, restricoes e limitacoes.

O contexto autoritativo inclui:

- `DecisionAuthorityProfile`, origem da competencia e delegacao;
- identidade ou referencia existente que exerceu o papel de autoridade decisoria;
- identidade do emissor material;
- Organization ou papel institucional responsavel pela custodia e governanca da `Decision`;
- Organization, audiencia, jurisdicao, territorio, Subject e escopo autorizados;
- metodo de emissao, aprovacoes e segregacao aplicaveis.

A evidencia operacional inclui, quando aplicavel, autenticacao, `ServiceIdentity`, artefato e ambiente autorizados, correlacao, recibo, assinatura, versoes, motor e digest. Esses elementos sustentam verificacao da emissao, mas nao substituem suas razoes, resultado, escopo ou autoridade.

Conforme `DOMAIN.md` e ADR-0048, toda `Decision` referencia exatamente uma `Evaluation`. Decisao que dependa de multiplas avaliacoes deve usar composicao publicada antes da `Evaluation`, conforme ADR-0049, ou relacoes explicitas entre `Decisions`; esta ADR nao introduz `Decision` multiavaliacao.

Explicacao apresentada a cada audiencia respeita `Authorization`, `Visibility`, `FieldScope`, classificacao e redaction. Restricao de visualizacao nao altera a razao original nem transforma falta de visibilidade em falta de autoridade.

---

## 13. Nova Decision, efeito e relacoes historicas

Uma `Decision` historica e imutavel. Nova `Decision` pode confirmar, substituir, revogar, suspender, corrigir ou restringir efeito anterior somente por relacao explicita, autoridade aplicavel, fundamento e temporalidade preservados.

Nova informacao, nova `Evaluation`, expiracao de autoridade, mudanca de `Policy`, correcao ou revisao posterior nao reescrevem a `Decision` original. Podem produzir novo ato, `DecisionRelation`, `Revocation`, `SupersessionRelation`, review ou avaliacao de impacto conforme o caso.

Revogacao ou expiracao posterior da autoridade nao reescreve automaticamente a competencia demonstrada no instante original. Quando a revogacao possuir efeito retroativo declarado ou revelar fraude, erro de competencia ou invalidade originaria, o Titan registra novo ato, contestacao, suspensao ou relacao explicita, sem mutar a `Decision` anterior.

---

## 14. Invariantes

1. `Evaluation` nao e `Decision`.
2. Toda `Decision` oficial exige autoridade identificavel e resolvida.
3. A autoridade e valida no instante da emissao.
4. Autoridade e limitada por Organization, finalidade, escopo, tipo e vigencia.
5. Acesso ao sistema nao equivale a autoridade decisoria.
6. O `DecisionEngine` nao cria autoridade.
7. `AUTOMATICA_AUTORIZADA` exerce delegacao, nunca autoridade propria do sistema.
8. `Decision` nao e emitida quando revisao ou aprovacao obrigatoria estiver pendente.
9. Emissor material e autoridade decisoria podem ser distintos.
10. Nova `Decision` nao reescreve `Decision` historica.
11. Toda `Decision` referencia exatamente uma `Evaluation` que a fundamenta.
12. Limitacoes, condicoes, metodo e origem da competencia permanecem explicitos.
13. Emissao fora do escopo da autoridade e recusada.
14. Segregacao de funcoes e aplicada quando exigida por `Policy`, mandato ou perfil de autoridade.
15. Falha de autoridade nao e apresentada como resultado tecnico ou regulatorio negativo.
16. `DecisionProposal` nao e `Decision` oficial.
17. Autoridade de emissao nao implica automaticamente autoridade de execucao, imposicao ou reconhecimento externo do efeito.
18. Revogacao ou expiracao posterior da autoridade nao reescreve automaticamente a competencia demonstrada no instante da emissao.
19. A identidade tecnica do emissor automatico e autenticavel e vinculada ao mecanismo e artefato autorizados.
20. Conversao implicita de `Evaluation` em `Decision` e proibida; emissao automatica exige fluxo autoritativo explicito.
21. Metadados operacionais e evidencias de autoridade nao se confundem com o conteudo semantico da `Decision`.

---

## 15. Fluxo de referencia

```text
Evaluation concluida
        -> verificar elegibilidade de emissao
        -> resolver DecisionAuthorityProfile
        -> validar escopo, vigencia em decision_issued_at e segregacao
        -> satisfazer revisao ou aprovacao, quando exigida
        -> emitir Decision autorizada
        -> registrar recibo, assinatura e auditoria quando aplicaveis
```

---

## 16. Estado atual e transicao

O `DOMAIN.md` ja define `DecisionAuthorityProfile`, metodos de emissao, `DecisionProposal`, `DecisionReview`, `DecisionRelation` e invariantes de autoridade. A ADR-0048 tambem registra que o caminho atual pode emitir `Decision` diretamente de `Evaluation`, antes de resolver perfil, metodo e aprovacoes.

A transicao deve:

- resolver `DecisionAuthorityProfile` no servidor antes de qualquer nova emissao oficial;
- registrar metodo, autoridade, emissor, escopo, vigencia em `decision_issued_at` e limitacoes da emissao;
- bloquear emissao automatica quando delegacao, revisao, aprovacao ou dados temporais exigidos nao estiverem demonstrados;
- preservar `Decisions` legadas como registros historicos do contrato sob o qual foram emitidas, sem alegar conformidade retroativa;
- introduzir testes para ausencia, expiracao, escopo, segregacao e revisao obrigatoria.

Enquanto a transicao nao estiver concluida, capacidade regulatoria nova nao deve apresentar emissao automatica como `Decision` oficial quando depender de autoridade humana, externa, adicional ou temporalmente nao demonstrada.

---

## 17. Alternativas rejeitadas

### 17.1 Converter toda Evaluation em Decision

Rejeitada porque resultado tecnico nao demonstra competencia, aprovacao, responsabilidade ou efeito oficial.

### 17.2 Tratar Permission ou Role como autoridade suficiente

Rejeitada porque autorizacao tecnica nao prova mandato, competencia, vigencia, jurisdicao ou segregacao.

### 17.3 Atribuir autoridade propria ao DecisionEngine

Rejeitada porque software coordena delegacao verificavel; nao cria competencia institucional ou regulatoria.

### 17.4 Permitir que o cliente selecione a autoridade aplicavel

Rejeitada porque perfil, versao e escopo autoritativos precisam ser resolvidos pelo servidor em contexto validado.

### 17.5 Corrigir Decision anterior por mutacao

Rejeitada porque destroi auditabilidade, temporalidade e explicabilidade do ato historico.

---

## 18. Criterios de conformidade

Uma implementacao esta conforme esta ADR quando:

- nao emite `Decision` oficial somente a partir de `EvaluationOutcome`;
- resolve `DecisionAuthorityProfile` no servidor para cada emissao;
- valida finalidade, Organization, Subject, escopo, tipo, vigencia no instante de emissao e segregacao;
- registra conteudo decisorio, origem da competencia, identidade ou referencia da autoridade, emissor, responsabilidade institucional e limitacoes relevantes;
- exige delegacao verificavel para `AUTOMATICA_AUTORIZADA`;
- vincula emissor automatico autenticavel ao artefato e ambiente autorizados;
- bloqueia emissao quando revisao, aprovacao ou validacao obrigatoria estiver pendente;
- preserva `DecisionProposal` e `Decision` como objetos distintos;
- preserva relacoes explicitas entre novas decisoes e decisoes anteriores;
- nao apresenta emissao como execucao, imposicao ou reconhecimento externo automatico;
- cobre em testes autoridade ausente, expirada no instante de emissao, fora de escopo, segregacao violada, revisao pendente, delegacao automatica invalida e revogacao posterior.

---

## 19. Questoes adiadas

- fluxo detalhado, estados e concorrencia de `DecisionProposal`, `DecisionReview`, aprovacao e override;
- contratos de assinatura, recibo e verificacao independente;
- regras de risco, dupla aprovacao e segregacao especificas de vertical ou jurisdicao;
- representacao especializada de autoridade externa e reconciliacao com decisao local;
- efeitos operacionais de suspensao, revogacao, expiracao ou substituicao de Decision.

Essas questoes nao autorizam emissao sem autoridade, competencia, escopo e vigencia demonstraveis.

---

## 20. Proximas ADRs registradas

1. **ADR-0054 - DecisionProposal, revisao humana e override**
2. **ADR-0055 - Dossier verificavel e validacao independente**

Elas permanecem planejadas. Esta ADR nao antecipa seus modelos persistidos ou implementacoes.

---

## 21. Consequencias

O Titan passa a demonstrar nao apenas por que uma conclusao tecnica foi produzida, mas por que ela podia produzir efeito oficial naquele caso e naquele instante.

Isso aumenta requisitos de perfil, evidencia, vigencia e auditoria, mas impede que permissao tecnica, automacao ou resultado positivo sejam apresentados como autoridade por si so.
