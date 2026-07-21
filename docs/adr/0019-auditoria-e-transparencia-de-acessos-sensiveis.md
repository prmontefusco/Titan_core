# ADR 0019 — Auditoria e transparência de acessos sensíveis
**Status:** Aceita  
**Data:** 21 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan decide Authorization por operação e pode entregar dados pessoais, sigilosos, comerciais, regulatórios ou estratégicos entre Organizations. Audit já é capacidade canônica, mas log técnico, decisão de autorização, tentativa, execução e visualização não são semanticamente equivalentes.

Transparência também possui limites: owner, titular ou concedente pode precisar conhecer acessos relevantes sem receber dados de terceiros, investigação ativa, controles antifraude ou segredo do consultante.

## Problema

Definir:

- quais acessos exigem registro reforçado;
- como distinguir decisão, tentativa, execução, entrega e visualização;
- como representar lote, worker, integração e acesso privilegiado;
- como comprovar integridade e completude sem copiar payload;
- como produzir transparência autorizada e limitada.

## Princípios

1. **Registro sem exagero:** cada marco declara somente o que foi observado.
2. **Minimização:** auditoria preserva identidade, escopo e razões, não conteúdo por conveniência.
3. **Falha segura:** ausência do registro obrigatório é falha de segurança, não prova de ausência de acesso.
4. **Transparência autorizada:** owner ou titular não recebe automaticamente todos os detalhes.
5. **Auditoria da auditoria:** acesso a registros de Audit também é protegido e rastreável.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Usar logs técnicos | Baixo custo inicial | Retenção, integridade e semântica inadequadas |
| Event por linha lida | Granularidade | Volume extremo e falsa precisão em consultas |
| Registrar payload | Investigação simples | Duplica dado sensível e amplia exposição |
| Notificar todo acesso | Transparência aparente | Vazamento, ruído e risco a investigações |
| Perfis e registros estruturados | Controle e explicação | Mais contratos, storage e revisão |

## Decisão

Manter Audit como capacidade canônica e introduzir SensitiveAccessProfile, DataAccessRecord, BulkAccessScope, PrivilegedAccessSession, AuditCompletenessAssessment, AccessTransparencyPolicy e AccessTransparencyReport.

Authorization decide se a operação pode ocorrer. DataAccessRecord registra marcos observados da tentativa e execução. TransparencyReport é representação autorizada derivada, não log integral.

Os novos conceitos são candidatos arquiteturais e dependem de aprovação no `DOMAIN.md`.

## Distinções obrigatórias

```text
Authorization
≠ DataAccessRecord
≠ DomainEvent
≠ TechnicalLog
≠ SecurityIncident
≠ AccessTransparencyReport
```

Authorization permitida não prova execução. Query executada não prova retorno de dados. Resposta produzida não prova entrega. Entrega técnica não prova visualização humana.

## SensitiveAccessProfile

Perfil versionado que define obrigação de auditoria para recurso e operação.

Preserva DataClassifications, operações, AccessPurposes, Actors, capacidades, Organizations, FieldScopes, canais, ambientes, marcos obrigatórios, granularidade, sincronismo, integridade, retenção, alertas, transparência, aprovação e limitações.

Perfis iniciais podem distinguir `PADRAO`, `SENSIVEL`, `ALTAMENTE_SENSIVEL`, `PRIVILEGIADO`, `EMERGENCIAL`. O nome não substitui regras versionadas.

Operação sem perfil aplicável falha conforme Policy. Classificação elevada não reduz obrigação existente.

## DataAccessRecord

Registro imutável de exatamente um marco observável de acesso. Uma jornada produz múltiplos records correlacionados; record nunca acumula status atual.

Preserva AccessOperationId, AccessAttemptId, MilestoneId, IdempotencyKey, principal, Actor, DecisionAuthority quando houver, capacidade, ServiceIdentity executora, destinatário externo, Organizations, recurso e versão ou referência segura, operação, Purpose, scopes, grants, Authorization, Channel, Device, ambiente, instantes, correlação, causação, BulkAccessScope, Evidence, ReasonCodes e limitações.

Não contém payload, token, secret, campo sensível, query arbitrária, nome pessoal ou valor anterior por padrão. Exceção exige perfil, minimização, classificação, criptografia, retenção e aprovação.

