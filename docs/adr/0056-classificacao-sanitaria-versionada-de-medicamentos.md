# ADR-0056 — Classificação sanitária versionada de medicamentos

**Status:** ACEITA
**Data:** 12 de agosto de 2026
**Aceita em:** 12 de agosto de 2026, com ajustes incorporados
**Decisores:** responsável pelo produto e arquitetura do Titan

## 1. Contexto

O `NEXT-01` já consegue registrar e compor coverage dimensional de histórico de tratamentos. A Policy fictícia `SANITARY_TEST_A_v1` precisa responder se existe tratamento antimicrobiano em uma janela de 90 dias, mas o cadastro atual de `Medication` distingue somente `PHARMACOLOGICAL` e `IMMUNOBIOLOGICAL` por meio de `MedicationProductClass`.

Essa classe geral não permite concluir se um produto é antimicrobiano. Tratar todo produto farmacológico como antimicrobiano geraria falsos positivos; tratar produto sem classificação como não antimicrobiano converteria ausência de conhecimento em fato negativo.

Além disso, uma classificação pode vir de cadastro técnico, documento do fabricante, catálogo oficial, integração externa ou curadoria aprovada. A origem, a validade e o conhecimento disponível podem mudar sem que o histórico de `Medication`, `TreatmentApplication`, `Evaluation` ou `Decision` seja reescrito.

## 2. Problema

Definir o menor contrato que permita:

- afirmar, com proveniência, que uma classificação sanitária se aplica ou não a um medicamento;
- distinguir classe geral do produto de categoria sanitária contextual;
- selecionar classificação por `reference_time` e `knowledge_cutoff`;
- manter fonte, validação, confiança e admissibilidade separadas;
- produzir `INDETERMINATE` quando a classificação material estiver ausente, conflitante, inacessível ou inadmissível;
- integrar tratamentos locais e importados à `SANITARY_TEST_A_v1` sem inventar taxonomia universal.

## 3. Precedentes e reaproveitamento

Esta decisão deve reutilizar, e não duplicar:

- **ADR-0011:** fonte normativa, interpretação aprovada, vigência e `NormativeBasisSnapshot` permanecem separadas da classificação factual;
- **ADR-0015:** Provenance, ValidationAssessment, ConfidenceAssessment e EvidenceAdmissibilityAssessment são dimensões distintas; origem não implica verdade;
- **ADR-0020:** adapters externos traduzem contratos, mas não decidem confiança, admissibilidade ou regra de negócio;
- **ADR-0043:** mudança de regra ou classificação não reescreve resultados publicados;
- **ADR-0045:** padrão `SourceArtifact` + Assertion bitemporal, confiança computada e ausência que nunca vira negação automática;
- **ADR-0049:** Policy publicada escolhe requisitos aplicáveis; dado técnico não se torna norma por estar cadastrado;
- **ADR-0051:** Evaluation preserva snapshot canônico e hashes das versões efetivamente utilizadas;
- **ADR-0052:** tempo válido e tempo de conhecimento são selecionados separadamente.

`MedicationProductClass` será preservada. Ela responde à classe geral do produto e não será reinterpretada como categoria terapêutica ou sanitária.

## 4. Alternativas consideradas

### 4.1 Acrescentar `ANTIMICROBIAL` a `MedicationProductClass`

Rejeitada. Mistura eixos diferentes e tornaria as opções indevidamente exclusivas: um antimicrobiano também pode ser farmacológico.

### 4.2 Adicionar `is_antimicrobial: bool` a `Medication`

Rejeitada. Um booleano não preserva fonte, autoridade, validade, conhecimento, conflito ou versão. `False` ainda confundiria negação demonstrada com classificação ausente.

### 4.3 Classificar pelo texto de `active_ingredient`

Rejeitada. Correspondência textual não constitui classificação aprovada, é sensível a sinônimos, composição e mudanças de catálogo e não oferece autoridade ou reprodução histórica.

### 4.4 Fazer a Policy manter uma lista embutida de medicamentos

Rejeitada como modelo principal. Duplicaria catálogo em cada Policy e confundiria fato técnico versionado com requisito normativo. A Policy pode declarar quais categorias aceita ou exige, mas não deve ocultar a origem da classificação de cada produto.

### 4.5 Assertion sanitária versionada e source-neutral

Proposta. Reutiliza o padrão comprovado pela ADR-0045, mantém a classificação fora da identidade intrínseca de `Medication` e permite fontes locais ou externas sem acoplar o domínio a um provider.

## 5. Decisão proposta

