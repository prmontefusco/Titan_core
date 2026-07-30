# ADR-0054 - DecisionProposal, revisao humana, aprovacao e override

**Data:** 2026-07-29<br>
**Status:** ACEITA<br>
**Aceita em:** 2026-07-29<br>
**Base normativa:** `DOMAIN.md` v1.19 e ADRs aceitas ate ADR-0053<br>
**Escopo:** Titan Core<br>
**Relacionadas:** ADR-0048, ADR-0050, ADR-0051, ADR-0052, ADR-0053

---

## 1. Contexto

Revisao humana nao e uma edicao livre do resultado tecnico; e processo autoritativo, versionado e auditavel que pode aceitar, rejeitar, devolver ou excepcionalmente superar uma proposta sem apagar sua origem.

Algumas `Evaluations` nao podem produzir `Decision` automaticamente. Elas podem exigir interpretacao humana, aprovacao institucional, tratamento de conflito ou incerteza, risco elevado, validacao externa ou override autorizado.

A ADR-0053 define quem possui competencia para emitir `Decision`. Esta ADR define como intervencao humana anterior a emissao ocorre sem confundir proposta, revisao, aprovacao, override e decisao oficial.

---

## 2. Problema

Sem ciclo formal podem ocorrer aprovacoes simultaneas, revisoes de material obsoleto, emissao depois de mudanca relevante, violacao de segregacao, pendencia indefinida, rejeicao sem fundamento, override que apaga resultado tecnico ou aprovacao parcial apresentada como `Decision` oficial.

Os objetos abaixo possuem responsabilidades distintas:

- `Evaluation`: resultado tecnico imutavel;
- `DecisionProposal`: proposta imutavel derivada de uma `Evaluation`;
- `DecisionReview`: caso e conclusao de revisao sobre objeto delimitado;
- aprovacao, rejeicao ou devolucao: conclusoes ou efeitos controlados de revisao, nao sinonimos de `Decision`;
- `DecisionOverride`: autorizacao excepcional para nova decisao divergente;
- `Decision`: conclusao oficial emitida sob autoridade.

---

## 3. Decisao

O Titan representa intervencao humana anterior a emissao oficial por `DecisionProposal` e `DecisionReview`.

Uma `DecisionProposal` e proposta historica e imutavel vinculada a uma `Evaluation`, resultado proposto, perfil de autoridade e requisitos de revisao aplicaveis. Uma revisao nao altera `Evaluation`, nao reescreve proposta e nao constitui `Decision` oficial isoladamente.

Quando intervencao humana, aprovacao adicional ou proposta formal forem exigidas, o fluxo de referencia e:

```text
Evaluation
        -> DecisionProposal imutavel
        -> uma ou mais DecisionReviews
        -> satisfacao dos requisitos autoritativos
        -> revalidacao de emissao
        -> Decision autorizada
```

Mudanca material nao atualiza proposta silenciosamente. Produz nova `Evaluation`, nova `DecisionProposal` ou relacao explicita, preservando propostas e revisoes anteriores.

Emissao somente ocorre quando revisoes, aprovacoes, segregacoes, vigencias, elegibilidade e demais pre-condicoes exigidas estiverem satisfeitas no instante de emissao.

---

## 4. Escopo e nao objetivos

Esta ADR define:

- ciclo conceitual de proposta e revisao;
- conteudo minimo, elegibilidade e imutabilidade de proposta e revisao;
- aprovacao simples, multipla e composicao de competencias;
- rejeicao, devolucao, expiracao, cancelamento e supersession;
- segregacao, concorrencia e revisao obsoleta;
- override e contestacao em nivel arquitetural;
- revalidacao antes da emissao de `Decision`.

Esta ADR nao define:

- assinatura, recibo publico, `Dossier` ou verificacao independente, reservados para ADR-0055;
- maquina de estados persistida, enum adicional ou API detalhada de proposta;
- regras de negocio de risco, quantidade de revisores ou segregacao de vertical e jurisdicao;
- efeitos externos, operacionais, contratuais ou regulatorios da `Decision`;
- alteracao de `EvaluationOutcome`, `RuleResult`, Facts ou Evidences por revisao ou override.

---

## 5. DecisionProposal

`DecisionProposal` e fotografia imutavel do que foi submetido a revisao, aprovacao ou outro fluxo autoritativo que exija proposta explicita. A emissao `AUTOMATICA_AUTORIZADA` somente utiliza `DecisionProposal` quando `DecisionAuthorityProfile`, `Policy` ou contrato normativo aplicavel assim exigirem. Esta ADR nao torna proposta obrigatoria para todo fluxo automatico.

