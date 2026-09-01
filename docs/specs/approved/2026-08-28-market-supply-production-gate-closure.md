# SPEC: Market Supply Production Gate Closure

- **Nível:** CRITICAL
- **Estado:** aprovada com mudancas; F3 ainda requer SPEC/PLAN de BUILD
- **Decisão de Discovery:** PROCEED para DESIGN CLOSURE; ADR-0071 ACCEPTED WITH CHANGES
- **Owner de produto:** Founder / Product Owner
- **Data:** 2026-08-28

## Problema e usuário

F0-F2H provaram, em memoria, a linguagem analitica, a agregacao producer-side, os guards de purpose/scope, privacy assessment, audit envelope, resposta uniforme, revogacao efetiva, Candidate Population snapshot e composicao de gates. Ainda falta transformar as decisoes produtivas pendentes em um contrato revisavel antes de qualquer endpoint buyer-facing/cross-Organization.

Os usuarios afetados sao compradores/frigorificos que precisam de resposta agregada e produtores que precisam manter controle, privacidade e revogacao. O risco principal e iniciar F3 com politica de privacidade, auditoria, idempotencia, resolver de populacao ou comportamento HTTP incompletos.

## Contexto e objetivo

Esta SPEC fecha o desenho produtivo minimo para um futuro CUT F3, sem implementar F3. O objetivo observavel e entregar uma proposta de contrato tecnico para:

- perfil produtivo de `AggregationPrivacyPolicy`;
- persistencia de auditoria/query log;
- idempotencia e rate limiting;
- resolver produtivo de Candidate Population;
- armazenamento/linkage de snapshot/digest;
- opt-in e revogacao operacional;
- comportamento HTTP publico uniforme;
- decisao sobre `CommercialDemand` como input transitorio ou persistido.

## Fora de escopo

- endpoint, rota, schema HTTP ou handler produtivo;
- migration;
- nova tabela;
- worker;
- query cross-tenant;
- persistencia de `CommercialDemand`, `CandidatePopulationSnapshot`, audit log ou report;
- resolver real de Animal/propriedade;
- visibilidade para comprador;
- forecast;
- ML/IA;
- alteracao de Policy, Rule, Evaluation, Decision, Dossier ou VerificationBundle.

## Comportamento e regras de negócio

O futuro F3 so pode expor agregados quando todos os gates abaixo estiverem satisfeitos:

1. Authorization: grant valido para `MARKET_SUPPLY_AGGREGATE_ASSESSMENT`, Organization owner, buyer Organization, Policy, purpose, FieldScope e janela temporal.
2. Candidate Population: criterios canonicos, resolver produtivo aprovado, snapshot/digest ligado ao fingerprint da query, exclusoes explicitas e ausencia de vazamento de IDs no payload publico.
3. Aggregation Privacy: politica produtiva explicita, versionada e auditavel, sem threshold global hardcoded no codigo.
4. Audit: envelope persistivel com decisao interna, disposicao externa uniforme, fingerprint da query, contexto temporal, grant e estado de revogacao.
5. Idempotency: repeticao da mesma intencao deve retornar resultado canonico compatível ou conflito explicito quando o digest da intencao divergir.
6. Rate limit/differencing: consultas repetidas ou parecidas devem ser avaliadas contra historico operacional antes de release.
7. Uniform Response: inexistente, invisivel, excluido, negado e suprimido continuam indistinguiveis no contrato publico.
8. Revocation: revogacao efetiva bloqueia nova consulta, reexecucao e novo relatorio; artefato previamente entregue permanece auditavel, mas nao prova autorizacao atual.

Regras adicionais aceitas:

- toda avaliacao Market Supply deve vincular `reference_time` e `knowledge_cutoff`;
- reexecucao com coordenadas temporais diferentes e query semanticamente distinta;
- autorizacao para contribuir dados nao implica inclusao em todo resultado agregado;
- privacy/disclosure evaluation pode suprimir, generalizar ou excluir contribuicoes autorizadas quando houver risco de identificacao;
- `DisclosureDecision` e conceito arquitetural separado de authorization e de Evaluation/Decision regulatorias;
- nenhum resultado agregado existe validamente sem `CandidatePopulationSnapshot`, `DisclosureDecision` e audit record;
- comportamento publico uniforme deve impedir inferencia de ausencia/nao-visibilidade/exclusao/supressao quando isso revelar membership ou atributos protegidos, sem eliminar a utilidade de respostas agregadas liberadas.

