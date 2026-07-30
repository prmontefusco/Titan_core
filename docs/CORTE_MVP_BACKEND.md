# Corte do MVP — Backend Titan Livestock

**Data:** 27 de julho de 2026 (atualizado em 30 de julho de 2026 — embargo ambiental do IBAMA)
**Escopo congelado em 30/07/2026**, por decisão do responsável, após validação manual da trilha comercial (`docs/CHECKLIST_DE_IMPLEMENTACAO.md`, entrada de 30/07/2026). A partir daqui, mudança de código nas áreas listadas como "dentro" só entra por correção de bug real, quebra de fluxo ou texto que impeça uso — não por generalização ou expansão de escopo.
**Fonte:** `docs/CHECKLIST_DE_IMPLEMENTACAO.md` (estado real do backend, verificado contra PostgreSQL, Keycloak e API rodando)
**Propósito:** dizer explicitamente o que está dentro, o que está fora, e por quê — para que nada pareça esquecido e para que o início do frontend (item 8 da fila) comece sobre contratos que não vão mudar por baixo.

Este documento não substitui o checklist. Ele é o corte: uma leitura de cima para baixo do que existe, não o histórico passo a passo de como chegou lá.

---

## O que está dentro do MVP

### Core (Marcos 0–7) — fundação, não vertical

- Identidade, autorização por permissão, RLS forçado por Organization, OIDC.
- Auditoria append-only (`DomainEvent`), Outbox/Inbox transacional, idempotência, workers.
- `Evidence`, criptografia, assinaturas, `Provenance`.
- `Policy`/`Rule`/`Evaluation`/`Decision` — motor de regra versionada e explicável.
- Relações universais e temporais, `Recall`, `Dossier`, `VerificationBundle` (verificável por terceiro sem acesso ao Titan), sincronização offline.
- Prova de ponta a ponta do Core com vocabulário genérico (não pecuário), para provar que o motor não vaza acoplamento com nenhuma vertical.

**Por que isso é MVP e não excesso:** é a tese do produto. O diferencial declarado (ADR e VISION) não é rastreabilidade — isso é *commodity*, resolvido por EPCIS e concorrentes prediais. É provar **por que** uma decisão foi tomada e permitir refazê-la anos depois. Cortar qualquer peça daqui descaracteriza o produto.

### Titan Livestock — ciclo de vida do animal

- Cadastro, identificadores, saída do rebanho (óbito/abate/venda) como fato terminal que não apaga o passado.
- Genealogia: maternidade genética vs. gestacional (transferência de embrião), paternidade com múltiplos touros vs. paternidade documentada exclusiva.
- Reprodução: parto e perda gestacional como fatos de natureza distinta.
- Propriedade rural, lote pecuário, movimentação entre propriedades, veterinário.

### Farmacovigilância e carência (Marco 9)

- Medicamento, lote de medicamento, prescrição veterinária, aplicação de tratamento (com correção append-only, nunca sobrescrita).
- Cálculo de carência com contribuições auditáveis (qual aplicação, qual lote, qual prazo).
- Elegibilidade farmacológica: `Evaluation` + `Decision` persistidas, bloqueio e reavaliação.

### Campanhas sanitárias (Marco 14 / NR-4 sanitário)

- Campanha sanitária oficial, exigibilidade mínima por campanha.
- **Mecanismo** de regra governada por mercado para exigência sanitária (`sanitary_requirement_fact_type` + `SANITARY_RULE_CODE`) — ver seção "Fora do MVP" para o que isso não inclui ainda.

### Governança de regras (ADR-0043)

- `RuleIdentity`, `RuleVersion`, `RuleAdoption`, linha do tempo imutável de regra.
- Substituição auditável de adoção (trocar a regra vigente sem apagar a anterior).
- `RuleCondition` declarativa — regra composta por comparações sobre fatos, sem precisar de código novo por norma.

### Elegibilidade por mercado (ADR-0041/0044)

- Matriz China/EUA/UE com avaliação **independente por finalidade** — cada mercado tem sua própria `Evaluation`/`Decision`, regra, vigência e sujeito.
- Sujeito secundário (frigorífico) exercitado de ponta a ponta para a China: dependência declarada quando não escolhido, promoção a `ELEGIVEL` só com habilitação explícita do estabelecimento.
- Falha fechada quando o mercado não declara a própria carência (nunca reaproveita carência de outro mercado por omissão).
- `REAVALIACAO_NECESSARIA` quando a política usada diverge da política vigente — reprodutibilidade histórica sem reescrever decisão passada.
- Cada célula da matriz expõe regra/versão/adoção/motivos/lacunas/requisitos, o suficiente para uma UI explicar a resposta sem reconsultar o banco.

