# NEXT-05 — Market Eligibility Dossier: Design Package

**Data:** 12 de agosto de 2026
**Estado:** CORTE 1 CONCLUÍDO
**Escopo:** primeiro dossiê verificável de elegibilidade de mercado, estritamente controlado e fictício.

## 1. Objetivo

Permitir que uma `Decision` de elegibilidade de mercado seja entregue como prova auditável e verificável, sem criar um novo tipo de dossiê, outro motor de decisão ou uma entidade paralela de elegibilidade.

O resultado responde somente:

> "Qual conclusão o Titan produziu para este sujeito, sob esta Policy e base normativa, neste instante e com este conhecimento?"

Ele não responde `EXPORT_ALLOWED`, não substitui autoridade pública, certificadora, importador, frigorífico ou autoridade sanitária e não promete reconhecimento externo.

## 2. Decisão proposta

**Reutilizar `Dossier`, `DossierService`, `VerticalSection`, `VerificationBundle` e `BundleManifest` existentes.**

O primeiro incremento estende a seção `livestock` do dossiê já existente para carregar a explicação de uma `Decision` de mercado. Não cria:

- `MarketEligibilityDossier` como aggregate ou entidade nova;
- tabela, migration, RLS ou repositório paralelos;
- `EligibilityGap` persistida;
- segundo motor de Policy/Rule;
- Decision composta sobre Animal e estabelecimento;
- integração SISBOV, Odoo ou mercado real.

O `Dossier` continua ancorado em **uma** `Decision`, **uma** `Evaluation`, **um** Subject e **uma** finalidade. Esta é uma invariante do incremento. A matriz comercial é uma projeção de leitura e não pode ser congelada como se fosse a própria decisão.

```text
FactSnapshot + NormativeBasisSnapshot
              + Evaluation + Decision
                         ↓
                 Dossier existente
                         ↓
        VerticalSection(namespace="livestock", v3)
                         ↓
        VerificationBundle existente, quando solicitado
```

## 3. Reuso confirmado no estado atual

| Necessidade | Mecanismo existente | Decisão para NEXT-05 |
|---|---|---|
| Identidade, imutabilidade e hash | `Dossier` / `DossierService` | Reusar sem mudar o envelope Core. |
| Conteúdo da vertical | `VerticalSection(namespace="livestock")` | Evoluir a seção Livestock de forma aditiva e versionada. |
| Policy, Rules, Facts e razões | Documento canônico já montado por `DossierService` | Não duplicar os mesmos dados sob outro formato. |
| Base normativa temporal | `Evaluation.normative_basis_snapshot` | Preservar o snapshot já associado à Evaluation; ausência legada permanece limitação explícita. |
| Cobertura e material importado | `LivestockDossierTemplate` | Reaproveitar a apresentação existente, sem atribuir completude inexistente. |
| Competência de Source | Fact controlado + limitation do snapshot do NEXT-03 | Expor somente a boundary já preservada; não alegar reconhecimento externo. |
| Verificação independente | `VerificationBundle` e `BundleManifest` | Reusar, sem manifesto de mercado paralelo. |

## 4. Conteúdo novo da seção Livestock

O primeiro corte acrescenta uma subseção `market_eligibility` dentro de `vertical.content`. Ela é suplementar: o documento Core permanece a fonte canônica para Decision, Evaluation, Rules, evidências e governança.

Forma conceitual:

```json
{
  "market_eligibility": {
    "market_profile": {
      "code": "MARKET_TEST_A",
      "profile": "STANDARD",
      "synthetic": true
    },
    "subject_scope": "animal",
    "evaluated_purpose": "livestock.market_eligibility.MARKET_TEST_A.STANDARD",
    "policy": {
      "policy_id": "...",
      "code": "MARKET_TEST_A",
      "version": 1,
      "valid_from": "...",
      "valid_to": null
    },
    "evaluation_context": {
      "reference_time": "...",
      "knowledge_cutoff": "...",
      "normative_basis_snapshot_status": "PRESERVED"
    },
    "authority_boundary": {
      "recognition_boundary": "INTERNAL_ONLY",
      "statement": "Titan decision; external recognition is not asserted."
    },
    "coverage": {
      "dimensions": [
        {"code": "treatment_history", "status": "COMPLETE", "interval": {"from": "...", "to": "..."}},
        {"code": "medication_classification", "status": "COMPLETE", "interval": {"from": "...", "to": "..."}}
      ]
    },
    "result_boundary": "MARKET_ELIGIBILITY_ASSESSMENT_NOT_EXPORT_AUTHORIZATION",
    "limitations": []
  }
}
```

