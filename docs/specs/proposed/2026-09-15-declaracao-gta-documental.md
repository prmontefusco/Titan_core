# Declaração documental de GTA (Guia de Trânsito Animal)

- **Nível:** STANDARD
- **Estado:** proposta
- **Decisão de Discovery:** PROCEED (Opção A — `docs/plans/GTA_DISCOVERY.md`, 15/09/2026)
- **Owner de produto:** Founder / Product Owner
- **Data:** 2026-09-15

## Problema e usuário

O operador de uma Organization que recebe um animal de terceiro (compra, transferência, recria) tem em
mãos a GTA — documento oficial e obrigatório que autorizou o trânsito — mas hoje não há forma **validada e
estruturada** de declará-la no Titan. O mecanismo genérico de fato importado (`POST /v1/livestock/
animals/{animal_id}/documentary-acquisitions`, ADR-0042) já aceita qualquer `fact_type`/payload livre, mas
sem nenhuma validação de conteúdo — um operador pode hoje registrar algo rotulado "GTA" com um payload
vazio ou sem sentido, e o sistema aceitaria. Isso é exatamente o gap que `docs/CORTE_MVP_BACKEND.md` item 4
e as notas de rumo NR-6/NR-8 apontam como o maior valor comercial não capturado: sem essa declaração
estruturada, a cadeia cria→recria→engorda permanece "a melhor estrutura de proveniência do mercado com nada
dentro" (NR-6).

## Contexto e objetivo

`ADR-0042` já resolveu a parte estrutural — `ExternalCounterparty`, `ReceivedTransferArtifact` (com
`HistoryCoverage` e lacunas explícitas) e `ImportedLivestockFact` (fato livre por `fact_type`, com
`ConfidenceTier`). Esta SPEC não cria nenhum conceito de domínio novo: acrescenta um **contrato de entrada
validado** para o caso específico de GTA, sobre a mesma máquina já existente e já em produção
(`ReceivedTransferArtifactService`, `ImportedLivestockFactService`, endpoint
`documentary-acquisitions`).

**Resultado observável desejado:** um operador consegue declarar os dados de uma GTA em mãos, com
validação de campos obrigatórios, e esse dado passa a aparecer na timeline e na consulta de fatos
importados do animal, com evidência (o documento anexado) e proveniência preservada — pronto para, em
incremento futuro e com decisão própria, alimentar `fact_provider.py`/elegibilidade de mercado.

## Fora de escopo

Esta SPEC **não**:

- integra com nenhum sistema estadual de e-GTA (Opção C do Discovery, DEFER);
- integra com NF-e/NT 2024.003 (Opção B do Discovery, DEFER — só disponível a partir de março/2026 e só
  entrega referência, não conteúdo);
- cria conceito de "lote de GTA" — um artefato por animal, reaproveitando a granularidade já existente de
  `ReceivedTransferArtifact`; uma GTA que cobre N animais é declarada N vezes, uma por animal, com o mesmo
  `bundle_digest` (calculado sobre o mesmo documento);
- cria referência tipada para "propriedade externa de origem" — o dado de origem/destino declarado na GTA
  entra como texto estruturado dentro do payload do fato, não como chave estrangeira para `RuralProperty`
  (a propriedade de origem pertence a um terceiro, frequentemente não cadastrado no Titan; inventar esse
  vínculo agora seria abstração sem segundo caso de uso real);
- reconcilia o destino declarado na GTA com o movimento/estadia já registrados pelo Titan
  (`AnimalMovement`/`PropertyStay`) — são duas fontes distintas (a alegação do documento e o fato
  operacional já registrado) e permanecem duas, sem fusão automática nesta etapa;
- altera `fact_provider.py`, `market_eligibility.py` ou qualquer `Policy`/`Rule` — o fato fica disponível
  para consulta e proveniência, mas não é consumido por elegibilidade nesta SPEC;
- cria migration — `imported_livestock_facts.payload` já é `JSONB` livre.

## Comportamento e regras de negócio

1. Pré-condição: a `ExternalCounterparty` (fazenda/frigorífico de origem) e o `Animal` já existem na
   Organization, e o operador tem o documento da GTA (PDF/imagem/XML) disponível para anexar como
   `Evidence` do Core (mecanismo já existente, sem mudança).
