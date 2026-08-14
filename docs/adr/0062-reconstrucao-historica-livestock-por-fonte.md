# ADR-0062 — Reconstrução histórica Livestock por fonte

**Status:** ACEITA
**Data:** 13 de agosto de 2026
**Escopo:** Titan Livestock; aplicação temporal da ADR-0052
**Relacionadas:** ADR-0041, ADR-0051, ADR-0052, ADR-0059, ADR-0061

## Contexto

A auditoria pós-implementação identificou que uma avaliação histórica não pode
ler o estado atual de Animal, permanência, territorialidade, carência ou
campanha e reapresentá-lo como fato conhecido no passado. O corte T-01 da
ADR-0059 corrigiu o falso positivo: o `LivestockFactProvider` recebe
`reference_time` e `knowledge_cutoff`, omite estado sem trilha temporal
demonstrável e declara
`LIVESTOCK_CURRENT_STATE_NOT_HISTORICALLY_RECONSTRUCTABLE`.

O bloqueio é correto, mas não é o objetivo final. O Titan precisa recuperar,
por fonte e quando houver evidência suficiente, o material que era válido no
período examinado e conhecido até o corte. Não existe um único mecanismo capaz
de fazê-lo com segurança: cada fonte possui semântica, mutabilidade, validade e
tempo de conhecimento próprios.

## Problema

Transformar o provider atual em um leitor do estado presente criaria novamente
conhecimento retroativo. Criar uma entidade genérica `BitemporalSnapshot` ou
preencher tempos faltantes de registros legados também fabricaria história não
preservada.

O desenho precisa responder, para cada fato entregue à Evaluation:

1. qual registro ou evento sustenta o fato;
2. qual é seu tempo válido;
3. qual é seu tempo de conhecimento demonstrável;
4. como supersession, correção, conflito e lacuna são tratados;
5. quando a fonte deve permanecer ausente com limitação, em vez de ser
   reconstruída por inferência.

## Decisão proposta

A reconstrução histórica Livestock será implementada **por fonte**, em cortes
independentes. Uma fonte só poderá contribuir a um snapshot temporal estrito
quando satisfizer todos os critérios abaixo:

- possui registro imutável ou versão selecionável que sustenta o fato;
- declara o campo usado como tempo válido;
- declara ou demonstra sem inventar o instante de conhecimento;
- seleciona apenas material elegível para `reference_time` e
  `knowledge_cutoff`;
- preserva identificadores, proveniência e limitações da seleção;
- possui testes T0/T1/T2 que provam que uma alteração ou recepção posterior
  não altera a resposta histórica.

Se um desses critérios não existir, o provider não emite o fato dependente da
fonte. Ele declara limitação determinística e deixa a Policy produzir resultado
indeterminado quando a informação for material.

Não será introduzido agora um aggregate genérico, backfill temporal, alteração
de API pública ou uma semântica universal de `known_at`.

## Matriz de fontes

| Fonte | Evidência atual | Situação no caminho estrito | Próximo corte possível |
| --- | --- | --- | --- |
| Fatos importados e artefato de transferência | ocorrência/efetividade + importação/criação preservadas | selecionável | manter testes de regressão |
| Coverage dimensional e classificação sanitária | `known_at` explícito | selecionável no caso controlado | ampliar apenas com nova Policy aprovada |
| Qualificação de estabelecimento e embargo | `recorded_at` distingue chegada de observação | selecionável para o fato já definido | manter limite da fonte externa |
| Movimentos e permanências | `movement_time`, `created_at`, `start_time`, `end_time` e timeline existem; fechamento de stay é atualização | não habilitar ainda | desenhar seleção por movimento append-only antes de usar `PropertyStay` fechado |
| Identificadores de Animal | validade e desativação existem; cadastro agregado é projeção atual | não habilitar ainda | projetar leitor de lifecycle do identificador e conhecimento de anexação/desativação |
| Dados constitutivos de Animal | nascimento e cadastro têm campos próprios, sem versão histórica geral | somente quando o registro de criação for suficiente para o fato específico | avaliar por fato, sem promover cadastro atual a snapshot histórico |
| Tratamentos locais e carência | aplicação tem instante clínico; disponibilidade histórica da aplicação e de suas correções precisa ser provada por fonte | não habilitar genericamente | contrato temporal próprio para aplicação/correção e cálculo de carência |
| Campanhas sanitárias | intervalo da campanha e `created_at` existem, sem versão/supersession | não habilitar genericamente | selecionar somente campanha criada até o cutoff e definir tratamento de alteração/revogação antes de usá-la historicamente |
| Territorialidade e consultas externas | resultado atual de geodados não é fotografia histórica do provedor externo | não habilitar | persistir captura/versionamento/fundamento da consulta antes de qualquer conclusão histórica territorial |

