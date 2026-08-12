# NEXT-01 — Coverage e admissibilidade sanitária explícitas

Status: APROVADO — SEGUNDO CORTE IMPLEMENTADO
Artifact ID: `NEXT-01-DP-v1`
Date: `2026-08-12`
Natureza: design package; nenhuma implementação autorizada

## 1. Objetivo

Definir o menor incremento capaz de tornar explícitas, por finalidade, tipo de informação e intervalo, a cobertura do histórico sanitário e a admissibilidade do material usado por uma `Evaluation`.

```text
não foi encontrado fato != foi demonstrada a ausência do fato
```

Nenhuma `Policy` pode produzir resultado favorável apenas porque deixou de declarar a cobertura e a admissibilidade de que depende.

## 2. Decisão conceitual

Não existe `historico_completo = true` em sentido absoluto. Existe cobertura conhecida por Subject, dimensão, intervalo, finalidade/Policy e `knowledge_cutoff`, que pode ou não ser suficiente para responder uma pergunta delimitada.

Uma história pode ser suficiente para uma Policy de identidade/movimentação e insuficiente para outra de tratamentos/alimentação. Coverage descreve alcance; suficiência é efeito da Policy.

## 3. Escopo

Inclui:

- coverage derivada por dimensão e intervalo;
- requisitos mínimos declarados pela `Policy`/`Rule`;
- distinção entre ausência demonstrada, ausência de registro e área não avaliada;
- validação/admissibilidade de fatos importados;
- preservação de escopo, origem, tempos, razões, restrições e lacunas;
- testes e roteiro manual de uma futura implementação.

Não inclui mercado real, autorização de exportação, `NEXT-02/03/05`, readiness, impacto em massa, Odoo, novo Dossier, `MarketEligibility`, `EligibilityGap`, segundo motor ou promoção de `HistoryCoverage` ao Core.

## 4. Autoridade

- [VISION.md](/C:/programing/Titan/VISION.md)
- [DOMAIN.md](/C:/programing/Titan/DOMAIN.md)
- [ARCHITECTURE.md](/C:/programing/Titan/ARCHITECTURE.md)
- [DEVELOPMENT.md](/C:/programing/Titan/DEVELOPMENT.md)
- [ADR-0015](/C:/programing/Titan/docs/adr/0015-proveniencia-validacao-e-niveis-de-confianca.md)
- [ADR-0048](/C:/programing/Titan/docs/adr/0048-arquitetura-decisoes-explicaveis.md)
- [ADR-0049](/C:/programing/Titan/docs/adr/0049-politicas-regulatorias-e-perfis-de-mercado.md)
- [ADR-0051](/C:/programing/Titan/docs/adr/0051-snapshot-canonico-identidade-criptografica-e-proveniencia.md)
- [ADR-0052](/C:/programing/Titan/docs/adr/0052-temporalidade-valida-registro-e-conhecimento-historico.md)
- [Capability Gap Analysis](/C:/programing/Titan/docs/plans/LIVESTOCK_CAPABILITY_GAP_ANALYSIS.md)

## 5. Estado comprovado

Reutilizar:

- `HistoryCoverage` e `livestock.history_coverage`;
- `ImportedLivestockFact`, origem, artefato, autoria, confiança e tempos;
- `FactSnapshot`, `Policy`, `Rule`, `RuleResult`, `Evaluation` e indeterminação;
- `ValidationScope`, `ValidationAssessment` e `EvidenceAdmissibilityAssessment`;
- Evidence e Provenance existentes.

Lacunas:

- coverage atual deriva principalmente do último artefato de transferência;
- `known_from`/`known_until` não identificam tipos de informação cobertos;
- fatos importados podem entrar no snapshot sem admissibilidade completa por Policy;
- Policy sem requisito de coverage pode interpretar silêncio favoravelmente;
- gaps atuais são centrados em transferência.

## 6. Semântica de coverage

