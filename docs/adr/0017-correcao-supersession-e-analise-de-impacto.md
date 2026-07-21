# ADR 0017 — Correção, supersession e análise de impacto
**Status:** Aceita  
**Data:** 21 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan mantém Events, Evidences, Evaluations e Decisions imutáveis, enquanto Projection e State representam visões atuais reconstruíveis. Erros, complementações, nova Evidence, mudanças metodológicas, revogações e substituições podem ocorrer depois que um registro já participou de decisões, publicações ou integrações.

Correction já é o conceito canônico para corrigir ou complementar registro sem apagar o original. Retenção e disposição seguem a ADR 0014; review e reavaliação decisória seguem a ADR 0016.

## Problema

Definir:

- quando usar Correction, Revocation, nova versão ou supersession;
- como representar escopo, temporalidade, autoridade e concorrência;
- como atualizar CurrentProjection sem reescrever história;
- como localizar e classificar dependentes potencialmente afetados;
- como decidir respostas downstream sem automação indevida.

## Princípios

1. **Mudança não implica erro:** nova informação ou método não torna o registro anterior falso ou fraudulento.
2. **Histórico preservado:** Correction e relações criam objetos novos; original permanece identificável durante retenção aplicável.
3. **Projeção não é fonte:** CurrentProjection aponta para estado preferido por finalidade e pode ser reconstruída.
4. **Impacto não é invalidação:** dependência localizada exige avaliação e decisão próprias.
5. **Tempo é multidimensional:** ocorrência, registro, descoberta, correção e efeito não são intercambiáveis.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Atualizar registro original | Consulta simples | Perde Evidence e explicação histórica |
| Campo `is_latest` manual | Implementação rápida | Corridas, bifurcações e finalidade ambígua |
| Reprocessar tudo automaticamente | Estado aparentemente atual | Custo, efeitos indevidos e perda de contexto |
| Tratar toda mudança como Correction | Vocabulário pequeno | Declara erro onde houve apenas evolução |
| Relações tipadas e impacto versionado | Semântica e auditoria | Mais avaliações, projeções e decisões |

## Decisão

Manter Correction como conceito canônico de correção ou complementação e introduzir contratos explícitos para solicitação, avaliação, escopo, supersession e impacto.

Nenhum registro histórico é atualizado. CurrentProjection é derivada de relações e Policies versionadas. Alteração downstream exige caso de uso e autorização próprios.

Os novos conceitos são candidatos arquiteturais e dependem de aprovação no `DOMAIN.md`.

## ChangeKind

Natureza controlada da mudança:

- `CORRECAO_DE_ERRO`;
- `COMPLEMENTACAO`;
- `NOVA_EVIDENCIA`;
- `ATUALIZACAO_METODOLOGICA`;
- `ATUALIZACAO_NORMATIVA`;
- `RECLASSIFICACAO`;
- `REVOGACAO`;
- `SUBSTITUICAO_PARA_NOVOS_EFEITOS`;
- `REPUBLICACAO`.

ChangeKind não determina sozinho operação ou efeito. Policy define contratos permitidos por tipo de objeto e finalidade.

## Semântica das mudanças

Correction declara que escopo anterior estava incorreto, incompleto ou precisava de complemento identificável. Nova Evidence acrescenta conhecimento e pode iniciar Correction ou Reevaluation, mas não corrige por si só.

Atualização metodológica ou normativa cria nova versão ou assessment correlacionada. Somente erro identificado no material anterior produz Correction. Revocation encerra validade ou autorização para finalidade e instante delimitados sem apagar usos históricos.

Supersession indica versão preferida para finalidade ou novos efeitos. Não declara automaticamente falsidade, invalidade ou revogação da versão anterior. Republicação produz Publication nova e correlacionada, sem alterar cópias já obtidas.

## CorrectionRequest

Solicitação imutável de mudança sobre objeto e versão específicos.

Preserva solicitante, OrganizationContext, ChangeKind alegado, CorrectionScope, motivo, conteúdo proposto ou referência, Evidence, finalidade, urgência, DataClassification, correlação e IdempotencyKey.

Cliente não escolhe efeito, versão corrente ou objetos impactados como valores confiáveis.

## CorrectionScope

Escopo imutável da mudança.

Delimita objeto, versão, campos ou relações, período factual, finalidade, Organization, valores alegados quando autorizados, exclusões e dependências conhecidas.

Ampliação ou redução exige nova CorrectionRequest e avaliação. Correção parcial não substitui campo fora do escopo.

## CorrectionAssessment