Uma coluna marcada como “não habilitar” não é ausência de funcionalidade: é
uma fronteira deliberada contra afirmação histórica não demonstrável.

## Ordem de implementação proposta

### T-05A — Contratos e testes de seleção para movimentos

Usar o `AnimalMovement` append-only como fonte primária, e não a projeção
mutável `PropertyStay`. Definir um leitor temporal que selecione movimentos
conhecidos até o cutoff e derive a permanência aplicável ao instante de
referência. Nenhuma atualização de `PropertyStay` será usada como prova de que
o fechamento já era conhecido antes de sua persistência.

A permanência derivada não é fonte histórica independente: é uma projeção
efêmera formada exclusivamente da sequência de movimentos temporalmente
admissíveis. O resultado preserva os IDs de todos os `AnimalMovement` usados na
derivação. Nenhum campo de `PropertyStay` pode completar lacuna, desempatar ou
resolver conflito. Dois movimentos incompatíveis no mesmo contexto resultam em
limitação estável `LIVESTOCK_MOVEMENT_HISTORY_CONFLICT`; a ordem de persistência
do banco não possui autoridade semântica para escolher um deles.

**Aceite:** mover o animal em T2 não altera a permanência retornada para T0;
movimento ocorrido em T0, registrado em T2, só aparece com cutoff >= T2;
conflito de movimentos não é resolvido por ordenação do banco.

### T-05B — Identidade temporal mínima

Introduzir, somente se os registros atuais não forem suficientes, uma trilha
append-only de anexação/desativação de identificador ou versão equivalente. A
seleção deve distinguir validade declarada de momento em que o Titan soube do
identificador.

**Aceite:** identificador anexado ou desativado depois do cutoff não modifica
um snapshot anterior; dois identificadores ativos incompatíveis produzem
lacuna/conflito, não escolha arbitrária.

#### Desenho proposto para T-05B

Os eventos já persistidos `livestock.identifier_attached` e
`livestock.identifier_deactivated` são a primeira fonte candidata. Ambos são
append-only, encadeados no fluxo do agregado `animal`, e preservam
`occurred_at` e `recorded_at`. Portanto, este corte **não** cria por enquanto
uma tabela de lifecycle, não altera `animal_identifiers` e não usa o agregado
`Animal` atual para reconstruir identidade.

O `DomainEventReader` existente já entrega ordem, autoria e tempos, mas
deliberadamente não expõe `payload_canonical_bytes`; sua documentação proíbe
desserializar conteúdo na leitura genérica. Portanto, ele **não basta**, por si
só, para T-05B. Antes de implementação será necessário aprovar uma porta de
leitura de conteúdo imutável, ainda genérica no Core, que entregue os bytes
canônicos e a versão do payload sem interpretar semântica Livestock. O adapter
da Infrastructure pode reutilizar o registro append-only existente; somente o
Livestock Application interpretará os schemas próprios.

Depois desse portão, será criado no Livestock Application um leitor puro de
identidade temporal. Para o animal e Organization solicitados, ele:

1. lê o fluxo `animal` ordenado por `aggregate_version`;
2. aceita somente eventos de esquema e versão conhecidos, com payload canônico
   válido e `animal_id` igual ao alvo;
3. seleciona eventos cujo `occurred_at <= reference_time` **e**
   `recorded_at <= knowledge_cutoff`;
4. aplica `identifier_attached` e `identifier_deactivated` em ordem de versão;
5. devolve somente identificadores ativos no instante solicitado, com IDs dos
   eventos-fonte e limites de conhecimento preservados.

O evento usa dois eixos distintos: `attached_at`/`deactivated_at` do payload
define a validade declarada do identificador; `recorded_at` do evento é o
conhecimento demonstrável do Titan. Um evento ocorrido no passado, mas gravado
depois do cutoff, não participa da reprodução. O leitor não promove
`recorded_at` a `known_at` novo: ele o expõe como a base de conhecimento do
evento, conforme o contrato `RecordTimestamps` já existente.

