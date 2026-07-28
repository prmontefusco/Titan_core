# ADR 0047 - Correção de TransformationEvent publicado (Marco 11, Passo 11.7)

Data: 2026-07-28
Status: ACEITA (após três rodadas de revisão arquitetural com o responsável)

## Problema

A ADR-0046 deixou deliberadamente em aberto a forma exata de correção de um
`TransformationEvent` publicado (item 11 da decisão), fixando apenas um
invariante: qualquer forma escolhida referencia explicitamente o registro
corrigido e declara o que substitui — nunca reescreve em silêncio. Esta ADR
fecha essa decisão, com "o mesmo cuidado que a correção de
`TreatmentApplication` recebeu no Marco 9", como a própria ADR-0046 pediu.

## O padrão já validado: correção de TreatmentApplication (Marco 9)

Investigado antes de propor qualquer coisa nova:

- **Append-only de verdade.** A correção nunca edita o original — cria um
  registro novo. `corrects_application_id` aponta para o original; não existe
  campo mutável "is_latest" em lugar nenhum.
- **Supersessão é derivada, nunca armazenada no corrigido.** A timeline
  calcula `superseded_by` a partir do vínculo (`_superseded_map`): procura o
  registro cujo `corrects_application_id` aponta para o original — nunca o
  contrário.
- **Os dois aparecem na timeline, cada um no seu `occurred_at`.**
- **Sem limite de profundidade de cadeia.** Isso nunca foi um problema real
  porque `TreatmentApplication` não gera nada a jusante.

## Por que TransformationEvent é mais difícil

`TransformationEvent` cria `TraceableItem`s novos como saída (Passo 11.2), e
esses itens podem já ter sido consumidos por uma transformação seguinte (uma
desossa, Passo 11.6) antes de alguém perceber que o evento original estava
errado. As duas primeiras versões desta ADR (ambas devolvidas `PENDENTE`)
fecharam o modelo conceitual — estado derivado `CURRENT`/`SUPERSEDED`, cadeia
linear, histórico ≠ disponibilidade operacional — mas deixaram três lacunas
que só aparecem sob execução concorrente e sob o eixo do tempo do
conhecimento, tratadas nesta versão.

## Decisão

### 1. `corrects_transformation_id` novo em `TransformationEvent`

Campo opcional (`TypedId | None`), com dupla guarda: `entity_type` precisa
ser `transformation_event`, e o evento não pode corrigir a si mesmo. A
correção é um `TransformationEvent` **completo e novo**: reafirma entradas,
saídas, balanço e evidências inteiros. Não existe patch parcial de um campo
só — a mesma razão que fez o Marco 9 rejeitar "atualizar registro original"
e "campo `is_latest` manual" (ADR-0017).

**Restrição estrutural:** a coluna `corrects_transformation_id` recebe
`UNIQUE` no banco. No PostgreSQL, múltiplos `NULL` continuam permitidos —
eventos comuns (a grande maioria) nunca colidem entre si; a constraint só
atua quando dois registros tentam apontar para o mesmo original. Isso
garante `E1 ← E2` e impede `E1 ← E2` **e** `E1 ← E3` simultaneamente: é o
uso correto de invariante de domínio (a guarda de serviço, que produz um
erro inteligível) somado a garantia estrutural no banco (que protege contra
corrida entre duas requisições concorrentes tentando corrigir o mesmo
alvo).

**`correction_reason` obrigatório quando há correção.** Todo evento com
`corrects_transformation_id` preenchido declara também `correction_reason:
str` (não vazio) — sem isso, a auditoria vê o que mudou mas não por que
mudou. `evidence_references` continua existindo à parte, para quem quiser
anexar prova documental da causa (ex.: laudo da balança de expedição).

### 2. `TraceableItem` nunca é editado; a correção cria itens novos

Os itens do evento original continuam existindo exatamente como estavam —
`TraceableItem` é imutável desde o Passo 11.2, e esta ADR não abre exceção.
A correção produz um conjunto novo de `TraceableItem` para as saídas
corrigidas, pela mesma rotina que já constrói saídas (`_build_outputs`).

### 3. Estado derivado `CURRENT`/`SUPERSEDED` — relativo a um instante de referência, não absoluto

Um `TransformationEvent` está em um de dois estados, sempre calculados,
nunca armazenados:

