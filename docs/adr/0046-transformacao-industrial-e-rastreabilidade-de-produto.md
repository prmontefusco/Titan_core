# ADR 0046 - Transformação industrial e rastreabilidade de produto (Marco 11)

Data: 2026-07-28
Status: ACEITA (após duas rodadas de revisão arquitetural com o responsável)

## Problema

Nenhuma rastreabilidade de produto existe hoje. O ciclo do animal termina em
`AnimalExit(ABATE)` apontando para um `destination_counterparty_id` — o
frigorífico — e nada mais é registrado sobre o que acontece lá dentro. A
cadeia deixa de ser linear no momento do abate: um animal produz múltiplos
itens rastreáveis (fan-out), e o processamento pode misturar itens de
múltiplos animais num produto só (fan-in). A NR-2 já apontava a direção —
alinhar ao vocabulário GS1 EPCIS — mas nunca foi detalhada o suficiente para
virar código.

Esta ADR passou por duas rodadas de revisão com o responsável, seguindo a
mesma disciplina da ADR-0045: nenhuma linha de domínio antes da arquitetura
estar validada.

## Visão conceitual

```
Animal
   │
AnimalExit               (a fazenda afirma: "o animal saiu")
   │
   │  ── protocolo ADR-0042 (transferência entre Organizations) ──
   ▼
TransformationEvent       (o frigorífico afirma: "isto foi produzido")
   │
   ├──────────────┐
   │              │
   ▼              ▼
TraceableItem   TraceableItem
   │              │
   └──────┬───────┘
          ▼
  UniversalRelation        (projeção navegável, não fonte)
          ▼
    RecallService          (travessia — tracking e tracing)
          ▼
       Dossier
```

Cada camada responde a uma pergunta distinta — o mesmo princípio que
organiza `Identity`/`Provenance`/`Evidence`/`Confidence`/`Decision` no
restante do Titan: fato, proveniência, relação, avaliação, decisão. Esta ADR
não inventa um mini-framework de transformação; encaixa `TraceableItem` e
`TransformationEvent` na mesma cadeia, reutilizando `UniversalRelation`,
`RecallService`, `Provenance`, `Evidence` e `CoverageGap` sem alterá-los.

## Decisão

### 1. O contrato nasce N→M; o primeiro cenário validado é 1→N

`TransformationEvent` sempre tem **listas** de entrada e saída — nunca
`input_id` singular com `output_ids` plural, mesmo no primeiro incremento.
N=1 é o caso degenerado da lista, não uma forma estrutural à parte.

O que é faseado é o **caso de uso validado**, não a forma: Marco 11a prova
fan-out real (uma entrada, várias saídas); Marco 11b, adiado, prova fan-in
real (várias entradas). A NR-2 já registrou como problema em aberto o que a
leitura de um produto com dezenas de origens deve mostrar — adia-se a
**semântica de leitura e decisão** do fan-in, não a capacidade estrutural de
aceitar múltiplas entradas.

### 2. Alinhamento com EPCIS é de forma, não de granularidade universal

O modelo se alinha à forma do GS1 EPCIS `TransformationEvent`, que admite
múltiplos inputs e outputs. **Isso não implica que todo processo industrial
deva ser agregado num único evento.** A granularidade concreta de cada
evento é determinada pelo ponto real de captura, pela operação observada,
pelos lotes envolvidos e pela capacidade real de identificação naquele
processo — nunca pela conveniência do modelo. Duas meias-carcaças podem
nascer do mesmo evento; couro, vísceras e miúdos podem ter pontos de
captura distintos, e portanto eventos distintos, mesmo dentro do mesmo abate
físico. Essa decisão é do processo observado, não desta ADR.

### 3. Abate e desossa são eventos distintos, não um evento só

```
TransformationEvent: SLAUGHTER
  input:   Animal A1
  outputs: HalfCarcass HC1, HalfCarcass HC2, Hide H1, OffalBatch O1

TransformationEvent: DEBONING           (evento seguinte, separado)
  inputs:  HalfCarcass HC1, HalfCarcass HC2
  outputs: CutBatch C1, CutBatch C2, TrimBatch T1
```