Avaliação imutável anterior à criação de Correction, Revocation, nova versão ou SupersessionRelation.

Preserva request, objeto original, ChangeKind confirmado, CorrectionScope, Evidence admitida e rejeitada, Provenance, conflitos, autoridade requerida, temporalidade, impacto preliminar, operação recomendada, ReasonCodes e limitações.

Resultados iniciais: `AUTORIZAVEL`, `EVIDENCIA_ADICIONAL_NECESSARIA`, `REVISAO_NECESSARIA`, `REJEITADA`, `INDETERMINADA`.

Assessment não altera registro, Projection ou State.

## Correction

Correction permanece registro imutável ligado ao original e ao CorrectionAssessment autorizado.

Além do contrato existente, preserva ChangeKind, CorrectionScope, valores anteriores por referência autorizável, novo conteúdo, temporalidade, AuthorityProfile aplicável, Evidence, ReasonCodes, IdempotencyKey, versão esperada e efeitos declarados.

Correction não altera Event, Evidence, Evaluation ou Decision. Quando retenção exigir disposição do valor anterior, permanece envelope mínimo conforme ADR 0014.

## SupersessionRelation

Relação imutável, direcional e acíclica entre duas versões ou registros.

Preserva origem, destino, tipo, finalidade, escopo, instante efetivo, AuthorityProfile, Evidence, ReasonCodes e limitações.

Tipos iniciais:

- `CORRIGE`;
- `COMPLEMENTA`;
- `SUBSTITUI_PARA_NOVOS_EFEITOS`;
- `REVOGA_PARA_NOVOS_EFEITOS`;
- `REPUBLICA`;
- `RECLASSIFICA`.

Relação não transfere ownership ou Visibility. Origem e destino distintos são obrigatórios; ciclos e reutilização do mesmo version ID são proibidos.

## Temporalidade da correção

Toda mudança distingue, quando aplicável:

- `occurred_at`: instante alegado do fato;
- `recorded_at`: instante do registro original;
- `discovered_at`: instante da descoberta;
- `requested_at`: instante da solicitação;
- `corrected_at`: instante da emissão da Correction;
- `effective_from`: início dos novos efeitos;
- `known_at`: instante em que o Titan passou a conhecer a mudança.

Timezone, Source e TimeConfidence acompanham os instantes relevantes. `effective_from` anterior a `corrected_at` não reescreve conhecimento histórico nem produz efeito retroativo automaticamente.

## CurrentProjection

Projection reconstruível que resolve versão aplicável por objeto, finalidade, instante, OrganizationContext e Policy.

Não usa apenas “último timestamp”. Considera relações, efetividade, Revocations, escopo, conflitos e Authorization.

Resultado ambíguo, ciclo, versão ausente ou bifurcação não resolvida produz `INDETERMINADA` ou revisão; não escolhe silenciosamente uma versão.

Projection preserva referência ao caminho histórico utilizado e nunca se torna Evidence da correção.

## Concorrência e idempotência

CorrectionRequest registra versão esperada. Mudança concorrente exige reavaliação sobre o novo grafo; last-write-wins é proibido. IdempotencyKey protege repetição da mesma intenção. Requests distintas sobre o mesmo escopo podem coexistir e devem ser reconciliadas conforme Policy.

Claim ou lease operacional abandonado é recuperável. Resultado desconhecido de persistência ou publicação não gera nova Correction sem reconciliação.

## ImpactTrigger

Gatilho imutável de análise de impacto.

Pode referenciar Correction, Revocation, SupersessionRelation, nova Evidence, mudança normativa, ValidationAssessment, Policy, método, fator, classificação, retenção, Decision, Override ou incidente.

Preserva objeto, versão, ChangeKind, instante, solicitante, finalidade, escopo inicial, Authorization e ReasonCodes. Gatilho não prova impacto.

## ImpactScope

Escopo imutável de navegação por Provenance e relações.

Delimita direção, profundidade, período, tipos de objeto e dependência, Organizations, finalidade, DataClassifications, exclusões, limites de Authorization, critérios de parada e regra de truncamento.

Alteração do escopo cria nova análise. Objeto invisível é contado como inacessível quando permitido, não revelado.

## ImpactAssessment

Avaliação imutável que localiza e classifica dependências em relação a ImpactTrigger e ImpactScope.

Preserva snapshot e consistência temporal do grafo, ProvenancePaths, objetos esperados, visitados, não avaliados e inacessíveis, profundidade alcançada, truncamentos, dependências, lacunas, ciclos, Policy, motor, Actor, ReasonCodes, limitações e instante.

