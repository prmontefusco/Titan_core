# NEXT-03 — Autoridade por requisito e fronteiras de reconhecimento externo

**Artifact ID:** `NEXT-03-DP-v1`
**Data:** 12 de agosto de 2026
**Estado:** CORTES 1 E 2 IMPLEMENTADOS; CORTE 3 AGUARDA REVISÃO
**Escopo:** desenho do primeiro incremento controlado de autoridade de evidência; não cria reconhecimento regulatório externo.

## 1. Objetivo

Depois de NEXT-01 (coverage e admissibilidade) e NEXT-02 (Policy temporal e fotografia normativa), responder de forma auditável:

```text
Para este requisito de Policy:
  quem pode afirmar este fato?
  qual Evidence sustenta a afirmação?
  a fonte é admissível para esta finalidade e neste período?
  existe reconhecimento externo demonstrado — ou apenas decisão interna?
```

O objetivo não é transformar o Titan em autoridade sanitária, certificadora, órgão governamental ou representante de mercado. É delimitar o que uma Evaluation e uma Decision Titan podem provar e o que permanece externo ou indeterminado.

## 2. Decisão conceitual proposta

O NEXT-03 deve separar três perguntas que não são intercambiáveis:

| Pergunta | Conceito responsável | Não demonstra sozinho |
| --- | --- | --- |
| Quem emitiu a Decision Titan? | `DecisionAuthorityProfile` | que uma fonte de Evidence tem competência para um requisito, nem reconhecimento externo |
| Quem afirma ou atesta um fato? | `Source` / `Evidence` / Claim / Provenance | que a afirmação é admissível ou aceita por mercado |
| Quem é aceito para este requisito e finalidade? | assessment de autoridade por requisito + `EvidenceAdmissibilityAssessment` | reconhecimento oficial universal |

Assim, `DecisionAuthorityProfile` permanece exclusivamente o perfil de competência para **emitir ou revisar uma Decision Titan**. Ele não deve ser reutilizado como atalho para afirmar que um veterinário, produtor, certificadora ou órgão externo é fonte admissível de um requisito.

O primeiro contrato de Application proposto é transitório e source-neutral:

```text
RequirementAuthorityAssessment
  subject_reference
  policy / rule / requirement_reference
  purpose
  reference_time
  knowledge_cutoff
  asserted_by / source_reference
  authority_basis_reference[]
  evidence_reference[]
  validation
  admissibility
  recognition_boundary
  outcome
  limitations[]
```

Ele é um resultado explicável da composição de contratos existentes, não uma nova entidade persistida no primeiro corte. Persistência só será considerada se o fluxo demonstrar identidade e ciclo de vida próprios.

## 3. Estados mínimos propostos

O resultado deve distinguir, sem colapsar ausência de conhecimento em negação:

| Resultado | Significado |
| --- | --- |
| `SATISFIED` | fonte/atestado aplicável, validado e admissível para o requisito delimitado |
| `NOT_SATISFIED` | existe conclusão explícita de que a fonte exigida não atende ao requisito |
| `INDETERMINATE` | fonte, competência, Evidence, vigência, escopo ou reconhecimento necessário não está demonstrado |
| `NOT_APPLICABLE` | requisito não se aplica, conforme Policy publicada |

`INDETERMINATE` é o resultado para ausência de fonte, fonte com competência não demonstrada, assinatura válida sem reconhecimento correspondente, delegação expirada, jurisdição desconhecida ou conflito não resolvido. Não deve produzir `NOT_SATISFIED` por conveniência.

## 4. Limite de reconhecimento externo

Reconhecimento externo é uma afirmação mais forte que integridade, autenticação, validação, admissibilidade interna ou emissão de Decision pelo Titan.

```text
digest válido
  != identidade confirmada
  != competência da fonte
  != admissibilidade para a Policy
  != aceitação por certificadora/órgão/mercado
```

No primeiro incremento, só existirão duas fronteiras explícitas:

- `INTERNAL_ONLY`: o Titan aceitou material para sua Policy controlada; nenhuma aceitação externa é alegada.
- `EXTERNAL_RECOGNITION_NOT_DEMONSTRATED`: há material externo ou alegação de competência, mas não há Evidence suficiente de que autoridade externa reconhece a conclusão para a finalidade em análise.

Não se introduz `EXTERNALLY_RECOGNIZED` até haver caso real, autoridade identificada, escopo, vigência, Evidence de competência/reconhecimento e regra de validação aprovada. Um nome de órgão, certificado, assinatura ou URL não basta.

## 5. Reaproveitamento obrigatório

O desenho não cria um segundo motor ou uma taxonomia universal de autoridades. Reutiliza:

- `Source`, `Evidence`, `Provenance`, `ValidationAssessment` e `EvidenceAdmissibilityAssessment` para origem, integridade, validação e uso pela Policy;
- `NormativeBasisSnapshot` de NEXT-02 para preservar a interpretação normativa selecionada;
- `Policy`, `Rule`, `Evaluation` e coverage dimensional para definir o requisito e suas lacunas;
- `DecisionAuthorityProfile`, `DecisionProposal`, `DecisionReview` e `Decision` somente para a autoridade de emissão interna;
- `UniversalReference`, Organization, tempos válidos e de conhecimento, RLS e trilha append-only existentes.

O `ReceivedTransferArtifact` continua podendo ser Source/Artifact de entrada, mas não é dono de competência, admissibilidade, authority assessment ou reconhecimento.

## 6. Achados no estado atual

1. ADR-0053 já proíbe inferir autoridade externa a partir da emissão de Decision Titan.
2. `DecisionAuthorityProfile` e persistência protegida já existem, mas o perfil atual é reduzido: não modela requisito, jurisdição, território, Source, Evidence de competência ou reconhecimento externo.
3. `automated_decision_authority()` em `livestock_application/eligibility.py` ainda fabrica um perfil ad hoc por execução. Isso é incompatível com a resolução server-side de perfil publicado exigida por ADR-0053; não deve ser ampliado para resolver NEXT-03.
4. `EvidenceAdmissibilityAssessment` já é a fronteira correta para decidir se Evidence participa de Evaluation, mas ainda não há composição explícita de competência da fonte por requisito/tempo.
5. A classificação sanitária de medicamento já preserva fonte, validação e confiança, porém não equivale a catálogo oficial ou reconhecimento externo.
6. Nenhum mercado real deve ser alegado com os perfis hoje presentes em `market_eligibility.py`; eles continuam sendo configuração de MVP e não autorização de exportação.

## 7. Primeiro caso controlado

Usar somente uma Policy fictícia, por exemplo `AUTHORITY_TEST_A/v1`, com um requisito singular:

```text
Requirement: sanitary_attestation
Purpose: MARKET_ELIGIBILITY_TEST
Required source capability: VETERINARY_ATTESTATION
Recognition boundary: INTERNAL_ONLY
```

Três fontes fictícias demonstram a semântica:

| Fonte | Declaração | Resultado esperado |
| --- | --- | --- |
| `VET_TEST_A` | competência documentada, Evidence válida e admissível | `SATISFIED`, `INTERNAL_ONLY` |
| `PRODUCER_TEST_A` | Evidence presente, mas competência não demonstrada para este requisito | `INDETERMINATE` |
| `EXTERNAL_CERT_TEST_A` | alegação de certificação sem Evidence de reconhecimento pelo mercado | `INDETERMINATE`, `EXTERNAL_RECOGNITION_NOT_DEMONSTRATED` |

O caso não declara que o veterinário ou a certificadora têm poder real; são identificadores sintéticos e controlados.

## 8. Invariantes

1. Autoridade de emitir Decision não é autoridade de atestar Evidence.
2. Source autenticada não é automaticamente competente.
3. Evidence válida não é automaticamente admissível.
4. Admissibilidade interna não é reconhecimento externo.
5. Ausência de competência ou reconhecimento demonstrado produz `INDETERMINATE`, não resultado negativo factual.
6. Competência é delimitada por requisito, finalidade, escopo e tempo.
7. Conhecimento posterior não altera Evaluation ou Decision histórica.
8. O cliente não escolhe resultado, perfil de autoridade, reconhecimento ou fonte autoritativa.
9. `INTERNAL_TEST` e `INTERNAL_ONLY` nunca são apresentados como ato de órgão público, mercado ou certificadora.
10. Novo assessment não reescreve Source, Evidence, Evaluation ou Decision existentes.

## 9. Cortes propostos

### Corte 1 — assessment puro, sem persistência/API

- definir contratos transitórios e outcomes controlados;
- compor Source/Evidence/validação/admissibilidade já existentes;
- provar os três casos sintéticos e temporalidade básica;
- não alterar `DecisionAuthorityProfile`, Evaluation, Decision, cobertura ou o adapter Odoo.

### Corte 2 — integração à Policy controlada

- conectar a suficiência de autoridade como dimensão explícita e independente;
- `INDETERMINATE` bloqueia conclusão positiva quando o requisito a exigir;
- preservar no `NormativeBasisSnapshot` a boundary de reconhecimento aplicável;
- nenhum mercado real e nenhuma Decision com alegação externa.

### Corte 3 — persistência operacional, somente se comprovada necessária

- decidir se assessment possui identidade e lifecycle próprios;
- se sim, migration aditiva, RLS, append-only, round-trip e compatibilidade legada explícita;
- API e roteiro em `apps/validacao` apenas caso haja comportamento observável novo.

## 10. Testes exigidos