O primeiro incremento (Marco 11a) implementa **SLAUGHTER**. DEBONING fica
desenhado (o contrato já suporta) mas não implementado até o primeiro
incremento estar provado. Qual fan-out entra primeiro é decisão de negócio
— depende do processo real do primeiro frigorífico-alvo — não técnica.

### 4. Nome do conceito-raiz: evitar "Product" prematuramente

Nome de trabalho: `TraceableItem` (não congelado até conhecer o vocabulário
real do frigorífico-alvo). A invariante correta é: **toda saída de
transformação que precise continuar rastreada recebe identidade própria** —
isso não pressupõe produto comercial.

`PALLET` é removido da lista de tipos ilustrativos: um pallet é tipicamente
**unidade logística de agregação**, não material resultante de
transformação (EPCIS trata agregação e transformação como conceitos
distintos). Tipos ilustrativos, sujeitos ao vocabulário real observado:

```
CARCASS
HALF_CARCASS
CUT_BATCH
TRIM_BATCH
OFFAL_BATCH
PACKAGED_PRODUCT
```

Se uma unidade logística (pallet, caixa de transporte) se mostrar necessária,
ela nasce como família própria (`LogisticUnit`), não como mais um
`ItemType` de `TraceableItem`.

### 5. A transformação é a fonte autoritativa; `UniversalRelation` é projeção navegável

`TransformationEvent` declara, ele mesmo, seus participantes — não deriva
essa informação de relações externas:

```
TransformationEvent
├── event_id
├── process_type               (ex.: SLAUGHTER, DEBONING)
├── occurred_at
├── facility_reference: UniversalReference    (o estabelecimento, sujeito estruturado)
├── operator_reference: UniversalReference | None
├── source_artifact_references: tuple[UniversalReference, ...]
├── inputs: tuple[TransformationParticipant, ...]   (nunca vazio)
├── outputs: tuple[TransformationParticipant, ...]  (nunca vazio)
├── balance: TransformationBalance | None
└── evidence_references: tuple[UniversalReference, ...]
```

**Nota de nomenclatura:** apesar do nome "Event", `TransformationEvent`
representa um fato persistente do domínio — um agregado com identidade
própria, consultável e referenciável — e não um `DomainEvent` do mecanismo
de log append-only do Core (`packages/core_infrastructure/persistence/events.py`).
São dois conceitos homônimos por convenção EPCIS, não pelo mecanismo do
Titan; um `TransformationEvent` publicado pode, adicionalmente, gerar
`DomainEvent`s de auditoria (como qualquer outra escrita relevante), mas ele
próprio não é um.

```
TransformationParticipant
├── subject_reference: UniversalReference   (Animal, TraceableItem, etc.)
├── role: INPUT | OUTPUT
├── quantity: Decimal | None
├── unit: str | None
├── measurement_basis: str | None   (ex.: "peso vivo", "peso líquido pós-sangria")
├── consumption_mode: FULL | PARTIAL | REFERENCE_ONLY   (default FULL em 11a)
└── lot_or_batch_reference: UniversalReference | None
```

Depois de gravado o evento, o Titan **projeta** `UniversalRelation`
(`input_of`/`output_of`, com `quantity`/`unit` já suportados pelo Core) para
navegação e recall — a mesma forma "fato autoritativo → projeção" já usada
em `reference_projection` (Passo 7.2). A relação nunca é fonte concorrente:
reconstituir um evento sempre lê o `TransformationEvent`, nunca as relações.

`TransformationParticipant` compartilha uma única forma estrutural para
`INPUT` e `OUTPUT` porque ambos carregam a mesma informação (sujeito,
quantidade, unidade, base de medição) — mas o `role` não é um rótulo
decorativo: ele decide regras de validação que **não são simétricas**, e o
código que constrói/valida `TransformationEvent` precisa tratá-las como
regras distintas, não como o mesmo caminho parametrizado por um enum:

- Todo participante com `role=OUTPUT` **cria** um `TraceableItem` novo
  (invariante 3). Nunca referencia um sujeito preexistente.