Introduzir na vertical Livestock o conceito `MedicationSanitaryClassificationAssertion` como afirmação imutável e bitemporal de que uma categoria sanitária se aplica, não se aplica explicitamente ou permanece desconhecida para um `Medication` em escopo delimitado.

O nome é conceitual até a aceitação desta ADR e a atualização formal dos documentos de domínio aplicáveis.

Contrato conceitual mínimo:

```text
MedicationSanitaryClassificationAssertion
  assertion_id
  record_owner_organization_id
  medication_id
  category_code
  asserted_status
  valid_from / valid_to
  observed_at / recorded_at
  source_reference
  validation
  confidence
  limitations
```

Para o primeiro incremento, a única categoria material será `ANTIMICROBIAL`. Isso não cria uma taxonomia terapêutica universal nem autoriza categorias futuras sem caso de uso aprovado.

Estados conceituais:

- `APPLIES`: a fonte afirma que a categoria se aplica;
- `DOES_NOT_APPLY`: a fonte afirma explicitamente que a categoria não se aplica;
- `UNKNOWN`: o material não sustenta nenhuma das duas conclusões.

Ausência de Assertion não equivale a `DOES_NOT_APPLY`.

Os três estados epistemológicos permanecem distintos:

```text
NO_ASSERTION != UNKNOWN ASSERTION != DOES_NOT_APPLY
```

`NO_ASSERTION` é lacuna de classificação; `UNKNOWN` é uma afirmação existente de indeterminação; `DOES_NOT_APPLY` é negação explícita sustentada por fonte admissível.

O conceito permanece específico do Livestock. Se um segundo domínio demonstrar a mesma semântica, o padrão poderá ser avaliado para promoção a uma abstração genérica de classificação factual versionada. Nenhuma generalização é autorizada agora.

## 6. Fonte, validação e admissibilidade

A Assertion referencia uma fonte por contrato source-neutral. A primeira implementação pode usar cadastro manual auditado ou artefato já existente, mas a semântica não pertence a `ReceivedTransferArtifact`, documento, API ou provider específico.

A existência da fonte demonstra apenas de onde veio a afirmação. Validação, confiança e admissibilidade continuam resolvidas separadamente conforme ADR-0015:

```text
source material
    -> classification assertion
    -> validation / confidence
    -> Policy admissibility
    -> temporal selection
    -> treatment classification used by Evaluation
```

O cliente não escolhe confiança efetiva nem autoridade. Informação externa autenticada não se torna automaticamente admissível. A Policy declara quais estados, fontes, níveis de suporte e limitações aceita para sua finalidade.

## 7. Temporalidade e histórico

A seleção deve combinar:

```text
classificação válida em reference_time
                  +
classificação conhecida até knowledge_cutoff
                  -> classificação temporalmente elegível
```

Nova classificação, correção, conflito ou conhecimento posterior cria nova Assertion ou relação explícita. Não altera `Medication`, `TreatmentApplication`, Evaluation ou Decision históricos.

Uma reprodução histórica usa somente Assertions elegíveis no corte original. Uma auditoria retrospectiva pode usar conhecimento posterior, desde que declare essa finalidade e produza nova Evaluation.

## 8. Relação com Policy e base normativa

A Assertion responde: “qual classificação foi afirmada para este medicamento, por qual fonte e em qual período?”.

A Policy responde: “essa classificação é admissível e qual efeito ela produz para esta finalidade?”.

Uma base normativa ou catálogo externo pode fundamentar a classificação ou a regra, mas os papéis não são intercambiáveis:

- fonte técnica não executa Rule;
- `NormativeBasis` não substitui a Assertion do medicamento;
- Assertion não determina sozinha elegibilidade;
- integridade ou assinatura não prova reconhecimento oficial.

Quando uma classificação depender de interpretação normativa, a versão utilizada deve integrar o `NormativeBasisSnapshot` ou a Provenance preservada pela Evaluation, conforme sua função no caso concreto.

## 9. Integração controlada com `SANITARY_TEST_A_v1`

Para cada `TreatmentApplication` dentro da janela exigida:

1. resolver `MedicationBatch -> Medication`;
2. selecionar a Assertion `ANTIMICROBIAL` temporalmente elegível;
3. avaliar validação, conflito e admissibilidade para a Policy;
4. classificar o tratamento como antimicrobiano somente quando existir `APPLIES` admissível;
5. considerar não antimicrobiano somente quando existir `DOES_NOT_APPLY` explícito e admissível;
6. produzir gap de classificação e resultado `INDETERMINATE` quando algum tratamento material permanecer sem classificação suficiente.