Ela preserva ou referencia, no minimo:

- `Evaluation`, `evaluation_hash`, snapshot e contexto correspondentes;
- resultado proposto, `DecisionReasons`, acoes, restricoes e limitacoes conhecidas;
- `DecisionAuthorityProfile`, metodo esperado e requisitos de revisao, aprovacao e segregacao;
- `Policy`, Rules, `NormativeBasisSnapshot`, finalidade e escopo aplicaveis;
- criador ou mecanismo originador, instante de criacao, validade e correlacao;
- identidade imutavel e inequivoca da proposta e, quando aplicavel, versao ou hash segundo o contrato de identidade correspondente.

Uma proposta nao e rascunho editavel. Ajuste de resultado, razao, material, perfil, `Policy`, requisito ou prazo que altere sua interpretacao requer nova proposta ou novo registro relacionado. A proposta original permanece navegavel e auditavel.

---

## 6. DecisionReview e evidencias de revisao

`DecisionReview` coordena revisao de `Evaluation`, `DecisionProposal` ou `Decision` dentro de escopo identificado. Para revisao anterior a emissao, deve preservar proposta e versao ou hash exato revisados, identidade do revisor, `DecisionAuthorityProfile`, escopo, conclusao, razoes, limitacoes, instante, conflitos de interesse declarados, autenticacao e correlacao aplicaveis.

Quando o objeto revisado for `Decision` ja emitida, a revisao possui natureza posterior e nao reabre nem modifica o fluxo pre-emissao original. Ela pode fundamentar contestacao, reavaliacao, suspensao, override ou nova `Decision` relacionada, conforme contrato proprio.

Mesmo quando `DecisionReview` representar caso com estado operacional, cada submissao, avaliacao, conclusao e transicao material permanece historicamente demonstravel. Atualizacao de estado corrente nao pode sobrescrever quem realizou cada acao, qual material foi examinado ou qual conclusao existia anteriormente.

`ReviewEvidenceSubmission` pode registrar Evidence ou referencia entregue durante a revisao. Essa submissao nao altera snapshot original, nao se torna automaticamente Evidence aceita e nao atualiza `Evaluation` ou proposta. Validacao, admissibilidade e eventual `Reevaluation` obedecem aos contratos ja definidos no dominio.

`ReviewAssessment` pode registrar material examinado e conclusao como `MANTER`, `REAVALIAR`, `OVERRIDE_ELEGIVEL`, `EVIDENCIA_ADICIONAL_NECESSARIA` ou `INDETERMINADO`. Ele nao e nova `Decision`.

---

## 7. Estados conceituais da proposta

Para descrever o ciclo, esta ADR separa conclusao de revisao de situacao de elegibilidade da proposta. Conclusoes de revisao podem ser conceitualmente aprovacao, rejeicao ou devolucao. O ciclo de vida da proposta pode ser conceitualmente pendente, em revisao, elegivel para emissao, emitida, expirada, cancelada ou superseded.

Esses nomes descrevem estado de processo; nao criam enum persistido novo nesta ADR. `DecisionReview` ja possui seus proprios estados normativos. A forma persistida e as transicoes detalhadas devem ser definidas antes de implementacao.

Conclusoes de revisao, como aprovacao, rejeicao e devolucao, sao historicas e nao sao revertidas por mutacao. A satisfacao dos requisitos de aprovacao nao torna necessariamente a proposta terminal nem garante emissao futura. A proposta pode perder elegibilidade por expiracao, supersession, mudanca material, perda de autoridade ou outra condicao publicada.

Nesses casos, aprovacoes anteriores permanecem historicas, mas deixam de satisfazer emissao quando o contrato aplicavel assim determinar. Novo exame exige nova revisao, nova proposta ou relacao explicita.

`EXPIRED` nao e `REJECTED`: expiracao indica perda de validade temporal, enquanto rejeicao indica que aquela proposta nao deve produzir `Decision` naquele fluxo. `RETURNED` nao e rejeicao: indica necessidade de correcao, informacao ou nova analise e pode originar Evidence, `Reevaluation` ou nova proposta.

---

## 8. Elegibilidade, aprovacao e segregacao

O `DecisionAuthorityProfile` e a `Policy` aplicaveis definem requisitos de revisao:

- quantidade minima de aprovacoes;
- papeis, capacidades, Organizations ou autoridades exigidos;
- ordem ou etapas, quando relevantes;
- independencia entre revisores;
- rejeicao impeditiva, regra de desempate e validade temporal;
- delegacao, autenticacao, escopo e segregacao;
- possibilidade de reaproveitar conclusao anterior e suas condicoes.