Falha fechada é obrigatória. Payload inválido, versão desconhecida, evento de
desativação sem anexação anteriormente elegível, identificador reanexado de
forma incompatível, dois identificadores ativos do mesmo tipo ou conflito entre
tempo do evento e tempo declarado não serão arbitrariamente resolvidos. O
leitor devolverá lacuna/limitação determinística; o `LivestockFactProvider` só
poderá emitir um fato de identidade quando a seleção estiver íntegra. O fato
não substituirá nem reinterpretará o fato de permanência do T-05A.

**Fora de escopo deste corte:** busca operacional por identificador, alteração
dos endpoints de Animal, migração/backfill da tabela atual, identificação em
fontes externas, birth data/breed/sex, Policy de mercado e qualquer Decision ou
Dossier já persistido.

**Portão arquitetural adicional:** não é permitido contornar a porta do Core
consultando `core_audit.domain_events` diretamente pelo Livestock Application,
nem ampliar `DomainEventReader` com interpretação de payload. A única opção
compatível é uma porta Core genérica, somente leitura, para conteúdo canônico
preservado; sua introdução exige ADR/aceite específico antes de T-05B.

**Matriz mínima de teste para eventual implementação:** duas Organizations;
anexação T0 conhecida em T0; desativação válida em T2; cutoff T1 que ainda vê
o identificador; evento retroativo ocorrido antes de T1, mas registrado em T2,
que só aparece em cutoff >= T2; desativação sem anexação; dois ativos do mesmo
tipo; payload/schema desconhecido; e prova de que a tabela `animal_identifiers`
atual não é consultada pelo leitor histórico.

### T-05C — Tratamentos locais, correções e campanhas

Definir fonte a fonte o tempo de disponibilidade de aplicações locais,
correções e campanhas. A carência só poderá ser derivada historicamente quando
todas as contribuições utilizadas forem temporalmente elegíveis.

**Aceite:** aplicação ou correção conhecida depois do cutoff não entra em
avaliação anterior; alteração de campanha não reescreve fotografia já emitida;
ausência de trilha de supersession mantém indeterminação.

#### Desenho proposto para T-05C

O corte será dividido para não esconder dependências temporais sob um cálculo de
carência aparentemente simples.

**T-05C1 — seleção de aplicações locais e correções.** `TreatmentApplication`
é append-only; `applied_at` é o tempo válido da aplicação e `created_at` é o
tempo de registro preservado. O seletor temporal considerará somente
aplicações com `applied_at <= reference_time` e `created_at <= knowledge_cutoff`.
`created_at` será tratado como limite de registro demonstrável, nunca renomeado
para `known_at`. Uma correção elegível só suprime a aplicação corrigida quando
ela própria já era elegível no cutoff; correção posterior não reescreve o
snapshot anterior. Cadeia cíclica, correção estrangeira, múltiplas correções
incompatíveis ou referência ausente produzem limitação, não escolha de versão.

**T-05C2 — material farmacológico e cálculo de carência.** A seleção de uma
aplicação não autoriza ainda uma conclusão de carência. Para cada aplicação
efetiva, lote de medicamento, medicamento e `withdrawal_period_days` precisam
possuir registro temporalmente elegível e proveniência preservada. Enquanto o
contrato de imutabilidade/registro desses materiais não for provado na mesma
seleção, o resultado é `INDETERMINATE`; `WithdrawalCalculator` atual, que relê
repositórios de medicamento/batch atuais, não será usado para reprodução
histórica.

**T-05C3 — campanhas sanitárias.** `SanitaryCampaign` hoje só registra criação
e não possui correção, revogação ou supersession. Poderá contribuir apenas como
registro de campanha criada até o cutoff e com intervalo declarado compatível;
qualquer alteração futura exige versão append-only explícita antes de poder
reconstruir passado. A fronteira `[starts_at, ends_at)` será aplicada no novo
seletor; o método legado inclusivo não define a semântica histórica.

Todos os subcortes preservam IDs e digests das fontes selecionadas. Nenhum deles
altera aplicações existentes, cria backfill, expõe API ou promove registro local
sem admissibilidade suficiente a prova de mercado.

**Matriz mínima antes de implementação:** aplicação T0 registrada T2; correção
ocorrida/registrada após cutoff que não suprime original; correção retroativa
conhecida depois; múltiplas correções do mesmo original; batch ou medicamento
criado depois do cutoff; prazo ausente/conflitante; campanha no limite final;
campanha alterada sem supersession; duas Organizations e preservação do snapshot
anterior.

### T-05D — Territorialidade versionada

Antes de usar PRODES, DETER, FUNAI, embargo ou geometrias em avaliação
histórica, persistir a captura ou fotografia verificável do material consultado,
com referência, digest, intervalo, tempo de conhecimento e limitações. Consulta
atual nunca responde retrospectivamente pelo que uma fonte externa apresentava
no passado.