```
CURRENT     — nenhum outro evento o corrige, até o instante de referência.
SUPERSEDED  — existe um TransformationEvent, com recorded_at <= instante de
              referência, cujo corrects_transformation_id aponta para ele.
```

`VOIDED` fica fora do escopo desta ADR.

**O instante de referência não é sempre "agora".** Existem duas funções
distintas, não uma:

- `operational_status_now(event_id)` — usada pelas guardas de escrita
  (registro e correção). Instante de referência = agora, dentro da mesma
  transação que vai gravar. É sempre absoluta no sentido de "o que é
  verdade neste exato momento para decidir se algo pode ser escrito".
- `status_as_known_at(event_id, known_until)` — usada por reconstrução
  histórica. Considera `SUPERSEDED` somente se existir correção com
  `recorded_at <= known_until`. Uma reconstrução com `known_until` anterior
  ao `recorded_at` da correção enxerga o evento original como `CURRENT`,
  porque é isso que o Titan sabia naquele instante — mesmo que hoje ele
  já esteja `SUPERSEDED`.

O cálculo em si é o mesmo: busca reversa por `corrects_transformation_id`,
exatamente como `_superseded_map` no Marco 9 — a diferença é só o filtro por
`recorded_at` quando a pergunta é histórica, não "e agora?".

**Invariante central:** um `TraceableItem` cujo evento criador está
`SUPERSEDED` (na função `operational_status_now`) não pode ser usado como
entrada de uma nova transformação. Ele continua inteiramente consultável —
timeline, dossiê, recall, reprodução histórica — porque nada foi apagado.

### 4. A cadeia de correção é linear; só o leaf atual pode ser corrigido

Corrigir uma correção continua permitido (`E1 → E2 → E3`), mas corrigir um
evento que já foi corrigido é recusado: se `E1` já tem `E2` como correção,
uma tentativa de `E3.corrects_transformation_id = E1` é recusada com um
erro de domínio explícito (`AlvoDeCorrecaoNaoEhVigente`) — a forma correta
é `E3.corrects_transformation_id = E2`. A guarda de serviço confere isso
(usando `operational_status_now`, nunca a versão histórica) antes de
gravar; a `UNIQUE` do item 1 é a segunda linha de defesa para o caso de
duas requisições concorrentes tentarem corrigir o mesmo alvo ao mesmo
tempo — mas ver item 5: a `UNIQUE` sozinha não fecha toda corrida possível.

### 5. Concorrência e atomicidade — o ponto central desta revisão

A `UNIQUE(corrects_transformation_id)` impede duas correções concorrentes
do **mesmo** evento. Ela **não** impede uma correção concorrendo com o
consumo de suas saídas: sem bloqueio explícito, uma transação que corrige
`E1` e uma transação que registra uma nova `DEBONING` consumindo `HC1`
(saída de `E1`) podem cada uma observar um estado válido antes de a outra
commitar, e as duas terminam com sucesso — violando a invariante 6 mesmo
com todo o resto do modelo correto.

**Protocolo obrigatório, para os dois caminhos de escrita (registro normal
e correção):**

1. Adquirir bloqueio transacional (`SELECT ... FOR UPDATE`) sobre todo
   sujeito que a operação vai ler para decidir disponibilidade, **antes**
   de decidir qualquer coisa: o `TransformationEvent` alvo (em correção),
   os `TraceableItem`/animal de entrada, e — em correção — os outputs do
   evento sendo corrigido (para a checagem de "consumida a jusante").
2. **Ordem determinística de bloqueio**, para reduzir deadlock: primeiro o
   `TransformationEvent` alvo (se houver, isto é, em correção), depois as
   entradas ordenadas por identificador, depois as saídas do evento sendo
   corrigido ordenadas por identificador.
3. **Revalidar depois do bloqueio, nunca confiar na leitura de antes dele.**
   A checagem de "é `CURRENT`?", "já foi consumido?", "é o leaf atual?" é
   refeita com os bloqueios já adquiridos — a leitura inicial (antes do
   bloqueio) serve só para decidir o que bloquear, nunca para decidir o
   resultado.
4. **Uma transação só.** Bloquear → revalidar → criar `TraceableItem`s
   novos → criar o `TransformationEvent` (normal ou corretivo) → projetar
   `UniversalRelation` → commit. Nenhuma etapa fica visível isoladamente;
   uma leitura concorrente nunca observa a correção pela metade.

