# NEXT-02 — Policy temporal e NormativeBasisSnapshot

**Artifact ID:** `NEXT-02-DP-v1`
**Data:** 12 de agosto de 2026
**Estado:** PROPOSTO PARA REVISÃO HUMANA
**Escopo:** desenho; nenhuma implementação autorizada por este documento

## 1. Objetivo

Provar, com duas versões inteiramente fictícias de uma Policy, que o Titan:

- seleciona a versão aplicável usando `reference_time` e `knowledge_cutoff` distintos;
- preserva a fundamentação normativa exata utilizada;
- produz `Evaluation` histórica imutável;
- não projeta Policy ou conhecimento posterior sobre avaliação anterior;
- não cria um segundo motor, uma segunda Policy ou um modelo específico de mercado.

## 2. Caso controlado

```text
Policy code: MARKET_TEST_A
Purpose: market-test-a

Version 1
  valid_from: 2026-01-01T00:00:00Z
  valid_to:   2026-07-01T00:00:00Z

Version 2
  valid_from: 2026-07-01T00:00:00Z
  valid_to:   ausente
```

Os intervalos são semiabertos `[valid_from, valid_to)`. Logo:

```text
reference_time = 2026-05-01 -> Version 1
reference_time = 2026-08-01 -> Version 2
reference_time = 2026-07-01 -> Version 2, nunca ambas
```

As versões podem possuir Rules fictícias diferentes para demonstrar mudança de resultado. Nenhum nome de país, autoridade, requisito real de exportação ou alegação regulatória será utilizado.

## 3. Documentos de autoridade

O desenho reutiliza:

- `DOMAIN.md`: `Policy`, `Rule`, `NormativeBasis`, `NormativeBasisSnapshot`, `Evaluation` e operações históricas;
- ADR-0011: fonte normativa, interpretação, vigência e fotografia normativa;
- ADR-0043: governança e linha do tempo imutável de Rules;
- ADR-0048: separação entre Evaluation e Decision;
- ADR-0049: perfil/finalidade não é fonte paralela de Rules;
- ADR-0050: execução determinística;
- ADR-0051: `snapshot_hash` e `context_hash` complementares;
- ADR-0052: tempo válido e tempo de conhecimento distintos.

Não é necessária nova ADR para o primeiro corte: os conceitos e invariantes já estão aprovados. Se a implementação revelar nova autoridade normativa, retroatividade, mudança incompatível de API ou novo conceito central, ela deve parar para decisão própria.

## 4. Estado atual comprovado

### 4.1 Reutilizável

- `Policy` possui identidade por versão, status, `valid_from`, `valid_to`, `created_at` e `published_at`.
- `PolicyService` cria, publica, versiona e substitui Policies.
- `TransactionalPolicyRepository.get_active_at()` já seleciona por código e vigência.
- `FactSnapshot` preserva `reference_time`, `knowledge_cutoff`, limitações temporais e exclui Facts conhecidos depois do corte.
- `Evaluation` preserva `policy_id`, `policy_version`, Rules/versões, `snapshot_hash`, `context_hash`, resultado e snapshot factual completo.
- `TransactionalEvaluationRepository` é append-only.
- `HistoricalReproductionService` recalcula hashes e resultados sem alterar Evaluation original.

### 4.2 Lacunas reais

1. `get_active_at()` recebe somente um instante e não distingue `reference_time` de `knowledge_cutoff`.
2. O fim de vigência é consultado hoje com `valid_to >= at_time`; a ADR-0052 exige fim exclusivo (`at_time < valid_to`).
3. A consulta escolhe `ORDER BY version DESC LIMIT 1`; sobreposição ou ambiguidade é escondida em vez de produzir razão controlada.
4. Policy não possui contrato explícito de disponibilidade contextual de conhecimento. No caso controlado, `published_at` pode demonstrar quando uma Policy criada dentro do Titan tornou-se utilizável, mas isso não deve ser generalizado para conhecimento de norma externa.
5. Embora `DOMAIN.md` exija finalidade em Policy, a classe e a tabela atuais não possuem `purpose`; hoje a finalidade entra apenas na Evaluation e no `context_hash`.
6. `NormativeBasis`, `NormativeReference` e `NormativeBasisSnapshot` existem no domínio e nas ADRs, mas ainda não possuem modelo implementado/persistido no fluxo de Evaluation.
7. `compute_context_hash()` cobre Policy, Rules, finalidade e motor, mas não recebe fotografia normativa.
8. `Evaluation` e sua tabela não preservam `NormativeBasisSnapshot`.
9. `Policy.publish()` e `create_next_version()` não impedem intervalos sobrepostos nem garantem continuidade; esse controle precisa ocorrer no caso de uso de publicação/seleção.