Estados por objeto:

- `NAO_AFETADO`;
- `NAO_AVALIADO`;
- `POTENCIALMENTE_AFETADO`;
- `AFETADO_CONFIRMADO`;
- `INDETERMINADO`;
- `INACESSIVEL`.

`AFETADO_CONFIRMADO` significa que a mudança alcança pressuposto ou conteúdo declarado do objeto segundo o escopo; não significa inválido, fraudulento ou juridicamente ineficaz.

`NAO_AFETADO` exige avaliação suficiente. Análise incompleta, limite alcançado, inventário parcial, autorização insuficiente ou método incapaz não produzem conclusão negativa.

Ausência de caminho encontrado não prova ausência de dependência. A classificação vale somente para ImpactScope, snapshot, Policy e instante declarados.

Mudança concorrente detectada no grafo exige snapshot novo ou resultado `INDETERMINADO`. Ciclo e truncamento permanecem limitações explícitas.

## ImpactFinding

Achado imutável para dependência específica.

Preserva objeto e versão, caminho, tipo de dependência, campo ou pressuposto afetado, estado, Evidence, materialidade contextual, confiança, limitações e ações candidatas.

Tipos de dependência iniciais: `DIRETA`, `INDIRETA`, `DERIVADA`, `SEMANTICA`, `NORMATIVA`, `TEMPORAL`, `OPERACIONAL`. Significados pertencem a vocabulário versionado pela Policy.

Múltiplos caminhos correlacionados ou derivados da mesma Source não aumentam automaticamente confiança ou materialidade. Finding material para uma finalidade não é universal.

Achado não executa ação e não altera o objeto dependente.

## ImpactResponseDirective

Diretiva imutável dentro de ImpactResponseDecision para uma resposta, escopo e conjunto de findings determinados.

Preserva tipo, prioridade, prazo, executor autorizado, dependências, estado, correlação, idempotência, resultado, Evidence e limitações. Estados iniciais: `PENDENTE`, `EM_EXECUCAO`, `CONCLUIDA`, `PARCIAL`, `FALHOU`, `RESULTADO_DESCONHECIDO`, `CANCELADA`.

## ImpactResponseDecision

Decisão autorizada sobre resposta a um ou mais ImpactFindings.

Tipos de diretiva candidatos: `NENHUMA_ACAO`, `MONITORAR`, `REAVALIAR`, `CORRIGIR`, `RESTRINGIR`, `REVOGAR_PARA_NOVOS_EFEITOS`, `REPUBLICAR`, `COMUNICAR`, `ABRIR_NAO_CONFORMIDADE`, `INICIAR_ANALISE_DE_RECALL`.

Preserva AuthorityProfile, Policy, Actor, escopo, findings, razões, aprovações, diretivas e limitações. Cada ação efetiva usa caso de uso próprio; a decisão não simula sua conclusão.

Conclusão global exige reconciliação de todas as diretivas. Resultado parcial, pendente ou desconhecido não é apresentado como resposta concluída.

## Dependentes

ImpactAssessment pode alcançar Facts, Events, Measurements, CalculatedMetrics, Evaluations, Decisions, Reviews, NonConformities, Dossiers, Publications, Sharings, VerificationBundles, integrações, Projections e objetos de Recall.

Nova Evaluation ou Decision é sempre correlacionada e autorizada. Dossier ou Publication histórica permanece imutável; versão nova explicita a mudança.

Cópia exportada pode permanecer fora do controle do Titan. Revocation ou republicação impede ou altera somente novos acessos controlados, sem apagar cópia externa.

## Notificação e integrações

ImpactResponseDecision pode solicitar notificação a consumidores conhecidos conforme DataContract, Sharing e Authorization. A notificação preserva objeto, versão, ChangeKind, escopo autorizado, razão segura, correlação e idempotência, sem transmitir valor anterior ou dado protegido por conveniência.

Aceitação pelo Message Broker não comprova recebimento, processamento ou ação do destinatário. Cada estágio permanece distinto e resultado desconhecido é reconciliável.

## Offline

CorrectionRequest e Evidence podem ser capturadas offline quando o perfil permitir. Correction oficial, Revocation, SupersessionRelation e ImpactResponseDecision exigem validação no servidor.

Sincronização revalida identidade, autoridade, versão esperada, DataContract, Policy, conflitos, temporalidade e escopo. Request rejeitada permanece auditável e não altera CurrentProjection.

## Fronteiras arquiteturais