## AccessOperation e AccessAttempt

AccessOperation identifica a intenção lógica de acesso. AccessAttempt identifica cada tentativa técnica de executá-la.

Retry preserva AccessOperationId, IdempotencyKey e CorrelationId; nova tentativa recebe AccessAttemptId próprio. MilestoneId nunca é reutilizado. Timeout ou resultado desconhecido não cria nova operação de negócio automaticamente.

## AccessTrace

Projection reconstruível dos DataAccessRecords de uma AccessOperation, contendo sequência conhecida, attempts, branches, lacunas, duplicações, marcos obrigatórios, estado técnico observado, completude e limitações.

Não é fonte autoritativa paralela. Marco posterior não é inferido do anterior; ausência de marco torna a jornada incompleta sem provar que a atividade material não ocorreu.

## AccessMilestone

Marco controlado do acesso:

- `SOLICITADO`;
- `NEGADO`;
- `AUTORIZADO`;
- `EXECUCAO_INICIADA`;
- `EXECUCAO_CONCLUIDA`;
- `DADOS_NAO_ENCONTRADOS_NO_ESCOPO`;
- `RESPOSTA_PRODUZIDA`;
- `ENTREGA_TECNICA_CONFIRMADA`;
- `ENTREGA_TECNICA_INDETERMINADA`;
- `APRESENTACAO_A_USUARIO_CONFIRMADA`;
- `FALHA`.

`EXECUCAO_CONCLUIDA` significa somente término da atividade técnica delimitada, independentemente de resposta, entrega ou sucesso de negócio. `APRESENTACAO_A_USUARIO_CONFIRMADA` exige Evidence e comprova apenas interação técnica declarada, nunca leitura, compreensão, concordância ou efeito jurídico.

`DADOS_NAO_ENCONTRADOS_NO_ESCOPO` é interno e não distingue externamente invisível, omitido, inacessível, parcial ou indisponível. `FALHA` usa ReasonCodes como `FALHA_DE_AUTORIZACAO`, `FALHA_DE_EXECUCAO`, `FALHA_DE_AUDITORIA`, `FALHA_DE_ENTREGA`, `FALHA_DE_DEPENDENCIA`, `FALHA_DE_INTEGRIDADE`, `RESULTADO_DESCONHECIDO`.

## Tentativa negada e existência

Negação registra principal, contexto solicitado, tipo de operação, Purpose, razão segura, instante e correlação.

Referência a recurso invisível é opaca ou redigida. Audit interna pode preservar identificador protegido quando necessário, mas resposta e transparência externa não distinguem inexistente de invisível.

Valor arbitrário do solicitante não é copiado quando puder conter dado pessoal, segredo, payload malicioso ou Identifier protegido. Registra-se tipo, classe, correlação, código seguro e sinal de abuso; Digest somente quando apropriado e não correlacionável indevidamente.

Ataques de enumeração, volume e padrões anômalos podem produzir sinal de segurança separado. DataAccessRecord não declara incidente automaticamente.

## BulkAccessScope

Escopo imutável para consulta, exportação ou processamento de múltiplos objetos.

Preserva critério controlado e versão, snapshot ou cursor, tipos de recurso, período, Organizations, FieldScope, Purpose, limites, contagem esperada quando conhecida, examinada, retornada, omitida, inacessível e indeterminada, Digest, truncamento e limitações.

Perfil decide registro agregado, amostral ou por objeto. Contagem não substitui identidade quando rastreabilidade individual for obrigatória.

Query livre, SQL ou expressão com dado pessoal não é copiada. Ausência de item no resultado não prova que não foi examinado sem marco e método compatíveis.

BulkAccessCompletionStatus: `COMPLETO`, `PARCIAL_POR_LIMITE`, `PARCIAL_POR_AUTORIZACAO`, `PARCIAL_POR_FALHA`, `PARCIAL_POR_TIMEOUT`, `PARCIAL_POR_CANCELAMENTO`, `INDETERMINADO`.

Digest declara cobertura: IDs opacos ordenados, manifesto e versões, resultado, scope resolvido, snapshot ou arquivo exportado. Digest sem semântica de cobertura não sustenta completude.

## ServiceIdentity, worker e integração