- Todo participante com `role=INPUT` **nunca** cria sujeito novo; referencia
  sempre um sujeito já existente (`Animal` ou `TraceableItem` anterior).
- `consumption_mode` só é significativo em `INPUT` (o quanto daquele sujeito
  foi consumido); em `OUTPUT` não se aplica e deve ser rejeitado se presente.
- `lot_or_batch_reference` normalmente qualifica o `INPUT` (de qual lote
  físico veio o material); em `OUTPUT` seu uso é decisão do `process_type`,
  não uma regra geral.

Se, na implementação, essas regras exigirem validação divergente o
suficiente para justificar dois tipos (`TransformationInput` /
`TransformationOutput`) em vez de um único tipo com `role`, essa divisão é
um detalhe de código permitido por esta ADR, não uma mudança de arquitetura
— o contrato observável (o que `TransformationEvent` declara) é o mesmo.

### 6. Quem pode ser entrada é decisão do perfil de processo, não do Core

```
subject_reference: UniversalReference
```

aceita qualquer sujeito rastreável — `Animal` no primeiro cenário,
`TraceableItem` nos seguintes. **O Core não valida a semântica**; o perfil
de `process_type` da vertical decide o que é entrada válida:

```
SLAUGHTER  → entrada permitida: Animal
DEBONING   → entrada permitida: CARCASS, HALF_CARCASS
MIXING     → entrada permitida: CUT_BATCH, TRIM_BATCH
```

Outputs sempre referenciam **novos** `TraceableItem` — reclassificação sem
criação de novo sujeito fica fora de escopo desta ADR.

### 7. Balanço é declarado e pode ser indeterminado — nunca conservação silenciosa

```
TransformationBalance
├── status: NOT_ASSESSED | DECLARED | ASSESSED | INDETERMINATE
├── measurement_basis: str | None
├── input_total: Decimal | None
├── output_total: Decimal | None
├── declared_loss: Decimal | None      # perda/descarte explicitamente registrado
├── unaccounted_quantity: Decimal | None  # diferença ainda não explicada
├── tolerance: Decimal | None
├── result: BALANCED | WITHIN_TOLERANCE | OUTSIDE_TOLERANCE | INDETERMINATE | NOT_APPLICABLE
├── reasons: tuple[str, ...]
└── evidence_references: tuple[UniversalReference, ...]
```

`balance` é `None`/`NOT_ASSESSED` quando o evento é importado com pesos
ausentes ou unidades incompatíveis — **nunca inventa zero ou diferença**.
`declared_loss` (perda conhecida: sangue, evaporação, descarte) e
`unaccounted_quantity` (diferença ainda não explicada) são conceitos
distintos e não podem ser somados silenciosamente. Comparar bases de medição
incompatíveis (peso vivo vs. peso líquido de produtos) sem declarar a base
de cada lado produz `INDETERMINATE`, nunca um número.

### 8. `AnimalExit` e `TransformationEvent` são conceitos distintos

`AnimalExit` diz **"o ciclo do animal terminou"**. `TransformationEvent` diz
**"quais novos sujeitos rastreáveis foram produzidos"**. A separação permite
registrar um abate antigo cuja produção detalhada é desconhecida
(`AnimalExit(ABATE)` + nenhuma `TransformationEvent` conhecida + lacuna
declarada) em vez de inventar produtos.

**Dívida semântica identificada nesta revisão, registrada e não resolvida
aqui:** `AnimalExit(ABATE)` hoje não distingue "destinado ao abate" de
"abate confirmado" — são fatos diferentes, e a ADR-0042 já separou venda de
abate para o caso de destino comercial. Esta ADR **não** altera
`AnimalExit` existente; registra a pergunta para revisão futura, porque a
resposta afeta quem tem autoridade para declarar `TransformationEvent(SLAUGHTER)`
(ver item 9).

### 9. Fronteira de Organization — a orquestração conjunta só vale dentro do mesmo tenant

**Correção bloqueante desta rodada.** O abate tipicamente ocorre no
frigorífico, uma Organization distinta da fazenda. A ADR-0042 já estabeleceu
que uma Organization nunca escreve na outra. Portanto:

```
❌ SlaughterService orquestrando, na mesma transação:
   AnimalExit (Organization Fazenda) + TransformationEvent (Organization Frigorífico)
```

não é uma operação válida — atravessaria tenants.

**Forma correta**, seguindo o protocolo já estabelecido pela ADR-0042
(contraparte externa, artefato de transferência, continuidade de
proveniência):

```
Organization Fazenda
  AnimalExit (venda/transferência, destino = frigorífico)
  ReceivedTransferArtifact / continuidade de proveniência

              ↓  (protocolo ADR-0042, não escrita cross-tenant)

Organization Frigorífico
  representação local do animal recebido (já coberta pela ADR-0042)
  TransformationEvent(SLAUGHTER)  ← só aqui, só se o frigorífico
                                     tiver representação local autorizada
```

A orquestração transacional conjunta (`SlaughterService` registrando
`AnimalExit` + `TransformationEvent` no mesmo ato) só é válida **quando
ambos pertencem à mesma Organization** — por exemplo, uma operação verticalizada
onde fazenda e frigorífico são a mesma empresa. No caso inter-organizacional
(o caso comum), são dois atos, em duas Organizations, ligados pelo protocolo
de transferência já existente — nunca uma escrita só.

**Consequência de autoridade:** `TransformationEvent(SLAUGHTER)` só pode ser
declarado pela Organization que tem representação local autorizada do
animal (custódia recebida, não apenas a intenção de venda da fazenda).
`AnimalExit` da fazenda, sozinho, **não é evidência de que o abate ocorreu**
— é evidência de que o animal foi destinado/transferido para lá. Um
`SlaughterService` pertence à Organization do frigorífico (ou de quem tiver
essa representação local), nunca à da fazenda de origem.

### 10. Invariantes estruturais

1. Todo `TransformationEvent` possui pelo menos uma entrada e uma saída.
2. Inputs e outputs são sempre listas, mesmo com um único elemento.
3. Todo output recebe identidade nova (`TraceableItem` novo).
4. Um `TraceableItem` possui no máximo um evento criador (zero é permitido —
   importação histórica ou origem externa sem produção detalhada conhecida;
   mais de um seria genealogia contraditória).
5. Um sujeito não pode ser input e output do mesmo evento.
6. Uma transformação não pode introduzir ciclo no grafo (`TraceableItem` é
   DAG, não árvore nem grafo genérico — a criação de relação que fechasse
   ciclo é recusada).
7. Participantes preservam quantidade, unidade e base de medição
   **declaradas pelo evento**, não derivadas de outra fonte.
8. Quantidade ausente permanece ausente — nunca vira zero por conveniência.
9. Balanço `INDETERMINATE` não é balanço aprovado, e nunca é tratado como
   `BALANCED` por omissão.
10. `AnimalExit` não cria implicitamente nenhum `TraceableItem`.
11. Uma Organization não cria `TransformationEvent` nem `TraceableItem`
    dentro de outra Organization — a orquestração conjunta exige mesma
    Organization; o caso inter-organizacional segue o protocolo da ADR-0042.
12. Evento publicado nunca é editado; correção é append-only (ver item 11
    desta seção de decisão, abaixo).
13. `UniversalRelation` é projeção navegável do evento — nunca fonte
    concorrente de quantidade/participante.
14. A timeline de um `TraceableItem` não copia o histórico das origens.
15. Fan-in (quando implementado) preserva o **conjunto** de origens, sem
    inventar correspondência 1:1 entre quantidade de saída e uma origem
    específica.

### 11. Correção é append-only, com forma ainda a detalhar antes da API existir

Nunca update destrutivo. Um evento publicado não é editado. A forma exata
(substituição total do evento, correção de um único participante,
fechamento de relações anteriores mais criação de novas, ou anulação
explícita de itens incorretos) **não é decidida nesta ADR** — fica para
antes de a API de correção ser construída, com o mesmo cuidado que a
correção de `TreatmentApplication` recebeu no Marco 9. O que já fica
fixado: qualquer forma escolhida referencia explicitamente o registro
corrigido e declara quais afirmações substitui — nunca reescreve em
silêncio.

## Decomposição proposta do Marco 11

