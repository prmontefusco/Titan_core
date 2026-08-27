# ADR-0068 — Autoavaliação compartilhada: de quem é a Evaluation

**Data:** 27 de agosto de 2026 · **Estado:** PROPOSTA (aguarda decisão humana)

**Contexto:** BuyerPolicy Fase 2 (ADR-0065) e Fase 3 (ADR-0066). Bloqueia o Incremento 3
(composição com a matriz regulatória) e a conexão entre a Fase 2 e o Incremento 1 já entregue.

---

## Contexto

`POST /v1/rule-governance/policies/shared-policies/{policy_id}/evaluate` está publicado desde a
Fase 2 e **não avalia nada**. O corpo da rota, em `apps/api/policy_governance.py`, termina em:

```python
# TODO: Implementar avaliacao compartilhada com sujeitos de outra Organization
# Por enquanto, criar uma avaliacao stub que passe nos testes
evaluation_id = str(UUID(int=0))
```

Verificado contra a API real, com Organizations, grant e Policy contratual semeados:

```
POST /evaluate  subject_id="sujeito-que-nao-existe-em-lugar-nenhum"
  → 201  {"evaluation_id": "00000000-0000-0000-0000-000000000000",
          "outcome": "CONFORM", "rule_results": [], "evaluation_hash": ""}

POST /decisions  com esse mesmo evaluation_id
  → 422 IDENTIFICADOR_INVALIDO
```

Duas consequências, ambas materiais:

1. **A rota afirma conformidade contratual sobre um sujeito que não existe.** O `subject_id` do
   pedido não é lido por nenhuma avaliação; nenhuma `Rule` é executada; nenhuma `Evaluation` é
   persistida; `evaluation_hash` é vazio.
2. **A Fase 2 e o Incremento 1 não se conectam pela API pública.** O `evaluation_id` devolvido é o
   UUID nulo, recusado por `typed_id_or_problem` na rota de proposta. O roteiro
   `apps/validacao/buyerpolicy_shared_decision.py` só funciona porque cria a `Evaluation` direto no
   banco (passo 6), contornando a rota que deveria produzi-la.

O ledger, em NEXT-10, descrevia a Fase 2 como "IMPLEMENTAÇÃO COMPLETA E PRONTA PARA INTEGRAÇÃO —
compartilhamento bilateral `CONTRACT`, **autoavaliação de fornecedor**". A autoavaliação não foi
implementada.

## O que impede a implementação direta

Não é esquecimento: implementar a autoavaliação como a Fase 2 a descreve esbarra num invariante do
Core. Em `packages/core_application/evaluation_service.py`:

```python
if policy.organization_id != snapshot.organization_id:
    raise ValueError("A política e o snapshot devem pertencer à mesma Organization.")
...
return Evaluation(organization_id=policy.organization_id, ...)
```

Na autoavaliação compartilhada, a Policy é do **comprador** e o snapshot de facts é do
**fornecedor** — exatamente a combinação que o invariante recusa. E a `Evaluation` que o serviço
produz nasce sempre sob a Organization da Policy, isto é, do comprador.

O invariante não é isolado. O mesmo pareamento por Organization aparece em
`decision_service.py:104`, `decision_governance_service.py:98,190,221` e `idempotency.py:43`. É a
ADR-0002 (isolamento e propriedade por Organization) aplicada sistematicamente, não um detalhe de
implementação de um módulo.

## O conflito entre documentos de autoridade

A ADR-0065 decidiu duas coisas que puxam em direção oposta ao código atual:

> **Nota:** Resultado da avaliação compartilhada **não é** retornado ao comprador por esses
> endpoints. Comprador não ganha acesso indireto aos facts do fornecedor.

E o FieldScope mínimo (§7) bloqueia explicitamente "facts brutos" e "evidências brutas" da
contraparte.

Já o Incremento 1 da Fase 3, **como foi construído e aprovado**, pressupõe o contrário:
`SharedDecisionService.create_proposal` executa `set_organization_context(owner_organization_id)`
antes de buscar a `Evaluation`. Para achá-la, a `Evaluation` precisa pertencer ao comprador — e com
ela viaja o `FactSnapshot` do fornecedor.

