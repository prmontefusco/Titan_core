# Titan Trust Core Assessment

**Data:** 2026-09-11
**Status:** DISCOVERY aprovado para documentação arquitetural
**Escopo:** reconhecer e endurecer arquiteturalmente capacidades existentes do Core como infraestrutura de confiança reutilizável. Este documento nao autoriza F1-F7 do Commercial Passport.

## 1. Visao atual

O Titan ja opera, conceitualmente, como uma infraestrutura de confianca para cadeias reguladas. A mudanca aprovada nao cria um novo modulo; ela torna explicita a leitura arquitetural do Core existente como infraestrutura reutilizavel para transformar fatos e evidencias em avaliacoes, decisoes, dossies, verificacoes e disclosures autorizados.

O fluxo ja existente e compativel com:

```text
Fact / Evidence
-> FactSnapshot
-> Policy / Rule
-> Evaluation
-> Decision
-> Dossier / VerificationBundle
-> Authorization / Disclosure controlado
```

O Trust Core, neste contexto, e uma interpretacao arquitetural do Core existente. Ele nao e um produto, pacote, servico ou engine novo.

## 2. Capacidades existentes

### Facts e temporalidade

`packages/core_domain/facts.py` ja fornece `Fact` e `FactSnapshot`. O snapshot preserva Organization, Subject, fatos selecionados, hash canonico, `reference_time`, `knowledge_cutoff` e limitacoes de conhecimento.

Ponto critico: `reference_time` e `knowledge_cutoff` ja sao campos separados. A criacao de snapshot filtra fatos por conhecimento efetivo (`known_at`, com fallback declarado) e preserva limitacoes quando conhecimento historico explicito esta ausente.

### Evidence, source e integridade

`packages/core_domain/evidence.py` ja modela `Evidence`, `Source`, `ConfidenceLevel`, validade, revogacao, verificacoes, assinatura e hash de conteudo. A semantica existente evita tratar integridade, fonte ou assinatura como verdade material.

### Policy, Rule, Evaluation e Decision

`packages/core_domain/policy.py`, `rule.py`, `evaluation.py` e `decision.py` ja estabelecem:

- Policy versionada;
- RuleResult explicavel;
- Evaluation como execucao tecnica de Policy/Rules sobre `FactSnapshot`;
- `context_hash` para identidade da semantica normativa;
- `evaluation_hash` para reproducibilidade da avaliacao;
- Decision como conclusao emitida a partir de Evaluation;
- DecisionReason com reason code estavel, regra, versao, severidade, corrective action e evidencias.

Isso atende a invariante central: facts are not decisions, and decisions are derived.

### Dossier e VerificationBundle

`packages/core_domain/dossier.py` ja fornece Dossier canonico, imutavel e verificavel por hash. A `VerticalSection` permite extensao vertical sem o Core interpretar semantica setorial.

`packages/core_domain/verification.py` ja fornece `VerificationBundle` com manifesto, componentes, assinatura, cobertura, verificacao offline e relatorio por dimensoes. O resultado nao e booleano opaco.

### Authorization, grants, audit e disclosure controlado

`packages/core_domain/policy_sharing.py` ja contem `AuthorizationGrant`, `SharedDecision` e `SharedPolicyAccessLogEntry`. Em Livestock, Market Supply compoe grants, candidate population snapshots, privacy gate, aggregation e audit context sem acesso global cross-tenant.

### Idempotency, outbox, inbox, eventos e integridade

O Core possui capacidades de eventos, cadeia de integridade, checkpoints, idempotencia, outbox e inbox nos pacotes `core_application`, `core_domain`, `core_infrastructure` e `core_integrity`. Elas sustentam reproducibilidade operacional, replay controlado e trilhas append-only.

## 3. Capacidades reutilizaveis

As capacidades reutilizaveis para o Trust Core sao:

- `FactSnapshot` como fotografia canonica e temporal do material avaliado;
- `Policy` e `Rule` como semantica versionada;
- `Evaluation` como avaliacao tecnica reproduzivel;
- `Decision` como conclusao explicavel emitida sob autoridade;
- `Dossier` como snapshot formal autocontido de decisao e avaliacao;
- `VerificationBundle` como pacote verificavel e independente;
- `AuthorizationGrant` e logs de acesso como base de compartilhamento controlado;
- serializacao canonica, hashes, timestamps e integridade;
- Organization boundaries e RLS como fronteira de isolamento;
- Market Supply como primeira prova de fluxo future disclosure/aggregate/audit.

## 4. Gaps reais

Os gaps sao de consolidacao, nao de reinvencao:

1. Falta uma ADR que declare que o Trust Core e o Core existente reconhecido, nao um subsistema.
2. Falta documentar invariantes especificas para produtos derivados como Commercial Passport.
3. Falta um modelo de application view para compor multiplas Evaluations/Decisions por oportunidade comercial.
4. Falta semantica explicita de requirement reasoning antes do Passport completo.
5. Falta separar formalmente property readiness de animal/lot/population eligibility.
6. Falta definir quando uma projection dinamica vira issued snapshot formal.
7. Falta preservar buyer-specific and commercial constraints sem promove-los ao Core.

## 5. Riscos

- Criar `trust_engine`, `trust_service` ou outro subsistema paralelo.
- Duplicar Policy/Evaluation/Decision/Dossier/VerificationBundle.
- Vazar termos Livestock para Core.
- Colapsar `UNKNOWN`, `MISSING`, `FAILED`, `BLOCKED` e `NOT_APPLICABLE`.
- Tratar readiness como Decision.
- Tratar score como decisao ou autoridade.
- Emitir Dossier/VerificationBundle a cada consulta dinamica.
- Projetar disclosure publico antes de AuthorizationGrant, FieldScope, privacy gate e audit.
- Usar estado atual do banco para reescrever conclusoes historicas.

## 6. Proposta minima de evolucao

1. Criar ADR de Trust Core como infraestrutura existente.
2. Criar capability map NOW/NEXT/LATER para preservar oportunidades sem scope creep.
3. Criar conceito e plano do Commercial Passport em Livestock.
4. Implementar primeiro requirement reasoning semantics em Livestock.
5. Usar Commercial Passport como application projection, composta por Evaluation/Decision existentes.
6. Reutilizar Dossier/VerificationBundle apenas para emissao formal.

## 7. Invariantes

- Trust Core nao e modulo novo.
- No separate Trust subsystem shall be created.
- Core permanece vertical-agnostic.
- Verticais fornecem semantica de dominio.
- Core fornece primitivas genericas.
- Facts are not decisions.
- Decisions are derived from evidence, fact snapshots, policies and evaluations.
- Uma Decision nunca e fato original.
- Evaluation historica nao e reescrita por fato posterior.
- `reference_time` e `knowledge_cutoff` nao podem ser conflados.
- Unknown is not false.
- Missing evidence is not evidence of non-compliance.
- Readiness is not Decision.
- Score is not Decision.
- Externally meaningful issued artifacts must be reproducible.
- Cross-tenant disclosure requires explicit authorization and audit.

## 8. Dependencias

- `VISION.md`: Titan como plataforma de confianca.
- `DOMAIN.md`: Core independente de verticais; fatos, evidencias, avaliacoes, decisoes e dossies nao sao verdade material.
- `ARCHITECTURE.md`: monolito modular, Core sem dependencia de vertical, evidencias, decisoes explicaveis, authorization, audit e verification.
- `DEVELOPMENT.md`: fluxo IDEA -> DISCOVERY -> DECISION -> SPEC -> PLAN -> BUILD -> VERIFY -> ACCEPT.
- ADRs 0010, 0015, 0016, 0018, 0019, 0041, 0044, 0048, 0049, 0051, 0052, 0055, 0069-0073, 0078 e 0080.

## 9. Anti-patterns

- Criar novo pacote `trust_*`.
- Criar outra engine de Policy/Evaluation.
- Criar outro framework de Dossier ou VerificationBundle.
- Mover Commercial Passport para Core.
- Colocar buyer-specific, logistics, weight, age, quantity ou private protocols no Core.
- Persistir projection dinamica como fonte de verdade.
- Usar cache, projection ou current state como autoridade historica.
- Criar endpoints publicos de Passport sem grants e audit.
- Fazer renaming cosmetico de conceitos Core ja existentes.

## 10. ADRs afetadas

Afetadas por referencia e consolidacao:

- ADR-0010: verificacao externa e VerificationBundle.
- ADR-0015: proveniencia, validacao e confianca.
- ADR-0016: decisoes explicaveis.
- ADR-0018: compartilhamento por finalidade, escopo e concessoes.
- ADR-0019: auditoria e transparencia.
- ADR-0041/0044: elegibilidade e matriz de mercado.
- ADR-0048/0049/0050: decisoes explicaveis, perfis de mercado e execucao deterministica.
- ADR-0051/0052: snapshot canonico e temporalidade.
- ADR-0055/0060: dossier verificavel e secoes verticais.
- ADR-0069/0070/0071/0072/0073: Market Supply, progressive disclosure e optionality.
- ADR-0078: capacidades aspiracionais nao devem ser apresentadas como entregues.
- ADR-0080: Core reutilizado por multiplas verticais sem fork.

Nenhuma ADR existente foi identificada como conflitante. A nova ADR deve consolidar, nao substituir, as decisoes acima.