Domain define mudança, scope, relações, temporalidade, impacto e invariantes. Não conhece banco, API, graph engine, broker ou interface.

Application coordena request, assessment, autorização, Correction, projeção, análise de impacto e decisões de resposta.

Infrastructure persiste versões, reconstrói índices e projeções, percorre relações e entrega notificações. Não decide versão correta, impacto material ou resposta.

Presentation coleta solicitações e mostra histórico, versão corrente, conflitos, impacto e limitações conforme Authorization.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | História íntegra; projeção reconstruível; impacto explicável; respostas autorizadas |
| Negativas | Grafo versionado; concorrência; análises potencialmente caras; estados ambíguos explícitos |

## Riscos e controles

| Risco | Controle |
|---|---|
| Toda evolução parecer erro | ChangeKind e semânticas distintas |
| Projection escolher versão errada | Policy, temporalidade e caminho preservado |
| Correções concorrentes se perderem | Versão esperada e sem last-write-wins |
| Impacto virar invalidação | Estados e ImpactResponseDecision separados |
| Correção apagar dado pessoal | ADR 0014 e envelope mínimo |
| Notificação vazar conteúdo | DataContract, minimização e Authorization |

## Verificação automatizada

Testes futuros devem cobrir:

- alteração direta de registro histórico;
- nova Evidence ou método tratada automaticamente como erro anterior;
- Correction fora de CorrectionScope;
- SupersessionRelation cíclica, autorreferente ou sem autoridade;
- CurrentProjection escolhida apenas pelo timestamp;
- correção concorrente usando versão obsoleta;
- retry criando Corrections duplicadas;
- retroatividade reescrevendo conhecimento histórico;
- objeto inacessível revelado por análise;
- profundidade limitada ou caminho truncado apresentado como análise completa;
- objeto oculto por Authorization tratado como `NAO_AFETADO`;
- mudança concorrente no grafo não detectada;
- dependência semântica ignorada por ausência de link direto;
- caminhos da mesma Source contados como confirmações independentes;
- finding material para uma finalidade aplicado universalmente;
- `POTENCIALMENTE_AFETADO` tratado como inválido;
- `AFETADO_CONFIRMADO` causando revogação direta;
- ImpactFinding executando ação automaticamente;
- diretivas parciais apresentadas como resposta concluída;
- aceitação pelo broker apresentada como recebimento;
- snapshot e finding usando versões divergentes;
- ciclo ou truncamento sem limitação registrada;
- republicação ou Revocation apagando cópia externa;
- request offline alterando projeção antes da validação.

## Critérios de aceitação

A ADR pode ser aceita quando:

- Correction permanecer conceito canônico e mudanças distintas não forem confundidas;
- request, scope, assessment, Correction e SupersessionRelation preservarem versões;
- temporalidade distinguir fato, conhecimento, descoberta, correção e efeito;
- CurrentProjection for reconstruível, finalística e falhar em ambiguidade;
- concorrência e idempotência impedirem perda ou duplicação silenciosa;
- impacto usar trigger, scope, assessment e findings imutáveis;
- completude, truncamento, snapshot e consistência temporal permanecerem explícitos;
- `NAO_AVALIADO`, `NAO_AFETADO`, `INDETERMINADO` e `INACESSIVEL` forem distintos;
- dependências semânticas usarem vocabulário versionado e caminhos correlacionados não inflarem confiança;
- `AFETADO_CONFIRMADO` não significar invalidação automática;
- resposta downstream exigir decisão, diretivas reconciliadas e casos de uso próprios;
- Dossiers, Publications, Decisions e cópias históricas não forem reescritos;
- retenção, privacidade, Authorization, offline e notificações preservarem limites;
- schema, API, graph engine, fila, worker e frontend permanecerem fora da decisão.

## O que esta ADR não decide

Esta ADR não escolhe:

- tabela, schema, índice, banco de grafo, endpoint ou interface;
- algoritmo de travessia, fila, worker, scheduler ou SLA;
- regra jurídica de retroatividade ou prazo de correção;
- invalidação, sanção, republicação ou Recall automático;
- mecanismo físico de disposição definido pela ADR 0014.

## Plano de reversão

Antes da implementação, esta decisão pode ser substituída por nova ADR. Depois da adoção, mudança preserva Requests, Assessments, Corrections, Revocations, SupersessionRelations, Projections, Triggers, Scopes, Findings, ImpactAssessments, ResponseDecisions e Directives históricos.

Reversão não reescreve registro original, escolhe versão silenciosamente, elimina relação ou executa resposta downstream.