## 5. Perguntas respondidas pelo desenho

### 5.1 Qual Policy era aplicável à realidade examinada?

Responder com `reference_time`, vigência semiaberta, finalidade, Organization, código e estado publicado/substituído.

### 5.2 Qual Policy podia ser conhecida e utilizada no corte declarado?

Responder com `knowledge_cutoff` e disponibilidade demonstrável. Para Policies internas do caso fictício, `published_at` será o primeiro instante de conhecimento utilizável. Uma Policy publicada depois do corte não participa, ainda que declare vigência retroativa.

### 5.3 Qual fundamentação foi usada?

Responder com um `NormativeBasisSnapshot` tipado, imutável e incorporado ao contexto da Evaluation. Código e versão isolados não bastam.

### 5.4 Uma mudança posterior altera o passado?

Não. Nova Policy, Rule, base, referência ou conhecimento produz novo contexto e nova Evaluation. Evaluation e Decision antigas permanecem byte a byte inalteradas.

## 6. Contrato de seleção temporal

Criar em Application um resolvedor explícito, conceitualmente:

```text
PolicySelectionRequest
  organization_id
  policy_code
  purpose
  reference_time
  knowledge_cutoff

PolicySelectionResult
  selected_policy | none
  candidates
  outcome
  reason_codes
  reference_time
  knowledge_cutoff
  temporal_rule_version
  limitations

PolicyTemporalCandidate
  policy
  purpose
  known_at
  knowledge_basis
```

Resultados mínimos:

- `SELECTED`;
- `NOT_FOUND` com `POLITICA_APLICAVEL_AUSENTE`;
- `AMBIGUOUS` com `MULTIPLAS_POLITICAS_APLICAVEIS`;
- `TEMPORAL_GAP` com `LACUNA_TEMPORAL`.

Critério do caso controlado:

```text
published_at <= knowledge_cutoff
valid_from <= reference_time
valid_to is null OR reference_time < valid_to
status in {PUBLISHED, SUPERSEDED}
organization, code e purpose compatíveis
```

O resolvedor retorna ambiguidade; nunca escolhe silenciosamente maior versão, data mais recente ou primeira linha do banco.

`published_at` é usado como conhecimento somente porque as duas Policies fictícias são publicadas dentro do próprio Titan. Fonte normativa externa, captura tardia, disponibilidade por audiência ou conhecimento contextual exigem contrato adicional já previsto na ADR-0052 e não serão simulados como resolvidos neste corte.

Como `Policy` persistida ainda não possui `purpose`, o Corte 1 recebe candidatos tipados de Application contendo `Policy`, finalidade controlada e `known_at`. Esse DTO não é entidade, aggregate, fonte de Rules ou persistência paralela: é a entrada explícita do resolvedor puro. O adapter persistente e eventual inclusão de `purpose` em Policy somente serão decididos no Corte 3, com evidência do primeiro corte.

## 7. NormativeBasis controlada

Cada versão de `MARKET_TEST_A` referencia uma base fictícia própria:

```text
NormativeBasis TEST-BASIS-A/v1 -> Policy MARKET_TEST_A/v1
NormativeBasis TEST-BASIS-A/v2 -> Policy MARKET_TEST_A/v2
```

O material deve ser rotulado como `INTERNAL_TEST`, sem oficialidade ou autoridade externa alegada.

Contrato mínimo de implementação:

```text
NormativeBasis
  normative_basis_id
  organization_id
  code
  version
  purpose
  jurisdiction
  intended_use
  interpreted_by
  approved_by
  approval_authority
  approved_at
  valid_from / valid_until
  status
  references[]
  limitations[]
  supersedes_id | none
```

`NormativeReference` mínima deve preservar identidade, versão, dispositivo opcional, digest e classificação de origem. Para o teste interno, o conteúdo será sintético e o digest será calculado sobre material canônico fictício.

## 8. NormativeBasisSnapshot

O snapshot é criado no instante da Evaluation a partir da base selecionada e nunca consulta estado futuro para se recompor.

Contrato mínimo:

```text
NormativeBasisSnapshot
  schema_version
  normative_basis_id / code / version
  policy_id / code / version
  rule_versions[]
  purpose
  jurisdiction
  intended_use
  reference_time
  knowledge_cutoff
  approved_by / approval_authority / approved_at
  references[]
    instrument identity/version
    provision
    digest/algorithm
    source classification
  applicability_conditions[]
  exceptions[]
  conflicts[]
  gaps[]
  limitations[]
  snapshot_digest
```

