# LIV-C07_DESIGN_PACKAGE

Status: DRAFT_FOR_IMPLEMENTATION
Artifact ID: `LIV-C07-DP-v1`
Plan version: 1.2
Stage: `LIV-C07`
Date: 2026-08-04
Derived from:

- [LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md)
- Stage `LIV-C07`

## 1. Objetivo

Definir o menor incremento conforme para ampliar o conteúdo canônico de `Dossier` e `VerificationBundle` ao escopo de conformidade sanitária vitalícia, preservando PDF apenas como `Presentation` derivada.

## 2. Escopo

Este artefato cobre:

- a pergunta arquitetural de `LIV-C07`;
- o estado atual comprovado de `Dossier`, `VerificationBundle` e verificação offline;
- a lacuna residual entre o conteúdo sanitário atual e a ambição de conformidade vitalícia;
- a recomendação mínima de implementação para a etapa;
- os testes e gates necessários para considerar a etapa concluída.

Este artefato não cobre:

- implementação de código nesta etapa documental;
- mudança de `DOMAIN.md`, `ARCHITECTURE.md` ou ADRs;
- criação de formato normativo paralelo ao `Dossier` ou ao `BundleManifest`;
- transformar PDF em fonte normativa;
- autorização automática de `LIV-C08`.

## 3. Entradas

- [AGENTS.md](/C:/programing/Titan/AGENTS.md)
- [VISION.md](/C:/programing/Titan/VISION.md)
- [DOMAIN.md](/C:/programing/Titan/DOMAIN.md)
- [ARCHITECTURE.md](/C:/programing/Titan/ARCHITECTURE.md)
- [DEVELOPMENT.md](/C:/programing/Titan/DEVELOPMENT.md)
- [docs/CHECKLIST_DE_IMPLEMENTACAO.md](/C:/programing/Titan/docs/CHECKLIST_DE_IMPLEMENTACAO.md)
- [LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md)
- [LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md)
- [LIVESTOCK_LIFETIME_COMPLIANCE_C02_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_C02_DESIGN_PACKAGE.md)
- [LIV-C05_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/LIV-C05_DESIGN_PACKAGE.md)
- [LIV-C06_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/LIV-C06_DESIGN_PACKAGE.md)
- [packages/core_application/dossier_service.py](/C:/programing/Titan/packages/core_application/dossier_service.py)
- [packages/core_application/verification_service.py](/C:/programing/Titan/packages/core_application/verification_service.py)
- [packages/core_domain/dossier.py](/C:/programing/Titan/packages/core_domain/dossier.py)
- [packages/core_domain/verification.py](/C:/programing/Titan/packages/core_domain/verification.py)
- [packages/livestock_application/dossier_template.py](/C:/programing/Titan/packages/livestock_application/dossier_template.py)
- [apps/api/verification.py](/C:/programing/Titan/apps/api/verification.py)
- [tests/application/test_dossier_service.py](/C:/programing/Titan/tests/application/test_dossier_service.py)
- [tests/application/test_verification_bundle.py](/C:/programing/Titan/tests/application/test_verification_bundle.py)
- [tests/livestock_application/test_dossier_template.py](/C:/programing/Titan/tests/livestock_application/test_dossier_template.py)
- [tests/api/test_verification_api.py](/C:/programing/Titan/tests/api/test_verification_api.py)

## 4. Documentos de autoridade

- [AGENTS.md](/C:/programing/Titan/AGENTS.md)
- [VISION.md](/C:/programing/Titan/VISION.md)
- [DOMAIN.md](/C:/programing/Titan/DOMAIN.md)
- [ARCHITECTURE.md](/C:/programing/Titan/ARCHITECTURE.md)
- [DEVELOPMENT.md](/C:/programing/Titan/DEVELOPMENT.md)
- [docs/CHECKLIST_DE_IMPLEMENTACAO.md](/C:/programing/Titan/docs/CHECKLIST_DE_IMPLEMENTACAO.md)
- ADR-0048
- ADR-0051
- ADR-0055

## 5. Documentos auxiliares

- [LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md)
- [LIVESTOCK_STAGE_PACKAGE_TEMPLATE.md](/C:/programing/Titan/docs/plans/LIVESTOCK_STAGE_PACKAGE_TEMPLATE.md)
- [LIV-C06_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/LIV-C06_DESIGN_PACKAGE.md)

## 6. Análise

### 6.1 Architectural Question

What is the minimum canonical Dossier/VerificationBundle content that honestly represents lifetime sanitary compliance before any PDF `Presentation`?

### 6.2 Estado atual comprovado

O repositório já possui o envelope canônico principal:

- `DossierService.build()` em [dossier_service.py](/C:/programing/Titan/packages/core_application/dossier_service.py) já preserva:
  - `Policy`, `rules`, `facts`, `Evaluation`, `Decision`, `governance`, `evidences`, `vertical` e `nonconformities`;
  - `knowledge_cutoff` e `knowledge_limitations`;
  - cadeia de autoridade e método de emissão da `Decision`.
