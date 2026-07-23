# Arquitetura do Titan

**Versão:** 1.32  
**Status:** Visão de destino congelada

## Regra de congelamento

Este documento descreve a arquitetura de destino e suas restrições. Ele não é backlog, ordem de implementação nem obrigação de construir toda a plataforma antes de validar o MVP.

Novos detalhes não são acrescentados durante a implementação ordinária. Alteração exige uma destas justificativas explícitas:

- corrigir contradição ou erro material;
- refletir ADR estrutural aceita;
- remover ambiguidade que bloqueie uma funcionalidade atual aprovada.

Funcionalidades, prioridades, experimentos e etapas pertencem ao plano ou backlog. A implementação cresce por incrementos verticais mínimos e preserva as fronteiras e invariantes aplicáveis ao incremento vigente.

Decisões de referência:

- `docs/adr/0001-monolito-modular-e-estrutura-do-repositorio.md`
- `docs/adr/0002-isolamento-e-propriedade-por-organization.md`
- `docs/adr/0003-postgresql-rls-e-defesa-em-profundidade.md`
- `docs/adr/0004-armazenamento-de-documents-com-mongodb-gridfs.md`
- `docs/adr/0005-autenticacao-com-oidc-provider.md`
- `docs/adr/0006-entrega-assincrona-com-outbox-e-message-broker.md`
- `docs/adr/0007-checkpoints-de-integridade-e-timestamp-independente.md`
- `docs/adr/0008-gestao-e-rotacao-de-chaves-criptograficas.md`
- `docs/adr/0009-assinaturas-certificados-e-perfis-de-confianca.md`
- `docs/adr/0010-verificacao-externa-e-verification-bundle.md`
- `docs/adr/0011-fontes-normativas-vigencia-e-reavaliacao-temporal.md`
- `docs/adr/0012-sustentabilidade-materialidade-metricas-e-divulgacoes.md`
- `docs/adr/0013-classificacao-e-ciclo-de-vida-de-dados.md`
- `docs/adr/0014-retencao-descarte-controlado-e-legal-hold.md`
- `docs/adr/0015-proveniencia-validacao-e-niveis-de-confianca.md`
- `docs/adr/0016-decisoes-explicaveis-revisao-humana-e-contestacao.md`
- `docs/adr/0017-correcao-supersession-e-analise-de-impacto.md`
- `docs/adr/0018-compartilhamento-por-finalidade-escopo-e-concessoes.md`
- `docs/adr/0019-auditoria-e-transparencia-de-acessos-sensiveis.md`
- `docs/adr/0020-integracoes-externas-e-validacao-de-fontes.md`
- `docs/adr/0021-operacao-offline-e-sincronizacao-segura.md`
- `docs/adr/0022-localizacao-residencia-e-transferencia-de-dados.md`
- `docs/adr/0023-resposta-a-incidentes-e-preservacao-forense.md`
- `docs/adr/0024-exportacao-portabilidade-e-encerramento.md`
- `docs/adr/0025-valkey-para-cache-e-coordenacao-efemera.md`
- `docs/adr/0026-postgis-para-evidencia-geoespacial-no-mvp.md`
- `docs/adr/0027-convencoes-da-api-http.md`
- `docs/adr/0028-keycloak-como-oidc-provider-inicial.md`
- `docs/adr/0029-rabbitmq-como-message-broker-inicial.md`

---

# Filosofia

O Titan adota um monólito modular em monorepo.

Módulos possuem fronteiras, contratos e ownership explícitos, mesmo quando compartilham processo e infraestrutura.

Não utilizar microserviços no MVP. Distribuição física exige nova ADR e evidência de necessidade operacional.

---

# Stack

Backend

- Python
- FastAPI
- Wasm Runtime (Wasmtime Sandbox) para execução determinística de regras normativas

Criptografia e Provas

- Verificador ZKP (zk-SNARKs / zk-STARKs) para provas de conhecimento zero em proveniência
- Verificador Autônomo Monolítico HTML/Wasm para exportação de SingleFileVerificationBundle

Banco

- PostgreSQL
- PostGIS para evidência geoespacial vetorial

Cache

- Valkey

Armazenamento de Documents

- Object Storage (Google Cloud Storage em produção com Bucket Lock WORM / MinIO em ambiente local)


Frontend

- React

Containers

- Docker Compose

Servidor

- Linux

---

# Direção das dependências

As dependências apontam para dentro:

Presentation / Infrastructure

↓

Application

↓

Domain

Regras obrigatórias:

- Domain não depende de framework, banco, mensageria ou apresentação;
- Application depende de Domain e de contratos internos;
- Infrastructure implementa portas definidas pelas camadas internas;
- Presentation invoca casos de uso da Application;
- apps compõem implementações e adaptadores;
- verticais podem depender de contratos públicos do Core;
- o Core nunca depende de uma vertical;
- integrações entre módulos utilizam contratos públicos ou eventos aprovados;
- dependências entre módulos devem permanecer acíclicas.

---

# Organização

O repositório separa executáveis de capacidades reutilizáveis:

```text
apps/
  api/
  worker/
  web/                  # opcional; criado somente quando aprovado

packages/
  shared_kernel/
  core_contracts/
  core_domain/
  core_application/
  core_infrastructure/
  testing/
  <vertical>_domain/
  <vertical>_application/
  <vertical>_infrastructure/
```

`apps/` contém executáveis, composição e mecanismos de entrega. Não contém regras de negócio.

`packages/` contém capacidades reutilizáveis, contratos e implementações internas.

A árvore representa destinos possíveis. Diretórios e pacotes são criados incrementalmente no primeiro passo que efetivamente os utiliza. Pacotes vazios, camadas sem comportamento e abstrações para funcionalidades futuras são proibidos.

Um novo app ou package exige capacidade atual, consumidor real, owner definido, dependências permitidas e teste proporcional à fronteira criada.

---

# Ownership

Ownership técnico do módulo é diferente da responsabilidade da Organization:

- a Organization determina isolamento, responsabilidade e autorização sobre o registro;
- o módulo determina qual capacidade cria, valida, escreve e evolui tecnicamente o registro.

Cada tabela, coleção, projeção persistida, migration e contrato público possui um único módulo owner.

Somente o módulo owner escreve diretamente em suas estruturas internas. Outros módulos colaboram por contratos públicos, referências tipadas, projeções autorizadas ou eventos.

Um agregado, depois de formalizado em `DOMAIN.md`, pertence a um único módulo e define fronteira de consistência e invariantes. Alteração de ownership exige ADR e plano de migração.

Compartilhar banco ou processo não autoriza acesso direto às estruturas internas de outro módulo.

---

# Regras arquiteturais

O domínio nunca depende do FastAPI.

O domínio nunca conhece SQLAlchemy.

O domínio nunca conhece PostgreSQL.

API e worker reutilizam as mesmas capacidades de Application. Regras de negócio não são duplicadas em executáveis.

Projeções derivadas não se tornam fonte de verdade e devem ser reconstruíveis.

As fronteiras devem ser protegidas por testes arquiteturais que verifiquem:

- ausência de dependência do Core para verticais;
- ausência de framework e infraestrutura no Domain;
- dependências acíclicas;
- ausência de acesso por caminhos internos não públicos;
- ausência de conceitos específicos de vertical no Core.

---

# Evidências

Evidence, Source, Provenance, validação, confiança, freshness e admissibilidade são dimensões distintas. Nenhuma delas prova verdade material isoladamente.

O fluxo conceitual é:

```text
Source → SourceSnapshot → ValidationRequest
    → ValidationAttempt → ValidationAssessment
        ├─ ConfidenceAssessment
        ├─ FreshnessAssessment
        └─ ConflictMaterialityAssessment
            → EvidenceAdmissibilityAssessment
                → Evaluation / Decision

ProvenanceLinks → ProvenancePath
```

## Fronteiras das camadas de evidência

Domain define objetos, relações, estados e invariantes. Não conhece HTTP, OCR, endpoint, JSON externo, banco ou broker.

Application resolve SourceProfile, ValidationScope, FreshnessProfile, OrganizationContext, ProcessingContext, DataContract e Policy; coordena attempts, assessments, admissibilidade, conflito e impacto.

Infrastructure implementa adapters, autenticação técnica, transporte, retry, material bruto e Evidence operacional. Não decide verdade, confiança, admissibilidade ou efeito de negócio.

Presentation expõe origem, escopo, freshness, estado, ReasonCodes e limitações sem revelar campo ou caminho não autorizado.

## Captura e snapshots

SourceSnapshot registra o estado observado de Source com perfil, contrato, instantes, ValidationScope, Digests e referência opaca ao material permitido. Snapshot não é a Source atual nem comprova correção ou completude.

Payload bruto permanece Artifact ou Document quando sua preservação for necessária e autorizada. Event, log, Outbox e contrato público usam referências e campos mínimos.

## Provenance navegável

Toda captura, importação, extração, transformação, validação, contestação e uso relevante produz ProvenanceLink versionado.

ProvenancePath é reconstruído sob Authorization, registra links, versões, direção, filtros, lacunas, ciclos, objetos inacessíveis e completude. Não se torna fonte autoritativa paralela.

Quando preservado para Dossier ou auditoria, o caminho é snapshot imutável do resultado conhecido no instante da consulta.

## Validação e escopo

ValidationScope delimita campo, objeto, coleção, relação ou Document. Application impede ampliação entre request, attempt, assessment e admissibilidade.

ValidationAttempt registra resultado técnico. `FONTE_INDISPONIVEL` e `RESULTADO_DESCONHECIDO` não alteram o VerificationStatus do conteúdo.

ValidationAssessment separa campos confirmados, divergentes, ausentes e não avaliados. Assinatura, resposta autenticada ou estrutura válida não confirma campo fora do escopo.

## Confiança, freshness e conflito

ConfidenceAssessment explica suporte e limitações do processo. Não representa probabilidade de verdade, fraude, precisão estatística ou certeza material, e ConfidenceLevel não é escala ordinal universal.

FreshnessProfile define exigências versionadas; FreshnessAssessment avalia o material no instante. O Core não fixa janela universal e indisponibilidade não renova atualidade anterior.

ConflictAssessment preserva versões divergentes. ConflictMaterialityAssessment avalia impacto somente para finalidade, Policy, Evaluation ou Decision delimitada. Infrastructure não escolhe último valor ou Source mais oficial.

## Admissibilidade e explicação

EvidenceAdmissibilityAssessment decide, por Policy, se Evidence ou ValidationAssessment pode participar de Evaluation. Não altera VerificationStatus nem declara verdade.

ReasonCodes são estáveis e em português; mensagem humana e tradução são separadas do código. Evidence não verificada pode ser admissível para captura e insuficiente para Publication ou Decision sensível.

## Histórico e estado atual

ValidationAssessment histórica preserva material, perfil, método e conhecimento disponíveis no instante original. CurrentValidationAssessment cria novo objeto correlacionado e não substitui o anterior.

Nova informação pode marcar Evaluation, Decision, Dossier ou Publication como potencialmente afetado e iniciar análise autorizada. Não reescreve história nem inicia Recall automaticamente.

## Privacidade, retenção e offline

DataClassification, ProcessingActivity, DataContract, RetentionAssignment e LegalHold acompanham snapshots, links, requests, material, assessments, caches, quarentena e derivados.

Offline registra Source, Actor, Device, Channel, instantes e EvidenceOriginType. Sem Source remota, permanece `NAO_VERIFICADO` ou `VERIFICACAO_PENDENTE`; horário do Device não é prova temporal independente.

## Persistência lógica de evidência

PostgreSQL mantém autoritativamente SourceProfiles, SourceSnapshots, ProvenanceLinks, ValidationScopes, requests, attempts, assessments, conflitos, admissibilidades e relações. GridFS pode manter somente bytes de Artifact ou Document conforme ADR 0004.

Nenhum schema, tabela, índice, adapter, Source concreta ou formato externo é decidido nesta seção.

## Controles arquiteturais de evidência

Testes futuros devem impedir:

- Source, Signature, Digest ou snapshot promovendo conteúdo a verdade;
- validação alcançando campo fora de ValidationScope;
- indisponibilidade ou resultado desconhecido tornando conteúdo inválido;
- ConfidenceAssessment convertida em probabilidade ou score universal;
- FreshnessAssessment sem perfil versionado;
- conflito resolvido sem assessment contextual;
- estado atual sobrescrevendo assessment histórico;
- ProvenancePath incompleto apresentado como completo;
- payload, credencial ou atributo protegido em log ou mensagem;
- offline apresentado como remotamente verificado.

Evidence, snapshots, links e assessments nunca são alterados. Correção ou nova observação cria novos objetos correlacionados.

---

# Localização, residência e transferência de dados

Localização e transferência seguem a ADR 0022. Configuração, declaração, observação e avaliação jurídica são dimensões distintas; região configurada não comprova residência efetiva.

O fluxo é:

`regra → DataLocationAssignment → movimento proposto → DataTransferAssessment → TransferAuthorization → DataMovementRecord → inventário e reconciliação`

## Perfis e composição

DataLocationProfile define locais permitidos para armazenamento, processamento, backups, DR, suporte, acessos, chaves e transferências sem depender de cloud específica.

DataLocationAssignment vincula perfil ao objeto ou escopo e acompanha cópias e derivados. Múltiplas origens compõem as restrições; redução exige assessment, fundamento, Evidence e aprovação.

JurisdictionMappingVersion traduz região nativa do provider para jurisdição canônica com Source, vigência e Evidence. Região sem mapping vigente permanece `LOCALIZACAO_DESCONHECIDA`.

## Inventário e cobertura

DataLocationInventory inclui bancos, objetos, réplicas, backups, DR, caches, busca, analytics, vetores, broker, quarentena, logs, traces, SIEM, email, CDN, temporários, exports, Devices, suporte, integrações, subprocessadores, chaves e ambientes de teste.

Cada entrada declara região configurada e observada, provider, finalidade, categorias, método, freshness, retenção, cobertura, lacunas, ConfidenceAssessment e Evidence. Inventário parcial ou vencido não comprova residência nem ausência de cópias.

## Assessment, autorização e movimento

DataTransferAssessment avalia origem, destino, categorias, titulares, Purpose, ProcessingActivity, papéis, DataContract, provider, subprocessadores, segurança, mecanismo e riscos. Resultado técnico não é parecer jurídico.

TransferAuthorization delimita origem, destino, campos, Purpose, volume, prazo, condições, mecanismo e autoridade. Não substitui Authorization, LegalBasis ou ConsentRecord. Destino ausente é negação e autorização parcial reduz explicitamente o movimento.

DataMovementRecord registra tentativa, início, conclusão, parcialidade, negação ou resultado desconhecido. Confirmação de transporte não comprova persistência, processamento, recebimento de negócio ou descarte na origem.

## Mecanismo e temporalidade

TransferMechanismReference registra mecanismo jurídico ou contratual alegado, partes, jurisdição, vigência, documento, Digest, Source e Evidence. Registro não comprova validade, suficiência ou execução conforme as condições.

Mudança normativa ou de mecanismo inicia revisão e análise de impacto prospectiva. Não invalida movimento histórico automaticamente nem altera onde o dado esteve.

## Acesso remoto, suporte e chaves

Acesso remoto pode constituir transferência mesmo sem download ou cópia persistente. SupportAccessSession exige AuthorizationGrant, PrivilegedAccessSession, TransferAuthorization, localização do operador, Purpose, ticket, escopo, prazo e DataAccessRecords.

Sede da empresa não substitui localização do operador. VPN, VDI e mascaramento reduzem risco, mas não eliminam avaliação.

Local dos dados, chaves, provider criptográfico, backups da chave e operadores são dimensões separadas. Criptografia não elimina localização ou transferência.

## Backups, restore e continuidade

Replicação secundária e DR integram o perfil antes do movimento. Falha primária não autoriza fallback proibido.

Restore é DataMovement próprio e exige destino, finalidade e autorização compatíveis. Autorização para backup não permite restore, processamento, suporte ou ambiente de teste em qualquer região.

## Observação e reconciliação

DataLocationObservation preserva fonte, método, instante, cobertura, confiança, Evidence e limitações. Declaração do provider é Evidence, não prova absoluta.

DataLocationReconciliation compara assignments, inventário, observations e movements. Divergência, incompletude ou localização desconhecida pode bloquear novos movimentos e iniciar remediação ou incidente, mas não move ou apaga dados automaticamente.

## Fronteiras e persistência

Domain não conhece AWS, Azure, GCP, região comercial, Terraform ou SDK. Application resolve restrições, assessments e autorizações. Infrastructure aplica regiões, rotas, storage policies, chaves, inventário e observações. Presentation evita expor topologia sensível.

PostgreSQL mantém autoritativamente profiles, assignments, mappings, inventories, assessments, authorizations, movements, mechanism references, support sessions, observations e reconciliations. GridFS contém somente bytes permitidos conforme ADR 0004.

Testes cobrem região configurada divergente, inventário parcial, backup ou restore incompatível, suporte estrangeiro, novo subprocessador, criptografia no exterior, chave incompatível, derivado multi-origem, profile histórico, cache ou log omitido, Device offline, export controlável indevidamente, mapping sem Evidence e mecanismo apresentado como conclusão jurídica.

Nenhuma cloud, região, mecanismo jurídico concreto, topologia ou prazo universal é escolhido nesta decisão.

---

# Resposta a incidentes e preservação forense

Resposta a incidentes segue a ADR 0023:

`IncidentSignal → IncidentTriage → IncidentCase → IncidentAssessment → ResponseDecision → ResponseAction → RecoveryAssessment → IncidentClosure`

IncidentKnowledgeState preserva o conhecimento usado em cada decisão. Nova Evidence cria snapshot e assessment correlacionados; não reescreve hipótese ou conclusão histórica.

## Avaliação e autoridade

Sinal, caso, suspeita e incidente confirmado são distintos. IncidentSeverityProfile avalia dimensões técnicas, operacionais, pessoais, regulatórias, contratuais e da cadeia sem inferir autoria, culpa, fraude ou responsabilidade.

ResponseDecision autoriza contenção, preservação, investigação, comunicação, recuperação ou monitoramento. Infrastructure executa ações aprovadas, mas SIEM, EDR, SOAR ou provider não confirmam incidente, aceitam risco ou encerram caso.

Containment, Isolation, Eradication, Mitigation e Recovery possuem resultados próprios. Aceitação técnica ou ação parcial não comprova contenção completa.

## Preservação e custódia

ForensicCollection preserva autorização, Source, método, ferramenta, instantes, TimeConfidence, escopo, Digests, original, cópia de trabalho, erros, classificação, retenção e limitações.