O formato final não deve copiar novamente Policy, Rule, Fact, DecisionReason, Evidence ou `NormativeBasisSnapshot` completos: estes já estão no envelope canônico. A seção somente adiciona a leitura setorial necessária para um auditor entender a finalidade de mercado e seus limites. O exemplo positivo mostra coverage efetiva porque `treatment_history` e `medication_classification` são dimensões independentes; o construtor só expõe os contratos de coverage realmente presentes no snapshot, sem inventar dimensão ou completude.

### Regras de coerência

1. `evaluated_purpose`, Policy, Subject e Evaluation devem corresponder exatamente à `Decision` que ancora o Dossier.
2. Um resultado de matriz de outro mercado não pode entrar no documento.
3. Dependência de estabelecimento ou operação não é atribuída ao Animal. No primeiro corte, requisito com outro Subject é apresentado como dependência/limitação, nunca como aprovação do Animal.
4. `INDETERMINATE`, ausência de coverage, base normativa legada ausente e reconhecimento externo não demonstrado permanecem visíveis como lacunas.
5. Não existe campo booleano equivalente a `export_allowed`.
6. O dossiê histórico não muda quando uma Policy nova ou uma fonte nova passa a existir.
7. Todo Dossier de finalidade de mercado declara `MARKET_ELIGIBILITY_ASSESSMENT_NOT_EXPORT_AUTHORIZATION`: o resultado é uma avaliação Titan sob uma Policy, não autorização de exportação, habilitação oficial, certificação externa ou garantia de acesso ao mercado.
8. `gaps` permanecem nos fatos, resultados de Rule, `DecisionReason` e snapshot normativo que já os explicam. A subseção usa `limitations` exclusivamente para limites interpretativos da conclusão; não cria estrutura paralela para lacunas.

## 5. Primeiro caso de prova

O caso inicial é integralmente fictício e controlado:

```text
Subject: Animal A
Market profile: MARKET_TEST_A / STANDARD
Policy: MARKET_TEST_A v1
Requirement: sanitary_attestation
Authority boundary: INTERNAL_ONLY
Reference time: 2026-08-12T00:00:00Z
Knowledge cutoff: 2026-08-12T00:00:00Z
```

Ele deve provar ao menos:

1. dossiê para conclusão `SATISFIED`/Decision correspondente, com Policy e snapshot normativo coerentes;
2. lacuna de autoridade ou coverage produzindo conclusão indeterminada, sem linguagem de inelegibilidade nem autorização;
3. alteração material na boundary de reconhecimento altera a identidade do Dossier;
4. nova versão de Policy produz novo Dossier quando reavaliada, preservando o anterior;
5. `VerificationBundle` verifica o Dossier sem criar formato específico de mercado.
6. Policy satisfeita sob `INTERNAL_ONLY` declara a avaliação Titan como satisfeita, mas não alega reconhecimento por terceiro.
7. O mesmo Animal sob `MARKET_TEST_A` e `MARKET_TEST_B` produz dossiês distintos, e cada documento contém exclusivamente o seu próprio mercado, finalidade, Policy, Evaluation e Decision.

Nenhum nome de país, programa oficial, requisito de exportação ou integração externa entra neste caso.

## 6. Cortes propostos

### Corte 1 — seção vertical pura, sem API ou schema

- introduzir um construtor de seção de mercado que apenas aceita Decision/Evaluation/Policy coerentes;
- estender a seção `livestock` de modo aditivo e elevar sua versão somente se o contrato efetivamente mudar;
- preservar finalidade, tempos, snapshot normativo, coverage declarada e boundary de reconhecimento;
- testes unitários de coerência, indeterminação, não-overclaim e estabilidade do hash;
- não persistir nada novo nem alterar endpoints.

### Corte 2 — emissão controlada por uma Policy fictícia