Coverage completa de tratamentos não implica coverage completa de classificação de medicamentos. As duas dimensões precisam estar satisfeitas para uma conclusão baseada em ausência.

## 10. Invariantes

1. `MedicationProductClass.PHARMACOLOGICAL` não implica `ANTIMICROBIAL`.
2. Ausência de classificação não implica `DOES_NOT_APPLY`.
3. `DOES_NOT_APPLY` exige afirmação negativa explícita e admissível.
4. Categoria sanitária não é propriedade absoluta e atemporal de `Medication` no modelo do Titan.
5. Fonte, validação, confiança, admissibilidade e verdade material permanecem distintas.
6. O cliente não declara confiança efetiva nem autoridade.
7. Mudança de classificação não reescreve TreatmentApplication, Evaluation ou Decision anterior.
8. Seleção histórica declara `reference_time` e `knowledge_cutoff`.
9. Conflito material de classificações não é resolvido por “último registro vence”.
10. Coverage de histórico de tratamentos e suficiência da classificação são dimensões separadas.
11. A Policy, não a Assertion isolada, determina o efeito sobre a Evaluation.
12. A primeira entrega suporta somente a categoria necessária a `SANITARY_TEST_A_v1`.

## 11. Primeiro incremento proposto

Após aceitação da ADR:

1. atualizar o documento de domínio aplicável com a nova Assertion e invariantes;
2. implementar contrato de aplicação source-neutral e persistência append-only com RLS;
3. disponibilizar registro e consulta auditáveis sem provider externo;
4. selecionar Assertion por `reference_time` e `knowledge_cutoff`;
5. adaptar `TreatmentApplication` para `AntimicrobialTreatmentRecord` somente após classificação admissível;
6. compor a suficiência de `medication_classification` como dimensão independente, sem alterar a semântica da coverage de `treatment_history`;
7. provar `ATENDIDA`, `NAO_ATENDIDA` e `INDETERMINADA` sem alterar resultados históricos;
8. entregar roteiro executável em `apps/validacao` e atualizar o checklist.

Ficam fora desse incremento:

- catálogo oficial ou mercado real;
- importação automática de provider;
- taxonomia completa de antibióticos, antiparasitários, vacinas ou classes farmacológicas;
- alteração de `MedicationProductClass`;
- `NEXT-02`, `NEXT-03` e `NEXT-05`;
- reconhecimento por autoridade externa.

## 12. Testes de aceitação previstos

- farmacológico sem Assertion -> `INDETERMINATE`, nunca antimicrobiano automático;
- `APPLIES` admissível dentro do corte -> tratamento antimicrobiano encontrado;
- `DOES_NOT_APPLY` explícito e admissível -> tratamento não contado como antimicrobiano;
- ausência de Assertion -> gap de classificação;
- Assertion conhecida depois do corte não entra em reprodução histórica;
- Assertion retroativa pode entrar em auditoria retrospectiva declarada;
- conflito material -> `INDETERMINATE`;
- fonte inacessível, não validada ou rejeitada pela Policy -> `INDETERMINATE`;
- classificação de outra Organization não atravessa RLS;
- nova versão não altera Evaluation histórica;
- coverage completa de tratamento com classificação incompleta continua inconclusiva.

## 13. Consequências

### Positivas

- evita falsos positivos e falsos negativos sanitários;
- reutiliza padrões temporais e de proveniência já aceitos;
- permite evolução para documentos e integrações sem acoplamento ao primeiro caso;
- preserva reprodução histórica e explicabilidade.

### Negativas

- exige curadoria ou fonte de classificação antes de conclusão automática;
- acrescenta seleção bitemporal e gaps próprios;
- aumenta o material que deve integrar snapshot e Dossier futuro.

## 14. Decisão registrada

O decisor confirmou:

1. a classificação será uma Assertion versionada, não campo booleano em `Medication`;
2. o primeiro escopo terá somente `category_code=ANTIMICROBIAL`;
3. ausência ou insuficiência produzirá `INDETERMINATE`;
4. `DOES_NOT_APPLY` dependerá de negação explícita admissível;
5. o primeiro adapter será cadastro manual auditado/source-neutral, sem catálogo externo;
6. a integração com `SANITARY_TEST_A_v1` ocorrerá somente depois da atualização formal do domínio.

## 15. Estado de implementação

A implementação do primeiro corte está autorizada após a atualização formal do domínio. Catálogo externo, taxonomia genérica e mercados reais permanecem fora do escopo.