2. O operador chama o endpoint existente `POST /v1/livestock/animals/{animal_id}/documentary-acquisitions`
   com um novo tipo de item de fato importado, **`livestock.gta_declared`**, cujo `payload` passa a ser
   validado contra um schema específico (ver Plano técnico) em vez do `dict[str, Any]` sem restrição atual.
3. Campos obrigatórios do payload de GTA (com justificativa de escopo mínimo, não exaustivo de tudo que uma
   GTA real contém — ver "Riscos, alternativas e perguntas abertas" sobre confiança na pesquisa que
   sustenta esta lista):
   - `gta_number` (string, não vazio) — número da guia;
   - `issuing_state` (string, UF de 2 letras) — estado emissor;
   - `issuing_agency` (string, não vazio) — órgão emissor (ex.: "IAGRO", "Agrodefesa");
   - `issued_at` (data, presente no documento) — data de emissão da guia;
   - `origin_description` (string, não vazio) — identificação da propriedade de origem **como consta na
     guia** (nome, código CAR se houver, município) — texto estruturado, não referência tipada;
   - `destination_description` (string, não vazio) — identificação da propriedade de destino como consta
     na guia;
   - `purpose` (string, não vazio) — finalidade declarada do trânsito (ex.: "venda", "recria", "abate");
   - `animal_count` (inteiro positivo) — quantidade de animais cobertos pela guia (não necessariamente 1;
     é a contagem total da guia, mesmo quando cada animal individual gera sua própria declaração).
4. Campos opcionais: `sanitary_conditions` (texto livre — condições sanitárias declaradas), `veterinarian_
   name` (texto livre).
5. Validação recusa payload sem os campos obrigatórios, com `422` e mensagem apontando o campo ausente —
   mesmo padrão de erro já usado no restante da API (`problem+json`).
6. O fato criado preserva `origin=IMPORTED_ASSERTION`, `confidence_tier` informado pelo operador (o
   documento em si não eleva confiança automaticamente — mesma regra que `ConfidenceLevel` já segue em
   todo o Core), e referencia o `ReceivedTransferArtifact` cujo `bundle_digest` foi calculado sobre o
   documento da GTA anexado como `Evidence`.
7. Nenhuma regra nova de bloqueio/elegibilidade é criada — o fato fica disponível para leitura e
   proveniência, ponto final desta SPEC.

## Critérios de aceite

- `POST .../documentary-acquisitions` com um item `fact_type="livestock.gta_declared"` e payload completo
  retorna `201` com o fato criado, visível em `GET /v1/livestock/animals/{animal_id}/imported-facts` e na
  timeline do animal.
- O mesmo request com qualquer campo obrigatório do payload de GTA ausente retorna `422`, nomeando o campo,
  e **não** persiste nada (nem o artefato, nem o fato) — transação atômica, mesma garantia que
  `documentary-acquisitions` já oferece para os demais tipos de fato.
- Dois animais diferentes, cobertos pela mesma GTA, podem ser declarados com o mesmo `gta_number`/
  `bundle_digest` sem conflito — a unicidade continua sendo por animal, não por GTA.
- Auditor com `LIVESTOCK_TIMELINE.LER` consegue ler o fato declarado; operador sem permissão de escrita
  correspondente recebe `403`.
- Isolamento por Organization: animal de outra Organization retorna `404` uniforme, mesmo padrão do resto
  da API.
- `fact_type` fora do conjunto validado (`"livestock.gta_declared"`) continua aceitando payload livre, como
  hoje — esta SPEC não restringe os demais tipos de fato importado já em uso (embargo, qualificação de
  estabelecimento etc.).

## Plano técnico

- **Capacidades e arquivos afetados:**
  - `apps/api/livestock_writes.py`: novo modelo de validação para o item de payload quando
    `fact_type == "livestock.gta_declared"` dentro de `RegistrarFatoImportadoDocumentalRequest` (validação
    condicional no mesmo request existente, ou um `discriminated union` do payload por `fact_type` — decisão
    de PLAN, não desta SPEC). Nenhuma rota nova.
  - `packages/livestock_domain/events.py` (ou onde já vivem convenções de `fact_type`): registrar a
    constante `"livestock.gta_declared"` como valor conhecido/documentado, sem transformar
    `ImportedLivestockFact.fact_type` em enum fechado (permanece `str`, para não quebrar os demais usos).
  - Nenhuma mudança em `packages/livestock_domain/`, `packages/livestock_application/imported_fact_service.py`,
    `transfer_artifact_service.py`, `acquisition_continuity_service.py` — reaproveitados sem alteração.
