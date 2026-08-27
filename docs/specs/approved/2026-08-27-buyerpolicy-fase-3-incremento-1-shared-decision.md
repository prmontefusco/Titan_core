# SPEC: BuyerPolicy Fase 3 Incremento 1 — SharedDecision para proposta e revisão bilateral

- **Nível:** CRITICAL
- **Estado:** aprovada
- **Decisão de Discovery:** PROCEED por decisão humana explícita em 2026-08-27, limitada a este incremento
- **Owner de produto:** Founder / Product Owner
- **Data:** 2026-08-27

## Problema e usuário

A BuyerPolicy Fase 2 permite que um comprador compartilhe uma Policy contratual e que o fornecedor faça autoavaliação dos próprios sujeitos. O resultado, porém, termina na Evaluation: o fornecedor não possui um canal estruturado para contestar, reconhecer limitação, anexar referências ou pedir revisão, e o comprador não possui uma resposta auditável dentro da mesma fronteira de compartilhamento.

Usuários afetados:

- fornecedor que recebe resultado `CONDICOES_NAO_SATISFEITAS` ou `INDETERMINADO` e precisa apresentar contexto;
- comprador que precisa revisar a proposta sem receber acesso amplo aos dados internos do fornecedor;
- auditor que precisa entender a sequência Evaluation → proposta → revisão sem inferir verdade material.

## Contexto e objetivo

Este incremento implementa somente o primeiro corte da BuyerPolicy Fase 3: uma trilha bilateral de `SharedDecision` vinculada a um `AuthorizationGrant` e a uma `Evaluation` já produzida pela Fase 2.

O objetivo observável é permitir que:

1. o fornecedor beneficiário de um grant ativo crie uma proposta vinculada a uma avaliação compartilhada;
2. o comprador owner do grant revise essa proposta com decisão estruturada;
3. ambas as partes listem o histórico dentro do escopo autorizado;
4. nenhuma Evaluation histórica seja alterada.

## Fora de escopo

- rate limiting e access log detalhado da Fase 3 Incremento 2;
- composição com matriz regulatória da Fase 3 Incremento 3;
- snapshot e acesso pós-expiração da Fase 3 Incremento 4;
- comprador avaliar sujeito do fornecedor unilateralmente;
- compartilhamento de fatos brutos do fornecedor;
- criação de `Decision` regulatória oficial ou `DecisionProposal` do Core;
- UI em `apps/web`;
- nova dependência externa, Redis/Valkey ou worker;
- alteração de `DOMAIN.md`, `ARCHITECTURE.md` ou contratos da Fase 2 fora do necessário para as rotas novas.

## Comportamento e regras de negócio

`SharedDecision` é um registro de governança da Policy compartilhada, não uma decisão regulatória oficial. Ela referencia uma `Evaluation` imutável e preserva o diálogo estruturado entre beneficiary e owner do grant.

Regras:

- apenas a Organization beneficiária do grant pode criar proposta;
- apenas a Organization owner do grant pode revisar;
- a proposta exige grant ativo, não expirado, Policy vinculada ao grant e Evaluation pertencente ao fluxo compartilhado;
- revisar proposta já revisada retorna conflito;
- resposta externa para terceira Organization deve continuar uniforme, sem revelar existência de grant, Policy, Evaluation ou proposta inacessível;
- `proposal_evidence_references` são referências opacas controladas, não payload bruto, token, segredo ou dado pessoal arbitrário;
- `record_owner_organization_id` da `SharedDecision` permanece a Organization owner do grant para RLS e responsabilidade do registro;
- nenhuma revisão altera, reabre ou reescreve a `Evaluation` referenciada.

Estados iniciais:

- `PROPOSTA`;
- `REVISADA`.

Resultados de revisão iniciais:

- `APROVADA`;
- `REJEITADA`;
- `REAVALIACAO_NECESSARIA`.

## Critérios de aceite

| # | Critério | Validação |
|---|---|---|
| 1 | Beneficiário cria proposta válida para Evaluation compartilhada | `POST` retorna `201` e status `PROPOSTA` |
| 2 | Owner revisa proposta pendente | `POST` retorna `200`, status `REVISADA`, `reviewed_at` preenchido |
| 3 | Beneficiário não revisa proposta | API retorna `403` ou negação equivalente já usada pela Fase 2 |
| 4 | Owner não cria proposta em nome do beneficiário | API retorna `403` |
| 5 | Proposal sem grant ativo ou sem vínculo com a Evaluation é recusada | API retorna `404`, `403` ou `409` conforme padrão existente, sem vazamento indevido |
| 6 | Terceira Organization não distingue inexistente de invisível | resposta uniforme mantém compatibilidade com P-198 |
| 7 | Proposta já revisada não pode ser revisada novamente | API retorna `409` |
| 8 | Listagem retorna apenas propostas autorizadas daquele contexto | owner e beneficiary veem o que o grant permite; terceiros não veem nada |
| 9 | Evaluation permanece imutável | teste confirma que revisão não altera Evaluation |