- competência documentada e admissível para requisito sintético;
- Evidence presente sem competência demonstrada → `INDETERMINATE`;
- alegação externa sem reconhecimento demonstrado → boundary explícita e `INDETERMINATE`;
- diferença entre validade, conhecimento e vigência da competência;
- mudança posterior não reproduz Evaluation anterior de modo diferente;
- DecisionAuthorityProfile não é aceito como prova de autoridade da Source;
- ordem de Sources/Evidences não altera resultado;
- isolamento por Organization e ausência de overclaim em qualquer resposta exposta.

## 11. Fora do escopo

- autoridade sanitária ou reconhecimento regulatório reais;
- integração governamental, consulta de API externa, captura de sites ou trust registry;
- credenciamento real de veterinários, certificadoras ou estabelecimentos;
- alteração de Odoo/ERP;
- mercado real ou `EXPORT_ALLOWED = TRUE`;
- taxonomia universal de autoridade;
- substituição da ADR-0053 ou redesenho de `DecisionAuthorityProfile` sem ADR específica.

## 12. Portão para autorizar somente o Corte 1

Antes de código, confirmar:

1. `RequirementAuthorityAssessment` será contrato transitório source-neutral, não entidade persistida;
2. o primeiro caso será `AUTHORITY_TEST_A/v1`, integralmente fictício;
3. competência de Source e autoridade de emissão de Decision permanecerão conceitos distintos;
4. o único reconhecimento positivo do primeiro corte será `INTERNAL_ONLY`; não haverá `EXTERNALLY_RECOGNIZED`;
5. ausência de competência/reconhecimento demonstrado resultará em `INDETERMINATE`;
6. nenhuma API, migration, alteração em `DecisionAuthorityProfile` ou mudança no Odoo será incluída no Corte 1.

Com essas confirmações, o próximo passo é implementar somente o Corte 1 e revisar seus resultados antes de integrar qualquer Policy ou persistência.

## 13. Registro de execução

**CORTE 1 CONCLUÍDO EM 12 DE AGOSTO DE 2026.**

`packages/livestock_application/requirement_authority.py` introduz somente contratos transitórios de Application: `SourceCompetenceAssertion`, `RequirementAuthorityAssessment` e o serviço puro de assessment. Não há entidade, aggregate, persistência, API, integração externa ou alteração de `DecisionAuthorityProfile`.

O resolvedor aplica competência por requisito/capacidade/finalidade, intervalo semiaberto de vigência e `knowledge_cutoff`; exige base de competência, Evidence, validação e admissibilidade para retornar `SATISFIED`. Fonte ausente, conhecimento posterior, competência `UNKNOWN`, ambiguidade entre Sources, Evidence não admissível e alegação externa sem reconhecimento demonstrado retornam `INDETERMINATE`. `NOT_SATISFIED` é reservado para afirmação explícita e não ambígua de incompetência. O único reconhecimento positivo é `INTERNAL_ONLY`.

Nove testes sintéticos provam os casos do pacote, temporalidade, intervalo de vigência, admissibilidade e conflito de Sources. O Corte 2 permanece bloqueado até revisão humana: ele é o primeiro ponto que poderá conectar este assessment a uma Policy/Evaluation controlada.

**CORTE 2 CONCLUÍDO EM 12 DE AGOSTO DE 2026.** `AuthorityTestARequirementService` traduz somente o assessment de `AUTHORITY_TEST_A/v1` em Fact de requisito. A chave `source_authority_sufficient` é publicada como `true` apenas para `SATISFIED`, como `false` apenas para incompetência explícita e não ambígua, e permanece ausente para `INDETERMINATE`; a Rule declarativa controlada preserva a lacuna como `INDETERMINADA`. Não há associação a mercado real, Decision externa ou mudança de `DecisionAuthorityProfile`.

A boundary de reconhecimento é preservável sem ampliar o schema de `NormativeBasisSnapshot`: entra na coleção canônica `limitations` como `RECOGNITION_BOUNDARY:<valor>` e altera seu digest. Quatro testes adicionais provam os três resultados da Rule e a alteração de identidade do snapshot.

**CORTE 3 E NEXT-03 CONCLUÍDOS EM 12 DE AGOSTO DE 2026.** A revisão do fluxo implementado confirmou que `RequirementAuthorityAssessment` é resultado derivado, sem identidade própria, repositório, transição de estado, aprovação, revogação, retenção autônoma ou consulta por identificador. Seu conteúdo relevante já é preservado nos contratos que o compõem e, quando consumido pela Policy controlada, no `Fact` produzido e no `NormativeBasisSnapshot` correspondente. Não há evidência que justifique uma entidade, migration, RLS, API ou roteiro de validação próprios. A decisão é **não persistir** o assessment neste incremento; qualquer necessidade futura deverá demonstrar um ciclo de vida independente antes de reabrir este corte.
