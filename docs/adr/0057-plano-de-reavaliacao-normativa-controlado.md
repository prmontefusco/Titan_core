# ADR-0057 — Plano de reavaliação normativa controlado

**Status:** PROPOSTA  
**Data:** 12 de agosto de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O NEXT-07 já identifica, para uma mudança sintética de Policy, quais Decisions históricas podem requerer reavaliação. O resultado é transitório: não inicia trabalho, não muda histórico e não prevê a conclusão futura.

Ainda não existe caso operacional real que determine volume, prioridade, audiência, autorização, janela de execução, regra de cancelamento ou forma de aprovação. Mesmo assim, é útil fixar o menor contrato que permita evoluir em poucos passos quando esse caso surgir.

## Problema

Definir como transformar um impacto potencial em trabalho assíncrono auditável sem:

- reescrever Decisions/Evaluations/Dossiers históricos;
- tratar publicação de Policy como gatilho automático;
- usar outbox, worker ou aceite técnico como autoridade normativa;
- confundir um plano com resultado da reavaliação;
- acoplar o mecanismo à vertical Livestock ou a um mercado.

## Decisão proposta

Quando um caso real for aprovado, introduzir um **NormativeReevaluationPlan** persistido e tenant-scoped, criado somente após revisão humana explícita de um `MarketChangeImpactAssessment` ou equivalente de outra vertical.

O plano é genérico de aplicação/Core: conhece Subjects, contexto normativo anterior/substituto, tempos, limites, estado e referências; não conhece Animal, mercado, SISBOV, Odoo ou conteúdo de Rules.

```text
Impact assessment (derivado)
        ↓ revisão humana
NormativeReevaluationPlan (persistido e auditável)
        ↓ itens idempotentes
Outbox / worker (transporte)
        ↓
nova Evaluation + nova Decision + novo Dossier, se emitíveis
```

Cada nova Evaluation e Decision permanece independente. O plano não atualiza nem substitui os registros que motivaram sua criação.

## Contrato futuro mínimo

```text
NormativeReevaluationPlan
  plan_id
  record_owner_organization_id
  purpose
  source_context_digest
  target_context_digest
  reference_time
  knowledge_cutoff
  recognition_boundary
  requested_by / approved_by / approved_at
  state
  limits (population, rate, retry policy)
  created_at / cancelled_at / completed_at

NormativeReevaluationPlanItem
  item_id
  plan_id
  subject_reference
  idempotency_key = subject + target context digest
  state / attempts / last_error
  source_decision_reference
  resulting_evaluation_reference / resulting_decision_reference
```

Estados iniciais propostos: `DRAFT`, `PENDING_APPROVAL`, `APPROVED`, `RUNNING`, `PAUSED`, `CANCELLED`, `COMPLETED`, `PARTIALLY_COMPLETED`, `FAILED`.

O plano só é operacional depois de `APPROVED`. Publicar uma Policy, detectar impacto ou criar plano nunca equivale a execução.

## Invariantes

1. Uma Decision histórica é imutável; nova Policy produz nova avaliação, nunca alteração retroativa.
2. Não existe execução sem contexto alvo completo e digest verificável.
3. Idempotência é por Subject + contexto alvo, não apenas por `plan_id`.
4. Falha de um item não conclui nem invalida os demais; estado parcial é explícito.
5. Cancelamento impede novos itens, mas preserva itens e resultados já emitidos.
6. Outbox/worker transportam comando aprovado; não confirmam resultado normativo ou reconhecimento externo.
7. O executor reconstrói OrganizationContext e autorização no consumo.
8. `INTERNAL_ONLY` permanece limite de reconhecimento até prova contextual de outro boundary.
9. O plano não cria autorização de exportação, reserva, transferência ou operação comercial.

## Alternativas descartadas

- **Reavaliar automaticamente ao publicar Policy:** mistura autoria normativa, impacto e execução; pode gerar volume e conclusões não aprovadas.
- **Guardar “resultado antes/depois” no plano:** o resultado futuro só existe após nova Evaluation/Decision; antecipá-lo criaria segunda verdade.
- **Usar somente um evento/outbox sem plano:** perde aprovação, limites, cancelamento, progresso e auditoria operacional.
- **Implementar aggregate genérico agora:** sem caso real, identidade, retenção e estados seriam especulativos.

## Cortes futuros

1. após um caso real, aceitar esta ADR e implementar somente plano + itens, RLS e aprovação, sem worker;
2. adicionar execução assíncrona idempotente via outbox/worker existente;
3. expor acompanhamento operacional derivado e, se necessário, API/roteiro manual;
4. estudar impacto multi-subject/Operation somente sob NEXT-04.

## Fora do escopo

- implementação agora; migration, API, worker ou novo contrato de broker;
- mercado real, SISBOV, GTA, Odoo, certificadora ou autoridade externa;
- política de prioridade comercial, preço, seleção de lote ou reserva;
- reavaliação em massa sem aprovação humana;
- resultado jurídico, autorização de exportação ou reconhecimento externo.

## Critérios para aceitação

Antes de aceitar, o primeiro caso real deve informar: vertical/finalidade, fonte da mudança, população, autoridade que aprova, taxa/limites, política de retry, regras de cancelamento, retenção e expectativa de apresentação operacional.