- `VerificationBundleService.build_from_dossier()` em [verification_service.py](/C:/programing/Titan/packages/core_application/verification_service.py) já empacota:
  - `dossier.json` como componente obrigatório;
  - `verification-policy.json` como opcional ou deliberadamente ausente;
  - `declared_scopes`, `declared_gaps`, `profiles` e assinatura opcional;
  - `BundleManifest` canônico, sem criar manifesto paralelo.
- `BundleVerifier` em [verification.py](/C:/programing/Titan/packages/core_domain/verification.py) já separa verificação por dimensões:
  - estrutura;
  - serialização;
  - integridade;
  - assinatura;
  - temporalidade;
  - revogação;
  - cobertura.
- `LivestockDossierTemplate` em [dossier_template.py](/C:/programing/Titan/packages/livestock_application/dossier_template.py) já materializa seção vertical com:
  - `subject`;
  - `withdrawal`;
  - `coverage`;
  - `timeline`;
  - `evidence_chain`;
  - `governed_rule`.

### 6.3 Prova de cobertura de testes existente

Já existe cobertura significativa do comportamento base:

- [test_dossier_service.py](/C:/programing/Titan/tests/application/test_dossier_service.py) cobre:
  - autocontenção do `Dossier`;
  - coerência entre `Decision`, `Evaluation` e `Policy`;
  - inclusão de evidências e ausência declarada quando o conteúdo não acompanha.
- [test_verification_bundle.py](/C:/programing/Titan/tests/application/test_verification_bundle.py) cobre:
  - montagem do bundle a partir do `Dossier`;
  - verificação offline;
  - adulteração de payload;
  - ausência de dossiê;
  - ausência de assinatura;
  - transporte/export/load sem depender do Titan.
- [test_dossier_template.py](/C:/programing/Titan/tests/livestock_application/test_dossier_template.py) cobre:
  - identidade do animal no snapshot;
  - aritmética de carência;
  - evidência copiada com hash;
  - cobertura parcial declarada;
  - timeline congelada no instante da decisão;
  - governed rule preservada;
  - recusa de sujeito que não seja animal.
- [test_verification_api.py](/C:/programing/Titan/tests/api/test_verification_api.py) cobre:
  - endpoint `/v1/verification/bundles`;
  - relatório dimensional;
  - pacote adulterado;
  - âncoras de confiança e limites de entrada.

### 6.4 Lacuna residual comprovada

A lacuna do `LIV-C07` não está na existência de `Dossier` ou `VerificationBundle`. A lacuna remanescente está no conteúdo sanitário ampliado.

Hoje o template vertical já demonstra:

- decisão;
- evaluation;
- carência;
- cadeia de evidências;
- cobertura parcial baseada em `received_transfer_artifact`.

Mas ainda não comprova, de forma completa e explícita para o problema de conformidade vitalícia:

- a diferença entre cobertura local, cobertura importada e cobertura desconhecida em toda a vida;
- o escopo do histórico importado que entrou no snapshot sanitário;
- limitações materiais da prova quando houver lacunas de cobertura ou dependência externa;
- a relação entre conteúdo canônico do `Dossier` sanitário e o `VerificationBundle` sanitário correspondente;
- a forma mínima de expor essas limitações sem sugerir cobertura vitalícia total.

### 6.5 Distinções conceituais obrigatórias

- `Dossier` continua sendo o artefato normativo primário.
- `VerificationBundle` continua sendo pacote de transporte e verificação do `Dossier`, não um segundo dossiê.
- `BundleManifest` continua sendo o manifesto canônico do pacote; não há espaço aprovado para `DossierManifest` paralelo.
- PDF continua sendo apenas `Presentation`.
- Cobertura sanitária vitalícia continua sendo insumo explicativo da prova, não alegação automática de conformidade.
- `Imported evidence` ou `imported fact` continuam distintos de observação local.

### 6.6 Alternativas avaliadas

Alternativa A: considerar o `LIV-C07` já concluído porque `Dossier`, `VerificationBundle` e verificação offline já existem.

- vantagem:
  - menor trabalho imediato.
- desvantagens:
  - ignora a lacuna específica da vertical sobre cobertura sanitária vitalícia e histórico importado;
  - deixaria o dossiê sanitário atual parecendo mais completo do que a prova realmente sustenta.
- veredito:
  - rejeitada.

Alternativa B: ampliar apenas a seção vertical do `Dossier` e derivar dela o `VerificationBundle`, sem criar novo formato.

- vantagem:
  - reutiliza o envelope já aceito;
  - preserva `Dossier` como fonte primária e `VerificationBundle` como derivado verificável;
  - segue derivation before persistence.
- desvantagens:
  - exige definir com precisão o conteúdo mínimo adicional da vertical.
- veredito:
  - recomendada.

Alternativa C: criar um artefato sanitário paralelo específico da vertical para depois converter em `Dossier`.

- vantagem:
  - poderia isolar a evolução sanitária em um formato próprio.