ChainOfCustody é append-only e distingue original, cópias e derivados. Transformação produz Artifact e ProvenanceLink novos. Digest não comprova origem, completude, licitude ou admissibilidade jurídica; lacunas permanecem explícitas.

IncidentPreservationScope e LegalHold impedem disposição sem ampliar Visibility, Purpose ou Permission. Quarentena mantém classificação, localização, retenção e acesso mínimo.

## Ações, impacto e desconhecido

ResponseAction preserva executor, tentativa, idempotência, resultado, receipts e Evidence. `RESULTADO_DESCONHECIDO` exige reconciliação; retry não repete efeito sem garantia.

ImpactAssessment localiza dados, Events, Evidence, Decisions, Dossiers, Publications, grants, Signatures, checkpoints, integrações e recalls potencialmente afetados. Dependência não invalida objeto e ausência de caminho não prova ausência de impacto com inventário incompleto.

Comprometimento de chave, Device, principal ou vínculo segue seu ciclo próprio e bloqueia novas operações sem reescrever validade histórica automaticamente.

## Comunicação

CommunicationAssessment é separado por audiência, jurisdição, base e contrato. CommunicationProfile preserva NormativeBasis, trigger, calendário, timezone, prazo, conteúdo e modalidades. O Core não fixa prazo universal.

IncidentCommunication preliminar, complementar ou corretiva permanece versionada. CommunicationDeliveryAssessment distingue entrega comprovada no canal, aceitação técnica, entrega provável, indeterminada e falha. Nenhum receipt comprova leitura ou compreensão humana.

Provider ou terceiro fornece Evidence, não escopo definitivo, papel jurídico, culpa ou obrigação.

## Recuperação, encerramento e melhoria

RecoveryAssessment verifica baseline, backups, restore, patches, secrets, identidades, configuração, integridade, reconciliações, monitoramento e riscos residuais. Restore reaplica LegalHolds, localização, retenção e bloqueios; não reativa Authorization ou direito de uso.

IncidentClosure exige reconciliação de ações, comunicações, holds, impactos, lacunas e riscos. Reabertura cria nova fase relacionada por nova Evidence, escopo, falha de recuperação, comunicação corretiva, impacto tardio ou recorrência.

PostIncidentReview gera ImprovementRecommendation. Mudança exige ImprovementDecision e ActionPlan próprios; equipe de resposta não altera Policy, retenção, configuração, Authorization, arquitetura ou fornecedor diretamente.

## Fronteiras e persistência

Domain não conhece ferramenta de detecção, resposta, ticketing, perícia ou canal regulatório. Application coordena autoridade, playbooks, holds, impacto, comunicação e recuperação. Infrastructure coleta sinais, executa ações e preserva material. Presentation aplica Need-to-Know e redaction.

PostgreSQL mantém autoritativamente sinais, triages, cases, knowledge states, assessments, decisions, actions, custody, communications, recoveries, closures e improvements. GridFS pode manter somente bytes de Artifacts ou Documents autorizados.

Testes cobrem promoção automática de alerta, ausência de log, severidade sem perfil, contenção destrutiva, hold ampliando acesso, coleta incompleta, lacuna de custódia, retry duplicado, atribuição automática, prazo incorreto, comunicação tratada como lida, restore reativando direitos, recuperação parcial, risco sem autoridade, fechamento não reconciliado e melhoria automática.

Nenhum produto, prazo universal, matriz final, obrigação jurídica ou admissibilidade judicial é escolhido nesta decisão.

---

# Exportação, portabilidade e encerramento

Saída de dados segue a ADR 0024:

`ExportRequest → ExportAssessment → ExportAuthorization → ExportOperation → ExportPackage → ExportDeliveryAssessment → ExportReconciliation`

Portabilidade utiliza PortabilityAssessment próprio. Offboarding utiliza plano, inventário, assessment, decisão, ações e reconciliação; não equivale a `Delete()`.

## Escopo, assessment e autorização

ExportScope delimita objetos e versões, Organizations, campos, relações, Provenance, anexos, derivados, formatos, exclusões e redactions. Cada componente recebe assessment individual.

ExportAssessment compõe Authorization, ownership, Visibility, Purpose, FieldScope, DataContract, classificação, papéis, licença, retenção, hold, localização, terceiros e inferência. Redução é declarada sem revelar objeto invisível.

ExportAuthorization é própria e nunca inferida de leitura. Preserva requester, recipient, scope, Purpose, ExportProfile, canal, prazo, volume, limites de download, autenticação e DataTransferAssessment.

PortabilityAssessment preserva interoperabilidade e semântica sem exigir o schema físico do Titan. Portabilidade não altera RecordOwnerOrganization ou ownership histórico.

## Pacote, manifesto e chunks

ExportPackage é composição lógica, não sinônimo de arquivo. ExportManifest descreve exatamente objetos, schemas, relações, componentes, Digests, redactions, LicenseConstraints, LicenseEvidence, warnings, lacunas e limitações.

ManifestDigest protege o manifesto, ChunkDigest protege partes e PackageDigest protege a composição lógica. Mudança de container, compressão ou transporte não altera identidade silenciosamente.

ExportChunk permite retomada idempotente. Alteração de scope, snapshot, profile, manifesto ou conteúdo cria nova identidade.

Secrets, tokens, chaves privadas, configuração defensiva e campos fora do scope nunca entram no pacote. Formato aberto não concede licença ou redistribuição.

## Entrega e importação

ExportDeliveryAssessment distingue pacote criado, disponível, download iniciado ou concluído, aceitação do canal, entrega confirmada e desconhecida. Nenhum marco prova importação, leitura ou uso.

ImportValidationReport valida estrutura, Digests, schema, cobertura e limitações. ImportAssessment avalia compatibilidade semântica, relações, unidades, Provenance, licenças, conflitos e redactions para destino e Purpose delimitados.

Importação parcial não é sucesso integral e importação real não escreve no Domain sem caso de uso autorizado.

ExportedCopyRecord registra o conhecimento sobre cópia entregue. Revogar novos downloads ou VerificationCode não apaga nem controla a cópia externa.

## Offboarding

OffboardingPlan inventaria serviços, principals, Memberships, grants, ServiceIdentities, Devices, integrações, credentials, keys, dados, packages, Publications, jobs, mensagens, contratos, holds, incidentes, terceiros e dependências.

ExitInventory registra estado observado e destino de dados ativos, backups, exports, VerificationBundles, Audit, caches, offline, tokens, webhooks, filas, replicações, Devices, keys, domains e subprocessadores.

OffboardingAssessment considera exportações pendentes, retenção, LegalHold, incidente, ação judicial alegada, ownership, terceiros, localização, dependências e remanescentes. Plano não garante viabilidade.

OffboardingDecision autoriza fases e ações. Revogar, suspender, exportar, handover, preservar e dispor possuem resultados próprios. HandoverRecord não comprova importação correta, assunção jurídica universal ou eliminação na origem.

OffboardingReconciliation compara inventário com entregas, revogações, holds, disposições, terceiros e desconhecidos. Remanescente desconhecido impede conclusão completa; encerramento comercial não é eliminação total.

Histórico de Actor, Audit, Evidence e material público necessário à verificação permanece conforme retenção. Chave privada não exportável não é prometida como portátil.

## Segurança, fronteiras e persistência

Geração usa ambiente temporário restrito, quotas, criptografia, expiração e acesso auditado. Recipient não é validado apenas por email ou nome; URL temporária não aparece em logs.

Domain não conhece ZIP, CSV, Parquet, storage, presigned URL ou ETL. Application resolve contratos, autorização, transferência, retenção e sequência. Infrastructure serializa, divide, cifra, entrega e expira temporários.

PostgreSQL mantém autoritativamente requests, scopes, assessments, authorizations, profiles, operations, manifests, chunks, deliveries, reconciliations, copy records, plans, inventories, decisions e handovers. GridFS pode guardar somente bytes autorizados.

Testes cobrem leitura usada como exportação, componente invisível, licença, scope reduzido, manifesto divergente, chunk alterado, versões concorrentes, secret no pacote, entrega tratada como importação, cópia externa controlável, término sob hold, sessão ativa, histórico removido, key não exportável, inventário parcial e remanescente desconhecido.

Nenhum formato físico, storage, canal, ferramenta, provider, prazo universal ou obrigação jurídica concreta é escolhido.

---

# Operação offline e sincronização segura

Operação offline segue a ADR 0021. O Device captura intenção e Evidence dentro de autoridade materializada e curta; somente o servidor revalida o contexto e produz efeito oficial.

O fluxo é:

`captura local → preservação imutável → transporte → revalidação central → resultado individual → reconciliação → efeito oficial ou rejeição preservada`

Offline nunca realiza autenticação remota, amplia autorização, cria grant, altera Policy ou emite Decision oficial.

## Perfil, sessão e autorização local

OfflineCapabilityProfile classifica comandos como permitidos, permitidos com limites, dependentes de conexão ou proibidos offline. Ausência de perfil é negação.

OfflineSession nasce de autenticação online e vincula principal, Actor, Device, Organization, capacidade, assurance e expiração. Access Token e Refresh Token não integram OfflineOperation.

OfflineAuthorizationSnapshot materializa Permission, grants, Purpose, FieldScope, DataContract e Policy para Device e prazo delimitados. A capacidade efetiva é a menor restrição entre perfil, snapshot, sessão, classificação e contrato. O servidor não confia livremente em contexto fornecido pelo cliente.

DeviceTrustAssessment é temporal e reavaliável. Device registrado com assessment expirado, revogado durante upload ou potencialmente comprometido pode ser bloqueado, limitado ou colocado em quarentena antes do efeito.

## Prévia local

LocalPreview usa `PREVIA_LOCAL_NAO_OFICIAL`, informa Policy e dados materializados, freshness, motor e limitações e pode divergir após sincronização.

Não utiliza identidade visual oficial nem produz DecisionProposal, Decision, Publication, grant, elegibilidade regulatória ou ação downstream.

## Operação e armazenamento

OfflineOperation é envelope append-only com OperationId, identidade semântica canônica, IdempotencyKey, Actor, Organization, Device, sessão, autorização, perfil, contrato, sequência, dependências, instantes, TimeConfidence, Digests, payload mínimo e Evidences.

Reutilização da IdempotencyKey com identidade semântica diferente produz conflito. Dependência referencia OperationId e tipo; ordem física não cria causalidade e ciclo não permanece pendente indefinidamente.

Armazenamento local segue DataClassification, minimização, criptografia, RetentionAssignment e proteção de chave. Falha ou resultado desconhecido de persistência não é apresentado como captura concluída. Logs locais não contêm credencial, token, secret ou PII desnecessária.

## Lote e integridade

SynchronizationBatch preserva BatchId, BatchVersion, OperationManifest, OperationCount, ManifestDigest, SequenceBoundary e CreatedAtDevice. O manifesto detecta remoção, duplicação, substituição e alteração de operação.

Integridade ou assinatura do lote não substitui Digests individuais. Compressão, divisão ou retomada não altera cobertura ou identidade.

SynchronizationBatchResult agrega estados e contagens, mas nunca substitui resultados individuais. Lote recebido ou processado pode conter operações aceitas, rejeitadas, duplicadas, conflitantes, em quarentena ou pendentes.

## Revalidação e resultado

Servidor valida contrato, tamanho, Digests, Device, duplicidade, sequência, dependências, principal, Membership, capacidade, OrganizationContext, Permission, grants, Purpose, FieldScope, DataContract, classificação, retenção, Policy, versão esperada, Evidence, freshness, relógio e conflitos.

Cada OfflineOperation recebe SynchronizationResult em português. `ACEITA` exige efeito oficial e resultado recuperável comprometidos na mesma fronteira transacional. Confirmação de transporte ou lote não comprova aceitação individual.

Falha após commit e antes da resposta produz `RESULTADO_DESCONHECIDO` para o cliente. Esse estado descreve conhecimento de um participante, não ausência, sucesso ou falha, e exige estratégia e prazo de reconciliação. Retry recupera resultado pela mesma identidade sem repetir efeito.

Rejeição, conflito, vínculo encerrado, grant revogado ou Policy alterada não apagam OfflineOperation nem provam fraude.

## Tempo, auditoria e disposição

Device preserva horário observado, horário alegado, timezone, continuidade monotônica, último servidor, offset e TimeConfidence. Relógio monotônico ordena somente dentro de sua continuidade; não produz horário civil, ordem global ou prova temporal.

Marcos locais de captura, apresentação e envio permanecem distintos dos marcos do servidor. Rejeição central não prova ausência de visualização ou materialização local. Worker ou ServiceIdentity não substitui Actor originador.

Aceitação torna a cópia elegível apenas para avaliação de disposição. RetentionPolicy, receipt auditável, reconciliação e LegalHold continuam aplicáveis. Remote wipe aceito não comprova execução ou destruição física.

## Fronteiras e testes

Domain não conhece banco local, sistema operacional, MDM, push, protocolo ou SDK. Application autoriza captura, revalida sincronização e resolve conflitos. Infrastructure implementa armazenamento, criptografia, transporte, retry e adapters de plataforma. Presentation diferencia todos os estados locais e centrais.

Testes cobrem sessão e trust expirados, revogação durante upload, autorização alterada, vazamento local, relógio divergente, IdempotencyKey conflitante, timeout antes e depois do commit, lote adulterado ou parcial, ordem física usada como causalidade, ciclos, resultado desconhecido, LocalPreview oficializada indevidamente, descarte precoce e remote wipe apresentado como concluído.

Nenhuma tecnologia de cliente, banco local, protocolo de sincronização, MDM ou período universal é escolhida nesta decisão.

---

# Integrações externas e validação de fontes

Integrações externas seguem a ADR 0020 e reutilizam SourceProfile, ValidationRequest, ValidationAttempt, SourceSnapshot e ValidationAssessment. Não existe modelo paralelo de proveniência ou confiança.

O fluxo mantém a gramática transversal:

`Request → Attempt → Assessment → Decision`, sustentada por `Evidence` e apresentada por `Report` quando aplicável.

Cada etapa possui significado próprio. Resultado técnico do provider não produz confiança, admissibilidade, conformidade, elegibilidade ou efeito jurídico.

## Fronteiras

Application define e utiliza a porta `ExternalEvidenceProvider`, resolve Authorization, Purpose, ValidationScope, DataContract, SourceProfile e FreshnessProfile e coordena assessments.

Infrastructure seleciona adapter previamente configurado e implementa autenticação técnica, transporte, parsing, retry, rate limit, cache, reconciliação e referência ao material bruto.

Domain não conhece a porta, HTTP, SOAP, SDK, endpoint, credencial, payload ou código específico do provider. Presentation expõe origem, instante, escopo, freshness, estado e limitações sem revelar campos não autorizados.

Provider, endpoint, redirect e credencial nunca são escolhidos pelo payload. Destinos e certificados seguem configuração confiável e allowlist.

## Contrato, mapping e capacidades

MappingVersion identifica tradução imutável entre schema externo e contrato interno, incluindo unidades, códigos, timezone, nulidade, serialização, precisão, paginação, cobertura, parser e limitações.

ContractCompatibilityAssessment separa compatibilidade completa, parcial, incompatível e desconhecida. Compatibilidade estrutural não comprova equivalência semântica. Mudança incompatível bloqueia uso automático até avaliação adequada.

SourceCapabilities registra capacidades comprovadas para SourceProfile e versão do contrato, como snapshot consistente, cursor estável, filtros, assinatura, idempotência, consulta de status, callback e limites. Capacidade não é presumida ou transferida entre versões.

Fallback entre providers exige equivalência aprovada de finalidade, contrato, autoridade e qualidade. A origem efetivamente utilizada permanece explícita e providers distintos não viram confirmações independentes automaticamente.

## Autorização e minimização

Antes da chamada, Application compõe principal, capacidade, Organization, Purpose, Permission, grant, FieldScope, DataContract, DataClassification, ProcessingActivity e Policy pela menor restrição aplicável.

Permissão de consulta interna não autoriza envio externo, persistência bruta, compartilhamento, exportação, inferência ou treinamento de IA. Request e response são minimizados antes de atravessar ou permanecer na fronteira.

Logs, traces, métricas, Outbox e relatórios não contêm secrets, tokens, payload integral ou atributos pessoais. Respostas preservadas recebem classificação, retenção e contrato próprios.

## Tentativa, desconhecido e reconciliação

Cada execução cria ValidationAttempt correlacionada à ValidationRequest. Conteúdo observado produz SourceSnapshot imutável com contrato, MappingVersion, Digests, escopo, instantes e limitações.

`RESULTADO_DESCONHECIDO` nunca é convertido automaticamente em inexistência, rejeição, invalidade ou falha de negócio. Retry cria nova tentativa, preserva IdempotencyKey, aplica limites e não apaga efeitos possíveis da anterior.

Operação externa com efeito somente recebe retry automático quando a idempotência for comprovada. Caso contrário, segue para reconciliação ou revisão segura. Ausência de resposta na reconciliação não prova ausência de processamento.

## Parsing, replay e material externo

ParsingAssessment registra Artifact ou Document, parser e versão, MappingVersion, formatos, campos, warnings, erros, conteúdo ignorado e limites. Parsing bem-sucedido não confirma verdade do conteúdo.

ReplayProtectionEvidence preserva identificador não secreto, timestamp, Digest, janela, mecanismo e resultado. Ela comprova apenas o controle executado no escopo observado.

Callbacks, uploads e respostas são não confiáveis até validação. Parsing ocorre com limites de tamanho, tipo e recursos. Conteúdo recebido não seleciona URL, caminho, parser, algoritmo ou credencial. Material sem correlação suficiente permanece em quarentena observável.

## Cache, lote e cobertura

Cache é otimização e respeita SourceProfile, contrato, scope, Purpose, Organization, classificação, instante e FreshnessProfile. Indisponibilidade não renova cache expirado e uma entrada não atravessa contexto autorizado.

Paginação e lote registram cursor, ordenação, páginas, contagens, duplicidades, omissões e truncamento. Completude exige fronteira demonstrável. Mudança concorrente sem snapshot consistente permanece como limitação, nunca lista vazia conclusiva.

## Persistência e testes

PostgreSQL mantém autoritativamente MappingVersions, ContractCompatibilityAssessments, SourceCapabilities, ReplayProtectionEvidences, ParsingAssessments e suas relações. GridFS pode guardar somente bytes de Artifact ou Document conforme ADR 0004.

Testes contratuais usam adapter determinístico e fixtures sintéticas sem credenciais reais. Cobrem contratos completos, parciais, incompatíveis e desconhecidos; mudança de capacidades; campos novos e nulos; timeout antes e depois do envio; retry e rate limit; paginação truncada; replay; parsing malicioso; minimização; isolamento contextual; cache expirado e tentativa do adapter de ampliar escopo ou produzir Decision.

