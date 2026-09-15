# MapBiomas — Discovery

**Data:** 15 de setembro de 2026
**Sessão:** Discovery (pré-planning)
**Escopo:** avaliar se a quarta camada territorial (MapBiomas), priorizada em
`docs/livestock/LIVESTOCK_CONTINUITY_ASSESSMENT.md` §8, está pronta para SPEC/PLAN/BUILD.

---

## Contexto

O Titan Livestock já lê quatro fontes territoriais reais via `Titan_geodata` (aplicação paralela do
responsável, `D:\projects\programming\Titan_geodata`): CAR/perímetro (SICAR), embargo do IBAMA, terras
indígenas da FUNAI e séries temporais PRODES/DETER. O padrão de consumo está maduro e replicado quatro
vezes: `CarLookupPort` (`packages/livestock_infrastructure/geodata/car_client.py`) declara um método
`fetch_<fonte>` por camada; `TerritorialOverlapService`/`TerritorialTimelineService`
(`packages/livestock_application/`) traduzem a resposta em `SEM_RESTRICAO`/`COM_RESTRICAO`/`INDETERMINADA`
com lacunas explícitas quando geometria ou referência externa estão ausentes; nenhuma tabela nova é criada
por camada — a leitura é sempre em tempo real contra o provedor, sem persistência própria no Titan (a
captura versionada existe só na forma sintético-realista de T-05D, para reconstrução histórica).

MapBiomas foi o item recomendado como "DISCOVERY leve (reaproveitamento de padrão já maduro)" no assessment
de 14/09/2026. Esta sessão investigou o que, de fato, seria reaproveitado.

## Achado central

**MapBiomas não existe como fonte de dados real em nenhum dos dois projetos.**

- No `Titan_geodata` (o provedor): `docs/plans/GEODATA_GENERAL_AUDIT.md:110` lista explicitamente
  `MapBiomas / NDVI Raster / Imagens de Satélite / Clima: PLANNED (Sem código/tabelas)`.
  `REQUISITOS.md:574` registra `- [ ] Integrar MapBiomas (novo data source, mesma arquitetura)` como item
  de backlog não iniciado. `README.md` e `VISION.md` citam MapBiomas na lista de fontes que o projeto
  pretende integrar, mas nenhum endpoint, adapter ou tabela existe hoje.
- No Titan (o consumidor): nenhuma menção a MapBiomas em `packages/`, `apps/` ou no checklist além da nota
  de rumo que já registrava "PRODES/DETER/MapBiomas" como as três camadas externas ainda fora (NR-6, NR-8;
  `docs/CORTE_MVP_BACKEND.md` item 2).

Isso é estruturalmente diferente de como FUNAI/PRODES/DETER foram entregues: naqueles três casos, o
`Titan_geodata` **já tinha** o endpoint funcionando (`/sicar/farm/summary`, `/prodes/timeline`,
`/deter/timeline`) antes do Titan Livestock construir o lado consumidor — o trabalho do lado Titan foi
puramente de consumo (Passo 17.2, validação de 10/09/2026). Para MapBiomas, **o trabalho de origem de dados
ainda nem começou**, e esse trabalho é código de outro repositório, sob outro `AGENTS.md`, outra governança
— não algo que esta sessão deva ou possa iniciar sem autorização e sem estar operando naquele projeto.

## O que reaproveitar quando a fonte existir (documentado para quando esta Discovery for retomada)

Se e quando `Titan_geodata` expuser um endpoint MapBiomas (uso e cobertura do solo anual, e/ou o sistema de
alertas de desmatamento do MapBiomas Alerta — são produtos distintos dentro do mesmo projeto MapBiomas;
qual dos dois faz sentido para o Titan é uma decisão de produto, não técnica), o lado Titan replica
exatamente o padrão FUNAI:

1. `CarLookupPort` ganha `fetch_mapbiomas_<produto>(cod_imovel, state) -> TerritorialOverlapAssessment` (ou
   `TerritorialTimelineAssessment`, se for série anual como PRODES/DETER, não sobreposição pontual como
   FUNAI).
2. `GeodataCarClient` implementa o método chamando o novo endpoint do provedor.
3. `TerritorialOverlapService`/`TerritorialTimelineService` ganham `assess_mapbiomas_overlap`/
   `mapbiomas_timeline`, mesma forma dos métodos irmãos já existentes.
4. `LivestockFactProvider` passa a emitir `livestock.territorial.mapbiomas` como fato governável, no mesmo
   padrão de `livestock.territorial.funai` — serviço opcional, ausência de serviço nunca vira fato negativo
   silencioso.
5. Nenhuma tabela nova, nenhuma migration, nenhum framework novo — confirma que a caracterização de
   "reaproveitamento de padrão maduro" está correta **para o lado Titan**, só não é o gargalo atual.