- desvantagens:
  - introduz fonte normativa concorrente;
  - conflita com ADR-0048 e ADR-0055;
  - amplia a superfície sem necessidade comprovada.
- veredito:
  - rejeitada.

### 6.7 Recomendação mínima

A recomendação mínima para `LIV-C07` é:

- não criar novo artefato normativo;
- manter `Dossier` como snapshot primário e `VerificationBundle` como embalagem verificável;
- ampliar apenas o conteúdo sanitário canônico já derivado pelo `LivestockDossierTemplate`;
- declarar explicitamente, na seção vertical e no bundle, limites de cobertura e material importado relevante;
- tratar PDF apenas depois que o conteúdo canônico e o bundle estiverem completos e testados.

### 6.8 Contrato alvo mínimo

O contrato mínimo desta etapa deve permitir que o `Dossier` sanitário e seu `VerificationBundle`:

- mostrem:
  - cobertura conhecida;
  - lacunas declaradas;
  - origem importada material;
  - limitações do snapshot;
  - fundamento governado relevante da decisão;
- não sugiram:
  - cobertura vitalícia total quando ela não existir;
  - imported fact como fato local;
  - verificação completa quando o bundle declarar lacunas;
- preservem:
  - `dossier_hash`;
  - `bundle_manifest`;
  - `declared_scopes`;
  - `declared_gaps`;
  - separação entre conteúdo normativo e apresentação.

### 6.9 Gate arquitetural

O principal gate antes da implementação é de conteúdo, não de infraestrutura:

- a etapa não precisa de novo aggregate, nova tabela ou nova API pública para existir;
- ela precisa provar qual conteúdo adicional é materialmente necessário para honestidade documental;
- se a implementação exigir novo tipo normativo, novo manifesto ou mudança de ADR para distinguir `Dossier` e `VerificationBundle`, a execução deve parar e voltar para aprovação arquitetural.

Conclusão:

- `LIV-C07` pode prosseguir pelo caminho mínimo se a implementação permanecer na ampliação do conteúdo canônico e dos testes do envelope já existente.

## 7. Decisões

- `LIV-C07` não exige novo artefato normativo para prosseguir.
- O envelope `Dossier` + `VerificationBundle` existente é suficiente para a etapa.
- O trabalho mínimo da etapa deve ficar concentrado em:
  - ampliar honestamente o conteúdo sanitário da seção vertical;
  - ampliar ou ajustar `declared_scopes` e `declared_gaps` quando necessário;
  - reforçar testes de autocontenção e verificação offline do material sanitário ampliado.
- Se surgir necessidade de novo manifesto, novo tipo documental ou mudança de ADR, a execução deve parar para `PLAN_CHANGE_REQUEST`.

## 8. Riscos

- O template atual pode já carregar informação suficiente para alguns cenários, mas insuficiente para deixar explícitas todas as limitações de cobertura vitalícia.
- Um aumento de conteúdo no `Dossier` pode quebrar testes de hash, snapshots documentais ou expectativas do bundle.
- A suíte de API continua com falha preexistente de import fora do escopo do `LIV-C07`, o que pode bloquear verificação integrada da superfície HTTP se não for tratado separadamente.

## 9. Critério de encerramento

O estágio `LIV-C07` é considerado concluído quando:

- [ ] o conteúdo sanitário canônico adicional do `Dossier` estiver definido e implementado sem criar formato normativo paralelo;
- [ ] o `VerificationBundle` refletir corretamente os limites e escopos do material sanitário ampliado;
- [ ] os testes de `Dossier`, `VerificationBundle` e template vertical cobrirem lacunas, material importado e limitações relevantes;
- [ ] PDF permanecer explicitamente como `Presentation` derivada, sem papel normativo primário;
- [ ] nenhuma pendência restante deste estágio exigir mudança de ADR ou novo artefato central.

## 10. Dependências liberadas

Este artefato prepara o pré-requisito documental para:

- `LIV-C08`

Observação:

- satisfazer pré-requisito não autoriza execução da próxima etapa;
- autorização continua dependendo de aprovação humana explícita.

## 11. Não conformidades

- Nenhuma não conformidade documental encontrada.
- Observação operacional:
  - a suíte integrada de API ainda possui falha preexistente e lateral de import em `apps/api/core_rule_governance.py`, fora do escopo específico deste pacote.

## 12. Limites

Este artefato não:

- implementa código do `LIV-C07`;
- autoriza `LIV-C08`;
- altera `DOMAIN.md`, `ARCHITECTURE.md` ou ADRs;
- transforma PDF em fonte normativa;
- cria um segundo contrato documental concorrente ao `Dossier` ou ao `VerificationBundle`.

## 13. Próxima etapa

A próxima etapa potencial é:

- implementação do `LIV-C07`, limitada à ampliação do conteúdo canônico do `Dossier` sanitário e do `VerificationBundle` correspondente.

Essa implementação continua dependente de revisão humana do presente Design Package.