O snapshot não será um `dict` anônimo no domínio. Pode ser serializado em JSONB na persistência, mas sua construção, invariantes e canonicalização pertencem a tipo imutável e versionado.

## 9. Identidades criptográficas

- `snapshot_hash` continua identificando fatos, proveniência factual e tempos selecionados.
- `NormativeBasisSnapshot` participa de `context_hash`, pois altera a semântica aplicada.
- `context_hash` passa a incluir o digest canônico da fotografia normativa, além de Policy, Rules, finalidade e motor.
- `evaluation_hash` continua derivando transitivamente de `snapshot_hash` e `context_hash`; não duplica o conteúdo normativo.

Mudanças em ordem física, apresentação ou texto traduzido sem efeito semântico não alteram digest. Mudança de referência, dispositivo, versão, digest, aplicabilidade, exceção, conflito ou limitação material altera o snapshot normativo e o `context_hash`.

## 10. Persistência proposta

Primeiro corte mínimo:

1. tabelas protegidas e versionadas para `normative_bases` e referências necessárias ao caso controlado;
2. RLS e FORCE RLS por `RecordOwnerOrganization`;
3. coluna JSONB tipada/versionada `normative_basis_snapshot` em `evaluations`, ou tabela 1:1 append-only se a revisão de implementação demonstrar vantagem concreta;
4. digest e versão de schema explícitos;
5. migration aditiva e reversível, sem preencher snapshots históricos por inferência.

Evaluations legadas permanecem sem snapshot normativo e devem expor limitação `NORMATIVE_BASIS_SNAPSHOT_LEGACY_ABSENT`. Migration não cria base fictícia retroativa nem calcula fundamento que não foi preservado.

## 11. Fluxo de referência

```text
reference_time + knowledge_cutoff + purpose
                  ↓
         Policy temporal resolver
                  ↓
    exatamente uma Policy publicada
                  ↓
  NormativeBasis aplicável e conhecida
                  ↓
    NormativeBasisSnapshot canônico
                  ↓
 Facts temporais → FactSnapshot
                  ↓
 Policy + Rules + dois snapshots
                  ↓
              Evaluation
                  ↓
 persistência append-only / reprodução
```

## 12. Invariantes

1. `reference_time` e `knowledge_cutoff` são obrigatórios no novo fluxo.
2. Intervalos usam `[inicio, fim)`.
3. Policy conhecida depois do corte não participa de reprodução anterior.
4. Vigência retroativa não equivale a conhecimento retroativo.
5. Zero candidata não produz Policy sintética.
6. Duas candidatas não são resolvidas por ordenação de versão.
7. Policy publicada/substituída é imutável como conteúdo executável.
8. Rule executada pertence exatamente à Policy selecionada.
9. NormativeBasis, Policy e Rule permanecem conceitos distintos.
10. NormativeBasisSnapshot é tipado, versionado e imutável.
11. Fotografia normativa participa de `context_hash`, não de `snapshot_hash`.
12. Evaluation histórica não é atualizada quando Policy ou base muda.
13. Evaluation legada sem fotografia não ganha fundamento reconstruído artificialmente.
14. Material `INTERNAL_TEST` não é apresentado como norma oficial.
15. Selection failure não produz Evaluation positiva, negativa ou Decision.

## 13. Cenários de prova

### Cenário A — versão 1

```text
reference_time:   2026-05-01
knowledge_cutoff: 2026-05-01
resultado:        MARKET_TEST_A/v1
basis snapshot:   TEST-BASIS-A/v1
```

### Cenário B — versão 2

```text
reference_time:   2026-08-01
knowledge_cutoff: 2026-08-01
resultado:        MARKET_TEST_A/v2
basis snapshot:   TEST-BASIS-A/v2
```

### Cenário C — fronteira

Em `2026-07-01T00:00:00Z`, v1 está fora do intervalo e v2 está dentro. Exatamente uma Policy é selecionada.

### Cenário D — Policy posterior desconhecida

V2 declara `valid_from=2026-07-01`, mas só é publicada em 10/07. Uma avaliação com `reference_time=05/07` e `knowledge_cutoff=06/07` não usa v2. O resultado é lacuna, não fallback silencioso para v1 nem conhecimento retroativo.

### Cenário E — auditoria retrospectiva

Nova avaliação em 15/07 pode examinar `reference_time=05/07` com `knowledge_cutoff=15/07`, usando conhecimento posterior declarado. Ela não se apresenta como reprodução do que era conhecido em 06/07.

