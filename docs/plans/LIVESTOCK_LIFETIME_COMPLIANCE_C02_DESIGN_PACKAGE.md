# LIVESTOCK_LIFETIME_COMPLIANCE_C02_DESIGN_PACKAGE

Status: DRAFT_FOR_IMPLEMENTATION
Artifact ID: `LIV-C02-DP-v1`
Plan version: 1.2
Stage: `LIV-C02`
Date: 2026-08-04
Derived from:

- [LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md)
- Stage `LIV-C02`

## 1. Objetivo

Definir o desenho mínimo e auditável para representar cobertura sanitária vitalícia e lacunas explícitas, preservando a separação entre coverage, claim, evidence, `Policy`, `Evaluation`, `Decision` e Dossier.

## 2. Escopo

Este artefato cobre:

- a pergunta arquitetural da etapa;
- a análise dos conceitos atuais já existentes;
- a decisão mínima de modelagem para cobertura sanitária;
- os critérios que autorizariam implementação futura da etapa;
- os riscos e limites documentais da solução escolhida.

Este artefato não cobre:

- implementação de código;
- criação de migrations;
- introdução automática de nova entidade, novo `Aggregate` ou novo conceito transversal;
- autorização das etapas posteriores.

## 3. Entradas

- plano aprovado [LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md)
- baseline documental [LIVESTOCK_LIFETIME_COMPLIANCE_C01_BASELINE.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_C01_BASELINE.md)
- template [LIVESTOCK_STAGE_PACKAGE_TEMPLATE.md](/C:/programing/Titan/docs/plans/LIVESTOCK_STAGE_PACKAGE_TEMPLATE.md)
- [packages/livestock_domain/transfer_artifact.py](/C:/programing/Titan/packages/livestock_domain/transfer_artifact.py)
- [packages/livestock_application/fact_provider.py](/C:/programing/Titan/packages/livestock_application/fact_provider.py)
- [packages/livestock_application/dossier_template.py](/C:/programing/Titan/packages/livestock_application/dossier_template.py)
- [tests/livestock_domain/test_transfer_artifact_domain.py](/C:/programing/Titan/tests/livestock_domain/test_transfer_artifact_domain.py)

## 4. Documentos de autoridade

- [AGENTS.md](/C:/programing/Titan/AGENTS.md)
- [VISION.md](/C:/programing/Titan/VISION.md)
- [DOMAIN.md](/C:/programing/Titan/DOMAIN.md)
- [ARCHITECTURE.md](/C:/programing/Titan/ARCHITECTURE.md)
- [DEVELOPMENT.md](/C:/programing/Titan/DEVELOPMENT.md)
- [docs/CHECKLIST_DE_IMPLEMENTACAO.md](/C:/programing/Titan/docs/CHECKLIST_DE_IMPLEMENTACAO.md)
- ADR-0042
- ADR-0048
- ADR-0051
- ADR-0052

## 5. Documentos auxiliares

- [LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md)
- [LIVESTOCK_LIFETIME_COMPLIANCE_C01_BASELINE.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_C01_BASELINE.md)

## 6. Análise

### 6.1 Architectural Question

Can lifetime sanitary coverage be represented without introducing a new `Aggregate`?

### 6.2 Pergunta de abertura obrigatória

É possível representar cobertura sanitária reutilizando exclusivamente os conceitos já existentes no Core? Se sim, nenhuma nova entidade ou `Aggregate` deverá ser introduzido.

Resposta desta análise:

- Sim, no nível de design atualmente comprovado.

### 6.3 Conceitos já existentes comprovados

Os conceitos existentes já cobrem parte importante do problema:

- `HistoryCoverage` já representa intervalo conhecido e lacunas derivadas de `ReceivedTransferArtifact` em [transfer_artifact.py](/C:/programing/Titan/packages/livestock_domain/transfer_artifact.py)
- `TransferArtifactGap` já representa lacuna explícita, inclusive com códigos distintos, no mesmo arquivo
- `FactSnapshot` já é o ponto de entrada de fatos para `Evaluation`, conforme uso em [fact_provider.py](/C:/programing/Titan/packages/livestock_application/fact_provider.py)
- o Dossier da vertical já sabe carregar cadeia explicativa e timeline limitada por conhecimento em [dossier_template.py](/C:/programing/Titan/packages/livestock_application/dossier_template.py)
- há teste de domínio provando que ausência de cobertura não vira histórico vazio em [test_transfer_artifact_domain.py](/C:/programing/Titan/tests/livestock_domain/test_transfer_artifact_domain.py)

### 6.4 Lacuna comprovada

A lacuna atual não é ausência total de conceito. A lacuna real é:

- `HistoryCoverage` existe, mas está acoplada ao contexto de transferência recebida;
- a cobertura ainda não aparece como insumo geral e explícito de snapshot/evaluation para todo o histórico sanitário do animal;
- o Dossier já possui mecanismos para timeline e explicação, mas ainda não possui contrato explícito para declarar coverage/lacuna vitalícia como dimensão própria;
- portanto, o déficit principal é de composição e projeção, não de inexistência absoluta de conceito base.

### 6.5 Alternativas avaliadas

Alternativa A: introduzir novo `Aggregate` ou nova entidade dedicada de cobertura sanitária vitalícia