- **11.1** — Esta ADR. Vocabulário, invariantes, fronteira de Organization.
- **11.2** — Fan-out real de abate (`SLAUGHTER`) **dentro de uma única
  Organization** (frigorífico com representação local do animal já
  estabelecida via ADR-0042, ou operação verticalizada): 1 animal →
  `TransformationEvent` → pelo menos 2 saídas rastreáveis. Não aceitar
  apenas uma saída no cenário principal.
- **11.3** — Timeline e recall de `TraceableItem`: provar travessia nas duas
  direções (item → transformação → animal; animal → transformação → todos
  os itens) sem copiar histórico.
- **11.4** — Balanço mínimo, incluindo o caso `INDETERMINATE`/`NOT_ASSESSED`.
- **11.5** — API e dossiê do `TraceableItem`: própria timeline, transformação
  que o criou, conjunto de origens, relações quantitativas, cobertura/lacunas,
  evidências.
- **11.6** — Fan-in: só depois de 11.2-11.5 provados.
- **11.7** (nova, desta rodada) — Correção de `TransformationEvent`: forma
  detalhada e API, depois de 11.2 estar em produção.

## O que esta ADR não decide

- Os `ProductType`/`ItemType` concretos além dos exemplos ilustrativos —
  aguardam processo real do primeiro frigorífico-alvo.
- O nome final do conceito-raiz (`TraceableItem` é provisório).
- Qualquer semântica de leitura/decisão de fan-in (Marco 11b) além de
  garantir que a estrutura já suporta.
- A forma exata de correção de um `TransformationEvent` publicado (item 11
  da decisão) — fica para antes da API de correção existir.
- A revisão semântica de `AnimalExit(ABATE)` (destinado vs. confirmado,
  item 8 da decisão) — registrada como dívida, não resolvida aqui.
- Se/quando `TraceableItem`/`TransformationEvent` sobem para o Core — fica
  para quando houver segunda vertical real.

## Não objetivos desta ADR

Fora de escopo mesmo como decisão futura próxima — não é "adiado", é
deliberadamente fora do que esta ADR endereça:

- **Embalagem logística** (caixas, pallets, contêineres) como unidade de
  agregação — ver item 4: se necessária, nasce como família própria
  (`LogisticUnit`), não como `ItemType` de `TraceableItem`.
- **AggregationEvent** e **AssociationEvent** do vocabulário EPCIS —
  conceitos de agregação física/lógica, distintos de transformação; não
  modelados aqui.
- **ObjectEvent** do vocabulário EPCIS — observação de um objeto sem
  transformação (ex.: leitura de sensor, checkpoint) não é o problema que
  esta ADR resolve.
- **EPCIS completo** — esta ADR alinha-se à *forma* do `TransformationEvent`
  do EPCIS (item 2), não implementa o padrão inteiro (EPCs físicos, eventos
  de agregação/associação, camada de compartilhamento entre organizações
  via CBV/EPCIS query interface).
- **Otimização de processo industrial** — rendimento, benchmarking entre
  plantas, previsão de perda — são leituras possíveis sobre os dados aqui
  modelados, não parte do modelo em si.
- **Gestão de estoque** — quantidade disponível, reserva, alocação — é
  outro domínio; `TraceableItem` registra proveniência e identidade, não
  posição de estoque.

## Referências

- NR-2 (`docs/CHECKLIST_DE_IMPLEMENTACAO.md`) — direção original de alinhar
  a GS1 EPCIS; problema em aberto sobre timeline de fan-in.
- NR-7 — disciplina de não generalizar (`Assertion`) sem segunda ocorrência
  real; mesma disciplina aplicada aqui a `TraceableItem`.
- ADR-0042 — contraparte externa, artefato de transferência e continuidade
  de proveniência; protocolo reutilizado para a fronteira de Organization
  do item 9, e para o padrão de lacuna declarada do item 8.
- Passo 7.1/7.2 — `UniversalRelation` e `reference_projection`, reutilizados
  como projeção navegável (item 5), sem mudança na forma existente.
- Passo 7.4 — `RecallService`, travessia de grafo reutilizada sem mudança.