DataAccessRecord distingue Actor originador, AuthenticatedPrincipal, ServiceIdentity executora, Organization atuante e consumidor externo.

DecisionAuthority permanece distinta desses participantes. Identidade técnica do worker não apaga origem humana ou institucional.

Worker reconstrói OrganizationContext e Authorization. Mensagem ou job não transporta autorização confiável e broker aceito não comprova acesso ou processamento.

Processamento interno também pode ser acesso sensível. Ser serviço da plataforma não dispensa Purpose, grant, perfil ou auditabilidade.

## PrivilegedAccessSession

Sessão imutavelmente identificada para administração privilegiada, suporte ou emergência.

Preserva tipo, solicitante, aprovadores, autoridade, justificativa, escopo, Purpose, ambiente, início, expiração, autenticação reforçada, segregação, comandos ou operações controladas, DataAccessRecords, Evidence, alertas e revisão posterior.

Break-glass é negado por padrão, temporal, mínimo e não concede acesso universal. Não pode ser usado para contornar LegalHold, disposição, classificação ou investigação sem autoridade específica.

Finalidades controladas incluem `SUPORTE_PRIVILEGIADO`, `ADMINISTRACAO_TECNICA`, `RESPOSTA_A_INCIDENTE`, `EMERGENCIA_OPERACIONAL`, `ORDEM_DE_AUTORIDADE`. Sessão privilegiada não cria Purpose novo implicitamente.

Sessão expirada ou revogada encerra novas operações. Revisão posterior não substitui aprovação prévia quando ela era possível.

Operação em andamento segue comportamento de Policy registrado: abortar, concluir com segurança, colocar resultado em quarentena ou exigir nova Authorization.

## Obrigatoriedade e falha de auditoria

SensitiveAccessProfile define se registro deve ser durável antes da execução, antes da resposta ou por mecanismo transacional correlacionado.

Quando Audit obrigatória não puder ser registrada ou correlacionada, acesso sensível é negado por padrão. Perfil emergencial pode permitir fallback durável e reconciliável, nunca execução silenciosa.

Falha parcial produz estado explícito, alerta e reconciliação. Retry preserva IdempotencyKey; duplicação de record não é mascarada como múltiplos acessos.

ReasonCodes distinguem `AUDIT_INDISPONIVEL`, `AUDIT_PERSISTENCIA_INDETERMINADA`, `AUDIT_CORRELACAO_FALHOU`. Reconciliação usa as mesmas identidades lógicas sem repetir cegamente a operação.

## AuditCompletenessAssessment

Avaliação imutável da suficiência dos registros para escopo e período declarados.

Preserva perfil, fontes esperadas, sequências, correlações, lacunas, duplicações, atrasos, falhas, relógios, checkpoints, cobertura, método, Actor, resultado e limitações.

Avalia separadamente completude estrutural, de fontes, temporal, de perfil e de integridade, sem score universal.

Resultados iniciais: `COMPLETA`, `COMPLETA_COM_LIMITACOES`, `INCOMPLETA`, `INDETERMINADA`.

`COMPLETA_COM_LIMITACOES` só é usada quando limitações não impedem a conclusão declarada; caso contrário, o resultado é incompleto ou indeterminado.

Nenhum DataAccessRecord encontrado significa somente ausência observada nas fontes avaliadas. Não comprova que nenhum acesso ocorreu quando cobertura ou integridade forem insuficientes.

## Integridade e temporalidade

DataAccessRecords participam de CanonicalSerialization, cadeia ou IntegrityCheckpoint conforme perfil. Checkpoint prova integridade e cobertura declarada, não completude absoluta ou verdade do conteúdo.

Checkpoint preserva intervalo, origem, partição, perfil, sequência inicial e final, lacunas conhecidas, algoritmo, versão e emissor.

Instantes distinguem client observed, server received, authorization evaluated, execution, response e delivery. TimeConfidence e Source acompanham alegações temporais.

Correção cria Correction ou novo record correlacionado. Registro original não é editado. Clock divergente, sequência impossível ou quebra de cadeia inicia assessment ou sinal de segurança.

## Classificação, retenção e acesso recursivo

Registros de Audit recebem DataClassification, ProcessingActivity, RetentionAssignment, LegalHold e DataContract próprios.