### Dimensão e intervalo

Dimensão é identificador controlado pela vertical. Candidatas: identidade, origem, movimentações, tratamentos, medicamentos/lotes, prescrições, campanhas, alimentação, documentos e habilitação. A lista não aprova todas elas.

Coverage usa intervalo semiaberto `[inicio, fim)`. A Policy declara a relação exigida (integral, interseção, precedência ou ocorrência). O início pode ser nascimento, aquisição ou marco normativo; o código não o escolhe.

### Estados mínimos

| Estado | Significado |
|---|---|
| `COBERTA` | O escopo suporta todo o intervalo exigido, sujeito às limitações. |
| `PARCIAL` | Parte identificada do intervalo/campos possui suporte. |
| `NAO_DECLARADA` | Não há declaração confiável de alcance. |
| `NAO_AVALIADA` | A dimensão/intervalo não foi avaliada. |
| `INDETERMINADA` | Conflito, tempo insuficiente ou ambiguidade impede classificar. |

`COBERTA` não significa verdadeira, válida, admissível ou suficiente. Percentual visual só pode ser derivado quando houver denominador defensável; não é estado normativo.

Gaps preservam código, dimensão, intervalo, razão, suporte e limitações. Devem distinguir período sem coverage, coverage parcial, tipo não coberto, material inacessível, conhecimento posterior ao corte, validação inconclusiva, rejeição/restrição da Policy e conflito material. Gap descreve a falta; Rule determina efeito.

### Ausência demonstrada

“Nenhum tratamento encontrado” só significa ausência quando a dimensão está coberta no intervalo/escopo exigidos, fontes requeridas estão presentes ou dispensadas, validação/admissibilidade são compatíveis, conflitos foram tratados e `knowledge_cutoff` foi preservado. Caso contrário: `INDETERMINADA`, `PENDENTE` ou revisão; nunca `ATENDIDA` por silêncio.

## 7. Requisito governado pela Policy

Contrato conceitual, não nova entidade:

```text
CoverageRequirement
  dimension
  required_interval_rule
  required_scope
  accepted_coverage_states
  admissibility_requirement
  conflict_behavior
  missing_behavior
```

Deve ser expresso pelo mecanismo atual de Rules, salvo prova de insuficiência. Um gate de publicação/teste deve impedir Rule que derive ausência material sem coverage/admissibility correspondente.

## 8. Admissibilidade

Origem não é confiança; confiança não é verificação; verificação não é admissibilidade; admissibilidade não é verdade; coverage não é admissibilidade; material admissível pode ser insuficiente; indisponibilidade não é rejeição.

Invariante textual deste incremento:

```text
COVERAGE      = tenho informação para esta dimensão e este período?
VALIDATION    = o material foi validado por qual método e escopo?
ADMISSIBILITY = esta Policy pode usar esse material nesta Evaluation?
```

Um material pode estar validado como declaração recebida e continuar não admissível para uma Policy que exija artefato documentado. Nenhuma dessas dimensões é promovida implicitamente à seguinte.

```text
Source/Artifact
 -> ImportedLivestockFact + Provenance
 -> ValidationScope
 -> ValidationAssessment
 -> EvidenceAdmissibilityAssessment por Policy/finalidade
 -> FactSnapshot com inclusões, exclusões e limitações
 -> RuleResult / Evaluation
```

Reutilizar `ACEITA`, `ACEITA_COM_RESTRICOES`, `REVISAO_NECESSARIA`, `REJEITADA_POR_POLITICA` e `INDETERMINADA`. Não criar enum Livestock concorrente. Assessment histórico não muda com validação posterior.

## 9. Fluxo futuro

```text
Subject + purpose + reference_time + knowledge_cutoff
 -> Policy/Rules publicadas
 -> requisitos de coverage/admissibility
 -> Facts locais/importados + Provenance/Evidence
 -> ValidationAssessment + EvidenceAdmissibilityAssessment
 -> coverage por dimensão/intervalo
 -> FactSnapshot -> Rules -> RuleResults -> EvaluationOutcome
```