Aprovacao multipla satisfaz composicao de competencia, nao mera contagem. "Um veterinario e um responsavel de compliance distintos" e diferente de duas aprovacoes por Actors elegiveis para apenas uma das competencias.

A autoridade do revisor deve estar valida no instante da revisao. O `DecisionAuthorityProfile` tambem declara se a aprovacao permanece utilizavel depois da expiracao da autoridade do revisor ou se a competencia precisa continuar valida ate `decision_issued_at`. Expiracao posterior nao apaga revisao historica, mas pode impedir que ela satisfaca requisito de emissao.

Segregacao somente e exigida quando perfil, mandato, `Policy` ou contexto aplicavel a determinar. Quando exigida, nao pode ser ignorada: proponente, produtor de Evidence, solicitante, avaliador, primeiro aprovador, segundo aprovador e emissor podem precisar ser identidades distintas conforme a regra publicada.

Autoridade para revisar ou aprovar nao implica autoridade para emitir `Decision`; a emissao continua sujeita a ADR-0053.

---

## 9. Concorrencia, obsolescencia e mudanca material

Toda revisao referencia versao ou hash exato da proposta revisada. Ela somente e valida para aquela proposta e `Evaluation` identificadas no instante em que foi emitida.

Quando houver nova Evidence admissivel, nova `Evaluation`, mudanca material de `Policy`, `Rules`, `NormativeBasis`, perfil de autoridade, escopo, validade ou resultado proposto, a proposta pode ser superseded ou expirada conforme o contrato aplicavel. Revisoes anteriores permanecem historicas; nova proposta exige novas revisoes, salvo regra publicada que permita reaproveitamento explicitamente tipado e verificavel.

Reaproveitamento de revisao somente e permitido quando regra publicada demonstrar que os elementos materialmente examinados permanecem identicos, que o escopo da aprovacao continua aplicavel e que o revisor possuia competencia para o novo contexto. Similaridade entre propostas nao basta.

O fluxo usa `OptimisticConcurrency`, identidade da proposta e verificacao final de estado para impedir dupla emissao e aplicacao de revisao antiga a proposta nova. Last-write-wins nao e mecanismo valido para aprovacoes, rejeicoes, supersession ou emissao.

---

## 10. Expiracao, rejeicao, devolucao e cancelamento

Proposta pode expirar por prazo proprio, expiracao da `Evaluation`, mudanca de `Policy`, expiracao ou alteracao de autoridade, mudanca material, limite operacional declarado ou outra condicao publicada.

Expiracao nao e rejeicao e nao converte a proposta em decisao negativa. Rejeicao deve preservar fundamento, Actor, autoridade, escopo, instante e razoes estruturadas. Devolucao deve preservar o que falta, o motivo e a proxima acao esperada, sem editar o resultado tecnico ou a proposta original.

Cancelamento encerra fluxo de proposta pelo motivo e autoridade aplicaveis; nao apaga registros, revisoes ou evidencias anteriores. Rejeicao, devolucao, expiracao e cancelamento nao produzem `Decision` oficial por si sos.

---

## 11. Override

`DecisionOverride` e autorizacao excepcional e imutavel para emitir nova `Decision` divergente em escopo delimitado. Override nao e edicao de `EvaluationOutcome`, `RuleResult`, Evidence, `DecisionProposal` ou `Decision` anterior.

Override deve preservar resultado tecnico original, resultado proposto, revisoes anteriores, `DecisionAuthorityProfile`, autoridade de override, fundamento excepcional codificado, justificativa, escopo, condicoes, prazo, risco, aprovacao adicional, limitacoes e vinculacao explicita com a decisao divergente.

Override somente e elegivel quando:

- perfil e `Policy` o permitirem;
- autoridade adicional estiver valida e competente;
- razao codificada, justificativa e limitacoes estiverem presentes;
- conflito e risco conhecidos estiverem preservados;
- aprovacao adicional exigida estiver satisfeita;
- nao houver restricao classificada como nao superavel no escopo aplicavel;
- a `Decision` resultante mantiver vinculo com o resultado tecnico divergente.

Override nao e permitido quando `Policy`, `Rule`, `NormativeBasisSnapshot` ou perfil aplicavel classificarem restricao como nao superavel. Excecao somente pode ocorrer quando o proprio contrato normativo reconhecer a condicao como superavel e definir autoridade, fundamento, limites e aprovacoes especificos.

Override nao pode alterar `RuleResult`, `EvaluationOutcome` ou Evidence conflitante, esconder divergencia, reclassificar falha tecnica como condicao satisfeita, nem superar restricao classificada como nao superavel. A `Decision` resultante usa metodo `OVERRIDE_AUTORIZADO` e permanece explicitamente distinguivel de emissao humana comum.