Pseudônimos, Identifiers e padrões de acesso podem ser pessoais ou estratégicos. Exportação, analytics e suporte não removem restrições.

Acesso a Audit usa AuditTier controlado: `TIER_0_NEGOCIO`, `TIER_1_ACESSO_A_AUDIT`, `TIER_2_ADMINISTRACAO_E_VERIFICACAO`. Policy limita recursão material; último nível mantém integridade, segregação e controle sem autorreferência infinita.

Administração do mecanismo não pode apagar ou alterar records sem autorização específica e Evidence independente.

Disposição preserva envelope mínimo e integridade possível conforme ADR 0014. Retenção de Audit não é ilimitada por conveniência.

## AccessTransparencyPolicy

Policy versionada que define quais metadados de acesso podem ser apresentados a audiência específica.

Preserva owner ou titular elegível, audiência, recursos, Purposes, consultantes, campos, granularidade, atraso, agregação, redaction, exceções, investigações, segurança, segredos, dados de terceiros, validade, aprovação e limitações.

Owner do registro, concedente e titular não recebem automaticamente identidade completa do consultante, algoritmo antifraude, investigação ativa, observação sigilosa ou dado de terceiro.

Omissão autorizada permanece explicada por ReasonCode seguro. Policy não pode fabricar evento ou ampliar acesso ao conteúdo consultado.

Identidade do consultante usa modo `IDENTIDADE_COMPLETA`, `ORGANIZACAO_APENAS`, `CATEGORIA_DO_CONSULTANTE`, `PSEUDONIMIZADA` ou `NAO_REVELADA`. Atraso deliberado possui motivo, prazo e reavaliação.

## AccessTransparencyReport

Relatório imutável e versionado derivado de DataAccessRecords sob AccessTransparencyPolicy e Authorization.

Preserva audiência, escopo, período, Policy, registros ou agregados autorizados, Organizations, Purposes, tipos de operação, resultados compartilháveis, redactions, omissões, cobertura, AuditCompletenessAssessment, instante, Digest e limitações.

Declara report scope, source record scope, excluded scope e coverage boundary. Ausência de consultante não prova ausência de acesso quando houver omissão, agregação ou atraso.

Relatório agregado não apresenta contagem como completa quando assessment for incompleta. Nova Policy ou record cria nova versão; relatório anterior não é reescrito.

Publicação, notificação e download são operações separadas. Relatório não prova que destinatário o leu.

Tipos: `RELATORIO_COMPLETO_DO_PERIODO`, `RELATORIO_INCREMENTAL`, `RELATORIO_DE_CORRECAO`, `RELATORIO_DE_ATUALIZACAO_DE_POLITICA`. Record tardio cria novo relatório correlacionado, nunca reescrita.

## Offline

Cliente offline registra operação, Actor alegado, Organization, Device, Purpose, scope, campos, client time e correlação, sem declarar Authorization final ou acesso aceito pelo servidor.

Marcos: `OBSERVADO_NO_DISPOSITIVO`, `RECEBIDO_PELO_SERVIDOR`, `IDENTIDADE_REVALIDADA`, `AUTORIZACAO_REAVALIADA`, `ACEITO`, `REJEITADO`, `QUARENTENA`.

Sincronização revalida identidade, capacidade, grant, Policy e operação; cria marcos de recebimento, validação, aceitação ou rejeição. Registro local original permanece.

Transparência distingue instante observado no Device e recebido no servidor. Revogação remota pode tornar operação rejeitada sem apagar tentativa offline.

Leitura de dado já materializado pode ter ocorrido localmente mesmo após rejeição posterior. Rejeição não afirma que apresentação local nunca aconteceu.

## Fronteiras arquiteturais

Domain define perfis, records, milestones, bulk scope, sessão privilegiada, completude, transparência e invariantes. Não conhece SIEM, logger, banco ou tracing SDK.

Application coordena Authorization, obrigação, marcos, acesso privilegiado, completude e relatório.

Infrastructure persiste registros, protege integridade, entrega alertas e fornece observabilidade técnica. Não decide transparência, Purpose ou materialidade.

Presentation mostra relatórios autorizados e mensagens indistinguíveis para inexistente e invisível.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Acesso explicável; investigação; transparência limitada; break-glass controlado |
| Negativas | Volume, retenção, latência em acesso sensível, reconciliação e proteção recursiva |