O `NEXT-01` referencia os tempos, mas não implementa a seleção normativa completa do `NEXT-02`.

## 10. Mudança mínima futura

1. Derivar coverage dimensional/temporal de fatos, artefatos e gaps existentes.
2. Representá-la como fato derivado e/ou assessment consumível pelas Rules, sem aggregate novo.
3. Integrar importados ao fluxo Core de validação/admissibilidade.
4. Declarar coverage/admissibility na primeira Policy controlada.
5. Adicionar gate contra ausência material sem coverage.
6. Preservar assessments, inclusões, exclusões, gaps e reasons na Evaluation.
7. Não alegar completude universal ou reconhecimento oficial.

Persistência adicional só após mapear os repositórios Core. Novo conceito, mudança de ownership ou API incompatível exige interrupção e aprovação.

### 10.1 Decisão do segundo corte — contrato source-neutral

Dimensional coverage não pertence a `ReceivedTransferArtifact`. O artefato é uma possível fonte capaz de sustentar fatos, Provenance e contribuições temporais no fluxo de importação/admissibilidade; ele não é a única porta de entrada nem o dono da semântica dimensional.

```text
Source Artifact -> origem do material
Import/Assessment Contract -> entrada, limites, validation e admissibility
Coverage Contribution -> dimensão e intervalo para os quais contribui
```

O contrato inicial é de Application, neutro quanto à fonte e sem aggregate persistente novo. `ReceivedTransferArtifact` será o primeiro adapter concreto, sem impedir documentos, APIs, sistemas legados ou outras fontes aprovadas em incrementos futuros.

Invariantes adicionais:

1. Uma contribuição pode referenciar `ReceivedTransferArtifact`, mas não depende dele.
2. A existência de `ReceivedTransferArtifact` não implica coverage completa para dimensão alguma.
3. O adapter só produz contribuição dimensional quando recebe declaração explícita; não infere dimensão do intervalo genérico do artefato.
4. Coverage final pode resultar da união contínua de várias contribuições admissíveis.
5. Sobreposição não duplica coverage e lacunas temporais permanecem explícitas.
6. Nenhuma persistência nova é autorizada por esta decisão.

## 11. Arquivos candidatos — não autorizados neste pacote

- `packages/livestock_domain/transfer_artifact.py`
- `packages/livestock_domain/imported_fact.py`
- `packages/livestock_application/fact_provider.py`
- `packages/livestock_application/market_eligibility.py`
- contratos Core de Rule/Policy, validation, admissibility e Evaluation;
- persistência/migrations/API somente se a implementação provar necessidade;
- testes e `apps/validacao`.

## 12. Invariantes

1. Não persistir `eligible` no Animal.
2. Não criar coverage absoluta/booleana universal.
3. Não converter ausência em fato negativo sem coverage suficiente.
4. Infrastructure não decide admissibilidade.
5. `ConfidenceLevel` não é score universal.
6. Não ampliar `ValidationScope`.
7. Conhecimento posterior não entra em reprodução anterior.
8. Não alterar Evaluation/Decision histórica.
9. `HistoryCoverage` não declara verdade, completude ou autoridade.
10. Não codificar mercado real sem base/autoridade aprovadas.
11. Não mover conceito Livestock ao Core por antecipação.
12. Policy não pode omitir coverage quando depende de ausência.

## 13. Aceite futuro