Nenhuma Source concreta, API, schema, fila, worker, scheduler ou tecnologia de cache é escolhida nesta decisão.

---

# Governança, classificação e ciclo de vida de dados

O Titan classifica dados antes de armazenar, transmitir, derivar, publicar ou exportar. Classificação, fundamento, consentimento, contrato de dados e autorização são dimensões distintas.

O fluxo conceitual é:

```text
ProcessingActivity
    ↓ declara contexto e finalidade
DataContract
    ↓ restringe o intercâmbio
Authorization
    ↓ decide a operação concreta
payload classificado
    ↓ transformação
ClassificationPropagation → objeto derivado
```

ProcessingActivity e DataContract não concedem acesso. ProcessingContext explica o tratamento; OrganizationContext autoriza a operação protegida.

## Fronteiras das camadas de dados

Domain define classificação, referências opacas, atividade, papéis declarados, contratos, avaliações, propagação e invariantes. Não conhece banco, provider de IA, algoritmo criptográfico ou legislação concreta.

Application resolve ProcessingActivity, ProcessingContext e DataContract; valida finalidade, campos e papéis; executa Authorization; coordena ClassificationAssessment, ClassificationPropagation, anonimização, correção e impacto.

Infrastructure implementa criptografia, armazenamento, transporte, redaction técnica, adapters de IA, observabilidade, backup e futura disposição física. Não decide fundamento, papel jurídico, finalidade, anonimização ou redução de proteção.

Presentation aplica FieldScope, Visibility e DisclosureAudience, preserva razões e não revela recurso, atributo protegido, pseudônimo como anônimo ou PrivacyImpactAssessment como relatório regulatório.

## Atividade, fundamento e papéis

Operação protegida resolve ProcessingActivity versionada e válida, contendo propósito, operações, categorias de dados e titulares, LegalBasisReferences, DataProcessingRoleAssignments, Sources, destinatários, DataContracts, transferências, retenção referenciada, segurança e sistemas.

LegalBasisReference, ConsentRecord e AuthorizationGrant não são equivalentes. Consentimento não é fundamento universal, claim confiável do cliente ou permissão interna.

DataProcessingRoleAssignment é resolvido por Organization, atividade, jurisdição, período, finalidade, NormativeBasis, Evidence e validade. RecordOwnerOrganization, armazenamento ou controle técnico não definem papel jurídico.

Tratamento observado deve ser reconciliável com atividade declarada. Ausência, expiração ou finalidade incompatível falham conforme Policy.

## Aplicação de DataContract

DataContract é selecionado pelo servidor e validado em entrada e resposta de API, comunicação entre módulos, Event, Outbox, Inbox, Message Broker, importação, exportação, Publication, VerificationBundle, integração e IA.

A validação confirma produtor, consumidor, versão, campos permitidos e proibidos, finalidade, DataClassifications, transformações, retenção, localização, publicação, disposição e compatibilidade.

Campo, finalidade, consumidor ou transformação incompatível bloqueiam produção ou consumo. Mudança incompatível cria nova versão. Revogação impede novos fluxos sem apagar histórico.

DataContract não substitui ProcessingActivity, AuthorizationGrant, OrganizationContext ou Authorization e não amplia Visibility.

## Avaliação e propagação

Entrada ou mudança relevante produz ClassificationAssessment com ClassificationOrigin, ClassificationConfidence, método, Evidence, assessor, revisão e limitações.

Derivação produz ClassificationPropagation com origem, destino, classificações, regra versionada, transformação, resultado e justificativa.

Ausência de regra aplica proteção mais restritiva, bloqueio ou revisão. Redução exige Policy, Permission, Actor, Evidence, justificativa, nova versão e auditoria. Regra nova não reclassifica histórico silenciosamente.

Classificação composta respeita o componente mais restritivo salvo composição formal aprovada.

## Fronteira de atributos pessoais

Registro operacional utiliza DataSubjectReference ou PersonalDataReference opaca. Resolução ocorre somente por caso de uso autorizado através de porta interna; adapter ou repositório operacional não resolve atributo diretamente.

```text
registro operacional → referência opaca → fronteira protegida
```

Nome, documento, contato, endereço, biometria ou saúde não são replicados por conveniência. Exceção exige finalidade, classificação, necessidade, autorização, retenção e teste.

IdentityVault, schema, banco, serviço e topologia permanecem para decisão própria.

## Events, Outbox e Message Broker

Antes da persistência ou publicação, Application valida DataContract, minimiza campos, preserva IDs opacos, registra DataClassification e limita consumidores e retenção operacional.

Nome, documento, contato, endereço, biometria, saúde, credencial ou Document integral não entram por padrão. Exceção exige contrato versionado, necessidade, criptografia, consumidores, retenção e teste.

Inbox, quarentena, dead-letter e replay preservam classificação, finalidade e limites e não transformam Message Broker em repositório pessoal.

## Logs e observabilidade

Logs, traces e métricas usam correlação, IDs opacos, códigos, categorias, resultado e razão segura. Payload, token, documento, atributo pessoal, prompt, output, embedding ou secret são proibidos por padrão.

Redaction posterior não substitui prevenção. Debug privilegiado exige finalidade, prazo, ambiente, aprovação, acesso e disposição próprios. Labels não contêm identificador pessoal ou conteúdo de alta cardinalidade.

## Operação offline

Perfil offline valida comando, DataClassification, campos mínimos, proteção local, prazo, Device, inventário, sincronização e disposição após confirmação.

OfflineOperation não contém credencial. Sincronização revalida identidade, vínculo, Permission, Organization, finalidade, ProcessingActivity, DataContract, classificação, Policy, versão, conflito e revogação.

Perda ou comprometimento de Device inicia resposta a incidente e análise de conteúdo potencialmente exposto.

## IA, OCR e derivados

Provider de IA é consumidor sujeito a DataContract, ProcessingActivity, Authorization e ClassificationPropagation.

Documento, imagem, prompt, contexto, OCR, output, embedding, vector store, índice, dataset, feature, feedback, cache e model artifact aplicável preservam classificação, finalidade, papel, licença e restrição.

O caso de uso avalia provider, localização, retenção, subprocessadores, uso para treinamento, memorization, reconstrução, inferência, exportação e incidentes. Acesso técnico ao endpoint não autoriza transmissão.

OCR, agregação, pseudonimização, embedding ou transformação estatística não produzem anonimização automática.

## Anonimização e impacto de privacidade

Application exige AnonymizationAssessment antes de reduzir IdentifiabilityLevel. Avalia técnica, informação adicional, meios razoáveis, adversários, singularização, ligação, inferência, finalidade, contexto e revisão.

PrivacyImpactAssessment pode ser exigida antes de tratamento de risco ou mudança relevante. Preserva necessidade, proporcionalidade, riscos, controles, risco residual, divergências, aprovação e revisão.

PrivacyImpactAssessment genérica não é apresentada como RIPD ou relatório regulatório sem DisclosureProfile, NormativeBasis, autoridade e escopo próprios. Versões interna e pública passam por minimização e Publication distintas.

## Retenção e revisão

Application resolve RetentionPolicy e RetentionAssignment sem aceitar política ou prazo fornecido livremente pelo cliente. RetentionClock calcula trigger, pausas, retomadas e expiração com TimeConfidence e fontes verificáveis.

Nova Policy, Evidence, mudança normativa, conflito ou review due produz RetentionReview. Conflito produz RetentionConflictAssessment; não prevalece automaticamente o maior ou menor prazo.

Vencimento, solicitação, retirada de consentimento ou liberação de hold tornam o objeto avaliável. Nenhum deles executa descarte automaticamente.

## Legal hold

LegalHold é criado, alterado ou liberado por caso de uso autorizado, Actor competente e segregação exigida. O cliente não escolhe autoridade, fundamento ou escopo como claim confiável.

Application aplica hold determinístico sobre DispositionScope antes de qualquer ação. Hold bloqueia disposição abrangida, mas não amplia Visibility, finalidade, DataContract, Publication, Sharing ou Authorization.

Liberação inicia nova avaliação. Jobs de disposição nunca removem ou ignoram hold.

## Avaliação e escopo de disposição

DispositionAssessment resolve assignments, clocks, conflitos, holds, contratos, inventário, cópias, derivados, impacto, autoridade e ação aprovada.

DispositionScope é imutável e compartilhado por decisão, operação, receipts e reconciliação. Ampliação ou exclusão exige nova avaliação e autorização.

Códigos de razão são estáveis e em português. Estado desconhecido, inventário incompleto, confiança temporal insuficiente ou conflito falham fechados.

## Plano de controle e plano de execução

O runtime ordinário pode solicitar e consultar avaliações, mas não executa PhysicalDisposition, destrói chave ou recebe `DELETE` em estruturas protegidas.

Um plano de controle privilegiado cria DispositionOperation após avaliação autorizada. Executores técnicos usam ServiceIdentity, menor privilégio, escopo imutável, IdempotencyKey e credenciais separadas por ambiente.

Solicitante, aprovador, executor e reconciliador são Actors distintos quando o perfil exigir segregação. Claim ou lease abandonado é recuperável.

Falha de comunicação pode produzir resultado desconhecido. Retry preserva identidade lógica e não amplia escopo.

## Disposição lógica, física e Evidence

LogicalDisposition bloqueia resolução, uso e novos acessos. PhysicalDisposition remove material dos alvos inventariados. Bloqueio lógico não é apresentado como destruição física.

Cada adapter produz DispositionReceipt imutável com resultado local. Receipt é registro operacional e referencia ou produz Evidence verificável; não se torna Evidence automaticamente.

DispositionReconciliation compara alvos esperados, concluídos, ausentes, desconhecidos e inconsistentes. Somente a reconciliação global pode sustentar DispositionReport concluído.

O histórico separa envelope mínimo de payload pessoal. Correction atualiza CurrentProjection sem reescrever Event, Evaluation ou Decision. Evento, receipt e relatório não contêm valor eliminado, hash previsível ou segredo de reconstrução.

Decision, Publication, Dossier ou VerificationBundle dependente recebe análise de impacto e pode ser marcado como potencialmente afetado. Disposição não o invalida nem inicia Recall automaticamente.

## Chaves e crypto-shredding

EncryptionKey, Data, Digest e Evidence são distintos. Destruir chave não elimina cópia em claro; rotação não muda DataClassification; recuperação não restaura Authorization.

Crypto-shredding exige chave exclusiva do escopo e considera backup, escrow e cópias. Evidência comprova procedimento inventariado, não inexistência absoluta do dado.

Gestão de chaves segue ADR 0008; hierarquia, KMS, HSM e escrow não são decididos aqui.

## Backup e restauração

Backup preserva DataClassifications, ProcessingActivities, DataContracts, RetentionAssignments, LegalHolds, propagações, bloqueios e ledger de disposição.

Restore reaplica holds, bloqueios e disposições antes de liberar uso, reconcilia PostgreSQL, GridFS, caches e índices e impede retorno operacional de conteúdo eliminado.

Backup possui política, inventário e acesso próprios. Expiração previsível pode coexistir com bloqueio lógico de reintrodução; cópia expirada não é conservada por conveniência.

## Persistência lógica

PostgreSQL mantém autoritativamente DataClassification, assessments, propagação, ProcessingActivity, papéis, DataContract, AnonymizationAssessment, PrivacyImpactAssessment, RetentionPolicy, RetentionAssignment, RetentionClock, LegalHold, DispositionScope, operações, receipts, reconciliações, relatórios, referências e eventos de ciclo de vida.

MongoDB/GridFS permanece limitado aos bytes de Artifact ou Document. Identidade, classificação, ownership, versão, estado, autorização e relações ficam no PostgreSQL.

Nenhuma tabela, schema, índice ou tecnologia de fronteira pessoal é decidida nesta seção.

## Controles arquiteturais de dados

Testes futuros devem impedir:

- operação protegida sem ProcessingActivity aplicável;
- DataContract ausente, incompatível ou com campo proibido;
- finalidade ou consumidor não autorizado;
- papel jurídico inferido de ownership;
- dado pessoal em mensagem, log, trace ou métrica;
- derivação, OCR, IA ou embedding sem propagação;
- provider usando conteúdo para treinamento fora do contrato;
- hash, pseudônimo, agregado ou embedding tratado como anônimo;
- PrivacyImpactAssessment apresentada como RIPD automaticamente;
- Correction reescrevendo histórico;
- disposição ou `DELETE` acessível ao runtime;
- vencimento, solicitação ou liberação de hold executando descarte automático;
- relógio inconsistente, conflito ou inventário desconhecido concluindo disposição;
- DispositionScope alterado durante execução;
- LegalHold ampliando acesso ou sendo removido pelo executor;
- receipt tratado como Evidence ou executor definindo conclusão global;
- LogicalDisposition apresentada como PhysicalDisposition;
- restore reativando conteúdo eliminado;
- crypto-shredding com cópia ou escrow acessível.

---

# Fundamentação normativa e decisões temporais

O Titan preserva a fundamentação normativa utilizada por Policy, Rule, Evaluation e Decision sem transformar texto externo em regra executável ou conclusão jurídica automática.

O fluxo conceitual é:

```text
Source externa
    ↓ captura e verificação
NormativeInstrumentVersion
    ↓ NormativeReference
NormativeBasis aprovada
    ↓ fundamenta
Policy / Rule
    ↓ executa
Evaluation
    ↓ produz
Decision
```

NormativeInstrument mantém a identidade do instrumento. NormativeInstrumentVersion preserva conteúdo imutável. NormativeProvision identifica dispositivo. NormativeRelation descreve alteração, revogação, substituição, consolidação, correção, regulamentação ou referência sem deduzir efeito jurídico total.

## Fronteiras das camadas

Domain define conceitos, invariantes, temporalidades, relações, tipos e escopos de afirmação. Não conhece portal, parser, protocolo, banco, legislação concreta ou regra de vertical.

Application coordena casos de uso de captura, validação, aprovação, publicação de interpretação, seleção contextual, reprodução, avaliação histórica, simulação, reavaliação e análise de impacto. Somente ela decide quando invocar regras de domínio e exigir revisão humana.

Infrastructure implementa portas para obtenção de fontes, armazenamento, Digest, Signature, material de Evidence e consulta a serviços externos. Não decide aplicabilidade, interpretação ou efeito jurídico.

Presentation preserva AssertionType, AssertionScope, Evidence, razões e limitações. Texto, API, relatório, exportação ou interface não podem ampliar conclusão técnica nem apresentá-la como jurídica.

Verticais fornecem significado, jurisdição, políticas e regras concretas por contratos públicos do Core. O Core nunca importa legislação concreta nem conceitos específicos de uma vertical.

## Ingestão e aprovação

Conteúdo normativo externo é não confiável. O caso de uso:

1. valida OrganizationContext, Permission, finalidade e Source;
2. captura conteúdo, metadata, instante, método e responsável;
3. preserva Artifact ou referência imutável permitida;
4. calcula Digest e registra Evidence disponível;
5. avalia separadamente identidade, autoridade e oficialidade da Source;
6. cria NormativeInstrumentVersion sem sobrescrever versão anterior;
7. registra NormativeProvisions e NormativeRelations sustentadas;
8. submete NormativeBasis a interpretação e aprovação autorizadas;
9. publica nova versão da base para uso delimitado.

`official_status_declared` nunca é promovido silenciosamente a `official_status_verified`. Digest válido confirma integridade da cópia, não autoridade, oficialidade, aplicabilidade ou validade jurídica.

Extração, classificação ou comparação automática pode auxiliar o fluxo, mas seu resultado é Claim ou material de revisão. Não cria Rule, NormativeBasis aprovada ou conclusão oficial sem Actor, competência declarada, Evidence e autorização.

Aprovação privada permanece decisão da Organization. Reconhecimento de autoridade pública, tribunal, certificadora ou auditor externo exige Evidence específica e escopo correspondente.

## Seleção temporal e snapshot

Seleção de NormativeBasis, Policy e Rules considera conjuntamente:

- emissão, publicação e vigência declarada;
- aplicabilidade contextual e regras transitórias;
- jurisdição, atividade, território, produto, mercado e Subject;
- instante ou intervalo dos fatos;
- instante de conhecimento pelo processo;
- instante de Evaluation, Decision e referência da pergunta.

`decision_at` sozinho nunca seleciona a fundamentação. Lacuna ou conflito produz estado explicado com razão controlada, incluindo política ausente, múltiplas políticas, conflito normativo, lacuna temporal, jurisdição ou autoridade indeterminadas.

Evaluation e Decision preservam NormativeBasisSnapshot correlacionado ao snapshot dos fatos. O snapshot contém versões, dispositivos, Digests, aplicabilidade, instantes de referência e conhecimento, aprovação, Evidence, lacunas e limitações e não muda quando fonte, interpretação ou Policy evoluem.

## Operações temporais

Os casos de uso possuem semânticas separadas:

- **HistoricalReproduction:** reexecuta snapshot, Policy, Rules, base e motor originais e produz relatório de reprodutibilidade;
- **HistoricalComplianceAssessment:** cria nova Evaluation sobre o contexto histórico e declara conhecimento posterior utilizado;
- **CounterfactualSimulation:** aplica alternativa identificada a snapshot declarado e produz resultado hipotético sem efeito operacional;
- **CurrentReevaluation:** executa contexto atual e pode produzir nova Evaluation e Decision autorizadas, correlacionadas às anteriores.

Nenhuma operação reescreve Evaluation ou Decision original. `Replay` de mensagem, reprodução histórica e simulação são mecanismos distintos. Código atual não é apresentado como reprodução exata de motor histórico sem versão e material correspondentes.

## Afirmações e apresentação

Toda conclusão transporta:

```text
resultado
+ AssertionType
+ AssertionScope
+ Evidence utilizada
+ códigos de razão
+ limitações
```

AssertionType distingue afirmação factual, computacional, de proveniência, normativa e jurídica. AssertionScope delimita objeto, Organization, finalidade, período, instante de referência, jurisdição, Policy, Rules, motor, dados incluídos ou excluídos, autoridade e lacunas.

O motor genérico não emite afirmação jurídica sem perfil especializado, autoridade competente e revisão e aprovação registradas. Afirmação normativa descreve interpretação adotada, não entendimento oficial universal.

## Impacto normativo e Recall

Mudança normativa pode iniciar análise autorizada:

```text
NormativeInstrumentVersion ou NormativeRelation
    ↓ dependências por Provenance
NormativeBasis → Policy → Rule
    ↓
Evaluations, Decisions, Dossiers e Subjects
    ↓
POTENCIALMENTE_AFETADO
    ↓ revisão autorizada
decisão operacional própria
```