## Decisoes propostas para F3

### AggregationPrivacyPolicy

Proposta: configurar por perfil/deployment em dados ou config operada, nao como constantes de dominio. A primeira versao produtiva deve conter:

- minimos por Organization, propriedade e sujeito;
- limite de precisao geografica permitido;
- lista de atributos raros/sensiveis por perfil;
- maximo de filtros combinados;
- janela de consultas repetidas;
- regra de similaridade/differencing usando fingerprints persistidos;
- disposicao `SUPPRESS` ou `GENERALIZE` quando seguro; `DENY` quando a generalizacao ainda revelar risco.

Valores numericos concretos ficam em HUMAN REVIEW de seguranca/produto antes da migration ou deploy.

### Audit/query log

Proposta aceita: criar um conceito persistente proprio para Market Supply audit, inicialmente `MarketSupplyQueryAuditRecord`, em vez de estender semanticamente `shared_policy_access_log`, porque o log existente e acoplado a acesso de Policy compartilhada por grant e acoes `READ`/`EVALUATE`.

Campos minimos futuros:

- audit_id;
- requester/buyer Organization;
- owner/network context;
- access_purpose;
- authorization_context_digest;
- grant_id ou grant assessment reference;
- policy_id/policy_version;
- privacy_profile_id/privacy_profile_version;
- candidate_population_snapshot_digest;
- query_fingerprint;
- disclosure_decision;
- decision_reason_codes;
- external disposition;
- result_digest, quando houver release;
- generated_at/requested_at/reference_time/knowledge_cutoff;
- idempotency scope;
- revocation state observed;
- correlation_id;
- report reference, quando houver.

Persistencia e retention seguem HUMAN REVIEW.

### CandidatePopulation production resolver

Proposta: F3 nao deve resolver populacao por consulta ampla ao rebanho. O resolver produtivo deve receber uma fonte autorizada por opt-in/GrantScope e produzir snapshot por Organization participante, agregando somente depois de passar pelos gates.

Fontes permitidas no primeiro desenho:

- MarketReadiness read model existente;
- dados de Livestock da Organization owner sob autorizacao;
- autorizacoes/participacoes explicitamente aprovadas;
- criterios temporais `reference_time` e `knowledge_cutoff`.

Fontes proibidas no primeiro F3:

- lookup global de Animal;
- Dossier/VerificationBundle como input automatico;
- Evidence raw;
- integracao oficial MAPA/IAGRO/SISBOV;
- Odoo como autoridade sanitaria;
- sensores como fato regulatorio direto.

### DisclosureDecision

`DisclosureDecision` e o resultado imutavel do servico de privacy/disclosure para uma query e um `CandidatePopulationSnapshot`.

Estados iniciais:

- `ALLOW`;
- `GENERALIZE`;
- `SUPPRESS`;
- `DENY`.

Campos minimos:

- state;
- reason_codes;
- privacy_policy_version;
- query_fingerprint;
- candidate_population_digest;
- evaluated_at.

Nao e `Evaluation`, `Decision`, certificacao, reconhecimento externo ou prova de elegibilidade. Pode ser Value Object ou resultado imutavel do servico de privacy na primeira implementacao.

### Snapshot/digest linkage

Proposta: manter o modelo de F2G/F2H: `CandidatePopulationSnapshot` possui digest canonico, e o fingerprint de privacy/audit deve referenciar esse digest. Persistir o snapshot completo ou apenas resumo+digest depende do tipo de artefato:

- consulta transiente: digest e resumo auditavel podem bastar;
- relatorio compartilhado: snapshot imutavel suficiente para reproducibilidade;
- disclosure detalhado futuro: outro corte, outro purpose.

O snapshot deve declarar o universo logico avaliado:

- authorized_sources_digest;
- selection_criteria_digest;
- reference_time;
- knowledge_cutoff;
- population_digest;
- population_size;
- organization_count;
- property_count;
- subject_count.

Counts podem ser internos quando a exposicao aumentar risco de inferencia.

### Idempotency

Proposta: usar o servico Core de idempotencia para eventual endpoint F3, com escopo semantico incluindo buyer Organization, purpose, policy, demand/context digest, candidate criteria digest, reference_time, knowledge_cutoff e request idempotency key.

Repeticao igual retorna resultado armazenado/canonico. Mesmo idempotency key com digest divergente retorna conflito explicito e auditavel.

