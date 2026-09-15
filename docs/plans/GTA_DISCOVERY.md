# Ingestão de GTA (Guia de Trânsito Animal) — Discovery

**Data:** 15 de setembro de 2026
**Sessão:** Discovery (pré-planning)
**Escopo:** avaliar a ingestão de GTA como fonte de proveniência para fornecedor indireto, priorizada em
`docs/livestock/LIVESTOCK_CONTINUITY_ASSESSMENT.md` §8 e nas notas de rumo NR-6/NR-8 como o maior gap de
valor comercial não capturado.

---

## Contexto

A cadeia real cria→recria→engorda depende da GTA — documento oficial e obrigatório emitido pelos órgãos
estaduais de defesa agropecuária que autoriza o trânsito de animais vivos. `ADR-0042` (26/07/2026) já
resolveu a parte estrutural do problema — como representar uma contraparte externa (fazenda de origem,
frigorífico) sem furar o isolamento por Organization, e como preservar proveniência com lacuna explícita
quando um animal chega por transferência — mas **nenhum dado real de GTA nunca foi declarado ou consumido**
através dela. O gap está registrado há dois meses: `docs/CORTE_MVP_BACKEND.md` item 4 ("fazenda de origem →
recria → engorda é hoje um cadastro local por Organization... a cadeia completa (GTA estadual, heterogênea)
não está integrada"), NR-6 ("sem ingestão, é a melhor estrutura de proveniência do mercado com nada
dentro"), NR-8 ("GTA — obrigatória e dolorosa... é o melhor wedge identificado").

## O que já existe e é 100% reaproveitável

- `ExternalCounterparty` (`packages/livestock_domain/external_counterparty.py`) — representação local que
  uma Organization mantém sobre um terceiro (fazenda, frigorífico, trader), com identificadores e evidências
  próprias, sem furar isolamento.
- `ReceivedTransferArtifact` + `HistoryCoverage` (`packages/livestock_domain/transfer_artifact.py`) —
  artefato recebido de uma contraparte, com digest, instante de emissão, instante efetivo da transferência e
  **lacuna de cobertura sempre explícita** (`COVERAGE_BEFORE_TRANSFER`, `HISTORY_BEFORE_ACQUISITION_UNKNOWN`)
  — nunca inventa histórico anterior à aquisição.
- `ImportedLivestockFact` (`packages/livestock_domain/imported_fact.py`) — fato importado com autoria,
  confiança (`ConfidenceTier`) e um `payload: MappingProxyType[str, Any]` **livre por `fact_type: str`** —
  não é um enum fechado. Isto é exatamente a forma que uma GTA precisa: um novo `fact_type` (ex.:
  `"livestock.gta_declared"`) com o payload específico da guia, sem exigir nenhuma classe de domínio nova.
- `ReceivedTransferArtifactService` (`packages/livestock_application/transfer_artifact_service.py`) e o
  endpoint HTTP correspondente já registram artefato + evento, validando animal e contraparte na mesma
  Organization.
- Roteiro executável já existente: `apps/validacao/artefato_transferencia.py`, `apps/validacao/
  contraparte_externa.py`, `apps/validacao/fato_importado.py`.

**Conclusão parcial:** a fundação estrutural (ADR-0042) está pronta havia dois meses; o que falta não é
mecanismo, é **conteúdo específico de GTA** — um `fact_type`/payload novo, e a decisão de como o dado chega
até o Titan.

## Pesquisa: como a GTA é emitida e se há caminho de integração real

Levantamento externo (nesta sessão, via busca web — não confirmado por fonte primária jurídica, mesmo
tratamento que `MARKET_NORMATIVE_BASIS_INTAKE_GUIDE.md` recomenda para qualquer claim de pesquisa):

- A GTA é emitida por sistemas **estaduais** de defesa agropecuária, cada um com seu próprio sistema
  (exemplos: SIDAGO em MG, GEDAVE em SP, SIAGRO no DF, IAGRO em MS) — confirma a heterogeneidade que NR-6 já
  registrava. **Não há uma API nacional única** que devolva o conteúdo completo de uma GTA de qualquer
  estado.
- **Achado novo, não registrado em nenhum documento do Titan até agora:** a Nota Técnica 2024.003 do ENCAT
  (Encontro Nacional de Coordenadores e Administradores Tributários Estaduais) está integrando a GTA à
  Nota Fiscal Eletrônica (NF-e) e ao sistema e-GTA do MAPA. A partir de sua entrada em vigor — adiada mais
  de uma vez, hoje prevista para **março de 2026** (era novembro de 2025, depois janeiro de 2026) —, número
  da GTA, data de emissão e órgão emissor passam a ser **campos obrigatórios no XML da NF-e** para operações
  com animais.
- **Limite importante desse achado:** a NF-e passa a carregar apenas a **referência** da GTA (número, data,
  órgão emissor) — não o conteúdo completo (propriedade de origem, propriedade de destino, identificação
  dos animais, finalidade do trânsito, condições sanitárias declaradas). Resolver a referência em conteúdo
  completo ainda exigiria consultar o sistema do estado emissor, ou receber o documento em si.
- A NF-e já é um formato nacional único e padronizado (schema XML mantido por CONFAZ/SEFAZ), diferente da
  GTA. Isso a torna um ponto de integração mais tratável que 27 sistemas estaduais heterogêneos — mas só a
  partir de março de 2026, e só como ponteiro.

## Opções

**A — Declaração manual/documental de GTA agora, reaproveitando ADR-0042 integralmente.**
Operador declara os dados da GTA que já tem em mãos (número, UF/órgão emissor, data de emissão,
identificação da propriedade de origem e de destino conforme constam na guia, finalidade do trânsito,
animais cobertos) como um novo `fact_type` de `ImportedLivestockFact`, referenciando um
`ReceivedTransferArtifact` (o "artefato" é a própria guia — PDF ou XML anexado como `Evidence`, com
`bundle_digest` sobre o documento recebido). Nenhuma classe de domínio nova, nenhuma migration além de
schema de payload, nenhuma integração externa. Funciona hoje, para qualquer estado, sem esperar NT 2024.003.

**B — Aguardar NT 2024.003 (março de 2026) e construir captura semi-automática a partir do XML da NF-e.**
Só entrega a referência (número/data/órgão) — não substitui a Opção A para conteúdo completo; seria um
enriquecimento posterior, correlacionando NF-e recebida com uma declaração de GTA já existente ou
levantando a necessidade de buscá-la.

**C — Integração direta com o sistema e-GTA de um estado específico (ex.: MS, mesmo estado piloto do
SICAR/CAR).**
Maior esforço: replica, para GTA, o mesmo caminho que o `Titan_geodata` percorreu para CAR — pesquisa do
sistema estadual, autenticação, contrato, adapter dedicado. Heterogêneo por estado; escolher um estado
piloto não resolve os demais. Muito provavelmente pertenceria ao `Titan_geodata` (o projeto que já
concentra integração com fontes externas geoespaciais/fundiárias), não ao Titan Core diretamente — mesmo
padrão de fronteira que a Discovery de MapBiomas já identificou.

## Trade-offs

| Opção | A favor | Contra |
|---|---|---|
| A — declaração manual | Funciona hoje, qualquer estado; reaproveita ADR-0042 sem nenhuma peça nova de domínio; fecha o gap de proveniência que NR-6/NR-8 apontam como prioritário; baixo risco | Depende do operador ter e digitar a guia; não é ingestão automática |
| B — NF-e (NT 2024.003) | Fonte nacional única, formato já padronizado | Só disponível a partir de março/2026 (já adiada duas vezes); só entrega referência, não conteúdo; não substitui A |
| C — API estadual direta | Ingestão automática de conteúdo completo | Maior esforço; heterogêneo; provavelmente pertence ao `Titan_geodata`, não a este repositório; escolher 1 estado não resolve os outros 26 |

## Recomendação

**PROCEED com a Opção A**, como incremento único e contido: um novo `fact_type` declarativo de GTA sobre a
máquina já existente de `ExternalCounterparty`/`ReceivedTransferArtifact`/`ImportedLivestockFact`. Não
requer decisão de arquitetura nova — é o mesmo padrão que `POST-LIV-03` (captura SISBOV simulada) e a
qualificação de estabelecimento (ADR-0045) já usam. As Opções B e C ficam registradas como **DEFER**: B por
dependência de data externa fora do controle do projeto (e por só entregar referência, não conteúdo), C por
provavelmente pertencer a outro repositório e exigir escolha de estado piloto — a mesma fronteira que a
Discovery de MapBiomas já identificou para integrações geoespaciais diretas.

## O que a Opção A concretamente precisaria decidir antes de SPEC

Estas são perguntas de domínio, não de engenharia — o tipo de decisão que `AGENTS.md` pede para não
inventar:

1. **Payload mínimo da GTA declarada.** Número da guia, UF/órgão emissor, data de emissão, propriedade de
   origem (como referenciar uma propriedade que não é do Titan — mesmo problema já resolvido por
   `ExternalCounterparty`, mas aqui é *propriedade* de terceiro, não a *contraparte* em si), propriedade de
   destino (pode ser a própria propriedade da Organization), finalidade do trânsito (venda, engorda, abate),
   quantidade/identificação dos animais cobertos, condições sanitárias declaradas na guia.
2. **Granularidade: por animal ou por lote.** Uma GTA real cobre um lote de animais movendo-se junto; o
   `ReceivedTransferArtifact` de hoje é por animal. Decisão: registrar um artefato por animal do lote
   (reaproveita 100% sem mudança), ou introduzir uma noção de lote de GTA — a primeira opção é
   estruturalmente mais barata e não exige nova classe de domínio.
3. **A guia em si é Evidence.** O PDF/XML da GTA deveria ser anexado como `Evidence` do Core (já suportado),
   com o `bundle_digest` do `ReceivedTransferArtifact` calculado sobre o documento — decisão de reuso, não
   de desenho novo.
4. **Quem declara.** Segue o mesmo modelo já usado para artefato recebido/fato importado — o operador da
   Organization que recebeu o animal. Sem integração externa nesta etapa, não há pergunta de autoridade
   adicional.

## Decisão necessária

Autorizar a Opção A para avançar a SPEC (payload/schema do `fact_type` de GTA, decisão de granularidade,
critério de aceite, roteiro de validação). Se aprovado, o próximo passo desta sessão é a SPEC, não o BUILD
direto — consistente com `DEVELOPMENT.md`.