O relatório de impacto preserva versões e dispositivos comparados, relações, dependências diretas, indiretas, semânticas possíveis ou desconhecidas, caminho de Provenance, período, Organizations, limites de Authorization, lacunas, razões, Actor e finalidade.

`POTENCIALMENTE_AFETADO` não significa inválido e não modifica Decision, Dossier, Publication, Signature ou Evidence. Detecção técnica, avaliação regulatória, decisão de negócio, comunicação e execução permanecem separadas.

Recall exige caso de uso específico, Policy aprovada e Actor competente. O Core pode localizar população potencial, mas não declara automaticamente obrigatoriedade, dispensa, culpa, fraude, sanção ou extensão final.

Anomalia, inconsistência, afirmação sem suporte, conflito de Evidence ou potencial manipulação não são fraude. Policy especializada pode solicitar revisão de fraude, mas a solicitação ainda não é conclusão.

## Persistência lógica

PostgreSQL mantém registros autoritativos de NormativeInstrument, NormativeInstrumentVersion, NormativeProvision, NormativeRelation, NormativeReference, NormativeBasis, NormativeBasisSnapshot, relatórios temporais, AssertionScope e análises de impacto.

MongoDB/GridFS pode armazenar somente bytes de Artifact ou Document conforme a ADR 0004. Digest e referência opaca ficam no PostgreSQL; conteúdo binário não atravessa para Domain.

Nenhuma tabela, schema, índice, formato de captura ou API é decidido nesta seção. Cada estrutura futura terá um único módulo owner, RecordOwnerOrganization quando protegida, imutabilidade, autorização e retenção compatíveis com sua função.

## Controles arquiteturais

Testes futuros devem verificar:

- ausência de conceitos de vertical ou infraestrutura no Core;
- impossibilidade de Infrastructure decidir aplicabilidade;
- versões e snapshots imutáveis;
- separação entre integridade, identidade, autoridade e oficialidade;
- aprovação privada não apresentada como oficial;
- seleção multitemporal e razões de indeterminação;
- reprodução, avaliação, simulação e reavaliação sem efeitos cruzados;
- conhecimento posterior separado do original;
- propagação de AssertionType e AssertionScope;
- isolamento e Visibility por Organization;
- impacto potencial sem invalidação ou recall automático;
- conteúdo externo malicioso, mutável ou apenas declarado oficial.

---

# Decisões explicáveis, revisão e contestação

O Titan separa resultado técnico, proposta, autoridade, Decision, revisão, contestação, override, reavaliação e impacto.

```text
Claim / Evidence → ValidationAssessment → EvidenceAdmissibilityAssessment
    → Evaluation / EvaluationOutcome → DecisionProposal
    → DecisionAuthorityProfile / aprovação → Decision
    → Review / Challenge / Override → Reevaluation
    → DecisionRelation → análise de impacto
```

Uma etapa não substitui a anterior. Análise de impacto localiza dependentes e não invalida objetos automaticamente.

## Fronteiras das camadas de decisão

Domain define resultados, razões, autoridade, review, challenge, override, relações e invariantes. Não conhece API, banco, workflow engine ou interface.

Application coordena Policy, Evaluation, proposal, autorização, review, reavaliação, emissão, efeito provisório, impacto e publicação.

Infrastructure persiste registros, entrega notificações e executa adapters. Não decide resultado, autoridade, override ou efeito de negócio.

Presentation coleta solicitações e apresenta explicações autorizadas. Resultado, status, AuthorityProfile, Permission ou aprovação fornecidos pelo cliente não são confiáveis.

## Evaluation e proposta

DecisionEngine produz Evaluation determinística e EvaluationOutcome. Quando autoridade ou revisão forem exigidas, produz DecisionProposal, nunca Decision oficial disfarçada.

Outcome separa condições satisfeitas, não satisfeitas, informação insuficiente, Evidence conflitante, validação pendente, revisão humana e indeterminação.

Proposal é imutável, não altera State e não atravessa contrato público como decisão emitida. Expiração ou rejeição não altera Evaluation.

## Razões e emissão

DecisionReason preserva código em português, Rule, condição, valores autorizados, Evidence, limitações e mensagem humana separada. Redaction ou tradução não inverte conclusão nem oculta restrição material.

Application resolve DecisionAuthorityProfile no servidor e valida finalidade, Organization, Permission, competência, Evidence, autenticação, segregação, limites, validade e aprovações.

Membership, cargo, ownership ou claim externo isolado não comprovam autoridade. Decision registra método `AUTOMATICA_AUTORIZADA`, `HUMANA`, `HUMANA_ASSISTIDA` ou `OVERRIDE_AUTORIZADO`.

## Review e challenge

DecisionReview possui transições, concorrência e reabertura controladas por Policy. ReviewEvidenceSubmission passa por Provenance, ValidationAssessment e EvidenceAdmissibilityAssessment antes do uso.

DecisionChallenge registra escopo, fundamento, razões, Evidence e prazo sem suspender, revogar ou invalidar Decision automaticamente.

ReviewAssessment recomenda manter, reavaliar, exigir Evidence ou considerar override. Não altera RuleResult e não é Decision.

Suspensão, restrição ou manutenção provisória exige caso de uso, autoridade, prazo, razões e registro próprios.

## Override, reavaliação e relações

DecisionOverride autoriza excepcionalmente nova Decision em escopo delimitado. Não altera Fact, Evidence, RuleResult, Evaluation ou Decision anterior e não declara condição satisfeita.

Expiração pode iniciar Reevaluation, nunca reversão histórica. Reevaluation registra snapshot, Evidence, Policy, Rules, motor e motivo; `VALIDACAO_CONCLUIDA` não implica resultado positivo.

DecisionRelation expressa confirmação, restrição, revogação ou substituição para novos efeitos e origem em revisão, override ou reavaliação. Efeitos históricos permanecem explicados.

## Automação, assistência e offline

Modelo estatístico ou IA pode produzir Claim, extração ou recomendação conforme DataContract e Provenance. Não recebe autoridade decisória por capacidade técnica.

Revisão humana registra acesso às informações materiais e conclusão própria. Clique formal sem contexto não é revisão significativa.

Captura offline de challenge ou Evidence depende de perfil. Emissão oficial, conclusão de review, efeito provisório e override exigem conexão ou são proibidos offline conforme Policy.

## Impacto e downstream

Review, Challenge, nova Evidence, Override, Reevaluation ou Decision podem iniciar análise autorizada por Provenance.

A análise localiza State, NonConformities, Dossiers, Publications, Sharings, integrações, Decisions dependentes e objetos de Recall potencialmente afetados.

Comunicação, republicação, revogação, ação corretiva, sanção ou Recall exigem decisões próprias. `POTENCIALMENTE_AFETADO` não significa inválido, fraude ou culpa.

## Persistência lógica de decisões

PostgreSQL mantém autoritativamente Outcomes, Proposals, Reasons, AuthorityProfiles, Reviews, Challenges, submissions, assessments, Overrides, Reevaluations, DecisionRelations e efeitos provisórios.

Nenhum schema, tabela, endpoint, fila, worker, SLA ou workflow engine é decidido nesta seção.

## Controles arquiteturais de decisão

Testes futuros devem impedir:

- Proposal apresentada como Decision;
- Decision sem Evaluation ou autoridade;
- razão sem estrutura ou redaction enganosa;
- review alterando RuleResult ou história;
- challenge produzindo efeito provisório implícito;
- Evidence de review usada sem validação e admissibilidade;
- override sem competência, justificativa, escopo, validade e aprovação;
- expiração de override reescrevendo efeitos anteriores;
- IA ou cliente escolhendo resultado ou autoridade;
- ação downstream ou Recall automático.

---

# Correção, supersession e análise de impacto

O Titan registra mudanças sem reescrever história e decide respostas downstream somente depois de análise autorizada.

```text
CorrectionRequest → CorrectionAssessment
    → Correction / Revocation / nova versão / SupersessionRelation
    → CurrentProjection
    → ImpactTrigger + ImpactScope
    → ImpactAssessment → ImpactFindings
    → ImpactResponseDecision → ImpactResponseDirectives
```

Mudança detectada não é consequência decidida. Nova Evidence, método ou norma não se torna Correction automaticamente.

## Fronteiras das camadas de correção

Domain define ChangeKind, scopes, relações, temporalidade, impacto, diretivas e invariantes. Não conhece banco, API, graph engine, broker ou interface.

Application coordena request, assessment, autorização, Correction, projeção, análise, decisão de resposta e reconciliação.

Infrastructure persiste versões, reconstrói projeções, percorre relações e entrega notificações. Não escolhe versão correta, materialidade ou resposta.

Presentation coleta solicitações e mostra histórico, versão aplicável, conflitos, impacto e limitações conforme Authorization.

## Mudança e supersession

CorrectionRequest aponta para objeto e versão esperada. Application resolve CorrectionScope, Evidence, ChangeKind e autoridade; cliente não escolhe efeito ou versão corrente.

CorrectionAssessment decide entre Correction, Revocation, nova versão, SupersessionRelation, Evidence adicional ou revisão. Assessment não altera State.

SupersessionRelation é direcional, acíclica e finalística. Não transfere ownership ou Visibility e não declara falsidade automática da origem.

Nova Evidence, evolução metodológica, mudança normativa, Revocation e republicação mantêm semânticas distintas.

## Temporalidade e concorrência

Application preserva ocorrência, registro, descoberta, solicitação, correção, efetividade e conhecimento com Source, timezone e TimeConfidence.

Efetividade anterior à correção não reescreve conhecimento histórico. Retroatividade exige decisão própria.

Versão esperada e concorrência otimista impedem last-write-wins. IdempotencyKey protege repetição da intenção; resultado desconhecido exige reconciliação.

## CurrentProjection

CurrentProjection é reconstruída por objeto, finalidade, instante, OrganizationContext e Policy usando relações, efetividade, Revocations, escopo, conflitos e Authorization.

Não seleciona apenas o timestamp mais recente. Ciclo, bifurcação, versão ausente ou ambiguidade falham como `INDETERMINADA` ou exigem revisão.

Projection registra caminho histórico usado e não se torna Evidence.

## Navegação e completude do impacto

ImpactAssessment opera sobre ImpactTrigger, ImpactScope, snapshot temporalmente consistente e vocabulário versionado de dependências.

Registra esperados, visitados, não avaliados, inacessíveis, profundidade, truncamentos, lacunas, ciclos, alterações concorrentes e critérios de parada.

Ausência de caminho não prova ausência de dependência. `NAO_AFETADO` exige avaliação suficiente; inventário parcial, autorização limitada ou método incompleto produzem `NAO_AVALIADO`, `INACESSIVEL` ou `INDETERMINADO`.

Mudança concorrente exige novo snapshot ou conclusão indeterminada. Classificação vale somente para scope, snapshot, Policy e instante declarados.

## Findings e materialidade

ImpactFinding preserva objeto e versão, ProvenancePath, dependência, campo ou pressuposto, Evidence, estado, materialidade, confiança e limitações.

Dependências diretas, indiretas, derivadas, semânticas, normativas, temporais e operacionais usam vocabulário versionado. Link direto não é requisito para dependência semântica.

Caminhos correlacionados da mesma Source não são corroboradores independentes. Materialidade para uma finalidade não é universal.

`AFETADO_CONFIRMADO` significa alcance de conteúdo ou pressuposto no escopo; não significa inválido, fraude, culpa ou efeito jurídico.

## Respostas e diretivas

ImpactResponseDecision autoriza uma ou mais ImpactResponseDirectives. Cada diretiva possui tipo, escopo, executor, prioridade, prazo, idempotência, estado, resultado, Evidence e limitações.

Finding não executa ação. Reavaliação, correção, restrição, revogação, republicação, comunicação, NonConformity e análise de Recall usam casos de uso próprios.

Conclusão global exige reconciliação de todas as diretivas. Estado pendente, parcial, falho ou desconhecido não é apresentado como concluído.

Aceitação pelo Message Broker não comprova recebimento, processamento ou efeito no destinatário.

## Offline, persistência e controle

Request e Evidence podem ser capturadas offline por perfil. Correction oficial, SupersessionRelation e decisão de resposta exigem validação no servidor.

PostgreSQL mantém autoritativamente requests, assessments, Corrections, Revocations, SupersessionRelations, Projections, triggers, scopes, ImpactAssessments, findings, response decisions e directives.

Nenhum schema, graph engine, endpoint, fila, worker ou algoritmo de travessia é decidido nesta seção.

Testes futuros impedem reescrita histórica, last-write-wins, ciclo, projeção por último timestamp, análise truncada apresentada como completa, inacessível tratado como não afetado, caminhos correlacionados inflando confiança, finding executando ação, diretivas parciais concluídas e broker aceito apresentado como recebido.

---

# Sustentabilidade, métricas e divulgações

O Titan trata sustentabilidade como capacidades transversais reutilizáveis, não como módulo monolítico, score universal ou conjunto fixo de colunas E, S e G.

O fluxo conceitual é:

```text
Source / Claim / Evidence
    ↓ captura autorizada
Measurement
    ↓ cálculo reproduzível
CalculatedMetric
    ↓ avaliação especializada
SustainabilityAssertion
    ↓ composição e aprovação
SustainabilityDisclosure
    ↓ autorização por audiência
Publication
```

AssuranceStatement e CertificationReference relacionam-se ao fluxo, mas não são etapas automáticas nem semanticamente equivalentes a Measurement, Assertion, Disclosure ou Publication.

## Fronteiras das camadas de sustentabilidade

Domain define MetricDefinition, Measurement, CalculationMethod, CalculatedMetric, ReportingBoundary, avaliações especializadas, SustainabilityAssertion, SustainabilityDisclosure, AssuranceStatement, CertificationReference e invariantes. Não conhece sensor, API, fator, indicador, metodologia científica ou referencial concreto.

Application coordena captura, validação, cálculo, materialidade, comparação, qualidade, metas, aprovação, divulgação, Publication, correção e análise de impacto. Também resolve perfis, métodos, fatores e versões aprovados.

Infrastructure implementa portas específicas para fontes, fatores, unidades, bases, sensores, ferramentas de cálculo, conteúdo licenciado e formatos externos. Resposta externa não se torna Measurement verificada ou SustainabilityAssertion sem caso de uso da Application.

Presentation exibe ValueOrigin, ReportingBoundary, cobertura, DataQualityAssessment, UncertaintyStatement, lacunas, método, perfil, AssertionScope, audiência e limitações. Não transforma resultado em selo, certificação, causalidade ou alegação jurídica.

Verticais definem tópicos, indicadores, métodos, fatores, materialidade setorial, Policies e Rules concretos. O Core nunca importa esses conceitos.

## Captura de Measurement

O caso de uso:

1. valida OrganizationContext, Permission, finalidade e Subject;
2. resolve MetricDefinition e versão;
3. valida período, ReportingBoundary, unidade e dimensionalidade;
4. preserva valor e unidade originais;
5. classifica ValueOrigin;
6. registra Source, Actor, Evidence e Provenance;
7. registra cobertura, lacunas e limitações;
8. produz UncertaintyStatement e DataQualityAssessment quando exigidos;
9. persiste Measurement imutável.

ValueOrigin da saída não esconde a origem das entradas. Estimativa, modelo, premissa, importação ou proxy nunca são apresentados como medição.

Lacuna usa razão explícita e não é convertida em zero. Valor zero observado, zero estimado, dado ausente, não aplicável, fora de escopo, protegido ou indisponível permanecem distintos.

## Cálculo reproduzível

O caso de uso:

1. resolve CalculationMethod e MetricDefinition versionados;
2. valida entradas, unidades, dimensões e ReportingBoundary;
3. preserva valores, Digests, ValueOrigins e versões;
4. resolve fatores com Source, região, período, unidade, aplicabilidade e Evidence;
5. aplica conversões, ausências, estimativas, precedência e arredondamento definidos;
6. propaga incerteza pelo método aprovado;
7. registra intermediários necessários, motor, tolerância e warnings;
8. produz CalculatedMetric imutável e AssertionScope.

Reprodução usa os mesmos dados, método, fatores, unidades, limites, regras e versões e confirma equivalência dentro da tolerância declarada. Não comprova verdade das entradas ou adequação científica, normativa ou jurídica.

Método, fator, limite ou Evidence novos produzem simulação, reavaliação ou correção correlacionada, nunca recálculo silencioso do histórico.

## Avaliações especializadas

Application utiliza casos de uso distintos para:

- DataQualityAssessment;
- MaterialityAssessment;
- ComparabilityAssessment;
- ProgressAssessment;
- RebaseliningAssessment.

Não existe Assessment genérico sem finalidade. Cada avaliação preserva objeto, perfil, método, período, ReportingBoundary, Evidence, Actor, aprovação, resultado, razões e limitações.

Materialidade é relativa a tipo, perfil, tópico, stakeholders, Organization, cadeia, período e metodologia. Materialidade de impacto, financeira, dupla, regulatória ou contratual não é convertida automaticamente.

Comparabilidade considera definição, MetricNature, limite, período, método, fatores, unidade, qualidade, cobertura, ValueOrigin, incerteza e ajustes. Igualdade de unidade ou período não basta.

## Natureza, causalidade e qualidade

MetricNature distingue atividade, insumo, produto direto, resultado, impacto, risco, oportunidade, conformidade, compromisso, progresso e exposição.

Uma natureza não é promovida automaticamente a outra. Alegação de impacto declara se o método sustenta associação, atribuição ou causalidade. Correlação isolada não sustenta conclusão causal.

DataQualityAssessment permanece multidimensional e dependente de perfil. O Core não produz nota universal. Cobertura apresenta proporções medidas, observadas, calculadas, estimadas, modeladas, assumidas, importadas, proxies e sem dados.

Tópicos heterogêneos não são compensados ou normalizados em score sem DisclosureProfile explícito, método versionado, justificativa, pesos, tratamento de ausências, limites, aprovação, sensibilidade e warnings. Métricas componentes permanecem disponíveis.

## Baseline, meta e progresso

Baseline, Target e ProgressAssessment são objetos distintos. Target não comprova progresso e progresso não comprova atingimento.

RebaseliningAssessment sustenta RestatedBaseline e preserva baseline anterior, motivo, diferença, método, período, objetos afetados e aprovação. Divulgação histórica continua vinculada à baseline original salvo republicação explícita.

Mudança de baseline, método ou limite registra efeito sobre comparabilidade. Meta não atingida não se torna NonConformity sem Policy aplicável.

## Afirmação, divulgação e publicação

SustainabilityAssertion preserva AssertionType, SustainabilityAssertionKind, AssertionScope, métricas, período, ReportingBoundary, DisclosureProfile, método, Evidence, incerteza, omissões, aprovação e limitações.