**Aceite:** consulta externa nova produz nova avaliação; reprodução anterior
usa a fotografia preservada ou declara limitação; nenhuma camada atual é usada
como evidência de estado histórico.

## Invariantes

1. `PropertyStay` atual não é fonte histórica por si só.
2. Cadastro atual de Animal não é fotografia histórica geral.
3. Um fato ocorrido no passado e conhecido depois não integra reprodução cujo
   cutoff é anterior ao conhecimento.
4. Fim de intervalo é exclusivo em toda nova seleção.
5. Correção e supersession preservam a versão anteriormente conhecida.
6. Ausência de registro temporal não é valor negativo nem estado limpo.
7. O mesmo snapshot conserva IDs e limitações das fontes selecionadas.
8. `HistoricalReproduction` reutiliza o snapshot preservado; não consulta o
   leitor temporal atual para completar passado.
9. Cada nova fonte habilitada exige testes com duas Organizations e cenário
   T0 (válido), T1 (cutoff) e T2 (mudança ou conhecimento posterior).
10. Nenhum corte desta ADR autoriza mercado real, reconhecimento externo ou
    alteração de `Decision`/`Dossier` históricos.
11. Uma reconstrução histórica pode conter menos fatos que a leitura atual; isso
    é conhecimento demonstrável menor, não perda de informação.
12. `reference_time` responde quando o estado é perguntado;
    `knowledge_cutoff` limita o conhecimento que pode participar da resposta.

## Alternativas rejeitadas

- **Usar `get_active_stay()` com `reference_time`:** ele expressa estado atual
  e não preserva quando o fechamento foi conhecido.
- **Reconstruir todo Animal a partir da linha atual:** atributos e
  identificadores presentes hoje podem não existir no corte histórico.
- **Backfill de `known_at` com `created_at` ou relógio do banco:** sem prova
  explícita, transforma aproximação em evidência histórica.
- **Uma tabela bitemporal universal agora:** mistura fontes com semânticas
  distintas antes de existir o segundo caso concreto.
- **Consultar a fonte territorial atual em reprodução histórica:** confunde
  reavaliação atual com reprodução do conhecimento anterior.

## Consequências

Até a conclusão de cada corte, Market Eligibility e demais avaliações temporais
continuam honestamente indeterminadas quando dependem de fonte ainda não
reconstruível. Isso reduz conveniência de leitura, mas preserva as garantias de
auditoria, não retroatividade e explicabilidade da ADR-0052.

## Portão para aceite

Antes de implementar T-05A, confirmar:

1. movimentos append-only serão a fonte autoritativa de permanência histórica,
   enquanto `PropertyStay` permanecer projeção operacional;
2. a primeira entrega ficará restrita a movimentos/permanência, sem identidade,
   tratamento, campanha ou territorialidade;
3. se a análise de T-05A revelar que `created_at` do movimento não prova
   disponibilidade de conhecimento, o corte deve parar sem inferir `known_at`;
4. toda API pública permanecerá compatível e o novo leitor será consumido
   inicialmente apenas pelo caminho temporal estrito.

## Aceite registrado

Aceita em 13 de agosto de 2026, com autorização restrita ao T-05A. O corte
permanece limitado a movimentos/permanência temporal; as demais fontes seguem
dependentes de seus próprios desenhos e portões.

## Registro de execução

**T-05A concluído em 13 de agosto de 2026.** O leitor temporal estrito agora
deriva a permanência somente da sequência contínua de `AnimalMovement`
append-only pertencente à Organization, ocorrida até `reference_time` e
registrada até `knowledge_cutoff`. `movement_time` permanece tempo válido e
`created_at` é preservado somente como `recorded_at`; o corte não fabrica
`known_at`. Ausência, conflito temporal ou sequência descontínua resultam em
limitação explícita e não em permanência atual. `PropertyStay` segue fora do
leitor histórico.

**T-05B concluído em 13 de agosto de 2026.** O lifecycle de identificadores é
reconstruído exclusivamente dos eventos canônicos append-only
`identifier_attached` e `identifier_deactivated`, selecionados por
`occurred_at` e `recorded_at` sem atribuir a este último semântica automática de
`known_at`. Schema, versão, agregado, Animal, tempo declarado e sequência são
validados; ausência, evento inválido ou lifecycle incompatível produzem
limitação, nunca leitura de `animal_identifiers` atual. O fato resultante
preserva IDs e digests dos eventos-fonte. Nenhuma migration, API, backfill ou
alteração de Decision/Dossier foi introduzida.