### Embargo ambiental do IBAMA (parcial, ADR-0041)

- `EnvironmentalEmbargoService.assess_ibama_embargoes` consulta a geometria vigente da propriedade e cruza contra o provider `Titan_geodata` de verdade (`fetch_ibama_overlaps`), não um cadastro manual.
- `EnvironmentalEmbargoAssertionService.record_ibama_assertion` congela essa avaliação como `PropertyEnvironmentalEmbargoAssertion` auditável (append-only, geometria e versão citadas), exposta em `POST /v1/livestock/properties/{property_id}/environmental-embargoes/ibama/assertions`.
- A matriz de mercado já consome essa assertion via `rule-embargo-ambiental-ibama` (fato `livestock.environmental_embargo.ibama`) quando a regra é adotada para o mercado — validado manualmente em 30/07/2026 (roteiro `matriz_elegibilidade_mercados`) e coberto por teste de integração sob RLS restrito.
- **O que ainda não existe:** nenhum roteiro de validação manual exercita este endpoint específico contra o provider `Titan_geodata` real via HTTP (os testes de integração escrevem a assertion direto no repositório); e as demais camadas territoriais do item 2 abaixo (FUNAI, PRODES/DETER, MapBiomas) continuam de fora. Portanto o item 2 ("Avaliação territorial") sai de "inteiramente fora" para "uma camada dentro, as outras três fora".

### Proveniência externa (ADR-0042)

- Contraparte externa local (fazenda/frigorífico de outra Organization, sem furar isolamento).
- Artefato de transferência recebido, com lacuna de cobertura declarada (nunca inventada).
- Fato importado com autoria, origem, confiança e artefato-fonte — usado de verdade na elegibilidade farmacológica.
- Qualificação de estabelecimento por mercado como dado append-only auditável.

### API HTTP

- 72 operações, 58 rotas, todas sob RLS e permissão granular (nunca por papel).
- Contrato de erro consistente: `401`/`403`/`404`/`409`/`422` presentes de forma uniforme, `problem+json`, mensagens sanitizadas (sem stack trace, sem caminho de arquivo).
- Paginação com teto rígido (`limit`/`offset`, sem contagem total) nos endpoints com risco real de crescimento sem limite — corrigido em 27/07/2026 após auditoria sistemática do OpenAPI.
- Append-only de verdade: nenhuma rota de domínio aceita `PUT`, `PATCH` ou `DELETE`; corrigir é gravar um evento novo que aponta para o anterior.
- Swagger com aviso obrigatório onde a ADR exige (ex.: material sensível na verificação externa).

### Roteiros de validação manual aprovados (rodam contra Docker + Keycloak + PostgreSQL reais)

`governanca_regras` (6/6) · `matriz_elegibilidade_mercados` (4/4) · `exigibilidade_sanitaria_minima` · `prescricao_veterinaria` · `fato_importado` · `simulacao_comercial` (11/11, ponta a ponta: fazenda → animal → prova recebida → matriz → frigorífico → abate).

---

## O que está fora do MVP — e por quê

### 1. Amarração de mercado a campanha sanitária específica
**Existe:** o mecanismo (fact_type por campanha + regra governada).
**Não existe:** nenhum `MarketProfile` diz "a UE exige campanha de febre aftosa". Isso é decisão normativa real — qual mercado exige qual vacina — e inventá-la sem fonte seria pior que não ter a funcionalidade. Fica para quando houver decisão normativa que a sustente.

### 2. Avaliação territorial (Marco 17.4/17.5)
**Existe:** georreferenciamento da propriedade, importação do CAR pelo `Titan_geodata` (perímetro, reserva legal, APP, hidrografia), e agora também o cruzamento com a camada de embargo do IBAMA (ver "Embargo ambiental do IBAMA" acima) — mecanismo, endpoint e consumo pela matriz de mercado já existem e estão testados, mas sem validação manual do caminho HTTP completo contra o provider real.
**Não existe:** terra indígena da FUNAI, alerta do PRODES/DETER, uso do solo do MapBiomas. A ADR-0026 já modela o problema para essas três; falta a camada externa e o `SpatialAssessment` genérico. Ainda é o maior valor comercial não capturado por completo (NR-6), mas o primeiro corte (IBAMA) deixou de ser "não construído".

### 3. Importação de qualificação de estabelecimento por fonte externa versionada
**Existe:** ADR-0045 aceita (asserção bitemporal, `SourceArtifact`, `EstablishmentQualificationAssertion`, `SourceCoverage`, confiança computada pelo Titan) e implementada.
**Não existe:** integração com uma fonte real (MAPA, frigorífico, importador) que publique essa lista automaticamente. O cadastro manual via API continua existindo, mas agora alimenta a mesma trilha auditável (`QualificationSourceArtifact` + `EstablishmentQualificationAssertion`) consumida pela elegibilidade; ele deixou de ser uma fonte paralela preferencial de decisão.