SustainabilityDisclosure compõe snapshot imutável de Assertions, métricas, métodos, fatores, limites, baseline, metas, progresso, cobertura, ValueOrigins, lacunas, omissões, incerteza, comparabilidade, aprovações e material relacionado.

Preparar SustainabilityDisclosure não concede direito de publicar. Publication avalia OrganizationContext, Permission, AuthorizationGrant, Visibility, finalidade, DisclosureAudience, canal, jurisdição, idioma e LicenseConstraint.

DisclosureAudience interna, contratual, cliente, auditor, regulatória ou pública exige autorização própria. Bytes acessíveis ou publicação anterior para outra audiência não autorizam reutilização.

## Tradução e conteúdo licenciado

Tradução é transformação de Artifact. Preserva idioma de origem e destino, tradutor ou processo, revisão, Digest, relação com original e versão prevalente definida pelo perfil. Tradução não substitui silenciosamente conteúdo original.

LicenseConstraint é avaliada na captura, armazenamento, cálculo, composição, exportação, Publication e VerificationBundle. Digest não concede licença; direito de acessar ou armazenar não implica direito de citar, exportar ou redistribuir.

Expiração ou alteração de licença pode restringir nova utilização sem reescrever a Evidence de que conteúdo foi usado historicamente. Material preservado continua sujeito a Authorization e restrições aplicáveis.

## Asseguração e certificação

AssuranceStatement registra padrão, versão, nível, conclusão, escopo, procedimentos, amostragem, limitações, competência, relacionamento, interesse financeiro, outros serviços, conflitos, base de independência, Signature e Evidence.

Nível só é interpretado no padrão correspondente. Independência é afirmação sustentada e delimitada; tipo do provider não a comprova. Asseguração parcial não cobre toda divulgação ou Organization.

CertificationReference e CertificationStatus registram esquema, titular, organismo, escopo, validade, suspensão, uso de marca, instante, Source e Evidence. Certificação não é AssuranceStatement nem prova sustentabilidade universal.

## Impacto, correção e Recall

Correction, nova Evidence, fator, método, Baseline, ReportingBoundary, DisclosureProfile, LicenseConstraint ou CertificationStatus pode iniciar análise autorizada por Provenance.

A análise localiza Measurements, CalculatedMetrics, Targets, avaliações, SustainabilityAssertions, SustainabilityDisclosures, Publications, Dossiers e VerificationBundles potencialmente afetados.

`POTENCIALMENTE_AFETADO` não significa inválido, fraude ou greenwashing e não inicia republicação, sanção ou recall. Efeito exige Policy, caso de uso, Authorization e Actor competentes.

Motivo distingue correção de dados, evolução metodológica, fator novo, mudança de limite ou perfil, rebaselining, nova Evidence e substituição de estimativa. Evolução científica não é apresentada automaticamente como erro anterior.

## Privacidade e dependência da classificação de dados

Métricas sociais, força de trabalho, saúde, denúncias, comunidades e cadeia podem conter dados pessoais, sensíveis ou sigilosos.

Essas capacidades obedecem à ADR 0013. Cada fluxo resolve DataClassification, ProcessingActivity e DataContract aplicáveis; agregações e grupos pequenos recebem controles contra inferência indevida.

Pseudonimização ou agregação não implica anonimização. Authorization e minimização são aplicadas por componente na coleta, cálculo, avaliação, agregação, revisão, asseguração, exportação e Publication.

## Persistência lógica

PostgreSQL mantém registros autoritativos de definições, medições, cálculos, limites, avaliações, baselines, metas, Assertions, divulgações, assegurações, certificações, licenças e impactos.

MongoDB/GridFS pode armazenar somente bytes de Artifact ou Document conforme ADR 0004. Digest, referência opaca, ownership, versão, estado, Authorization e relações permanecem no PostgreSQL.

Nenhuma tabela, schema, índice, pacote, formato externo ou API é decidido nesta seção. Estruturas futuras terão módulo owner, RecordOwnerOrganization quando protegidas, retenção, imutabilidade e Authorization compatíveis.

## Controles arquiteturais de sustentabilidade

Testes futuros devem impedir:

- conceitos ou indicadores de vertical no Core;
- Infrastructure decidindo materialidade ou alegação;
- estimativa apresentada como medição;
- lacuna convertida em zero;
- atividade ou correlação promovida a impacto;
- cálculo irreproduzível ou histórico recalculado;
- comparação sem compatibilidade de qualidade e limites;
- score ou compensação sem perfil;
- audiência ampliada sem autorização;
- tradução tratada como original;
- conteúdo redistribuído sem licença;
- asseguração confundida com certificação;
- impacto potencial produzindo invalidação automática.

---

# Armazenamento de Documents

PostgreSQL é a fonte autoritativa de identidade, ownership, estado, versão, hash, relações, Authorization e auditoria de Documents.

MongoDB GridFS armazena exclusivamente conteúdo binário e metadados técnicos mínimos. MongoDB nunca é consultado para decidir autorização, conformidade, elegibilidade ou existência de Document no domínio.

## Separação de responsabilidades

PostgreSQL mantém:

- Document ID, versão e RecordOwnerOrganization;
- Actor, Issuer e Source;
- nome e tipos declarado/verificado;
- tamanho esperado e confirmado;
- SHA-256 calculado pelo Titan;
- Validity, Signature e VerificationStatus;
- estado do upload;
- referência opaca ao GridFS;
- EvidenceReferences, Corrections e Revocations;
- Authorization e histórico.

GridFS mantém:

- bytes em chunks;
- file ID opaco;
- tamanho e metadados exigidos pelo driver;
- cópias técnicas não autoritativas para reconciliação.

Organization, Event, Evidence, AccessPurpose, GrantScope, GrantScopeResolution, FieldScope, PrincipalCapacityBinding, SharingRequest, GrantAssessment, AuthorizationGrant, AccessRestriction, GrantConflictAssessment, EffectiveAuthorizationScope, SensitiveAccessProfile, AccessOperation, AccessAttempt, DataAccessRecord, AccessMilestone, AccessTrace, BulkAccessScope, BulkAccessCompletionStatus, PrivilegedAccessSession, AuditCompletenessAssessment, AuditTier, AccessTransparencyPolicy, AccessTransparencyReport, SourceProfile, SourceSnapshot, ProvenanceLink, ProvenancePath, ValidationScope, ValidationRequest, ValidationAttempt, ValidationAssessment, ConfidenceAssessment, FreshnessProfile, FreshnessAssessment, EvidenceAdmissibilityAssessment, ConflictAssessment, ConflictMaterialityAssessment, CurrentValidationAssessment, MappingVersion, ContractCompatibilityAssessment, SourceCapabilities, ReplayProtectionEvidence, ParsingAssessment, DataLocationProfile, DataLocationAssignment, JurisdictionMappingVersion, DataLocationInventory, DataTransferAssessment, TransferAuthorization, DataMovementRecord, TransferMechanismReference, SupportAccessSession, DataLocationObservation, DataLocationReconciliation, IncidentSignal, IncidentTriage, IncidentCase, IncidentKnowledgeState, IncidentAssessment, IncidentSeverityProfile, ResponseDecision, ResponseAction, ForensicCollection, ChainOfCustody, IncidentPreservationScope, CommunicationAssessment, CommunicationProfile, IncidentCommunication, CommunicationDeliveryAssessment, RecoveryAssessment, IncidentClosure, PostIncidentReview, ImprovementRecommendation, ImprovementDecision, ActionPlan, ExportRequest, ExportScope, ExportAssessment, PortabilityAssessment, ExportAuthorization, ExportProfile, ExportOperation, ExportPackage, ExportManifest, LicenseEvidence, ExportChunk, ExportDeliveryAssessment, ImportValidationReport, ImportAssessment, ExportReconciliation, ExportedCopyRecord, OffboardingPlan, ExitInventory, OffboardingAssessment, OffboardingDecision, HandoverRecord, OffboardingReconciliation, OfflineCapabilityProfile, OfflineSession, OfflineAuthorizationSnapshot, DeviceTrustAssessment, LocalPreview, OfflineOperation, SynchronizationBatch, SynchronizationBatchResult, SynchronizationResult, SynchronizationConflict, DataClassification, ClassificationAssessment, ClassificationPropagation, ProcessingActivity, DataProcessingRoleAssignment, DataContract, AnonymizationAssessment, PrivacyImpactAssessment, RetentionPolicy, RetentionAssignment, RetentionClock, LegalHold, DispositionScope, DispositionOperation, DispositionReceipt, DispositionReconciliation, DispositionReport, Correction, CorrectionRequest, CorrectionAssessment, SupersessionRelation, CurrentProjection, ImpactTrigger, ImpactScope, ImpactAssessment, ImpactFinding, ImpactResponseDecision, ImpactResponseDirective, NormativeInstrument, NormativeInstrumentVersion, NormativeReference, NormativeBasis, NormativeBasisSnapshot, Policy, Rule, Evaluation, EvaluationOutcome, DecisionProposal, DecisionReason, DecisionAuthorityProfile, Decision, DecisionReview, DecisionChallenge, ReviewEvidenceSubmission, ReviewAssessment, DecisionOverride, Reevaluation, DecisionRelation, AssertionScope, Measurement, CalculatedMetric, MaterialityAssessment, SustainabilityAssertion, SustainabilityDisclosure, AssuranceStatement, CertificationReference, NonConformity, RecallResult, Dossier e OutboxMessage autoritativos nunca são armazenados no MongoDB.

## Identidade e acesso

Document ID e GridFS file ID são identidades diferentes. File ID, bucket e nome físico são detalhes de Infrastructure e não pertencem a contratos públicos.

Cliente nunca conecta diretamente ao MongoDB. Application valida OrganizationContext e Authorization no PostgreSQL antes de fornecer referência opaca ao adapter.

Busca por filename não identifica conteúdo. Erros não revelam existência de objeto pertencente a outra Organization.

MongoDB não possui a RLS definida para PostgreSQL. Credenciais usam menor privilégio, buckets necessários e acesso somente pela Infrastructure.

## Upload coordenado

GridFS não participa da transação PostgreSQL. O fluxo usa estado persistido, idempotência e reconciliação:

1. validar contexto, Permission, finalidade, formato e limites;
2. registrar upload iniciado no PostgreSQL;
3. transmitir bytes ao GridFS com ID opaco;
4. calcular SHA-256 e tamanho durante streaming;
5. verificar conteúdo e metadados;
6. confirmar referência e disponibilidade no PostgreSQL;
7. gravar Event e OutboxMessage atomicamente no PostgreSQL.

Estados técnicos iniciais: `INICIADO`, `RECEBENDO`, `RECEBIDO`, `EM_VERIFICACAO`, `DISPONIVEL`, `FALHOU` e `EM_QUARENTENA`.

Somente `DISPONIVEL` pode ser baixado ou utilizado como Evidence. Upload incompleto é staging, não Document.

## Integridade e versões

SHA-256 é calculado pelo Titan sobre os bytes originais. Hash enviado pelo cliente serve apenas para comparação. MD5 interno ou legado do GridFS não constitui prova do Titan.

Conteúdo disponível:

- não é renomeado como operação de domínio;
- não é sobrescrito;
- não é removido por API normal;
- é reverificado após restore ou suspeita de adulteração.

Nova versão gera novo Document ID, file ID e hash. Correction ou Revocation preserva versões anteriores.

## Reconciliação

Processo idempotente identifica:

- upload sem conteúdo;
- conteúdo sem confirmação PostgreSQL;
- chunks incompletos;
- referência sem conteúdo;
- tamanho ou hash divergente;
- objeto sem upload conhecido.

Staging abandonado pode ser removido somente por política aprovada e papel técnico separado. Conteúdo disponível não é removido pela reconciliação. Conteúdo suspeito permanece em quarentena.

## Segurança de conteúdo

Antes da disponibilidade, aplicar limites aprovados de tamanho, formato, tipo real, arquivos compactados, timeout e consumo de recursos.

Conteúdo não é executado ou renderizado em contexto privilegiado. Downloads usam nome sanitizado e headers seguros. Mecanismo antimalware depende de decisão própria.

## Backup e restauração

PostgreSQL e MongoDB são tratados como conjunto lógico verificável. Restore deve preservar IDs, referências e bytes, reconciliar objetos e verificar tamanhos e hashes.

Referência ausente, objeto órfão ou divergência mantém o Document indisponível até investigação. Backup só é válido após teste de restauração e relatório de reconciliação.

Topologia, buckets, versões, retenção, expurgo, criptografia de aplicação e alta disponibilidade permanecem para decisões próprias.

---

# Eventos

Eventos descrevem fatos relevantes já ocorridos. Eles não substituem entidades, comandos, trabalhos técnicos, contratos de integração nem registros operacionais.

O Core distingue `DomainEvent`, `IntegrationEvent`, `Command` e `Job` conforme a ADR 0006. A classificação determina semântica, consumidores, autorização, compatibilidade, replay, ordenação e idempotência; um evento não contém uma ordem de execução implícita.

Eventos preservam identidade, tipo, versão, instante, correlação, causalidade, Actor originador, Organization aplicável e referência ao agregado ou escopo. Payloads contêm somente o mínimo imutável necessário e não carregam segredo, token ou dado pessoal desnecessário.

Produção, persistência transacional, publicação, aceitação pelo broker, consumo e efeito de negócio são marcos distintos. Ausência de confirmação ou resultado desconhecido não é convertida automaticamente em falha nem em sucesso.

Cada módulo é owner dos eventos internos que produz. Contratos públicos de integração são versionados e não expõem conceitos específicos de uma vertical pelo Core. Retenção, observabilidade e capacidade operacional são definidas por perfil e justificadas pelo uso real.

---

# Integridade e prova temporal

O Titan distingue quatro contratos técnicos:

- Digest é o resultado criptográfico sobre bytes determinados;
- IntegrityCheckpoint é o registro imutável que define conjunto coberto, serialização, algoritmo e Digest;
- TimestampToken é a resposta bruta assinada pela TSA sobre um `messageImprint`;
- TemporalAnchor é a associação validada entre checkpoint, tentativa e token.

Esses contratos pertencem a Application e Infrastructure até eventual inclusão aprovada no `DOMAIN.md`. Timestamp não comprova autoria, verdade material ou validade jurídica do conteúdo.

## Semântica temporal

Ocorrido, registrado, observado, solicitado, comprovado e validado são instantes distintos. Relógio do Titan produz instante observado, não prova temporal externa. Instante comprovado existe somente depois da validação de TimestampToken e não afirma quando o fato real ocorreu.

Instantes usam representação UTC inequívoca, precisão conhecida e fonte identificável.

## Checkpoint e serialização

IntegrityCheckpoint protegido pertence a uma RecordOwnerOrganization e ancora cabeça ou conjunto verificável da cadeia. Ele preserva escopo, delimitadores, sequências, contagem, raiz ou último hash, algoritmos, versões, Digest, instante observado, produtor, correlação, perfil e referências às tentativas.

O conjunto coberto é determinável exatamente por IDs ou sequências ordenadas, contagem, critérios e leitura transacional consistente. Intervalo de datas isolado não comprova completude.

Digest é calculado sobre bytes de versão específica da CanonicalSerialization. Ordem, timezone, Unicode, decimais, valores ausentes e ordenação de registros pertencem à versão. Serializações históricas permanecem disponíveis e testáveis durante toda a retenção.

Checkpoint não reescreve Event, não corrige cadeia inválida e não transforma Projection em fonte de verdade. Agregação entre Organizations e árvore de Merkle exigem decisão posterior.

## TimestampProvider e validação

Application utiliza TimestampProvider substituível. Infrastructure envia somente Digest, algoritmo, perfil, nonce quando aplicável e correlação. RFC 3161 é o perfil interoperável inicial, sem fixar TSA concreta.

TimestampToken recebido permanece não confiável. TemporalAnchor somente é formado depois de validar formato, `messageImprint`, assinatura, algoritmo permitido, certificado, cadeia, política, validade histórica, revogação, nonce enviado, instante e precisão.

Trust anchors, endpoints, políticas e algoritmos são previamente configurados. Token não direciona livremente o verificador para rede ou material de confiança.

Validação produz `VALIDO`, `INVALIDO` ou `INDETERMINADO`, acompanhados de escopo, perfil, verificações e códigos de razão. Resultado indeterminado nunca é convertido permissivamente em válido.

## Tentativas, indisponibilidade e preservação

Retry preserva IntegrityCheckpoint e `messageImprint`, mas cada tentativa possui identidade, instante, correlação e nonce próprios. Resultado de comunicação pode ser desconhecido, e múltiplos tokens válidos para o mesmo checkpoint permanecem correlacionados.

Provider secundário somente substitui o principal quando aprovado para o perfil exigido, considerando cadeia, política, algoritmos, precisão, jurisdição, qualificação e assurance. Compatibilidade RFC 3161 não implica equivalência jurídica.

Indisponibilidade não desfaz checkpoint. Operação que exija prova temporal permanece pendente; relógio, banco, log, broker, arquivo ou operador não substituem TSA e não existe carimbo retroativo.

Expiração atual de certificado não invalida automaticamente token histórico. Cadeia e revogação são avaliadas no instante relevante. Nova ancoragem preserva tokens e âncoras anteriores e cria prova correlacionada, sem sobrescrita.

Verificador independente recebe registros, serialização, checkpoint, token, cadeia, trust anchors, política e material histórico necessários. Recalcula a prova sem segredo ou estado mutável do Titan; material insuficiente resulta em `INDETERMINADO`.

Auditoria distingue RecordOwnerOrganization, Actor ou processo solicitante, ServiceIdentity executora e identidade certificada da TSA. TSA self-hosted pelo operador do Titan pode apoiar testes, mas não oferece independência institucional por si só.

TSA concreta, Merkle, blockchain, chaves Titan, assinatura de Evidence ou Dossier, efeito jurídico e VerificationBundle completo permanecem para decisões próprias.

---

# Gestão de chaves criptográficas

Esta arquitetura trata das chaves de assinatura ou selo institucional controladas pelo Titan. Chaves de pessoas, TLS, OIDC Provider, TSA, banco, backup, conteúdo e autenticação de ServiceIdentity possuem ciclos e decisões próprias.

## KeyProvider e fronteiras

Application utiliza KeyProvider substituível. Domain conhece Signature, mas não HSM, KMS, PKCS#11, referência física, certificado, PIN, secret ou chave privada.

Em produção, material privado permanece exclusivamente no mecanismo protegido e é preferencialmente não exportável. Titan persiste referência opaca, chave pública ou referência verificável e metadados necessários ao ciclo e à validação.

PIN, wrapping key, seed, chave privada, recovery share, secret de acesso e material suficiente para reconstruir a chave nunca entram no PostgreSQL, MongoDB, Domain, Application, payload ou log.