---

## 12. Contestacao

`DecisionChallenge` nao modifica proposta, revisao ou `Decision` original. Ele inicia fluxo proprio e pode resultar em nova Evidence, `Reevaluation`, revisao, override ou `Decision` relacionada, conforme autoridade e `Policy` aplicaveis.

Contestacao nao suspende, revoga, invalida ou produz efeito provisorio implicitamente. Suspensao, restricao ou manutencao provisoria exigem decisao autorizada, temporal e separada.

---

## 13. Emissao depois da revisao

Mesmo quando requisitos de revisao aparentarem satisfeitos, o `DecisionEngine` revalida no `decision_issued_at`:

- identidade, versao ou hash e estado atual da proposta;
- `Evaluation` ainda elegivel e vinculada ao mesmo material;
- `DecisionAuthorityProfile`, autoridade, delegacao e escopo ainda aplicaveis;
- aprovacoes, rejeicoes, devolucoes e suas vigencias;
- segregacao, composicao de competencias e ausencia de rejeicao impeditiva;
- ausencia de expiracao, supersession ou mudanca material bloqueadora.

Aprovacao nao reserva indefinidamente direito de emitir. Falha nessa revalidacao nao produz resultado regulatorio negativo; bloqueia emissao, preserva o historico e pode encaminhar para revisao ou nova proposta.

---

## 14. Invariantes

1. `DecisionProposal` nao e `Decision`.
2. `DecisionReview` nao altera `Evaluation` nem `DecisionProposal`.
3. Toda revisao referencia versao ou hash exato da proposta revisada.
4. Aprovacao de proposta nao se aplica automaticamente a versao posterior.
5. Mudanca material durante revisao exige nova proposta ou regra explicita de reaproveitamento.
6. Revisores possuem autoridade valida no instante da revisao.
7. Autoridade de revisar nao implica autoridade de emitir.
8. Conclusao historica de revisao nao e revertida por mutacao.
9. Rejeicao nao e expiracao.
10. Devolucao nao e rejeicao.
11. Override nao modifica resultado tecnico original.
12. Override exige autoridade e fundamento adicionais.
13. Divergencia entre `EvaluationOutcome` e `DecisionResult` permanece explicita.
14. Aprovacoes multiplas satisfazem composicao de competencia, nao apenas contagem.
15. Segregacao e verificada conforme perfil aplicavel.
16. Emissao revalida proposta, autoridade, aprovacoes e elegibilidade.
17. Dupla emissao concorrente da mesma proposta e impedida.
18. Nova proposta nao apaga proposta ou revisoes anteriores.
19. Revisao expirada ou fora de escopo nao satisfaz requisito de aprovacao.
20. Falha no fluxo de revisao nao produz resultado regulatorio negativo.
21. Evidence submetida em revisao nao altera snapshot ou `Evaluation` original sem novo fluxo de admissibilidade e reavaliacao.
22. Contestacao nao altera ou produz efeito provisorio sobre objeto anterior sem decisao autorizada e separada.
23. Satisfacao dos requisitos de aprovacao nao garante elegibilidade permanente para emissao.
24. Perda posterior de elegibilidade nao apaga revisoes ou aprovacoes historicas.
25. Restricao classificada como nao superavel nunca e afastada por override.
26. Toda proposta possui identidade imutavel e inequivoca.
27. Expiracao posterior da autoridade do revisor nao apaga a revisao, mas pode impedir seu uso na emissao conforme o perfil.
28. Revisao posterior de `Decision` nao reabre nem modifica o fluxo pre-emissao original.
29. Reaproveitamento exige equivalencia material demonstrada e regra publicada; similaridade nao e suficiente.

---

## 15. Fluxos de referencia

### 15.1 Revisao ordinaria

```text
Evaluation
        -> criar DecisionProposal imutavel
        -> resolver requisitos de revisao
        -> atribuir revisores elegiveis
        -> registrar DecisionReviews
        -> verificar aprovacao, rejeicao ou devolucao
        -> revalidar proposta e autoridade
        -> emitir Decision
```

### 15.2 Mudanca material

```text
DecisionProposal v1
        -> revisao em andamento
        -> nova Evaluation ou mudanca material
        -> Proposal v1 superseded ou expirada
        -> DecisionProposal v2
        -> novas revisoes
```

### 15.3 Override

```text
EvaluationOutcome
        -> DecisionProposal
        -> revisao identifica divergencia
        -> autoridade de override e fundamento excepcional
        -> Decision com OVERRIDE_AUTORIZADO
```

---