### Cenário F — ambiguidade

Duas Policies temporalmente elegíveis produzem `MULTIPLAS_POLITICAS_APLICAVEIS`; nenhuma Evaluation é emitida.

### Cenário G — imutabilidade

Depois de publicar v2 e sua base, Evaluation persistida com v1 mantém Policy, Rule versions, snapshot normativo, hashes e resultado originais.

### Cenário H — fotografia alterada

Mudar digest ou dispositivo da referência gera outro `NormativeBasisSnapshot` e outro `context_hash`, mesmo com os mesmos Facts.

## 14. Testes exigidos

- domínio: invariantes, canonicalização e digest do snapshot normativo;
- Application: seleção v1/v2, fronteira, lacuna, ambiguidade e conhecimento posterior;
- Evaluation: fotografia no `context_hash` e reprodução estável;
- persistência: round-trip completo e append-only;
- PostgreSQL: RLS/FORCE RLS e isolamento entre Organizations;
- compatibilidade: Evaluation legada sem backfill inventado;
- API, se exposta: autorização, erro controlado e cliente incapaz de escolher Policy/base autoritativa;
- roteiro em `apps/validacao`: cria dados fictícios, descobre IDs, mostra request/response, explica cada passo, preflight e `--pausar`;
- suíte integral: pytest, Ruff, format check, Mypy e Alembic check.

## 15. Cortes de implementação recomendados

### Corte 1 — seleção pura, sem migration/API

- corrigir semântica semiaberta em resolvedor novo;
- receber `reference_time` e `knowledge_cutoff` explicitamente;
- receber `PolicyTemporalCandidate` com finalidade e conhecimento explícitos, sem alterar ainda a persistência de Policy;
- provar v1, v2, fronteira, lacuna e ambiguidade com Policies fictícias em memória;
- não modificar ainda Evaluation persistida.

### Corte 2 — NormativeBasisSnapshot tipado

- implementar tipos mínimos e canonicalização;
- integrar digest ao `context_hash`;
- provar reprodução e mudança de identidade sem persistência nova.

### Corte 3 — persistência operacional

- migration/RLS;
- round-trip de base e snapshot na Evaluation;
- compatibilidade legada explícita;
- API/roteiro somente se necessários ao caso de uso aprovado.

Cada corte exige revisão antes do seguinte. Não implementar os três simultaneamente.

## 16. Fora do escopo

- mercado ou norma real;
- captura de site oficial ou provider externo;
- determinação jurídica de aplicabilidade;
- autoridade externa ou reconhecimento oficial (`NEXT-03`);
- Market Eligibility Dossier (`NEXT-05`);
- readiness, lote, impacto em massa ou reavaliação assíncrona;
- Odoo;
- segundo motor ou Policy agregadora;
- retroatividade jurídica genérica;
- UI de autoria normativa.

## 17. Riscos e controles

| Risco | Controle |
|---|---|
| selecionar maior versão silenciosamente | resultado explícito de ambiguidade |
| tratar `valid_to` como inclusivo | intervalo semiaberto e teste de fronteira |
| confundir publicação com conhecimento externo universal | uso limitado a Policy interna fictícia e limitação declarada |
| inventar fundamento para Evaluation legada | ausência explícita, sem backfill semântico |
| hash não mudar com a base | digest normativo no `context_hash` |
| base virar Rule | tipos e persistência separados |
| teste fictício parecer norma oficial | classificação `INTERNAL_TEST` e mensagens sem overclaim |
| misturar NEXT-02 com autoridade/dossiê | limites de escopo e cortes independentes |

## 18. Decisões humanas solicitadas

Para liberar somente o Corte 1, confirmar:

1. `published_at` será aceito como limite de conhecimento apenas para as Policies internas fictícias deste incremento;
2. ausência de Policy conhecida/aplicável produzirá erro de seleção controlado e nenhuma Evaluation;
3. ambiguidade nunca será resolvida por maior versão;
4. os intervalos de Policy serão semiabertos;
5. o Corte 1 será puramente de Application/testes, sem migration ou API;
6. persistência de `NormativeBasisSnapshot` ficará para revisão após a prova do resolvedor;
7. `PolicyTemporalCandidate` será contrato transitório de Application no Corte 1, não nova entidade persistida nem segunda fonte de Policy.

## 19. Portão

**AGUARDANDO REVISÃO HUMANA.**

Este documento não autoriza implementação. Após aprovação, apenas o Corte 1 estará liberado. Corte 2 e Corte 3 dependerão de revisão dos resultados do corte anterior.