Isso vale tanto para `SlaughterService`/`DeboningService` registrando uma
transformação nova (bloquear as entradas antes de checar "produtor
`CURRENT`, não consumido") quanto para a correção (bloquear o alvo e suas
saídas antes de checar "leaf atual, nada consumido por evento `CURRENT`").
Sem isso, as invariantes desta ADR são corretas em execução sequencial e
não são garantidas sob concorrência real — que é exatamente o ambiente de
produção.

### 6. Fórmula formal de disponibilidade operacional de um item

```
item_operationally_available(item):
    (item.created_by_transformation_id is None
     or status_of(item.created_by_transformation_id) == CURRENT)
    and not exists consumer:
        consumer.status == CURRENT
        and item in consumer.inputs
```

`created_by_transformation_id is None` cobre o caso já prescrito pela
ADR-0046 (invariante 4: "zero é permitido — importação histórica ou origem
externa sem produção detalhada conhecida"); um item sem evento criador
conhecido é tratado como disponível por padrão, na ausência de qualquer
outra informação — ausência não vira indisponibilidade inventada, o mesmo
princípio da ADR-0040.

### 7. Reafirmar as mesmas entradas do evento corrigido é permitido

A guarda de reaproveitamento (`_ja_usado_como_entrada`, Passo 11.2) recebe
um parâmetro novo: o evento sendo corrigido (`excluding_event_id`). Ao
verificar se um sujeito já está em uso, a guarda ignora especificamente a
relação `input_of` que aponta para o evento sendo corrigido. Uma entrada
que não pertencia ao evento original passa pela guarda normal.

### 8. Entradas removidas pela correção ficam livres, sem contabilidade extra

Se o evento original consumia o item `B` e a correção não o inclui mais,
`B` volta a ficar disponível automaticamente — consequência direta da
fórmula do item 6, não uma regra separada. Assim que o original vira
`SUPERSEDED`, `B` deixa de contar como consumido por um evento `CURRENT`,
sem precisar de nenhuma rotina para "liberar" `B` explicitamente.

### 9. "Consumida a jusante" — definição precisa, e olhando só o leaf

A correção de um evento `E` é recusada se qualquer saída de `E` aparece
como entrada de outro `TransformationEvent` que está `CURRENT` (função
`operational_status_now`, sob os bloqueios do item 5). A verificação olha
as saídas do **leaf atual** sendo corrigido — nunca as de um ancestral já
`SUPERSEDED`, que já não podem ser consumidas por ninguém. Correção em
cascata continua fora de escopo: se a saída já foi consumida por um evento
`CURRENT`, a correção é recusada, sem propagação automática — dívida
registrada, do mesmo jeito que a ADR-0046 fez com `AnimalExit(ABATE)`.

### 10. Leitura (recall, timeline, dossiê) continua histórica e completa — mas anotada

`RecallService` e `LivestockTimelineService` **não são alterados** e não
ganham um modo de consulta "operacional" separado — continuam mostrando o
grafo inteiro, porque são ferramentas de auditoria e reconstrução. Mas a
resposta da vertical (não o Core) anota, para cada `TransformationEvent` e
`TraceableItem` que aparece num caminho de recall, o estado derivado
correspondente (`CURRENT`/`SUPERSEDED`), calculado por
`operational_status_now` no instante da consulta. Isso evita que uma
integração leia um caminho corrigido como se fosse igualmente vigente ao
caminho atual — sem transformar `RecallService` numa máquina de decisão: a
anotação é responsabilidade de `livestock_queries.py`, que já entende o
domínio de transformação, não do Core, que continua agnóstico.

O dossiê do item (Passo 11.5) expõe o mesmo estado — 
`transformation.status: "CURRENT" | "SUPERSEDED"` e, quando `SUPERSEDED`,
`transformation.corrected_by_transformation_id` — calculado com o mesmo
`operational_status_now`, porque o dossiê hoje não aceita `known_until`
(é sempre "o estado agora"). Se um dossiê histórico vier a existir no
futuro (com `known_until`), o status exposto deve usar `status_as_known_at`
com esse mesmo corte — nunca consultar o estado operacional atual e
inseri-lo retroativamente numa visão que pretende reproduzir conhecimento
anterior.

### 11. Mudança de `process_type` não é correção

Uma correção exige o mesmo `process_type` do original. Reclassificar a
natureza do evento (`SLAUGHTER` quando deveria ser `DEBONING`) não é a
mesma afirmação contada de novo — fica marcado como exigindo, no futuro,
anulação explícita mais um evento novo e independente, fora do escopo
desta ADR.

## Invariantes

1. `TransformationEvent` publicado nunca é editado nem apagado.
2. Toda correção é um `TransformationEvent` novo, completo, do mesmo
   `process_type` do original, com `correction_reason` obrigatório.
3. `TraceableItem` nunca é editado; a correção nunca reaproveita identidade
   de item existente.
4. Um `TransformationEvent` está em exatamente um de dois estados
   derivados — `CURRENT` ou `SUPERSEDED` — nunca armazenados, sempre
   calculados em relação a um instante de referência.
5. Para guardas de escrita, o instante de referência é agora
   (`operational_status_now`). Para reconstrução histórica, é o
   `known_until` da consulta (`status_as_known_at`), considerando somente
   correções com `recorded_at <= known_until`.
6. Um `TraceableItem` operacionalmente indisponível (fórmula do item 6 da
   decisão) não pode ser usado como entrada de uma nova transformação,
   embora continue consultável em timeline, dossiê, recall e reprodução
   histórica.
7. Cada `TransformationEvent` possui no máximo uma correção direta,
   garantido por `UNIQUE` em `corrects_transformation_id` (múltiplos `NULL`
   permitidos).
8. Somente um evento `CURRENT` pode ser corrigido; corrigir um evento
   `SUPERSEDED` é recusado.
9. A cadeia de correção é linear; bifurcação é estruturalmente impossível
   (invariantes 7 e 8 juntas).
10. Reafirmar, na correção, uma entrada que já pertencia ao evento sendo
    corrigido é permitido; qualquer entrada nova segue a guarda normal.
11. Uma entrada não reafirmada pela correção volta a ficar operacionalmente
    disponível sem contabilidade além do estado derivado.
12. "Consumida a jusante" significa entrada de outro `TransformationEvent`
    `CURRENT`; a verificação, ao corrigir `E`, olha somente as saídas do
    próprio `E`.
13. `RecallService` e `LivestockTimelineService` preservam a visão
    histórica completa e não eliminam eventos `SUPERSEDED`; quando o
    contrato da vertical expõe eventos ou itens originados de
    transformação, inclui o estado derivado correspondente. Disponibilidade
    operacional continua decidida somente nas guardas de escrita.
14. Criação de transformação (normal ou corretiva) e consumo de item usam
    o mesmo protocolo transacional: bloqueio determinístico dos sujeitos
    envolvidos, revalidação após o bloqueio, e persistência atômica do
    evento, dos itens novos e das projeções — nenhum visível isoladamente.
15. A `UNIQUE` da invariante 7 é defesa contra bifurcação; não substitui o
    bloqueio transacional da invariante 14 contra corrida entre correção e
    consumo.
16. Mudança de `process_type` não é correção; exige, no futuro, anulação
    explícita mais um evento novo e independente.

## O que esta ADR não decide

- **Correção em cascata** — o que fazer quando a saída do evento original
  já foi consumida por um evento `CURRENT` a jusante. Recusada em vez de
  resolvida; dívida registrada.
- **Anulação/void explícito (`VOIDED`)** de um `TraceableItem` ou
  `TransformationEvent` sem substituição.
- **Reclassificação de `process_type`.**
- **Dossiê histórico do item com `known_until` parametrizável** — hoje o
  dossiê só responde "e agora?"; a extensão para "e no instante X?" fica
  para quando houver caso real, usando `status_as_known_at` (item 10 da
  decisão) em vez de inventar um mecanismo novo.

## Referências

- ADR-0046, item 11 — decisão de correção deliberadamente adiada até aqui.
- ADR-0045 — formalização bitemporal (valid time vs. knowledge time),
  reaproveitada sem alteração na distinção `operational_status_now` vs.
  `status_as_known_at`.
- ADR-0017 — correção e supersessão do Core; rejeita "atualizar original" e
  "campo `is_latest` manual" em favor de objetos novos com histórico
  preservado.
- Marco 9 / Passo 9.4 — correção de `TreatmentApplication`, o precedente
  direto que esta ADR segue e adapta.