## 16. Estado atual e transicao

O `DOMAIN.md` ja define `DecisionProposal`, `DecisionReview`, `ReviewEvidenceSubmission`, `ReviewAssessment`, `DecisionOverride`, `DecisionChallenge`, `DecisionRelation` e `OptimisticConcurrency`. A ADR-0048 registra que o caminho atual ainda nao produz necessariamente proposta quando revisao humana for exigida.

A transicao deve:

- criar proposta imutavel para `Evaluation` que exigir intervencao humana ou aprovacao adicional;
- registrar revisoes vinculadas a proposta e `Evaluation` exatas;
- resolver requisitos e segregacao pelo `DecisionAuthorityProfile` no servidor;
- impedir dupla emissao por controle otimista e revalidacao final;
- preservar proposta, revisoes e resultados legados sem afirmar conformidade retroativa;
- criar testes para concorrencia, obsolescencia, expiracao, segregacao, rejeicao, devolucao e override.

Enquanto a transicao nao estiver concluida, capacidade nova que dependa de revisao humana nao deve apresentar proposta, aprovacao parcial ou review como `Decision` oficial.

---

## 17. Alternativas rejeitadas

### 17.1 Editar DecisionProposal durante a revisao

Rejeitada porque elimina o material efetivamente revisado e permite aprovacoes ambiguas.

### 17.2 Tratar aprovacao como Decision oficial

Rejeitada porque aprovacao pode ser parcial, condicional, expirada ou insuficiente para emissao.

### 17.3 Aplicar aprovacao antiga a nova Evaluation

Rejeitada porque o revisor nao examinou material, resultado ou condicoes novos.

### 17.4 Resolver concorrencia por last-write-wins

Rejeitada porque pode ocultar dupla emissao, rejeicao impeditiva ou revisao perdida.

### 17.5 Usar override para corrigir resultado tecnico

Rejeitada porque override decide excepcionalmente sobre efeito; nao altera Facts, Evidence, `RuleResult` ou `EvaluationOutcome`.

### 17.6 Suspender Decision automaticamente por contestacao

Rejeitada porque challenge nao possui efeito provisiorio implicito.

---

## 18. Criterios de conformidade

Uma implementacao esta conforme esta ADR quando:

- cria `DecisionProposal` imutavel vinculada a `Evaluation` e identidade exatas;
- registra `DecisionReview` com proposta ou hash exato, revisor, autoridade, escopo, razoes e instante;
- resolve elegibilidade, composicao de aprovacao e segregacao no servidor;
- nao aplica revisao ou aprovacao a proposta superseded, expirada ou materialmente diferente;
- revalida requisitos no `decision_issued_at` antes da emissao;
- impede dupla emissao concorrente;
- distingue rejeicao, devolucao, expiracao e cancelamento;
- preserva `ReviewEvidenceSubmission` sem mutar snapshot ou `Evaluation` original;
- identifica override como `OVERRIDE_AUTORIZADO` e preserva divergencia tecnica;
- nao trata review, aprovacao parcial, rejeicao ou contestacao como `Decision` oficial;
- cobre em testes aprovacao simples, dupla aprovacao, mesmo Actor quando proibido, revisor sem autoridade, autoridade expirada, proposta expirada, supersession, hash antigo, dupla emissao, rejeicao impeditiva, devolucao, override autorizado e sem competencia, mudanca de `Evaluation`, mudanca de `Policy`, segregacao violada e tentativa de mutar revisao historica.

---

## 19. Questoes adiadas

- maquina de estados persistida e API de transicao para propostas;
- modelo detalhado de filas, atribuicao, escalonamento, prazos e reabertura de revisoes;
- representacao de assinatura e recibo para aprovacao e emissao;
- semantica especializada de voto, desempate e aprovacao parcial por vertical;
- efeitos operacionais de `Decision` aprovada, rejeitada, suspensa ou revogada;
- apresentacao publica e verificacao independente do fluxo completo.

Essas questoes nao autorizam mutacao de origem, emissao sem requisitos satisfeitos ou ocultacao de divergencia por override.

---

## 20. Proxima ADR registrada

**ADR-0055 - Dossier verificavel, assinatura e validacao independente**

Ela permanece planejada. Esta ADR nao antecipa seu modelo persistido ou implementacao.

---

## 21. Consequencias

O Titan passa a tratar intervencao humana como evidencia de processo, e nao como campo editavel depois do resultado tecnico.

Isso aumenta requisitos de versao, concorrencia, autoridade e auditoria, mas permite demonstrar quem revisou qual proposta, sob que competencia, com qual resultado e por que uma `Decision` foi ou nao emitida.