Infrastructure resolve a referência nativa, autentica ServiceIdentity técnica e executa operação permitida sem devolver bytes privados. SoftHSM e keystore local são restritos a desenvolvimento e testes.

## Identidade, finalidade e perfil

O Titan distingue:

- KeyPurpose controlado e versionado;
- perfil de chave com ambiente, algoritmo, proteção, exportabilidade, criptoperíodo, operações e aprovações;
- identidade representada pela assinatura;
- `key_id` lógico de uma geração de material;
- referência nativa mantida somente em Infrastructure;
- custodiante técnico, ServiceIdentity executora e Actor aprovador.

`key_id` é estável, opaco, nunca reutilizado e não precisa coincidir com identificador do provider. Cada geração distinta de material recebe novo `key_id`, ainda que finalidade, identidade e perfil permaneçam iguais.

Uma chave não muda de finalidade por payload ou conveniência. Custódia técnica pela plataforma não autoriza representar Organization, pessoa, profissional ou autoridade sem contrato, delegação e perfil aprovados.

Chaves são separadas por ambiente, finalidade, perfil e identidade representada. Chave de plataforma declara selo da plataforma e não assinatura de outra Organization ou User.

## Ciclo, rotação e estado

Toda chave possui estado explícito e transições autorizadas entre planejamento, geração, ativação, suspensão, expiração, revogação, comprometimento, perda e destruição.

Comprometimento não retorna a estado confiável; destruição é irreversível; recuperação não reativa automaticamente; suspensão somente é revertida por procedimento autorizado; expiração impede novas assinaturas sem eliminar verificação histórica.

Estado criptográfico do material, autorização administrativa e disponibilidade operacional são dimensões distintas. Metadados Titan e provider são reconciliados; divergência suspende ou nega uso.

Rotação cria novo `key_id`, admite sobreposição controlada e encerra novas assinaturas pela versão anterior. Assinaturas históricas preservam algoritmo, perfil, material público, certificado quando houver e chave utilizada; artefatos não são reassinados silenciosamente.

## Falhas, comprometimento e recuperação

Indisponibilidade ou resultado desconhecido não comprova assinatura. Tentativas permanecem correlacionadas, e idempotência lógica não exige bytes criptográficos idênticos.

Não existe fallback automático para arquivo local, chave de desenvolvimento, algoritmo inferior ou outra identidade.

Perda significa indisponibilidade sem evidência de exposição. Comprometimento registra último uso confiável, primeiro instante suspeito, bloqueio, revogação, artefatos afetados e confiança da delimitação. O histórico não é presumido integralmente seguro nem inválido; cada resultado é explicado.

Backup e recuperação permanecem no mecanismo protegido, com proteção equivalente, separação de funções, dupla aprovação e auditoria. Recuperação não altera estado ou autorização automaticamente.

Destruição gera evidência do procedimento executado nos mecanismos e locais inventariados, sem afirmar inexistência absoluta de cópias desconhecidas. Material público e histórico de validação são preservados.

## Substituição e agilidade

Troca de provider preserva contratos e permite novas chaves em outro mecanismo, mas não garante migração de material privado não exportável. Nesse caso, novas operações usam nova geração e a validação histórica utiliza material público preservado.

Algoritmos e parâmetros seguem allowlist versionada por perfil e não são escolhidos livremente pelo cliente. Algoritmo descontinuado deixa de assinar, mas permanece verificável enquanto houver artefato retido dependente dele.

Papéis de administração, uso, auditoria, backup e recuperação são separados. ServiceIdentity possui grants mínimos; operações sensíveis podem exigir dupla aprovação e autenticação reforçada; inventário e alertas detectam uso anômalo, expiração e divergência.

HSM/KMS concreto, certificado, CA, algoritmos finais, assinatura de pessoa física, PAdES/CAdES/JAdES e efeito jurídico ICP-Brasil/eIDAS permanecem para decisões próprias.

---

# Assinaturas, certificados e confiança

O Titan distingue Signature de domínio, bytes de assinatura criptográfica, Certificate, CertificationPath, SignatureProfile, SignatureValidation e ValidationReport. Contratos técnicos permanecem em Application e Infrastructure até eventual inclusão aprovada no `DOMAIN.md`.

Assinatura demonstra somente o que seu perfil, conteúdo protegido e confiança validada permitem. Não certifica verdade material nem produz automaticamente manifestação humana ou efeito jurídico.

## Providers e perfil

Application utiliza SigningProvider e TrustValidator substituíveis. SigningProvider usa KeyProvider para chaves sob custódia Titan ou integra cerimônia externa sem receber chave privada pessoal. TrustValidator avalia conteúdo, assinatura, certificado, confiança, tempo e perfil.

SignatureProfile versionado define finalidade, alegação permitida, artefato, identidade representada, Organization, bytes protegidos, CanonicalSerialization, algoritmo, KeyProfile, certificados, trust anchors, timestamp, material histórico, instante de referência, jurisdição, provider e preservação.

Perfil é resolvido pelo servidor. Cliente, payload, certificado ou provider não ampliam finalidade, identidade, confiança ou classificação jurídica. Mudança incompatível cria nova versão preservada enquanto houver Signature dependente.

## Conteúdo, identidade e intenção

Conteúdo protegido utiliza domínio de separação e inclui, conforme perfil, finalidade, tipo, ID e versão do artefato, RecordOwnerOrganization, identidade representada, Digest, algoritmo, versão da serialização, referência temporal e perfil.

Assinar hash isolado é proibido quando permitir substituição semântica. Bytes ou representação reproduzível permanecem disponíveis.

Identidade representada combina identidade declarada, atributos certificados, perfil, vínculo interno e finalidade. Nome no certificado não comprova mandato, representação institucional ou manifestação humana.

Actor solicitante, signatário declarado, identidade representada, ServiceIdentity executora, Issuer, custodiante e provider são papéis distintos. Selo de plataforma não representa Organization ou User.

Assinatura externa de pessoa preserva autenticação, intenção, artefato apresentado, consentimento ou aprovação, instante e evidências exigidas. O Titan não controla sua chave privada.

## Certificados e confiança

Certificate recebido não é trust anchor. TrustValidator constrói CertificationPath e avalia assinatura da cadeia, âncora previamente aprovada, identidade, Key Usage, Extended Key Usage, políticas, OIDs, restrições, validade, revogação histórica, algoritmos, correspondência da chave e status do prestador.

Trust store, trust anchors e Trusted Lists possuem identificador, versão e material ou Digest preservado. Referência mutável ao estado atual não reproduz validação histórica.

Certificado self-signed somente é confiável por trust store privado explicitamente distribuído; não se torna público, independente ou qualificado automaticamente.

Expiração atual não invalida automaticamente assinatura histórica. Revogação, motivo, TemporalAnchor, material histórico e instante de referência são avaliados conforme perfil.

## Validação e relatório

Cada execução registra separadamente validade criptográfica, integridade dos bytes, adequação do certificado, confiança da CertificationPath, conformidade técnica, conformidade jurídica e suficiência histórica.

Instante de referência é determinado pelo perfil e pode ser assinatura declarada e confiável, TemporalAnchor, recebimento pelo Titan ou validação atual. Instante fornecido pelo cliente não é confiável sem evidência.

Resultado agregado é `VALIDA`, `INVALIDA` ou `INDETERMINADA`, sempre acompanhado de perfil, versão, escopo, instante de referência, verificações parciais e códigos de razão. Válida significa válida apenas nesse contexto; indeterminada nunca é convertida permissivamente em válida.

ValidationReport imutável preserva Signature, Digest, bytes ou referência imutável, perfil, instantes, algoritmo, `key_id`, certificado, caminho, trust store versionado, material temporal e de revogação, resultados, razões, warnings, limitações e versão do motor.

Nova validação cria relatório correlacionado. Mudança de norma, política, trust store, Trusted List ou motor não reclassifica silenciosamente resultado histórico.

## Jurisdição e preservação

TimestampToken e assinatura são provas distintas. Material de estado e revogação aplicável — CRL, OCSP, Trusted Lists ou equivalente — é preservado com seus instantes e política.

Classificações simples, avançada e qualificada somente existem com perfil jurídico e jurisdição explícitos. Termos semelhantes em regimes diferentes não implicam requisitos ou efeitos equivalentes.

Perfil brasileiro identifica cadeia, política, certificado, regras ICP-Brasil e legislação setorial no instante relevante. Perfil eIDAS preserva Trusted List, estado histórico e serviço qualificado aplicável. ICP-Brasil não é qualificação eIDAS automática.

Assinatura pode ser evidência sem garantir força probatória, aceitação judicial ou veracidade. Alegação jurídica exige revisão profissional para finalidade, jurisdição e data concretas.

Formato futuro define como assinatura, certificados, timestamps e material de validação são associados ou incorporados sem alterar esta semântica.

Certificadora, produto, certificado concreto, algoritmo final, cerimônia externa, PAdES/CAdES/XAdES/JAdES/ASiC, perfil jurídico habilitado e VerificationBundle completo permanecem para decisões próprias.

---

# Verificação externa

O Titan adota modelo híbrido: VerificationBundle imutável e autossuficiente para o escopo declarado, complementado por API autorizada e explicável. Prova histórica offline não depende do banco Titan; estado atual exige fontes e instantes explícitos.

VerifiedArtifact, BundleManifest, VerificationBundle, ValidationReport, VerificationCode e OnlineVerificationResponse são contratos técnicos distintos de Dossier e permanecem fora do Domain até eventual aprovação.

## Modos e escopos

Verificação seleciona explicitamente `OFFLINE`, `ONLINE` ou `REFERENCE`. Offline usa somente material local; online consulta fontes aprovadas; reference resolve versão imutável no Titan. Nenhum modo muda automaticamente para outro.

Escopos distinguem integridade do artefato, Signature conforme perfil, inclusão em IntegrityCheckpoint, TemporalAnchor, reprodução do Dossier, Provenance incluída e completude delimitada da cadeia Titan.

Verificar PDF não comprova automaticamente Dossier JSON, Decision, Genealogy ou cadeia Titan. Checkpoint válido não comprova verdade dos registros.

Completude somente é válida contra fronteira declarada e verificável por sequências, contagem, IDs, cursor, prova de cobertura, subconjunto ou redaction. Sem prova do conjunto esperado, componentes presentes podem ser íntegros, mas completude é `INDETERMINADA`.

## Manifesto e estrutura

BundleManifest é canônico, versionado, imutável e protegido por Digest e selo ou Signature. Identifica bundle, Organization, Issuer, Publication, audiência, finalidade, artefatos, componentes, referências, tipos, tamanhos, Digests, obrigatoriedade, relações, ordem relevante, algoritmos, perfis, lacunas e limitações.

Validade estrutural confirma consistência entre manifesto, inventário e componentes; não comprova autenticidade de emissão. Esta depende do mecanismo exigido pelo perfil.

Componente não listado não integra o escopo. Extensão permitida usa namespace próprio, não altera interpretação protegida e aparece no relatório. Arquivo inesperado fora dessa área torna o bundle inválido ou incompatível.

O bundle contém material específico do artefato necessário ao escopo. Trust policy, trust anchors e regras jurídicas podem permanecer externos, desde que identificados. Material incluído não se torna confiável apenas por estar no pacote.

## Autorização, publicação e minimização

Gerar, publicar, compartilhar, baixar e revogar referência online são operações distintas. Application avalia OrganizationContext, RecordOwnerOrganization, Permission, Publication, AuthorizationGrant, audiência, finalidade e Visibility de cada componente.

Acesso ao Dossier não implica acesso a toda Evidence subjacente. Componente não exportável é omitido ou substituído por prova mínima aprovada, com lacuna explícita.

Bundle exportado pode ser copiado fora do Titan. Revocation impede novas entregas controladas, mas não apaga cópias. Chaves privadas, tokens, secrets, credenciais, biometria bruta, OrganizationContext e conteúdo não autorizado são proibidos.

Redaction gera novo artefato, manifesto e Digests. Remoção visual isolada é insuficiente; bytes, metadados, anexos e campos ocultos são inspecionados.

## Verificação offline e online

Verificador offline opera sem rede por padrão, valida estrutura e limites, confere manifesto, recalcula Digests, valida assinaturas e provas e produz ValidationReport. Falta de material resulta em `INDETERMINADA`, sem consulta silenciosa.

Resultado offline descreve estado histórico do material incorporado e não afirma revogação, Publication ou acontecimento atual.

API informa dimensões, escopo, perfil, versões, instantes, motor, fontes, frescor, limitações e falhas parciais. Conteúdo protegido exige autenticação, OrganizationContext e Authorization; endpoint público retorna somente Publication deliberadamente pública.

OnlineVerificationResponse não altera relatório histórico. “Não revogado” significa apenas ausência de revogação nas fontes e instantes declarados.

## Código e resultado

VerificationCode é aleatório, de alta entropia, vinculado a versão imutável de Publication e escopo mínimo. Não autentica User nem concede acesso geral. Nova versão recebe novo código ou associação versionada.

Revogar ou expirar código impede novas resoluções pelo Titan, mas não invalida bundle, Signature, TimestampToken, checkpoint ou Evidence já obtidos.

QR Code público usa preferencialmente VerificationCode. Digest exposto inclui algoritmo, domínio de separação e finalidade e exige análise de privacidade para conteúdo sensível ou previsível.

ValidationReport separa integridade estrutural, componentes, autenticidade da emissão, Signatures, confiança, timestamps, checkpoints, completude, perfil, estado histórico, estado atual e suficiência. Cada dimensão possui resultado, razões, evidências, limitações e instante.

Relatório identifica material incorporado e fontes externas, versões de motor e parser, perfil, política, trust store, configuração relevante e suíte de test vectors. Resultado agregado não elimina parciais nem afirma verdade.

## Preservação e segurança

Mudança de conteúdo, escopo, redaction ou material cria novo bundle correlacionado. Formatos históricos permanecem documentados e verificáveis durante a retenção.

Test vectors públicos são sintéticos, documentados e licenciados e cobrem casos válidos, adulterados, parciais, incompatíveis, maliciosos e ambíguos.

Parser trata bundle como não confiável: limita tamanho, quantidade, profundidade e expansão; impede path traversal, links, scripts, algoritmos não permitidos e acesso de rede induzido; aplica timeout e isolamento proporcional.

Container físico, compressão, criptografia, URL/schema final da API, biblioteca, UI, hospedagem pública, prova seletiva, formato final do PDF e perfil jurídico permanecem para decisões próprias.

---

# Processamento assíncrono

O Titan utiliza Transactional Outbox no PostgreSQL e Message Broker como transporte. Event, mudança de estado e OutboxMessage da mesma operação são persistidos atomicamente; a transação de domínio não depende da disponibilidade do broker.

O fluxo arquitetural é:

```text
Application → transação PostgreSQL → OutboxMessage → publisher → Message Broker → worker → Application
```

PostgreSQL preserva a OutboxMessage autoritativa. O publisher transporta somente registros de transações confirmadas, registra aceitação após confirmação positiva do broker e mantém resultado desconhecido elegível para nova tentativa com o mesmo `message_id`. Aceitação pelo broker não significa consumo ou efeito de negócio concluído.

A entrega é pelo menos uma vez. Exactly-once não é prometido. Worker confirma consumo somente após commit local bem-sucedido, e todo consumidor produz efeito lógico idempotente.

`message_id` deduplica redelivery da mesma mensagem. IdempotencyKey ou invariante natural protege a mesma intenção lógica representada por mensagens diferentes. Esses mecanismos não são equivalentes e seus registros permanecem disponíveis por toda a janela de redelivery e replay.

## Semântica e contratos

OutboxMessage é registro técnico transacional, não modelo universal do domínio. Cada contrato classifica a mensagem como:

- DomainEvent, para acontecimento interno do domínio;
- IntegrationEvent, para contrato público versionado derivado de acontecimento interno;
- Command, para solicitação direcionada de ação;
- Job, para trabalho técnico ou operacional.

Evento não contém ordem implícita. Command e Job não são apresentados como fato ocorrido. IntegrationEvent, Command e Job permanecem semânticas de Application ou Infrastructure até eventual definição aprovada no `DOMAIN.md`.

Tipo e versão identificam o contrato. Versão publicada não muda de significado. Versão não suportada é rejeitada, e seu suporte não é removido enquanto houver OutboxMessage, cópia no broker, quarentena ou replay elegível dependente dela.

Envelope preserva identificador, classificação, versão, Organization, Actor originador, processo produtor, timestamps, correlação, causação e referência ou payload mínimo necessário. Access Token, Refresh Token, ID Token, secrets, OrganizationContext materializado e binários são proibidos.

Processamento baseado no estado da produção utiliza snapshot mínimo imutável ou referência a versão imutável. Consulta ao estado mutável atual somente ocorre quando essa reavaliação fizer parte explícita da semântica do contrato.

## Execução, isolamento e falhas

Publisher, Actor originador, ServiceIdentity executora e Actor administrativo de replay são participantes distintos na auditoria.

Worker autentica-se como ServiceIdentity de menor privilégio e invoca Application. Mensagem não transporta Authorization confiável; operação protegida reconstrói OrganizationContext e distingue efeito técnico já autorizado de nova decisão de negócio que exige reavaliação.

Claim ou lease de publicação abandonado é recuperável. Falha transitória utiliza retry limitado com atraso progressivo e variação. Falha permanente exige motivo determinístico. Exceção inesperada permanece observável e não é classificada automaticamente como defeito permanente da mensagem.

Após o limite, mensagem segue para quarentena ou dead-letter. Replay é explícito, autorizado, justificado, auditado e sujeito aos mesmos controles de idempotência, isolamento e Authorization. Replay utiliza o handler suportado no presente e não equivale automaticamente à reprodução histórica da lógica original.

Não existe ordenação global. Ordenação por agregado, Subject ou chave é introduzida somente por invariante documentada e combinada com versão esperada ou concorrência otimista.

Publisher e worker suportam desligamento seguro, retomada, reconciliação e backpressure. Métricas acompanham idade da Outbox, latência, tentativas, redelivery, quarentena e divergências sem expor payload protegido.

Produto de Message Broker, executor, topologia e valores operacionais permanecem para decisões próprias. Infrastructure pode usar capacidades específicas do produto desde que não alterem a semântica pública nem atravessem as fronteiras do Core e da Application.

---

# Linhagem e relações de derivação

Transformações materialmente relevantes preservam relações explícitas entre fontes, entradas, derivados e resultados. A linhagem identifica operação, versão, parâmetros, responsável técnico, instante, Digests, limitações e classificação propagada quando aplicável.

Uma relação de derivação não comprova verdade, equivalência, autoria ou confiança. Múltiplos caminhos provenientes da mesma origem não constituem confirmações independentes.