## Plano técnico

Capacidades e arquivos afetados:

- criar modelo de domínio ou contrato interno para `SharedDecision`, preferindo fronteira já existente de policy sharing;
- criar persistência em `core_audit.shared_decisions` com `record_owner_organization_id` e RLS compatível;
- criar `SharedDecisionService` na Application para validar grant, papel da Organization e vínculo com Evaluation;
- adicionar permissões específicas para propor e revisar ou justificar reutilização explícita de permissão existente;
- expor rotas sob `/v1/rule-governance/shared-policies/{policy_id}/decisions` ou prefixo equivalente consistente com Fase 2;
- atualizar testes de superfície pública do Core se novas rotas forem adicionadas.

Contratos, persistência e erros:

- migration Alembic obrigatória para a tabela nova;
- FKs para grant, Evaluation e Organizations quando compatíveis com o schema real;
- `proposal_evidence_references` deve ser serializado como estrutura controlada, não string livre de payload;
- erros devem seguir os padrões existentes de `policy_governance.py` e preservar negação uniforme para Organization sem acesso.

Impacto em arquitetura, segurança e tenancy:

- a mudança toca autorização e compartilhamento cross-Organization, portanto é crítica;
- Core não deve depender de Livestock;
- a Application deve orquestrar regras; Presentation só adapta HTTP;
- RLS deve continuar como defesa em profundidade, sem confiar em IDs enviados pelo cliente como autorização.

Impacto de dados, migration e rollback:

- migration aditiva e reversível;
- sem alteração destrutiva ou backfill obrigatório;
- rollback remove somente a tabela nova e índices associados se ainda não houver dados aceitos em ambiente compartilhado.

Compatibilidade:

- endpoints da Fase 2 devem continuar com mesmo contrato;
- `POST /shared-policies/{policy_id}/evaluate` não ganha rate limiting neste incremento.

## Verificação e observabilidade

Testes automatizados esperados:

- testes de domínio para transições e invariantes de `SharedDecision`;
- testes de Application para owner/beneficiary, grant inativo, Evaluation incompatível e revisão duplicada;
- testes de integração HTTP para criação, revisão, listagem, autorização negativa e terceira Organization;
- teste de não regressão provando que Evaluation referenciada não é alterada;
- teste de superfície pública para rotas novas.

Roteiro manual/API:

- por adicionar comportamento observável pela API, o incremento deve entregar roteiro em `apps/validacao`, seguindo as regras do `AGENTS.md`: descobrir Organizations e entidades, mostrar request/response, explicar o propósito de cada passo e sondar ambiente antes do primeiro passo.

Portão:

```text
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

## Documentação afetada

- `docs/CHECKLIST_DE_IMPLEMENTACAO.md` deve ser atualizado somente após BUILD/VERIFY/ACCEPT do incremento;
- `docs/specs/implemented/` deve receber esta SPEC quando aceita e implementada;
- ADR-0066 ainda não existe no repositório; antes do BUILD, criar e aprovar ADR ou registrar decisão equivalente aceita pelo responsável.

## Riscos, alternativas e perguntas abertas

**CONTEXTO:** Fase 3 afeta autorização, auditoria e compartilhamento entre Organizations. O plano existente marca a fase como ready, mas ADR-0066 está apenas em rascunho nos documentos de plano.

**EVIDÊNCIA NO REPOSITÓRIO:** `docs/plans/BUYERPOLICY_FASE3_REQUIREMENTS.md` declara D1-D4 e a opção segura para sujeitos cross-org; `docs/plans/BUYERPOLICY_FASE3_LAUNCH.md` ainda pede validação final e cita ADR-0066 como rascunho.

**OPÇÕES:**

- aprovar ADR-0066 completa antes de qualquer BUILD;
- aprovar somente este corte, registrando que os incrementos 2-4 continuam dependentes de decisão própria;
- adiar Fase 3 e retomar adequações pendentes da ADR-0048.

**TRADE-OFFS:**

- ADR completa reduz ambiguidade, mas atrasa o primeiro valor operacional;
- corte limitado mantém o diff menor, mas exige disciplina para não puxar rate limiting, composição e snapshot junto;
- retomar ADR-0048 fortalece o motor regulatório, mas não fecha a lacuna operacional aberta pela Fase 2.

**RECOMENDAÇÃO:** aprovar somente este Incremento 1 como BUILD separado, mantendo D1, D2 e a opção segura de sujeitos cross-org; deixar rate limiting storage, composição com matriz e histórico pós-expiração para SPECs ou decisões próprias.

**DECISÃO REGISTRADA:** SPEC aprovada em 2026-08-27 para BUILD do Incremento 1. A aprovação vale somente para este corte limitado; rate limiting, composição com matriz e histórico pós-expiração continuam dependentes de decisão própria.