## Riscos e controles

| Risco | Controle |
|---|---|
| Log técnico tratado como Audit | Contratos e retenção separados |
| Record copiar payload | Minimização e referência opaca |
| Ausência virar prova negativa | CompletenessAssessment e limitações |
| Transparência vazar investigação | Policy, atraso, redaction e exceções |
| Break-glass virar acesso global | Scope, prazo, aprovação e revisão |
| Audit ser consultada sem rastreio | Trilha correlacionada de segunda ordem |

## Verificação automatizada

Testes futuros devem cobrir:

- Authorization permitida apresentada como acesso executado;
- record mutável acumulando milestones;
- perfil menos restritivo reduzindo obrigação aplicável;
- jornada concluída com marco obrigatório ausente;
- retry criando nova operação de negócio;
- resposta produzida apresentada como visualizada;
- acesso sensível sem profile ou record obrigatório;
- record contendo payload, token, query ou atributo protegido;
- tentativa negada revelando existência do recurso;
- lote truncado ou agregado apresentado como completo;
- item não examinado classificado como não encontrado;
- Digest sem declaração de cobertura;
- worker sem OrganizationContext ou Purpose;
- worker ocultando Actor originador;
- broker aceito apresentado como processamento;
- break-glass sem justificativa, prazo, aprovação ou revisão;
- sessão expirada em operação longa sem comportamento registrado;
- falha de Audit permitindo acesso silencioso;
- fallback emergencial não reconciliado;
- retry contado como múltiplos acessos;
- ausência de record apresentada como ausência de acesso;
- completude estrutural confundida com cobertura das fontes;
- `COMPLETA_COM_LIMITACOES` usada quando limitação impede conclusão;
- checkpoint apresentado como completude absoluta;
- acesso à Audit sem trilha correlacionada;
- administração da trilha sem Evidence independente;
- owner recebendo identidade ou investigação não autorizada;
- omissão ou atraso de transparência sem declaração e revisão;
- relatório incompleto apresentado como completo;
- record tardio reescrevendo relatório anterior;
- apresentação técnica tratada como compreensão;
- offline apresentado como acesso aceito pelo servidor.
- offline rejeitado apresentado como nunca executado localmente;
- tentativa negada copiando valor arbitrário para Audit.

## Critérios de aceitação

A ADR pode ser aceita quando:

- Audit permanecer capacidade canônica e distinta de log técnico;
- Authorization, milestones, Event, incidente e transparência forem separados;
- SensitiveAccessProfile definir obrigação, granularidade e falha segura;
- DataAccessRecord preservar contexto e escopo sem copiar payload;
- cada record representar um marco e AccessTrace reconstruir a jornada;
- retries preservarem operação lógica e distinguirem attempts;
- lote declarar contagens, truncamentos e limitações;
- BulkAccessCompletionStatus e Digest declararem conclusão e cobertura;
- ServiceIdentity, worker e consumidor externo forem distinguíveis;
- break-glass for mínimo, temporal, aprovado e revisado;
- ausência de Audit não produzir conclusão negativa indevida;
- completude estrutural, de fontes, temporal, de perfil e integridade permanecerem distintas;
- integridade, classificação, retenção e acesso recursivo forem controlados;
- Evidence de milestone não for confundida com compreensão ou efeito jurídico;
- transparência usar Policy, redaction, cobertura e limitações;
- offline preservar tentativa sem declarar aceitação;
- SIEM, schema, API, frontend e regras jurídicas concretas permanecerem fora.

## O que esta ADR não decide

Esta ADR não escolhe:

- SIEM, logger, tracing, banco, tabela, índice ou storage;
- endpoint, frontend, notificação automática ou formato de relatório;
- prazo jurídico, identidade sempre revelável ou direito concreto do titular;
- detecção completa, classificação ou resposta a incidente;
- granularidade universal para todos os módulos.

## Plano de reversão

Antes da implementação, esta proposta pode ser substituída. Depois da adoção, mudança preserva Profiles, DataAccessRecords, milestones, bulk scopes, privileged sessions, completeness assessments, Policies e Reports históricos.

Reversão não apaga acesso, promove log técnico a Audit, revela conteúdo redigido ou transforma ausência de record em prova de ausência.