Correção, supersession, anonimização, disposição e retenção não reescrevem silenciosamente a linhagem. Quando conteúdo puder ser descartado legitimamente, permanece a Evidence autorizada da operação e das relações que possam ser conservadas sem reter o dado eliminado.

Proveniência, transformação, causalidade, correlação e dependência semântica são relações distintas. Vocabulários e perfis versionados definem quais relações cada módulo pode produzir e consumir; o Core não incorpora relações próprias de uma vertical.

---

# Compartilhamento por finalidade, escopo e concessões

O Titan autoriza operações pela interseção restritiva de identidade, capacidade, Organization, Purpose, recurso, ação, campos, tempo, classificação, contrato, Policy, grants e restrições.

```text
SharingRequest → GrantAssessment → AuthorizationGrant
    → GrantScopeResolution + FieldScope + AccessRestrictions
    → EffectiveAuthorizationScope → Authorization
```

Relação, Publication, Identifier, ProvenancePath, DataContract, token ou autenticação não concedem acesso isoladamente.

## Fronteiras das camadas de compartilhamento

Domain define AccessPurpose, scopes, capacidade, request, assessment, grants, restrições, conflito e invariantes. Não conhece endpoint, token, cache, banco ou engine externo.

Application resolve participantes, autoridade, vínculos, grants, restrições e Authorization concreta.

Infrastructure persiste grants, resolve conjuntos, invalida caches, entrega notificações e aplica filtros técnicos. Não decide Purpose, precedência ou acesso.

Presentation solicita Organization e Purpose, aplica FieldScope e não distingue recurso inexistente de invisível fora da resposta autorizada.

## Purpose, scope e campos

AccessPurpose é código canônico versionado resolvido pelo servidor. Texto equivalente não autoriza mapeamento aproximado.

GrantScope delimita recursos, ações, período, Organization, Purpose, FieldScope, derivados, exportação, volume e condições.

GrantScopeResolution distingue conjunto fixo, critério dinâmico e snapshot autorizado. Conjunto fixo não cresce; critério dinâmico possui regra e versão, limites, instante, Digest e resultado reavaliados por operação.

FieldScope protege payload, campos derivados, Digest, Identifier, nome, metadados, Provenance e existência de anexo. Ausência é negação.

Leitura, exportação, derivação, inferência, treinamento de IA e redistribuição são ações independentes.

## Participantes e capacidade

PrincipalCapacityBinding liga beneficiário interno à Membership, ServiceIdentity ou capacidade institucional utilizada.

Application revalida vínculo, Organization, capacidade, validade e condições do beneficiário e concedente. Mesmo User não reutiliza grant emitido para outra capacidade.

Perda de vínculo ou competência torna o grant não utilizável sem apagar história. E-mail, nome, client ID e token subject não são identidades canônicas suficientes.

## Emissão, delegação e conflito

SharingRequest e GrantAssessment não concedem acesso. Grant é emitido explicitamente após autoridade, Purpose, scope, Permission, DataContract, classificação, retenção e aprovações.

Delegação é proibida por padrão. Subgrant referencia pai, é acíclico e não excede Purpose, scope, condições, prazo ou profundidade. Suspensão ou término do pai bloqueia novo uso dos descendentes.

AccessRestriction participa da decisão e não é ignorada por grant positivo. GrantConflictAssessment não soma grants entre Purposes ou Organizations nem escolhe o mais recente.

Conflito sem regra segura falha fechado.

## Authorization e redução de escopo

Application reconstrói OrganizationContext e calcula EffectiveAuthorizationScope como interseção entre Permission, Purpose, grants, scopes resolvidos, FieldScopes, AccessRestrictions, DataContract, classificação, Policy e condições.

Dimensões incompatíveis não possuem ordem presumida. Authorization registra recurso e versão, operação, contexto, grants e restrições considerados, solicitado, autorizado, ReasonCodes e instante.

Autorização parcial declara redução no contrato e nunca é apresentada como resposta integral. Não revelar existência integra FieldScope e resultado.

Token, mensagem ou cache não substituem estado interno. Cache é derivado, curto, invalidável e depende também de Membership, capacidade, Policy e restrições vigentes.

## Derivados, Publication e cópias

Derivado preserva Provenance, DataClassification, Purpose e limites das fontes. Combinação exige compatibilidade e análise de inferência; não produz audiência mais ampla automaticamente.

Publication pública pode dispensar grant individual apenas para versão, audiência, Purpose e campos publicados. Evidence ou anexo subjacente permanece protegido.

Dossier, VerificationBundle e Document são autorizados por componente. VerificationCode resolve escopo publicado mínimo e não funciona como grant privado.

Revocation impede novos acessos controlados, mas não apaga uso histórico ou cópia entregue. Aceitação de notificação pelo Message Broker não comprova recebimento ou aplicação.

## Offline, persistência e controles

Criar, ampliar, delegar, reativar, suspender ou revogar grant exige operação online. Autorização offline é materializada para Device, capacidade, operação, Purpose, scope e prazo curtos.

Synchronization revalida vínculo, grant e cadeia, Purpose, Permission, scopes, Visibility, Policy, relógio e revogação; operação rejeitada permanece auditável.

PostgreSQL mantém autoritativamente Purposes, scopes, resolutions, bindings, requests, assessments, grants, restrictions, conflicts, effective scopes e Authorizations.

Testes futuros impedem crescimento silencioso de conjunto, capacidade encerrada, scope além da autoridade, resposta parcial integral, inferência de campo proibido, metadado vazando anexo, IA sem Purpose, restrição ignorada, filho mais amplo, cache obsoleto, Purpose incorreto e diferença entre inexistente e invisível.

Nenhum schema, endpoint, cache, engine de autorização ou formato de expressão é decidido nesta seção.

---

# Isolamento por Organization

Organization é a unidade principal de isolamento, responsabilidade e autorização do Titan.

Todo registro protegido de domínio possui exatamente uma RecordOwnerOrganization. Ela representa a Organization responsável pelo registro dentro do Titan e não implica automaticamente propriedade civil, intelectual, posse, custódia, autoria, emissão ou responsabilidade regulatória.

Não existe copropriedade do registro. Outras Organizations podem possuir relações, Visibility ou acesso delimitado sem se tornarem responsáveis por ele.

Ownership, Visibility, Publication, Sharing e Authorization são dimensões independentes:

- ownership define a Organization responsável pelo registro;
- Visibility define o que pode ser descoberto ou visualizado no contexto avaliado;
- Publication torna versão de recurso elegível para audiência e finalidade definidas;
- Sharing produz concessão explícita, delimitada e revogável;
- Authorization decide uma operação concreta.

Issuer pode ser diferente de RecordOwnerOrganization. Publicação ou compartilhamento não transferem ownership e não autorizam alteração automática.

## OrganizationContext

Toda operação protegida executa em uma única Organization ativa por meio de OrganizationContext construído e validado pelo servidor.

O cliente pode solicitar atuação em uma Organization, mas identificadores, Roles ou Permissions fornecidos por header, token ou payload não são confiáveis por si só.

O servidor deve:

1. validar o AuthenticatedPrincipal;
2. resolver User ou ServiceIdentity internos;
3. validar Membership ou AuthorizationGrant aplicável;
4. calcular Roles e Permissions efetivas;
5. validar finalidade e recurso;
6. construir OrganizationContext imutável para o caso de uso.

Trocar a Organization exige nova validação. OrganizationContext não pode ser reutilizado entre Organizations.

O OIDC Provider autentica a identidade. O Titan executa Authorization e mantém os vínculos e concessões.

## Autenticação e identidade externa

O OIDC Provider é um componente operacional externo ao processo, banco e ciclo de release do monólito Titan. A integração utiliza OIDC/OAuth por contratos de Infrastructure e não introduz tipos do protocolo no Domain.

A API protegida aceita somente Access Token emitido para o Resource Server correspondente. ID Token é destinado ao cliente OIDC e não autentica requisições da API. Refresh Token permanece entre cliente autorizado e provider e não é enviado à API de domínio.

O formato do Access Token não integra o contrato de domínio. Infrastructure pode validar token autoportante ou utilizar introspection autenticada, conforme provider e configuração aprovados.

A validação ocorre antes de confiar em qualquer conteúdo e confirma, quando aplicável, assinatura, algoritmo em allowlist, issuer exato, audience, validade, finalidade, tipo, chave e claims mínimas. Issuer desconhecido, chave não resolvida, algoritmo inesperado, token destinado a outro recurso ou impossibilidade de introspection resultam em negação.

Após a validação do protocolo, Infrastructure produz AuthenticatedPrincipal normalizado. Token bruto, JWT, JWKS, authorization code, PKCE, Refresh Token, introspection, client secret e redirect URI não atravessam para Domain.

O vínculo externo canônico utiliza `(issuer, subject)`. Email e demais atributos mutáveis não identificam o principal e não autorizam linking automático. Relink e account linking exigem fluxo autenticado, aprovação apropriada e auditoria.

User interativo utiliza Authorization Code com PKCE S256. Implicit Flow e Resource Owner Password Credentials são proibidos. Swagger e console técnico usam clientes próprios, redirect URIs exatas e permissões mínimas.

ServiceIdentity utiliza Client Credentials ou mecanismo aprovado para workload identity. Client ID, escopos e claims externos não substituem ServiceIdentity, AuthorizationGrant, Permission ou OrganizationContext mantidos pelo Titan.

MFA e recuperação são executados pelo provider. O Titan pode exigir autenticação recente ou nível de garantia confiável para operações sensíveis, sem transformar essa evidência em autorização de domínio.

Suspensão de User, ServiceIdentity, Membership ou vínculo externo bloqueia novas operações na autorização interna mesmo quando Access Token autoportante ainda é criptograficamente válido.

## Atores humanos e não humanos

User humano atua por Membership válida ou concessão explicitamente autorizada.

Serviço, sistema, integração, processo automatizado ou Device autenticável atua por ServiceIdentity e AuthorizationGrant delimitada. ServiceIdentity não possui Membership humano e não recebe acesso universal.

Actor de plataforma também exige Permission privilegiada explícita, finalidade, justificativa e auditoria reforçada para operar entre Organizations.

## Relações e travessia

Referência, UniversalRelation, Genealogy ou Transformation não concedem acesso.

Operação que envolva várias Organizations possui exatamente uma Organization atuante e preserva owner de cada registro, Organizations afetadas, autorização utilizada, Actor, finalidade, momento e resultado.

Recall atravessa fronteiras somente com autorização. Quando restrição de Visibility impedir conclusão completa, o resultado deve ser marcado como limitado ou inconclusivo, sem afirmar ausência de afetados.

## Aplicação transversal

O isolamento deve ser preservado em todas as vias:

- API e contratos exigem OrganizationContext em operações protegidas;
- IDs nunca comprovam autorização;
- busca, paginação e exportação aplicam as mesmas regras;
- OutboxMessage e tarefas carregam Organization e contexto auditável;
- worker reconstrói e valida contexto antes do caso de uso;
- operação offline não realiza autenticação remota nem armazena Access Token ou Refresh Token em OfflineOperation;
- OfflineOperation preserva a identidade alegada, Actor, Organization, Device, timestamps e contexto auditável;
- identidade, estado, vínculos, Permissions, OrganizationContext, validade e conflitos são revalidados durante Synchronization;
- chaves de cache incluem Organization para conteúdo protegido;
- projeções preservam owner e Visibility e não misturam Organizations;
- retries e reprocessamentos mantêm contexto e correlação originais.

## Persistência

Repositórios protegidos exigem OrganizationContext ou RecordOwnerOrganization explícita. Consultas sem escopo são proibidas, exceto operações administrativas formalmente autorizadas e auditadas.

PostgreSQL é o banco transacional principal. O monólito utiliza instância lógica compartilhada, organizada por schemas de módulos. Schemas não representam Organizations.

Compartilhar banco ou schema não reduz as regras de ownership, contratos e isolamento.

### Responsabilidade estrutural

Cada schema, tabela, índice, constraint e migration possui exatamente um módulo responsável.

Responsabilidade estrutural do módulo não é RecordOwnerOrganization dos registros armazenados.

Schemas são criados incrementalmente com a primeira estrutura real do módulo. Runtime não recebe `CREATE`; nomes são qualificados e `search_path` não é fronteira de segurança.

### Classificação das estruturas

Toda tabela nasce protegida por padrão. A migration declara uma categoria:

- `PROTECTED`: dados pertencentes a RecordOwnerOrganization;
- `PLATFORM_INTERNAL`: dados estritamente técnicos, sem conteúdo de domínio interorganizacional;
- `REFERENCE_CATALOG`: catálogo ou Publication versionada com Organization responsável;
- `DERIVED_PROJECTION`: projeção reconstruível com origem e Visibility preservadas.

Classificação fora de `PROTECTED` exige justificativa. Estrutura técnica nunca armazena dados de domínio para evitar RLS.

### Row-Level Security

Tabela `PROTECTED` possui RecordOwnerOrganization obrigatória, `ENABLE ROW LEVEL SECURITY` e `FORCE ROW LEVEL SECURITY`.

Application runtime:

- não é superuser;
- não é table owner;
- não possui `BYPASSRLS`;
- não altera policies;
- não executa `TRUNCATE` protegido.

Contexto ausente ou inválido resulta em negação. `USING` e `WITH CHECK` são definidos e testados por operação.

Na primeira implementação, policy ordinária permite somente registro cuja RecordOwnerOrganization corresponda à Organization atuante. Compartilhamento e travessia interorganizacional usam caminho dedicado futuro, sem bypass genérico.

### Contexto transacional

Depois da Authorization na Application, a Infrastructure inicia transação e define contexto local para a Organization atuante.

- contexto nunca persiste na sessão ou conexão do pool;
- caso de uso protegido executa dentro da transação contextualizada;
- commit ou rollback elimina o contexto;
- API, worker e Synchronization seguem o mesmo fluxo;
- reutilização de conexão é testada contra vazamento de contexto.

### Transferência e projeções compartilhadas

Transferência de RecordOwnerOrganization não é update ordinário. Exige caso de uso, Permission, auditoria e validação de origem e destino, sem bypass genérico.

Projeção compartilhada preserva:

- Organization responsável pela projeção;
- RecordOwnerOrganization da fonte;
- referência verificável à fonte;
- AuthorizationGrant aplicável;
- validade e estado da concessão.

Projeção não transfere ownership da fonte.

### Constraints e índices

- `NOT NULL` protege campos obrigatórios;
- unicidade organizacional inclui RecordOwnerOrganization;
- foreign key não é mecanismo de Authorization;
- referência protegida é validada pela Application antes da persistência;
- erros não revelam existência de registro inacessível;
- índices seguem consultas comprovadas, sem ordem automática universal;
- PostGIS integra o caminho crítico do MVP conforme a ADR 0026, limitado a evidência geoespacial vetorial, operações reproduzíveis e adapters de Infrastructure. Não autoriza GIS genérico, sensoriamento remoto próprio ou conclusão regulatória automática.

### Papéis e imutabilidade

Migration owner, Application runtime, operação administrativa, backup e observabilidade usam papéis separados e de menor privilégio.

Tabelas append-only negam `UPDATE`, `DELETE` e `TRUNCATE` ao runtime. Corrections e Revocations criam novos registros.

Essa imutabilidade operacional não impede o ciclo de vida autorizado de payload pessoal separável. PhysicalDisposition segue ADR 0014 por processo privilegiado, autorização, LegalHold, auditoria e reconciliação fora do papel ordinário da aplicação.

A adoção da ADR não cria `DELETE`, novo grant ou rotina de descarte para o runtime. Implementação física exige passo próprio, modelo aprovado e testes de segurança e restauração.

Observabilidade acessa métricas, locks, deadlocks e saúde sem obter conteúdo protegido. Administração de dados exige finalidade, autorização e auditoria próprias.

### Transações e migrations

`READ COMMITTED` é o padrão inicial com concorrência otimista. Isolamento mais forte ou locks exigem justificativa e testes concorrentes. Falhas repetíveis devem reiniciar a transação completa de forma idempotente.

Event, mudança de estado e OutboxMessage da mesma operação são atômicos.

Schema muda somente por migration versionada do módulo responsável. Aplicação, reversão, RLS, grants, constraints e índices são verificados em banco descartável. ORM nunca cria schema automaticamente em produção.

### Verificação automatizada

A CI consulta catálogos do PostgreSQL e falha se tabela protegida:

- não possuir RecordOwnerOrganization;
- não tiver RLS e `FORCE ROW LEVEL SECURITY`;
- não tiver policies necessárias;
- conceder mutação indevida ao runtime;
- estiver no schema incorreto;
- possuir owner, grants ou categoria incompatíveis;
- permitir acesso sem contexto ou por outra Organization.

Backup e restauração devem incluir todos os schemas, evitar filtragem silenciosa por RLS e verificar migrations, policies e integridade após restauração.

---

# Auditoria e transparência de acessos sensíveis

A auditoria de acesso sensível segue a ADR 0019 e distingue autorização, tentativa, execução, entrega e efeito de negócio. A autorização permite tentar uma operação; não comprova que dados foram acessados.

O fluxo conceitual é:

`Authorization → AccessOperation → AccessAttempt → DataAccessRecord → AccessTrace`

Operações em massa acrescentam `BulkAccessScope` e `BulkAccessCompletionStatus`. A transparência é produzida depois de avaliação de completude e aplicação de `AccessTransparencyPolicy`.

### Fronteiras

- Domain define perfis, operações, tentativas, marcos, escopos, completude, tiers e políticas de transparência;
- Application autoriza a operação, coordena tentativas, registra marcos e produz avaliações e relatórios;
- Infrastructure persiste registros append-only, preserva correlação e integra armazenamento, entrega e observabilidade;
- Presentation exibe somente escopo autorizado e não converte estado técnico em conclusão jurídica ou de negócio.

O PostgreSQL é autoritativo para esses conceitos. Sistemas de log, métricas ou SIEM podem receber projeções minimizadas, mas não substituem o registro autoritativo nem decidem autorização.

### Jornada e marcos

`AccessOperation` representa uma intenção lógica. Cada execução ou retry cria `AccessAttempt` correlacionada; retries não criam silenciosamente nova operação. `AccessOperationId`, `AccessAttemptId`, `MilestoneId`, `IdempotencyKey` e `CorrelationId` possuem finalidades distintas.

Cada `DataAccessRecord` registra exatamente um marco imutável. Ele não é uma linha mutável de status atual. Marcos posteriores não podem ser inferidos de marcos anteriores.

`AccessTrace` é projeção reconstruível que explicita sequência, tentativas, ramificações, duplicidades, lacunas e marcos exigidos. Ela auxilia explicação, mas não substitui os registros-fonte.