- duas Policies sobre o mesmo snapshot podem exigir dimensões e produzir resultados diferentes;
- identidade/movimentação cobertas não cobrem tratamentos;
- coverage parcial identifica intervalo/dimensão faltantes;
- falta obrigatória produz indeterminação com reason estável;
- coverage permite avaliar, mas não força resultado favorável;
- inacessível é distinto de ausente;
- fato posterior ao corte não completa coverage histórico;
- fato local/importado preserva origem e escopo admissível;
- restrições são propagadas;
- rejeição por Policy não altera `VerificationStatus`;
- indisponibilidade não vira rejeição;
- conflito produz indeterminação/revisão conforme Policy;
- nova Evidence gera novo assessment/snapshot/Evaluation;
- isolamento por Organization é provado.

## 14. Policy fictícia controlada aprovada para o incremento

| Decisão | Conteúdo aprovado |
|---|---|
| Policy | `SANITARY_TEST_A_v1` |
| finalidade | demonstrar ausência conhecida de tratamento antimicrobiano nos 90 dias anteriores ao `reference_time` |
| Subject | Animal |
| dimensão | `treatment_history` |
| intervalo | `[reference_time - 90 dias, reference_time]` |
| escopo | ocorrências de tratamento antimicrobiano aplicadas ao Animal |
| fontes aceitas | `TreatmentApplication` local; fato importado acompanhado de `source_artifact_id` |
| validação | registro local estruturado ou importação estruturalmente vinculada ao artefato recebido |
| admissibilidade | fonte local estruturada e importada documentada são admissíveis; declaração sem artefato é insuficiente |
| conflitos | `INDETERMINADA` |
| coverage ausente/parcial/inacessível | `INDETERMINADA` |
| coverage completa + tratamento encontrado | `NAO_ATENDIDA` |
| coverage completa + nenhum tratamento encontrado | `ATENDIDA` |
| tolerâncias | nenhuma |

Esta Policy é exclusivamente técnica e fictícia. Não representa mercado, legislação, recomendação clínica, proibição material de medicamento ou autorização de exportação.

## 15. Portão

**LIBERADO PARA O PRIMEIRO CORTE INTERNO DO NEXT-01.**

A liberação é limitada à Policy fictícia da seção 14, dados fictícios, avaliação derivada sem persistência adicional e sem API nova. Mudança arquitetural, de domínio Core, segurança, migration ou API pública permanece bloqueada por aprovação própria.

## 16. Verificação futura

- testes unitários e de aplicação com duas Policies;
- PostgreSQL/RLS se houver persistência;
- API positiva, negativa, autorização e erro se houver API;
- teste arquitetural Core → Livestock;
- roteiro em `apps/validacao` sem copiar IDs, com request/response, propósito, preflight e `--pausar`;
- checklist, diff e riscos;
- suíte completa: `pytest`, `ruff check`, `ruff format --check`, `mypy`, `alembic check` via `python -m uv run --locked`.

## 17. Riscos

- falsa completude ao colapsar dimensões;
- taxonomia excessiva antes da primeira Policy;
- duplicação de gap, RuleResult e DecisionReason;
- aceitar importado por origem/confiança sem admissibilidade;
- persistir projeção como verdade;
- misturar `NEXT-01` com `NEXT-02`;
- percentuais sem denominador;
- overclaim oficial.

## 18. Próxima etapa

O primeiro corte interno foi implementado em `packages/livestock_application/sanitary_test_coverage.py`, sem persistência ou API. A suíte de referência em `tests/livestock_application/test_sanitary_test_coverage.py` prova os três resultados centrais e as lacunas controladas.

O segundo corte implementa `packages/livestock_application/dimensional_coverage.py`: contrato source-neutral, composição determinística de intervalos e adapter explícito de `ReceivedTransferArtifact`. `tests/livestock_application/test_dimensional_coverage.py` prova fonte sem artefato, artefato sem inferência, união contínua, lacuna preservada e consumo pela Policy fictícia.

A ampliação para persistência/API de coverage dimensional exige novo corte aprovado. O artefato de transferência atual continua com intervalo genérico e não é presumido como coverage de tratamentos. `NEXT-02`, `NEXT-03` e `NEXT-05` permanecem fora do escopo.