- vantagem:
  - tornaria a cobertura uma peça nominalmente central do domínio.
- desvantagens:
  - aumenta superfície de domínio antes de provar insuficiência dos conceitos atuais;
  - cria pressão prematura por persistence e migration;
  - contraria o princípio global de reuse before creation sem prova técnica suficiente;
  - não é exigida explicitamente por nenhuma ADR aplicável.

Alternativa B: reutilizar `HistoryCoverage`, `TransferArtifactGap`, timeline conhecida, snapshot e Dossier, promovendo coverage a dimensão derivada e explicitamente transportada pelos contratos da etapa

- vantagens:
  - introduz a menor superfície de domínio;
  - preserva semânticas já aceitas;
  - exige o menor número de conceitos persistentes novos, potencialmente zero;
  - minimiza impacto de migration;
  - permanece compatível com ADR-0042, ADR-0048, ADR-0051 e ADR-0052.
- desvantagens:
  - exige cuidado para não sobrecarregar `HistoryCoverage` com responsabilidades indevidas;
  - pode exigir adaptação de contratos de snapshot e Dossier sem criar novo tipo persistente.

### 6.6 Decision rule aplicada

A solução preferida é a que:

- introduz a menor superfície de domínio;
- preserva semânticas já aceitas;
- exige o menor número de conceitos persistentes;
- minimiza impacto de migration;
- permanece compatível com ADRs já aceitas.

Resultado da aplicação:

- Alternativa B é a solução preferida.

### 6.7 Desenho mínimo recomendado

O desenho mínimo recomendado para `LIV-C02` é:

- não criar novo `Aggregate`;
- não criar nova entidade persistente como primeiro movimento;
- tratar coverage como dimensão derivada e explícita, composta a partir de conceitos existentes;
- expandir o uso de `HistoryCoverage` e de lacunas explícitas para além de `ReceivedTransferArtifact`, sem rebatizar o problema como novo agregado;
- transportar o resultado de coverage para snapshot/evaluation como insumo de `Policy`;
- declarar no Dossier cobertura conhecida e lacunas de forma honesta, sem promover ausência de evento a claim de não uso.

### 6.8 Critérios de prova para futura implementação

A futura implementação de `LIV-C02` deverá provar:

- que coverage e lacuna entram em snapshot sem alterar o significado de `Fact`, `Evidence`, `Evaluation` ou `Decision`;
- que ausência de evento continua sendo apenas ausência de evento;
- que coverage parcial é apresentada como parcial, nunca como completude silenciosa;
- que o Dossier consegue declarar limites temporais conhecidos e lacunas explícitas;
- que nenhum novo `Aggregate` foi introduzido sem prova de insuficiência dos conceitos atuais.

## 7. Decisões

- A resposta formal à `Architectural Question` é “sim”: coverage pode ser representada sem novo `Aggregate`, no estado atual da análise.
- A etapa `LIV-C02` deve começar por composição, derivação e explicitação contratual sobre conceitos existentes.
- Se, durante implementação, os conceitos atuais se mostrarem insuficientes, a execução deve parar antes de introduzir nova entidade, novo `Aggregate` ou novo conceito transversal.
- O primeiro caminho autorizado de implementação futura é derivation before persistence.

## 8. Riscos

- superestimar coverage derivada e mascarar lacunas reais;
- acoplar coverage a apenas um tipo de origem e não ao problema vitalício completo;
- transformar ausência de evento em conclusão material;
- criar persistence prematura para resolver problema que ainda pode ser derivado;
- espalhar coverage por múltiplos contratos sem semântica única de apresentação.

## 9. Critério de encerramento

O `LIV-C02` será considerado documentalmente pronto para implementação quando:

- [x] a `Architectural Question` estiver respondida;
- [x] a decisão mínima de modelagem estiver registrada;
- [x] os conceitos já existentes reutilizáveis estiverem identificados;
- [x] os critérios de prova da implementação estiverem definidos;
- [x] nenhuma pendência documental restante deste estágio impedir o início da implementação.

## 10. Dependências liberadas

Este artefato satisfaz o pré-requisito documental de modelagem para:

- execução futura do próprio `LIV-C02`;
- análise de dependência de `LIV-C03`, que depende de coverage/lacuna explicitadas.

Observação:

- isso não autoriza `LIV-C03`;
- autorização de implementação continua dependendo de aprovação humana explícita para etapas posteriores.

## 11. Não conformidades

Nenhuma não conformidade documental encontrada nesta etapa.

Observação relevante mantida:

- a cobertura existente comprovada hoje ainda está focalizada em transferência recebida, e não em contrato geral já consolidado para toda a vida sanitária.

## 12. Limites

Este artefato não:

- implementa `LIV-C02`;
- cria migration;
- altera ADRs, `DOMAIN.md`, `ARCHITECTURE.md` ou código;
- prova que zero persistence nova será necessária;
- autoriza `LIV-C03` ou etapas posteriores.

## 13. Próxima etapa

Próxima ação potencial:

- implementar `LIV-C02` segundo este `Design Package`.

Condição:

- a implementação deve permanecer dentro da resposta à `Architectural Question` aqui registrada;
- se a implementação exigir novo `Aggregate`, nova entidade persistente central ou novo conceito transversal, a execução deve parar e retornar para aprovação arquitetural explícita.