6. Amarração a um `MarketProfile` real continua sendo decisão normativa separada, como já é para
   FUNAI/PRODES/DETER/IBAMA hoje (nenhuma das quatro está amarrada a mercado por padrão).

## Opções

**A — Proceder mesmo assim, com stub/mock no lado Titan.**
Construir o consumidor contra um contrato hipotético do MapBiomas, sem provedor real. Rejeitado: cria
código morto e um contrato que pode não corresponder ao que `Titan_geodata` de fato expuser — exatamente o
tipo de acoplamento prematuro que `ARCHITECTURE.md` e `AGENTS.md` proíbem ("nunca criar abstração para
necessidade futura sem uso atual").

**B — Escalar como pedido ao `Titan_geodata`, no formato que aquele projeto já usa para pedidos na direção
oposta.**
`Titan_geodata` já tem o hábito formal de registrar pedidos de decisão para o Titan Core em
`integracao/PENDENCIAS_CONSUMIDOR_TITAN.md`, no formato CONTEXTO/EVIDÊNCIA/OPÇÕES/TRADE-OFFS/RECOMENDAÇÃO/
DECISÃO NECESSÁRIA. O caminho simétrico — um pedido do Titan para o `Titan_geodata` — não tem arquivo
próprio hoje. Esta Discovery poderia virar a base desse pedido, mas **escrever dentro do repositório
`Titan_geodata`** está fora do escopo desta sessão (projeto diferente, `AGENTS.md` diferente, sem
autorização para editar lá).

**C — Registrar como DEFER nesta Discovery, com gatilho explícito de retomada.**
Não avança para SPEC/PLAN/BUILD agora. Fica documentado o que falta e o que fazer quando faltar deixar de
faltar. Não impede que o responsável, atuando diretamente no projeto `Titan_geodata`, priorize a integração
lá por conta própria — essa decisão pertence àquele projeto.

## Trade-offs

| Opção | A favor | Contra |
|---|---|---|
| A — stub | Mostra "progresso" imediato no lado Titan | Código sem uso real; risco de contrato errado; violação direta de "nunca criar abstração para necessidade futura sem uso atual" |
| B — pedido formal ao Geodata | Usa um canal já existente e testado (a direção oposta já funciona) | Exige atuar/escrever em outro repositório, fora do escopo desta sessão sem autorização explícita |
| C — DEFER | Honesto sobre o que falta; não gera código morto; não expande escopo sem pedir | Não produz avanço de código nesta sessão |

## Recomendação

**DEFER.** O prerequisito (fonte MapBiomas real em `Titan_geodata`) não existe, e construir contra ele
agora seria abstração especulativa — exatamente o que `ARCHITECTURE.md`/`AGENTS.md` proíbem. Diferente de
GTA (que é falta de decisão + fonte que precisa ser desenhada do zero em qualquer lugar) ou de Market
Supply (que é decisão de produto sobre capacidade já construída), MapBiomas tem sua próxima ação concreta
**fora deste repositório**.

## Decisão necessária

Se você quiser seguir com MapBiomas agora, a decisão é: **priorizar a integração MapBiomas dentro do
projeto `Titan_geodata`** (que já a lista como backlog próprio) antes de qualquer trabalho aqui. Essa
decisão e esse trabalho pertencem àquele repositório e àquela sessão de trabalho — não a esta. Quando
`Titan_geodata` expuser o endpoint (e publicar o contrato, no mesmo padrão de
`CONTRATO_INTEGRACAO_TITAN_CORE.md`), esta Discovery pode ser retomada diretamente na etapa SPEC, porque o
desenho do lado consumidor já está resolvido acima.

Enquanto isso não acontecer, as demais prioridades do assessment (GTA, decisão de `NormativeBasis`
territorial/sanitária, decisão sobre Market Supply, SISBOV Corte 2) não dependem de nenhum outro
repositório e podem avançar independentemente.

## Achado colateral, fora do escopo desta Discovery

`Titan_geodata/integracao/PENDENCIAS_CONSUMIDOR_TITAN.md` (datado de 10/09/2026) ainda lista como abertos
os itens 1-4 (documentação de variáveis, distinção UF-não-carregada, `FUNAI` via `/sicar/farm/summary`,
validação manual), mas `docs/CHECKLIST_DE_IMPLEMENTACAO.md` (entrada "10/09/2026 — Ponto de retomada
externo: correcoes geodata") já registra os quatro como fechados no mesmo dia, do lado Titan. Os dois
repositórios parecem ter desincronizado sobre o status desses itens — não é algo que compete a esta
Discovery resolver (é atualização de status em outro projeto), mas vale mencionar caso gere confusão numa
sessão futura em qualquer um dos dois repositórios.