Reexecucao com `reference_time` ou `knowledge_cutoff` diferentes e query semanticamente distinta.

### Rate limiting e differencing

Proposta: F3 exige query audit persistente antes de release. A avaliacao de privacy deve receber consultas anteriores relacionadas e recusar ou generalizar quando houver risco por repeticao, pequenas diferencas, tempo, geografia ou filtros raros.

Rate limit operacional pertence ao gateway/implantacao quando for volume puro, mas differencing semantico pertence ao application/audit layer.

Differential Privacy matematica formal nao e obrigatoria nesta fase, mas o historico deve suportar `QueryHistory -> SemanticSimilarity -> DisclosureRisk`.

### Uniform HTTP behavior

Proposta: contrato publico deve impedir que o requester distinga ausencia, nao-visibilidade, exclusao ou privacy suppression quando essa distincao revelar membership ou atributos protegidos. Isso nao impede distinguir uma oferta agregada liberada de uma resposta sem informacao apresentavel. Status HTTP, cache, timing padding e pagination ficam em HUMAN REVIEW antes de API.

### CommercialDemand

Proposta para o primeiro F3: aceitar `CommercialDemand` como contexto transitorio no request ou fixture de validacao, sem persistir demanda comercial. Persistencia de `CommercialDemand` fica para corte posterior quando houver necessidade de ciclo de vida, reabertura, auditoria comercial ou workflow de comprador.

## Critérios de aceite

- Documento declara F3 ainda nao autorizado.
- Documento propoe contrato produtivo minimo para privacy, audit, idempotency, resolver, snapshot, revogacao e resposta uniforme.
- Documento incorpora `DisclosureDecision`, invariantes temporais e Snapshot -> Disclosure -> Result -> Audit.
- Nenhuma migration, API ou codigo produtivo cross-tenant e criado.
- Decisoes que exigem valores concretos, schema ou comportamento HTTP ficam em HUMAN REVIEW.
- O checklist registra F2I como design closure, nao como release comercial.

## Plano técnico

Arquivos afetados neste corte:

- `docs/specs/approved/2026-08-28-market-supply-production-gate-closure.md`;
- `docs/adr/0071-market-supply-production-gates-before-cross-tenant-aggregate-api.md`;
- `docs/plans/CUT_F2I_PRODUCTION_GATE_DESIGN_CLOSURE_REPORT.md`;
- `docs/plans/FIRST_MARKET_SUPPLY_VERTICAL_SLICE_PROPOSAL.md`;
- `docs/plans/MARKET_SUPPLY_AND_LIFETIME_COMPLIANCE_FINAL_REPORT.md`;
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`.

Sem codigo, migration, API, worker ou testes funcionais.

## Verificação e observabilidade

Verificacao deste corte:

- revisao documental;
- `git diff --check`;
- Ruff/Mypy/pytest globais devem permanecer verdes apos as correcoes de gate global ja realizadas.

Verificacao futura de F3:

- unit tests para cada gate;
- integration tests com banco/RLS;
- tenant isolation;
- temporal T0/T1/T2;
- revogacao antes/no/depois;
- idempotency conflict;
- repeated-query/differencing;
- uniform response;
- audit persistence;
- roteiro em `apps/validacao` sem copia manual de IDs.

## Documentação afetada

- ADR-0069 e ADR-0070 permanecem aceitas.
- ADR-0071 aceita com mudancas detalha gates produtivos antes de API agregada cross-tenant.
- Checklist deve registrar que F2I nao autoriza F3.

## Riscos, alternativas e perguntas abertas

Alternativa A: autorizar F3 direto usando os componentes F2B-F2H em memoria. Rejeitada por risco de auditoria, retention, HTTP, idempotency e differencing incompletos.

Alternativa B: persistir `CommercialDemand` ja no F3. Mantida como opcao futura, mas nao recomendada para a primeira API agregada porque adiciona lifecycle comercial antes de provar o release agregado.

Alternativa C: reusar `shared_policy_access_log`. Nao recomendada sem ADR especifica porque o log atual tem semantica de Policy sharing, nao de analytics agregada.

HUMAN REVIEW restante:

- aprovar valores concretos de privacy profile;
- aprovar storage/retention de audit;
- aprovar contrato HTTP e comportamento operacional;
- aprovar resolver produtivo e fontes;
- aprovar se F3 usa `CommercialDemand` transitorio ou persistido.