`EXECUCAO_CONCLUIDA` confirma apenas o término da atividade técnica. `APRESENTACAO_A_USUARIO_CONFIRMADA` comprova somente a interação técnica definida pelo perfil; não comprova leitura, compreensão, ciência jurídica ou efeito de negócio.

### Negação e operações em massa

Tentativas negadas registram classe segura do recurso, decisão, motivo e correlação. Não copiam token, consulta, payload ou valor arbitrário fornecido pelo solicitante. Digest só é admitido quando necessário, não correlacionável de forma indevida e autorizado pelo perfil.

Respostas externas não distinguem objeto inexistente de objeto invisível. `DADOS_NAO_ENCONTRADOS_NO_ESCOPO` é diagnóstico interno controlado.

Operações em massa preservam escopo declarado, contagens esperadas, processadas, omitidas, negadas, desconhecidas e falhas. O estado pode ser completo, parcial com razão ou indeterminado. Digest de lote declara precisamente quais elementos, ordem, serialização e fronteira cobre.

### Participantes e acesso privilegiado

A auditoria distingue Actor originador, AuthenticatedPrincipal, DecisionAuthority, ServiceIdentity executora e destinatário externo. A execução por worker não apaga nem substitui o Actor original.

`PrivilegedAccessSession` exige finalidade controlada, autoridade, escopo, prazo, justificativa e correlação. Uma sessão privilegiada não cria finalidade por si só. Ao expirar durante uma operação, a Policy determina abortar, concluir com segurança, colocar em quarentena ou exigir nova autenticação; o comportamento fica auditado.

### Obrigatoriedade, completude e integridade

`SensitiveAccessProfile` compõe classificação, finalidade, operação, campos, contrato e Policy pela restrição efetiva mais estrita. Quando a auditoria for obrigatória, incapacidade de registrar o marco necessário impede ou interrompe a operação de forma segura.

O perfil também calibra granularidade e marcos obrigatórios segundo risco, finalidade e obrigação aplicável. Não se cria um DataAccessRecord para toda leitura interna por padrão. Antes de ativar perfil de alto volume, estimam-se amplificação de escrita, retenção, custo de índices e checkpoints e executa-se teste representativo. Reduzir volume não autoriza omitir marco material, mas multiplicar registros sem finalidade auditável também é proibido.

Falhas distinguem autorização, execução, auditoria, entrega, dependência, integridade e resultado desconhecido. Persistência com resultado desconhecido exige reconciliação; não é tratada automaticamente como sucesso ou ausência.

`AuditCompletenessAssessment` avalia separadamente completude estrutural, de fontes, temporal, de perfil e de integridade. Ausência de registro não prova ausência de acesso quando fontes, cobertura ou coleta forem incompletas. `COMPLETA_COM_LIMITACOES` só é permitido quando as limitações não impedem a conclusão declarada.

Checkpoint comprova integridade e cobertura do intervalo declarado, não completude universal. Registra fronteiras, fontes, lacunas e limitações conhecidas.

### Auditoria da auditoria e transparência

`AuditTier` controla recursão: Tier 0 registra operação de negócio; Tier 1, acesso aos registros de auditoria; Tier 2, administração e verificação. Acesso administrativo não permite alteração ou exclusão sem autorização específica e Evidence independente.

`AccessTransparencyPolicy` define identidade exibida, granularidade, atrasos, exceções e proteção de terceiros. A transparência pode identificar Actor, Organization ou categoria autorizada. Atraso exige motivo, prazo e revisão; não apaga o registro original.

`AccessTransparencyReport` declara período, fontes, escopo incluído, exclusões, fronteira de cobertura, limitações e versão da Policy. Relatórios completos, incrementais, de correção e de atualização de política não são intercambiáveis. Registro tardio produz relatório correlacionado; publicação anterior não é reescrita.

### Operação offline e verificação

O cliente offline registra marcos locais com Device, sessão previamente estabelecida, relógio observado e confiança temporal. Sincronização e aceitação pelo servidor são marcos distintos. Rejeição no servidor não prova que uma apresentação ou leitura local nunca ocorreu.

Testes arquiteturais cobrem retries e duplicidades, marcos ausentes ou fora de ordem, negação sem vazamento, lotes parciais, falha e resultado desconhecido de auditoria, expiração privilegiada, completude limitada, tiers recursivos, transparência atrasada, registros tardios e divergência entre acesso local e aceitação no servidor.

---

# Valkey para cache e coordenação efêmera

Valkey segue a ADR 0025 e existe somente na Infrastructure. Perda total pode reduzir desempenho ou disponibilidade controlada, mas não altera verdade histórica nem perde efeito de negócio confirmado.

PostgreSQL, Source externa ou Artifact aprovado são resolvidos como AuthoritativeSourceReference conforme o caso de uso. Valkey contém apenas materializações derivadas, efêmeras e reconstruíveis.

## Usos e proibições

Usos permitidos: cache de leitura, metadata externa curta, rate limiting, supressão técnica de duplicidade, leases best-effort, redução de stampede e hints efêmeros de invalidação ou refresh.

Valkey nunca armazena autoritativamente Domain, Authorization, Membership, grant, Policy, Event, Evidence, Decision, Audit, Outbox, Inbox, ConsumerReceipt ou efeito idempotente durável. Não é Message Broker, scheduler ou workflow autoritativo e não será broker do Celery por esta decisão.

## CacheProfile e envelopes

Cada uso exige CacheProfile versionado com finalidade, classificação, dimensões da key, AuthoritativeSourceReference, TTL, freshness, bounded staleness, comportamento de falha, cache negativo, invalidação, rebuild, tamanho, cardinalidade, serialização, criptografia, observabilidade e limitações.

CacheKey é opaca e inclui ambiente, Organization ou escopo público, capacidade quando relevante, Purpose, operação, recurso, versão, Policy, DataContract e variante que altere resultado. Não contém PII, token, secret ou informação que revele recurso protegido.

CacheEntryEnvelope preserva schema, profile, source e AuthorizationContextVersion, created_at, valid_until, stale_until, source Digest, classificação e limitações. Entrada incompatível, vencida ou de outro contexto produz miss seguro.

Namespace não substitui ACL, credenciais separadas, segregação de ambientes, validação de contexto ou Authorization.

## Freshness, invalidação e negative caching

TTL, freshness, retenção e disposição são dimensões distintas. Eviction é evento operacional esperado e não falha de integridade do domínio.

AuthorizationContextVersion ou RevocationEpoch impede novos hits na geração anterior após mudança material. Invalidation reduz a janela, mas não é garantia única; bounded staleness e revalidação continuam aplicáveis.

NegativeCachePolicy distingue `NAO_ENCONTRADO`, `NEGADO`, `INACESSIVEL` e `INDETERMINADO`. Negação não vira inexistência, indeterminação não vira lista vazia e miss não prova ausência.

TTL usa jitter. Single-flight ou lease curta reduz stampede. Stale-while-revalidate somente é permitido quando o profile demonstrar que obsolescência delimitada não afeta segurança ou Decision.

## Falha e degradação

CacheFailureBehavior pode recorrer à fonte autoritativa, negar com segurança, degradar com limites ou ignorar a otimização. CacheResolutionResult registra resolvido, resolvido com degradação, negado ou indeterminado.

DegradedCapability declara capacidades disponíveis e removidas, freshness, fonte, prazo, ReasonCodes e limitações. Presentation diferencia degradação do funcionamento normal e bloqueia efeitos proibidos pelo profile.

Circuit breaker aberto prova decisão local de suspender chamadas, não indisponibilidade da Source. Timeout não prova ausência de efeito externo.

## Rate limiting

RateLimitProfile delimita principal técnico, Organization, Purpose, operação, classe de recurso, origem de rede ou ServiceIdentity, janela, limite, burst, custo e comportamento de falha.

Operação sensível pode negar com segurança; consulta pública de baixo risco pode usar limite local conservador. Resposta e timing não revelam User existente, recurso invisível, quota ou atividade de terceiro.

## Leases, locks e fencing

Lease distribuída representa posse temporária best-effort. `lock adquirido` não significa autoridade para commit.

Efeito crítico exige FencingToken validado pelo PostgreSQL ou recurso autoritativo; token obsoleto é rejeitado. Sem essa validação, fencing é decorativo. Lock sem fencing protege apenas otimização idempotente cuja duplicação seja segura.

Unicidade, numeração oficial, sequência de auditoria, saldo, limite contratual, assinatura, disposição e efeito irreversível usam constraint ou transação autoritativa.

## Deduplicação, restore e warm-up

Deduplicação Valkey reduz trabalho em janela curta e não prova consumo ou efeito. Inbox, ConsumerReceipt, IdempotencyKey e constraints duráveis permanecem no PostgreSQL quando replay ou negócio exigir.

RDB, AOF e replication são otimizações operacionais. Write reconhecido não significa durabilidade, consenso ou efeito oficial.

Restore não recoloca entries como confiáveis. Warm-up é nova materialização e reaplica profile, Organization, Purpose, classificação, contrato, Authorization, schema, freshness e versão da key.

## Segurança e serialização

Valkey opera em rede privada, com autenticação, TLS quando aplicável, ACL mínima e credenciais por ambiente. Runtime não administra, altera configuração, executa flush global ou acessa namespace alheio.

Tipos e schemas de serialização são controlados; não há desserialização genérica executável. Conteúdo incompatível produz miss seguro e compressão possui limite de expansão. Tokens, secrets, chaves privadas, payload bruto e PII desnecessária são proibidos.

## Separação e testes

PostgreSQL é autoridade de domínio; GridFS guarda bytes; Message Broker entrega mensagens; Outbox publica transacionalmente; Inbox comprova consumo durável; Valkey acelera e coordena de forma efêmera.

Métricas observam hits, misses, idade, fallback, degradação, eviction, stampede, rebuild, contextos rejeitados, invalidações, leases, fencing, cardinalidade e recuperação sem labels sensíveis.

Testes cobrem perda total, miss conclusivo, key cruzada, autorização revogada, invalidation perdida, negative caching incorreto, stampede, stale sensível, falha fora do profile, canal lateral de rate limit, lease expirada, fencing não validado, dedupe antes do replay, secret no cache, restore obsoleto e Valkey usado como broker ou Audit.

Versão, client, standalone, Sentinel, Cluster, persistence, eviction policy, capacidade e topologia ficam para o passo de infraestrutura.

---

# Segurança

Segurança é requisito transversal e adota negação por padrão, menor privilégio, defesa em profundidade, segregação de funções e rastreabilidade proporcional ao risco. Autenticação não implica Authorization, e nenhum endpoint protegido opera sem principal validado e contexto interno aplicável.

Autenticação segue a ADR 0005 e falha de forma fechada. Metadata e chaves são obtidas somente de endpoints previamente confiáveis. Dados do token não podem indicar livremente URLs de chaves, certificados ou configuração.

Cache de metadata e chaves possui duração e atualização controladas. `kid` desconhecido não provoca consultas ilimitadas, e chaves antigas não permanecem confiáveis indefinidamente. Token opaco que não possa ser validado por introspection é rejeitado.

Logout, encerramento de sessão, revogação de Refresh Token, revogação de Access Token e bloqueio interno são mecanismos distintos. Access Tokens possuem duração curta compatível com o risco.

Clientes externos não acessam bancos, cache, broker ou armazenamento diretamente. A Infrastructure utiliza identidades de serviço distintas, credenciais mínimas por ambiente e interfaces autorizadas pela Application.

Segredos nunca ficam no código, imagens, fixtures, logs ou payloads. Gestão de segredos cobre geração, distribuição, uso, rotação, revogação, recuperação e evidência de acesso. O mecanismo concreto, criptoperíodo e procedimento operacional são definidos por perfil e decisão própria.

Tokens, authorization codes, senhas, client secrets e chaves privadas nunca ficam no domínio, auditoria ou logs.

## Modelo de ameaças e hardening

Cada incremento exposto atualiza um threat model proporcional ao seu escopo, considerando fronteiras de confiança, ativos, atores, abuso, exfiltração, elevação de privilégio, negação de serviço, supply chain e operação offline. Riscos aceitos possuem autoridade, prazo e Evidence; ferramenta de segurança não decide risco de negócio.

Ambientes são segregados. Produção usa configuração endurecida, dependências verificáveis, menor superfície exposta, proteção de headers e transporte, limites de recursos, validação de entrada e administração privilegiada auditada. Dados ou credenciais de produção não são copiados para ambientes inferiores sem processo autorizado.

Dependências, imagens e artefatos possuem inventário e origem verificável. Vulnerabilidades, secrets expostos e configuração divergente geram triagem, decisão e resposta observáveis conforme a ADR 0023.

## Verificação operacional

Testes de segurança cobrem isolamento entre Organizations, elevação de privilégio, enumeração, autorização parcial, replay, limites de recursos, entradas hostis e vazamento em logs. Backup, restauração, rotação de credenciais e resposta a incidentes são exercitados; configuração declarada não é tratada como controle comprovado sem Evidence operacional.

Alvos de correção, detecção, resposta e recuperação são requisitos de cada perfil operacional. Ausência de alvo aprovado permanece lacuna explícita e não autoriza alegação de segurança ou resiliência.

---

# Escalabilidade

O Titan começa como monólito modular e escala primeiro por medição, otimização segura e replicação de componentes stateless. Workers são introduzidos para trabalho assíncrono aprovado; distribuição física de módulos ou adoção de microserviços exige nova ADR e evidência de que isolamento operacional supera o custo de consistência e operação.

## Perfis e alvos operacionais

Capacidade, latência, disponibilidade, durabilidade e recuperação são definidas por perfil operacional e workload, não por promessa global implícita. Cada perfil identifica ao menos:

- Organizations, principals e sessões concorrentes esperados;
- taxa e pico de comandos, consultas, eventos e operações offline;
- volume, crescimento, retenção e padrão de acesso de registros, Documents e auditoria;
- orçamento de latência por caso de uso e limite de processamento assíncrono;
- disponibilidade requerida e dependências críticas;
- RPO e RTO por categoria de dado e serviço;
- janela de manutenção, degradação permitida e critérios de backpressure;
- método, ambiente, massa e data da medição.

Os valores permanecem a definir antes de dimensionamento ou compromisso externo. Ausência de perfil impede afirmar que a plataforma atende determinado volume, latência, disponibilidade, RPO ou RTO.

## Estratégia de crescimento

Consultas críticas possuem orçamento e dados representativos. Índices, particionamento, cache, réplicas, filas e processamento em lote são adotados somente quando a medição demonstrar necessidade e sem reduzir isolamento, auditabilidade ou correção.

Componentes stateless podem escalar horizontalmente. Estado autoritativo permanece nas tecnologias aprovadas; cache, réplica, Projection e broker não se tornam fonte de verdade por conveniência. Backpressure, quotas, bulkheads, retry limitado e degradação explícita impedem que uma carga ou Organization esgote recursos compartilhados.

Particionamento ou arquivamento preserva RLS, RecordOwnerOrganization, ordenação aplicável, retenção, LegalHold, integridade e replay autorizado. Crescimento da auditoria e de DataAccessRecords é acompanhado separadamente do tráfego de negócio e calibrado por perfis de sensibilidade aprovados.

## Resiliência e evolução

Backup reconhecido só atende ao perfil após restauração testada e reconciliação. RPO mede perda máxima tolerada de dados; RTO mede tempo máximo tolerado para recuperar a capacidade declarada. Ambos são específicos por serviço e categoria, versionados e validados por exercício periódico.

Observabilidade acompanha saturação, latência, erros, filas, idade da Outbox, consumo, armazenamento, reconciliações e objetivos definidos, sem expor conteúdo protegido. Mudança de topologia, particionamento ou execução não quebra contratos públicos nem altera silenciosamente semântica, Authorization ou resultados históricos.

---

# Inovações Arquiteturais e Protocolo Aberto (TEP)

## 1. Provas de Conhecimento Zero (ZKP - Zero-Knowledge Proofs)

O Titan Core suporta a ancoragem de provas de conhecimento zero em `VerificationBundles` e `Dossiers` (ADR-0033).
- **Abstração do Domínio:** `ZeroKnowledgeProof`, `ZkCircuitReference`, `PrivateProofConstraint`.
- **Funcionamento:** Permite provar que um caminho de proveniência (`ProvenancePath`) satisfaz regras regulatórias ou restrições de conformidade sem expor identificadores sensíveis (como pessoas, coordenadas GPS de propriedades ou volumes comerciais).

## 2. Dossiê Autônomo Monolítico em HTML/Wasm (`SingleFileVerificationBundle`)

Para garantir verificabilidade perpétua sem dependência de servidores ativos ou APIs online (ADR-0034):
- O dossiê é empacotado em um arquivo único `.html`.
- O arquivo contém a árvore de hashes canônicos, os metadados das evidências, as chaves públicas e um kernel de verificação criptográfica compilado em WebAssembly.
- Ao abrir em qualquer navegador web offline, o kernel Wasm executa o recálculo dos hashes e exibe o grafo de proveniência interativo com validação gráfica de integridade e lacunas declaradas.

## 3. Motor Abstrato de Detecção de Incoerências (`ContradictionEngine`)

O Core possui um motor abstrato de validação de restrições relacionais, físicas e matemáticas sobre o grafo de proveniência (ADR-0035):
- **Abstrações:** `ContradictionAssessment`, `InconsistencyRule`, `DomainConstraint`, `PhysicalBoundAssertion`.
- **Operação:** Analisa taxas de variação, limites agregados e intersecções de conjuntos disjuntos. Quando uma contradição é detectada, o Titan marca o resultado da avaliação como `INDETERMINADA` com o código de razão `CONTRADICAO_DETECTADA`, sem alterar ou apagar o histórico de dados.

## 4. Execution Sandbox de Políticas Normativas em Wasm

Garante a reavaliação determinística atemporal de políticas normativas históricas (ADR-0036):
- **Abstrações:** `WasmNormativePolicyEvaluator`, `PolicyExecutionSandbox`, `NormativeExecutionReceipt`.
- **Operação:** Compila regras normativas para bytecode WebAssembly determinístico e imutável. Reavaliar um fato histórico executa o bytecode exato da regra na data do evento, impedindo que mudanças posteriores no código da aplicação alterem decisões passadas.

## 5. Titan Evidence Protocol (TEP) e Modelo Open-Core

Para eliminar o risco de *lock-in* comercial para clientes e auditores (ADR-0037):
- A especificação esquemática do **Titan Evidence Protocol (TEP)**, serialização canônica determinística e verificadores offline são mantidos sob licença aberta (MIT/Apache 2.0).
- A plataforma enterprise (gestão multi-tenant, isolamento RLS, motor adversarial avançado e verticais comerciais como o Titan Livestock) é mantida sob modelo comercial proprietário.

