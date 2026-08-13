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

### T-05C — Tratamentos locais, correções e campanhas

Definir fonte a fonte o tempo de disponibilidade de aplicações locais,
correções e campanhas. A carência só poderá ser derivada historicamente quando
todas as contribuições utilizadas forem temporalmente elegíveis.

**Aceite:** aplicação ou correção conhecida depois do cutoff não entra em
avaliação anterior; alteração de campanha não reescreve fotografia já emitida;
ausência de trilha de supersession mantém indeterminação.

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