- **Contratos, persistência, concorrência, idempotência e erros:** nenhuma mudança de contrato de
  persistência (`JSONB` já livre); erro `422` no padrão `problem+json` já usado; nenhuma migration.
- **Impacto em arquitetura, segurança e tenancy:** nenhum — reaproveita RLS, permissões e isolamento já
  existentes do fluxo `documentary-acquisitions`.
- **Impacto de dados, migration e rollback:** nenhuma migration; rollback é remover a validação (campo
  sempre foi `dict[str, Any]` livre, então reverter não perde dado já gravado).
- **Integrações, compatibilidade e performance:** nenhuma integração externa nesta etapa.

## Verificação e observabilidade

- Testes automatizados: payload de GTA completo aceito; cada campo obrigatório ausente recusado
  individualmente com `422`; dois animais com o mesmo `gta_number` sem conflito; isolamento por
  Organization; auditor lê, operador sem permissão não escreve; `fact_type` diferente de
  `"livestock.gta_declared"` continua sem validação de payload (regressão negativa).
- Roteiro manual/executável novo em `apps/validacao/` (ex.: `declaracao_gta.py`), seguindo o padrão do
  projeto: descobre Organization/animal/contraparte sozinho, mostra requisição/resposta, explica o porquê
  de cada passo, sonda ambiente antes do primeiro passo, suporta `--pausar`.
- Sem métricas/alertas novos — reaproveita observabilidade já existente do fluxo de fato importado.

## Documentação afetada

- `docs/CHECKLIST_DE_IMPLEMENTACAO.md` — nova entrada no mesmo commit do BUILD, quando entregue.
- `docs/plans/GTA_DISCOVERY.md` — permanece como registro da Discovery; não editado por esta SPEC.
- Nenhuma mudança em `DOMAIN.md`/`ARCHITECTURE.md` — não introduz conceito de domínio novo, só um
  `fact_type` validado dentro do conceito `ImportedLivestockFact` já existente.

## Riscos, alternativas e perguntas abertas

**Risco — confiabilidade da lista de campos obrigatórios.** A lista de campos (item 3, acima) vem da
pesquisa não-jurídica feita durante o Discovery (mesmo tratamento de `MARKET_NORMATIVE_BASIS_INTAKE_GUIDE.md`:
claim de pesquisa, não fonte primária confirmada). Diferente da `NormativeBasis` de mercado, este risco é
menor aqui porque os campos pedidos (número, UF, órgão, data, origem, destino, finalidade, quantidade) são
identificação estrutural do documento, não conteúdo regulatório que possa estar errado sobre o que é
exigido — mas vale registrar que não foi confirmado contra um exemplar real de GTA.

**Alternativa considerada e rejeitada — payload sem validação, só documentação.** Deixar o `fact_type`
`"livestock.gta_declared"` sem nenhuma validação de schema, confiando na disciplina do operador. Rejeitada:
o próprio problema desta SPEC é que hoje **já é possível** declarar "GTA" sem sentido nenhum — não validar
não resolveria o problema, só formalizaria o nome sem a garantia.

**Alternativa considerada e rejeitada — nova classe de domínio `GtaDeclaration`.** Rejeitada por
`ARCHITECTURE.md`/`AGENTS.md` ("nunca criar abstração para necessidade futura sem uso atual"): o payload
livre de `ImportedLivestockFact` já cobre a necessidade; criar uma classe nova duplicaria o mecanismo de
`ReceivedTransferArtifact`/`ImportedLivestockFact` sem ganho real nesta etapa.

**Pergunta aberta — para o PLAN, não travar aqui:** o formato exato da validação condicional (payload
tipado por `fact_type` dentro do endpoint existente vs. um segundo endpoint dedicado só para GTA) é decisão
técnica de PLAN. Ambas preservam os critérios de aceite desta SPEC; a diferença é só onde a validação vive.

**Decisão humana necessária antes de PLAN/BUILD:** aprovar esta SPEC (mover de `docs/specs/proposed/` para
`docs/specs/approved/`) e confirmar a lista de campos obrigatórios do item 3, já que ela não foi validada
contra um exemplar real de GTA.
