# Políticas, Regras, Avaliação e Decisão Explicável

Este documento especifica como o **Titan Core** versiona políticas normativas, executa regras de forma determinística sobre fatos fornecidos por uma vertical e produz decisões explicáveis.

Três princípios atravessam o marco:

1. **O Core não conhece nenhuma vertical.** Fatos entram por uma porta; nenhum termo de pecuária, crédito ou saúde existe no núcleo.
2. **Lacuna nunca vira reprovação.** Dado ausente é pendência ou indeterminação, jamais descumprimento.
3. **Não existe conclusão sem justificativa.** Toda decisão carrega as razões que a sustentam.

---

## 1. Policy versionada (`PolicyService`)

### O que é?
Política de conformidade com ciclo de vida formal e imutabilidade estrita após a publicação.

### Para que serve?
Permitir reavaliar um caso antigo com a política vigente à época, sem anacronismo — a política de ontem continua existindo e executável.

### Como funciona?
```
DRAFT ──publish──► PUBLISHED ──supersede──► SUPERSEDED
  │                    │                        │
  └────────────────────┴──────revoke────────────┴──► REVOKED
```

Depois de publicada, a política **não é editada**. Mudanças produzem nova versão.

### Como utilizar no código Python:
```python
from packages.core_application.policy_service import PolicyService
from packages.core_infrastructure.persistence.policy import TransactionalPolicyRepository

service = PolicyService(repository=TransactionalPolicyRepository(connection=db_connection))

rascunho = service.create_draft(
    organization_id=org_id,
    code="pol-sanitaria-lotes",
    name="Política de Sanidade dos Lotes",
)
politica = service.publish_policy(rascunho.policy_id)
```

---

## 2. Rule versionada e condições declarativas (`RuleService`)

### O que é?
Regra pertencente a uma política, com severidade, fonte normativa, evidências exigidas, justificativa, ação corretiva e **condições declarativas**.

### Para que serve?
Expressar o que a norma exige de forma verificável e versionada, sem escrever código por regra.

### Como funciona?
A condição é **dado, nunca código**. Cada `RuleCondition` declara um tipo de fato, uma chave do payload, um operador e o valor esperado:

```python
from packages.core_domain.rule import ComparisonOperator, RuleCondition

RuleCondition(
    fact_type="sanitary.attestation",
    payload_key="result",
    operator=ComparisonOperator.EQUALS,
    expected_value="approved",
    description="Atestado sanitário deve estar aprovado",
)
```

Operadores disponíveis: `EQUALS`, `NOT_EQUALS`, `GREATER_THAN`, `GREATER_OR_EQUAL`, `LESS_THAN`, `LESS_OR_EQUAL`, `IN`, `NOT_IN`.

> Lógica normativa arbitrária **não** entra aqui: ela pertence ao motor Wasm versionado do ADR-0036. As condições declarativas cobrem o caso comum de forma auditável e determinística.

### Severidade (`SeverityLevel`)
`INFO`, `WARNING`, `CRITICAL`, `BLOCKING`. A severidade tem efeito real na decisão final (seção 6).

### Como utilizar no código Python:
```python
from packages.core_application.rule_service import RuleService
from packages.core_infrastructure.persistence.rule import TransactionalRuleRepository

service = RuleService(repository=TransactionalRuleRepository(connection=db_connection))

regra = service.create_rule(
    policy_id=politica.policy_id,
    organization_id=org_id,
    code="rule-exame-brucelose",
    name="Exame de Brucelose Obrigatório",
    severity=SeverityLevel.BLOCKING,
    required_evidence_types=("laudo_laboratorial",),
    conditions=(condicao,),
    corrective_action="Coletar e anexar o laudo laboratorial.",
)
```

---

## 3. Contrato de fatos da vertical (`FactProviderPort`)

### O que é?
A fronteira entre o Core e qualquer vertical. O Core **não lê o banco da vertical**: ele recebe um snapshot de fatos.

### Para que serve?
Manter o núcleo genérico e permitir que uma nova vertical seja integrada sem alterar uma linha do Core.

### Como funciona?
A vertical implementa `FactProviderPort.get_snapshot(...)` e devolve um `FactSnapshot` imutável com hash SHA-256 determinístico — **independente da ordem de inserção dos fatos**.

### Como integrar uma vertical:
```python
from packages.core_application.fact_service import FactProviderPort, FactService
from packages.core_domain.facts import Fact, FactSnapshot

class MeuProviderDaVertical(FactProviderPort):
    def get_snapshot(self, organization_id, target_id, at_time) -> FactSnapshot:
        fatos = [
            Fact.create(
                fact_type="sanitary.attestation",
                payload={"result": "approved"},
                observed_at=at_time,
                source_reference=referencia_da_evidencia,  # liga o fato à Evidence
            )
        ]
        return FactSnapshot.create(
            organization_id=organization_id,
            target_id=target_id,
            as_of=at_time,
            facts=fatos,
        )

snapshot = FactService(provider=MeuProviderDaVertical()).get_snapshot_for_evaluation(
    org_id, subject_id, instante
)
```

> Preencher `source_reference` é o que permite à decisão final **citar as evidências** que sustentam cada fato. Sem isso, a decisão perde rastreabilidade.

---

## 4. Execução de regra pura (`RuleEvaluationEngine`)

### O que é?
Motor determinístico: mesma regra e mesmo snapshot produzem sempre o mesmo resultado e o mesmo hash de entradas.

### Como funciona?
A avaliação segue esta ordem:

1. **Vigência** — regra fora do período resulta em `NAO_APLICAVEL`.
2. **Evidências exigidas** — tipo ausente no snapshot resulta em `PENDENTE`.
3. **Condições declaradas** — avaliadas na ordem de declaração.

Resultado de cada condição:

| Situação | Status |
|---|---|
| Todas satisfeitas | `ATENDIDA` |
| Alguma violada | `NAO_ATENDIDA` |
| Fato ausente | `PENDENTE` |
| Chave ausente ou tipo incomparável | `INDETERMINADA` |

**Precedência:** uma violação definitiva prevalece sobre lacunas, porque a conjunção já é falsa. Entre lacunas, pendência (acionável) precede indeterminação.

### Como utilizar:
```python
from packages.core_application.evaluation_service import RuleEvaluationEngine

resultado = RuleEvaluationEngine().evaluate(regra, snapshot)
print(resultado.status, resultado.reason, resultado.inputs_hash)
```

---

## 5. Agregação em Evaluation (`PolicyEvaluationService`)

### O que é?
Execução registrada de uma política inteira sobre um snapshot delimitado.

### Para que serve?
Manter a avaliação **reproduzível depois que os fatos mudarem**. Uma avaliação de janeiro continua explicável em dezembro.

### Como funciona?
A Evaluation preserva o **snapshot completo dos fatos**, não apenas seu hash. Guardar só o hash provaria que algo mudou, mas não permitiria reconstruir o que foi avaliado.

Resultado agregado (`EvaluationOutcome`): `CONDICOES_SATISFEITAS`, `CONDICOES_NAO_SATISFEITAS`, `INFORMACAO_INSUFICIENTE`, `EVIDENCIA_CONFLITANTE`, `VALIDACAO_EXTERNA_PENDENTE`, `REVISAO_HUMANA_NECESSARIA`, `INDETERMINADO`.

> **Ausência de regra aplicável nunca é conformidade.** Se nada foi efetivamente verificado, o resultado é `INDETERMINADO`, jamais `CONDICOES_SATISFEITAS`.

Apenas políticas `PUBLISHED` ou `SUPERSEDED` são executáveis. Rascunho nunca é avaliável; revogada não produz nova avaliação; substituída permanece executável para reavaliação histórica fiel.

### Como utilizar:
```python
from packages.core_application.evaluation_service import (
    PolicyEvaluationService, RuleEvaluationEngine,
)
from packages.core_infrastructure.persistence.evaluation import (
    TransactionalEvaluationRepository,
)

service = PolicyEvaluationService(engine=RuleEvaluationEngine())
avaliacao = service.evaluate_policy(
    policy=politica,
    rules=[regra],
    snapshot=snapshot,
    purpose="CONFORMIDADE_SANITARIA",
)

TransactionalEvaluationRepository(connection=db_connection).save(avaliacao)
assert avaliacao.is_reproducible()
```

---

## 6. Decision explicável (`DecisionService`)

### O que é?
Conclusão registrada derivada de uma Evaluation. **Não reavalia nada** — apenas traduz o resultado técnico em conclusão fundamentada.

### Como funciona?
`DecisionResult`: `APROVADA`, `REJEITADA`, `APROVADA_COM_RESTRICOES`, `INDETERMINADA`.

| Situação da Evaluation | Decisão |
|---|---|
| Condições satisfeitas | `APROVADA` |
| Descumprimento `BLOCKING` ou `CRITICAL` | `REJEITADA` |
| Descumprimento apenas `INFO` ou `WARNING` | `APROVADA_COM_RESTRICOES` |
| Informação insuficiente, conflito, revisão humana | `INDETERMINADA` |

Revisão necessária é **estado do processo, não resultado final** — por isso não existe como `DecisionResult`.

### Garantias
- **Nenhuma conclusão sem justificativa.** Garantido no domínio *e* no banco, por `CHECK (jsonb_array_length(reasons) > 0)`: nem escrita direta em SQL produz decisão muda.
- **Código de razão é contrato; mensagem é traduzível.** O digest inclui o código e ignora a mensagem, então traduzir não inverte a conclusão.
- **Evaluation adulterada não fundamenta decisão.** Conteúdo que não confere com o hash registrado é recusado.

### Como utilizar:
```python
from packages.core_application.decision_service import DecisionService
from packages.core_infrastructure.persistence.decision import TransactionalDecisionRepository

decisao = DecisionService().decide(avaliacao)

TransactionalDecisionRepository(connection=db_connection).save(decisao)

for razao in decisao.reasons:
    print(razao.code.value, razao.rule_code, razao.message, razao.corrective_action)
```

Códigos de razão (`DecisionReasonCode`): `REGRA_ATENDIDA`, `REGRA_NAO_ATENDIDA`, `EVIDENCIA_PENDENTE`, `REGRA_INDETERMINADA`, `REGRA_NAO_APLICAVEL`, `NENHUMA_REGRA_APLICAVEL`.

---

## 7. Fora de escopo neste marco

Permanecem no ADR-0016, previstos para etapas seguintes: `DecisionAuthorityProfile`, aprovações, método de emissão, `DecisionProposal`, override, contestação e revisão humana.

Três estados de `EvaluationOutcome` estão declarados no contrato mas **ainda não são produzidos**: `EVIDENCIA_CONFLITANTE` (depende do motor de incoerências do ADR-0035), `VALIDACAO_EXTERNA_PENDENTE` e `REVISAO_HUMANA_NECESSARIA`.