### 4. Contraparte externa como fornecedor indireto de ponta a ponta
Fazenda de origem → recria → engorda é hoje um cadastro local por Organization. A cadeia cria→recria→engorda completa (GTA estadual, heterogênea) não está integrada — é a lacuna que a ADR-0042 deixou explícita desde o início.

### 5. Rastreabilidade de produto (abate, cortes, produtos mistos)
Nada do Marco 11 em diante (abate, EPCIS/GS1, `TransformationEvent`, fan-out/fan-in de produto) está implementado. A `RelationService`/`RecallService` já suportam travessia de grafo, e a recomendação registrada (NR-2) é mapear para o vocabulário EPCIS quando chegar, não desenhar um grafo próprio — mas isso é trabalho não iniciado.

### 6. Autoria de regra por administrador não-programador (NR-5)
`RuleCondition` já é declarativa (fact_type/payload_key/operator/expected_value), o que resolve a maior parte do problema sem precisar de sandbox. Mas não existe interface para um administrador compor essas condições sem tocar em código — hoje só a API de governança faz isso, e é consumida programaticamente. O caminho caro (ADR-0036, Wasm determinístico) está aceito e não implementado; a suspeita registrada é que a maior parte da regulação real caiba nas primitivas declarativas, sem precisar dele.

### 7. Âncora temporal por documento de terceiro (NR-1)
O intervalo provável de um evento offline já é ancorado no servidor (`DeviceClockReading`), mas nota fiscal de medicamento/serviço veterinário como corroboração independente não está implementada. `EvaluationOutcome.VALIDACAO_EXTERNA_PENDENTE` existe no Core e não tem nenhum produtor ainda.

### 8. Frontend
Zero linhas. Deliberadamente adiado até este documento existir — não faz sentido construir UI sobre contrato que ainda pode mudar.

---

## Riscos conhecidos, não escondidos

| Risco | Descrição | Mitigação atual |
|---|---|---|
| **Relógio de dispositivo como prova temporal** | Quem controla o aparelho controla a alegação de `occurred_at`; antedatar aplicação encurta carência efetiva | ADR-0021 veda tratar relógio local como prova; intervalo é sempre ancorado no servidor. Documento de terceiro (NR-1) mitigaria mais, não implementado |
| **Fornecedor indireto sem integração de GTA** | Contaminação de fazenda embargada pode viajar pela cadeia sem o Titan enxergar | Contraparte externa local captura o que é declarado; não há verificação automática contra GTA estadual |
| **Autoria de regra concentrada em desenvolvedor** | Mudança normativa ainda depende de alguém escrever `RuleCondition` via API, não de um administrador de negócio | `RuleCondition` declarativa já reduz o problema a composição, não a código; falta só a interface |
| **Modelo de receita indefinido (NR-8)** | Quem paga (frigorífico, produtor, banco/seguradora) ainda não está fechado comercialmente | Hipótese de porta de entrada via GTA/PNIB registrada; não bloqueia o backend, mas deveria informar o que priorizar a seguir |
| **`Assertion` como padrão emergente não generalizado (NR-7)** | O mesmo formato (sujeito/fato/afirmante/evidência/confiança) já apareceu 4+ vezes em domínios distintos; resistir a generalizar cedo é deliberado, mas o custo de não generalizar cresce a cada nova ocorrência | Registrado para revisão na próxima vez que aparecer em domínio novo |
| **Cobertura E2E de `REAVALIACAO_NECESSARIA`** | O mecanismo existe e tem teste unitário; falta um teste de integração exercitando via API real | Pequeno, não bloqueia o corte |

---

## Próximos marcos, em ordem de valor comercial (não de dependência técnica)

1. **Avaliação territorial (item 2 acima)** — maior valor comercial ainda não construído; reaproveita o motor de carência já pronto.
2. **Importação de qualificação por fonte externa** — reduz risco de cadastro manual desatualizado silenciosamente.
3. **Amarração real de mercado→campanha sanitária** — quando houver decisão normativa que a sustente.
4. **Frontend** — só depois que este documento parar de mudar a cada sessão.

---

## Como este documento se mantém honesto

Toda vez que um item aqui mudar de "fora" para "dentro", ou vice-versa, este arquivo muda no mesmo commit que a mudança de código — como o `docs/CHECKLIST_DE_IMPLEMENTACAO.md` já faz para passos individuais. Este documento é o resumo executivo; o checklist continua sendo a fonte de verdade passo a passo.