- conectar o construtor ao caminho que já persiste Dossier para uma única Policy `MARKET_TEST_A`;
- garantir que o Dossier seja ancorado na Decision exata e não em uma matriz inteira;
- se houver alteração observável de API, atualizar OpenAPI, testes de integração e roteiro executável em `apps/validacao`;
- nenhum perfil real, integração externa ou conclusão de exportação.

### Corte 3 — bundle e apresentação derivada

- provar a entrega via `VerificationBundle` atual e a verificação independente;
- decidir, por evidência de uso, se o PDF Livestock precisa apenas renderizar a nova subseção;
- PDF permanece apresentação derivada e não vira o Dossier normativo.

## 7. Fora do escopo

- lote operacional e seleção de lote (NEXT-06);
- impacto e reavaliação em massa por mudança de Policy (NEXT-07);
- composição de Animal + estabelecimento + operação (NEXT-04, quando houver caso concreto);
- Policy ou mercado real;
- reconhecimento de autoridade externa;
- SISBOV, GTA, Odoo e quaisquer conectores externos;
- redaction seletiva, portal público, trust profile de produção ou PKI nova;
- persistência de `RequirementAuthorityAssessment`.

## 8. ADRs e contratos respeitados

- **ADR-0041:** elegibilidade é relação temporal entre Subject, finalidade e Policy; não é propriedade absoluta do Animal e não autoriza decisão comercial.
- **ADR-0044:** a matriz é derivada de leitura; seus estados não se confundem com `DecisionResult`.
- **ADR-0053:** competência da Source, autoridade de emissão de Decision e reconhecimento externo permanecem fronteiras distintas.
- **ADR-0055:** Dossier e bundle têm identidades próprias; hash e PDF isolados não significam autoridade, trust ou conformidade.
- **NEXT-01/02/03:** coverage é dimensional, snapshot normativo é histórico e a boundary de reconhecimento precisa sobreviver ao artefato.

## 9. Portão para autorizar somente o Corte 1

Antes de código, confirmar:

1. o primeiro perfil é `MARKET_TEST_A`, integralmente fictício;
2. a implementação estende somente a seção Livestock do `Dossier` existente;
3. o Dossier é ancorado em uma única Decision/Evaluation/Policy, e não na matriz calculada na leitura;
4. `INTERNAL_ONLY` é a única recognition boundary suportada no primeiro corte; ela delimita o escopo da afirmação ao Titan/Organization e não é selo de reconhecimento;
5. nenhuma API, migration, conector externo ou `DecisionAuthorityProfile` entra no Corte 1;
6. a seção declara explicitamente que a conclusão Titan não autoriza exportação nem implica reconhecimento externo.

Com essas confirmações, o próximo passo é implementar somente o Corte 1 e revisar o documento produzido antes de integrar qualquer endpoint ou mercado real.

## 10. Aprovação e registro de execução

**Design aprovado em 12 de agosto de 2026. Autorização: somente Corte 1.** Os refinamentos de revisão tornam explícitos a ancoragem em uma única Decision, coverage dimensional real no caso positivo, `result_boundary` como invariante, separação entre gaps e limitations e os casos de fronteira `INTERNAL_ONLY` e de isolamento entre `MARKET_TEST_A`/`MARKET_TEST_B`.

**CORTE 1 CONCLUÍDO EM 12 DE AGOSTO DE 2026.** `MarketEligibilityDossierSectionBuilder` em `packages/livestock_application/dossier_template.py` produz uma `VerticalSection` pura e versionada para um perfil sintético. Ele exige coerência exata entre Decision, Evaluation, Policy, Subject, finalidade e versão da Policy; só aceita `INTERNAL_ONLY`; lê `treatment_history` e `medication_classification` diretamente do snapshot quando declaradas; e fixa `MARKET_ELIGIBILITY_ASSESSMENT_NOT_EXPORT_AUTHORIZATION` como limite interpretativo. `limitations` da subseção contém somente limites próprios da Evaluation, enquanto coverage incompleta permanece exposta na dimensão já existente. Seis testes cobrem coverage completa/incompleta, boundary, isolamento de dois mercados sobre o mesmo Animal e recusas de coerência. Não houve integração ao template farmacológico existente, persistência, API, bundle, PDF, mercado real ou conector externo.