**T-05C1 concluído em 13 de agosto de 2026.** Aplicações locais e correções são
selecionadas apenas quando `applied_at <= reference_time`, o registro local e o
evento canônico `treatment_applied` correspondente existiam até
`knowledge_cutoff`. Correção temporalmente elegível suprime somente o original
que ela referencia; correção posterior não altera snapshot anterior. Desativação
órfã, evento ausente/ambíguo ou cadeia incompatível geram limitação. O fato
`livestock.treatment_history.local` preserva IDs e digests de evento, mas
declara `withdrawal_assessment=NOT_CALCULATED_IN_T05C1`: medicamento, batch,
prazo e campanhas seguem fora deste corte.

**T-05C2 concluído em 14 de agosto de 2026.** A carência histórica é calculada
somente a partir das aplicações efetivas do T-05C1 quando o lote e o medicamento
imutáveis pertencem à mesma Organization, foram registrados até o
`knowledge_cutoff` e possuem evento canônico de registro único cujo payload
corresponde integralmente ao material persistido. O prazo é tomado desse
medicamento comprovado, não do `WithdrawalCalculator` de leitura atual; lote,
medicamento, eventos e digests integram a proveniência do fato
`livestock.withdrawal`. Material posterior, evento ausente/ambíguo ou divergência
entre registro e evento produzem limitação explícita, sem conclusão de carência.

**T-05C3 concluído em 14 de agosto de 2026.** Campanhas sanitárias passam a ser
fonte histórica limitada somente quando o registro atual coincide com um evento
canônico único `sanitary_campaign_registered`, criado até `knowledge_cutoff` e
já iniciado em `reference_time`. Sem lifecycle de alteração, revogação ou
supersession, divergência entre registro e evento remove a campanha da seleção
histórica em vez de reinterpretar o passado. O `LivestockFactProvider` emite o
fato `livestock.sanitary_requirement.<code>` com derivação
`TEMPORAL_SANITARY_CAMPAIGN_V1`, IDs e digests da campanha e, quando houver
atendimento comprovado, da aplicação selecionada pelo T-05C1. A aplicação só
conta dentro da fronteira semiaberta `[starts_at, ends_at)`; ausência de
aplicação elegível produz `INDETERMINADA`, nunca afirmação negativa de que o
animal não foi tratado. Nenhuma migration, API, mercado real ou alteração de
Decision/Dossier foi introduzida.

**T-05D Corte 1 concluído em 14 de agosto de 2026.** A primeira reconstrução
territorial histórica usa somente fonte sintética `TERRITORIAL_TEST_SOURCE`.
`TerritorialSourceCapture` preserva propriedade, geometria/versionamento,
camada, operação, escopo, resumo canonizado, digest, versões da fonte,
`captured_at`, `known_at` e limitações. `TemporalTerritorialCaptureReader`
seleciona capturas por `reference_time` e `knowledge_cutoff`; captura posterior,
conhecimento posterior, intervalo inválido ou múltiplas capturas para o mesmo
escopo falham fechados. O `LivestockFactProvider` emite os fatos
`livestock.territorial.test_timeline` e `livestock.territorial.test_overlap`
somente quando a propriedade do animal já foi derivada temporalmente por
movimentos, preservando IDs/digests da captura e sem consultar PRODES, DETER,
FUNAI, IBAMA ou geodados atuais. Ausência de captura elegível vira limitação, não
`SEM_RESTRICAO`. Nenhuma migration, API, fonte real, mercado real ou alteração
de Decision/Dossier foi introduzida.

**T-05D Corte 2 concluído em 14 de agosto de 2026.** A fotografia territorial
sintética ganhou persistência append-only em
`core_audit.territorial_source_captures`, com ownership vertical Livestock,
contrato canônico explícito (`response_schema`, `response_schema_version` e
`canonicalization_version`), FKs compostas por Organization para propriedade e
geometria, constraints de perfil/camada/digest/intervalo e RLS somente para
`SELECT`/`INSERT`. O repositório PostgreSQL preserva os tempos `captured_at`,
`known_at` e `recorded_at` sem recalcular digest nem reinterpretar fonte atual, e
mantém a seleção temporal do Corte 1 via `TemporalTerritorialCaptureReader`.
Continuam fora API pública, fonte real, adapter geodados, mercado real, Dossier,
VerificationBundle e alteração de Decisions.