Ou seja: **a propriedade da `Evaluation` compartilhada nunca foi decidida.** O stub adiou a decisão,
e o Incremento 1 foi construído sobre a suposição não escrita de que ela é do comprador.

## Alternativas

### Alternativa 1 — A Evaluation é do fornecedor (beneficiário)

O snapshot é do fornecedor, as Rules são do comprador, e a `Evaluation` nasce com
`organization_id = grant.beneficiary_organization_id`.

- **A favor:** é a única que preserva a Nota da ADR-0065 e o FieldScope §7 — decisões de privacidade
  já tomadas e justificadas. O fornecedor não entrega seu dataset ao avaliar-se.
- **Custo:** parametrizar explicitamente o invariante de `evaluate_policy` para o caso contratual
  compartilhado, registrando as duas Organizations envolvidas em vez de assumir uma só; e ajustar o
  `SharedDecisionService`, que hoje busca sob o contexto do comprador.
- **Pergunta que abre:** o que o comprador vê ao revisar uma proposta? Só a alegação do fornecedor e
  o `evaluation_hash`, sem o conteúdo da avaliação? Essa resposta precisa ser explícita, porque hoje
  o `SharedDecisionService` valida a existência da `Evaluation` como pré-condição da proposta.

### Alternativa 2 — A Evaluation é do comprador (owner)

Mantém `Evaluation.organization_id = policy.organization_id` e o Incremento 1 intacto.

- **A favor:** nenhum código do Core muda; o Incremento 1 passa a funcionar sem ajuste; a revisão do
  comprador tem substância.
- **Custo:** contraria diretamente a Nota da ADR-0065. O `FactSnapshot` do fornecedor passaria a
  viver sob a RLS do comprador — que é, literalmente, o acesso indireto aos facts que a ADR-0065
  decidiu bloquear. Exigiria emendar a ADR-0065 e refazer a análise de FieldScope.

### Alternativa 3 — A rota compartilhada não persiste Evaluation

Devolve `rule_results` calculados em memória, sem `evaluation_id` nem hashes persistidos.

- **A favor:** preserva os dois isolamentos sem tocar em invariante nenhum.
- **Custo:** quebra o contrato de resposta que a própria ADR-0065 especifica (`evaluation_id`,
  hashes) e deixa o Incremento 1 sem âncora — `SharedDecision` referencia uma `Evaluation` por
  construção, com FK no banco. Na prática, desfaz o Incremento 1.

## Recomendação

**Alternativa 1.** As decisões de privacidade da ADR-0065 são as mais caras de reverter e as que
protegem a parte mais exposta da relação — o fornecedor, que precisa avaliar-se contra o critério de
um comprador sem entregar seu rebanho junto. O custo da Alternativa 1 é técnico e contido:
tornar explícito, num ponto do Core, um pareamento que hoje é implícito, e ajustar um serviço
entregue há um dia.

A Alternativa 2 é mais barata hoje e mais cara depois: transforma uma decisão de privacidade
documentada em efeito colateral de RLS, num sistema cuja ordem de prioridade é
Corretude → Segurança → Auditoria.

## Decisão necessária

1. De quem é a `Evaluation` produzida pela autoavaliação compartilhada?
2. Se Alternativa 1: o que o comprador enxerga ao revisar uma `SharedDecision` — apenas a alegação e
   o hash, ou também o `outcome` agregado?

Enquanto isso não for decidido, o Incremento 3 (composição com a matriz regulatória) não deve ser
construído: compor um `composite_verdict` sobre um `CONFORM` constante produziria veredito com
metade contratual fabricada, e a trilha de acesso da ADR-0066 passaria a registrar composições sem
lastro.

## Referências

- ADR-0002 — Isolamento e propriedade por Organization
- ADR-0050 — Execução determinística e isolada de Policies e Rules
- ADR-0051 — Snapshot canônico, identidade criptográfica e proveniência
- ADR-0064 — BuyerPolicy Fase 1: autoavaliação privada
- ADR-0065 — BuyerPolicy Fase 2: compartilhamento contratual
- ADR-0066 — BuyerPolicy Fase 3 (docs/plans/BUYERPOLICY_FASE3_*)
