# ADR 0021 — Operação offline e sincronização segura
**Status:** Aceita  
**Data:** 21 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan será utilizado em locais com conectividade limitada ou intermitente. Capturas operacionais não podem depender de conexão contínua, mas desconexão também não pode ampliar autenticação, autorização, finalidade ou autoridade do dispositivo.

O Domain já define Device, OfflineOperation, SynchronizationBatch, SynchronizationResult, SynchronizationConflict e TimeConfidence. As ADRs 0005, 0013, 0015, 0018 e 0019 delimitam autenticação local, classificação, proveniência, autorização materializada e auditoria offline.

Esta ADR consolida essas regras sem criar um segundo domínio de sincronização. Os novos conceitos são candidatos arquiteturais e somente serão incorporados ao `DOMAIN.md` após aprovação.

## Problema

Definir:

- quais operações podem ser capturadas ou executadas sem rede;
- como delimitar sessão, Device, Organization, Purpose, campos e validade offline;
- como proteger dados locais e preservar Provenance e relógio alegado;
- como ordenar, enviar, retomar e deduplicar operações;
- como revalidar o contexto no servidor sem apagar a captura original;
- como representar aceitação, rejeição, conflito, dependência e resultado desconhecido;
- como revogar ou bloquear um Device perdido ou comprometido.

## Princípios

1. **Offline captura, não cria autoridade:** desconexão não amplia Permission, grant, Membership, Purpose ou Policy.
2. **Servidor decide o efeito oficial:** registro local não é automaticamente Event, Fact, Decision ou Publication oficial.
3. **Original preservado:** rejeição, correção ou conflito não apaga a OfflineOperation.
4. **Tempo alegado é distinto de prova temporal:** relógio do Device não substitui servidor, checkpoint ou TSA.
5. **Sincronização é por operação:** sucesso do lote não oculta resultado individual.
6. **Retry não duplica intenção:** IdempotencyKey e identidade lógica sobrevivem a interrupções.
7. **Desconhecido não é sucesso nem rejeição:** resultado incerto permanece reconciliável.
8. **Proteção acompanha o dado:** classificação, minimização, retenção e autorização também se aplicam localmente.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Exigir conexão para tudo | Segurança central simples | Inviável em campo e favorece registros paralelos |
| Replicar banco do servidor no Device | Consultas locais amplas | Grande superfície, conflito e vazamento |
| Aceitar tudo e reconciliar depois | Alta disponibilidade | Cria efeitos não autorizados e decisões incorretas |
| Fila local de comandos delimitados | Menor escopo e retomada segura | Exige perfis, conflitos e armazenamento protegido |
| Event sourcing completo no cliente | Histórico detalhado | Transfere invariantes e autoridade demais ao Device |

## Decisão

Adotar fila local append-only de OfflineOperations autorizadas por perfil curto, materializado para Device e contexto específicos.

O cliente captura intenção e Evidence dentro do perfil. Na sincronização, o servidor reautentica o principal quando aplicável, revalida todas as condições atuais e decide individualmente se transforma a operação em efeito oficial.

O cliente não executa regras regulatórias autoritativas nem emite Decision oficial. Pode produzir prévia local explicitamente não oficial para orientação, vinculada à versão conhecida e às limitações offline.

## LocalPreview

`LocalPreview` é resultado local orientativo com estado público `PREVIA_LOCAL_NAO_OFICIAL`. Não é DecisionProposal nem Decision.

Preserva OfflineOperation, Policy e versão materializadas, dados e Evidences utilizados, freshness conhecida, instante, motor local, resultado estimado e limitações. A apresentação não usa identidade visual, selo ou linguagem de decisão oficial e informa que o resultado pode divergir após sincronização.

LocalPreview não produz Publication, grant, autorização, efeito regulatório, elegibilidade oficial ou ação downstream. Ausência de dados atuais resulta em limitação ou indeterminação, nunca aprovação presumida.

## OfflineCapabilityProfile

Perfil versionado que classifica tipo de operação, dados e comportamento offline.

Categorias iniciais:

- `PERMITIDA_OFFLINE`: captura local permitida dentro do perfil;
- `PERMITIDA_OFFLINE_COM_LIMITES`: exige limites adicionais de prazo, quantidade, campos ou Evidence;
- `CONEXAO_OBRIGATORIA`: pode ser preparada, mas exige servidor antes de produzir efeito;
- `PROIBIDA_OFFLINE`: não pode ser iniciada nem simulada como operação oficial sem conexão.

O perfil preserva tipo de comando, Purpose, Organization, capacidade, FieldScope, DataContract, DataClassification, prazo, volume, dependências, Evidence exigida, comportamento de relógio, proteção local e regra de sincronização.

Cliente ou payload não escolhe categoria. Ausência de perfil aplicável resulta em proibição offline.

Exemplos conceituais:

- registrar observação ou manejo pode ser permitido;
- capturar Document pode ser permitido com limites;
- consultar estado oficial atual exige conexão;
- criar grant, alterar Policy, conceder autoridade ou emitir Decision oficial é proibido offline.

## OfflineSession

Sessão local previamente estabelecida por autenticação online e vinculada a User ou ServiceIdentity, ExternalIdentity, Actor, Device, Organization, capacidade e issuer confiável.

Preserva início, expiração, último contato confiável, AuthenticationAssurance aplicável, OfflineCapabilityProfile e motivo de encerramento. Não contém Access Token ou Refresh Token em OfflineOperation.

Expiração não converte a sessão em autorização permanente. Depois do limite, o cliente bloqueia novas operações ou permite somente captura de emergência explicitamente prevista, nunca efeito oficial.

MFA não é executada offline pelo Titan. Operação que exija autenticação recente ou assurance não disponível permanece dependente de validação online.

## OfflineAuthorizationSnapshot

Snapshot imutável da autorização materializada para uso local delimitado.

Preserva principal, capacidade, Organization atuante, Permission, AuthorizationGrants e versões, AccessPurpose, FieldScope, DataContract, Policy conhecida, recursos ou critérios, Device, emissão, expiração e limitações.

O snapshot é condição necessária para captura autorizada, não garantia de aceitação futura. Não permite criar, ampliar, delegar, reativar, suspender ou revogar grant.

Autorização local efetiva nunca excede a menor restrição entre perfil, snapshot, classificação, contrato, sessão e estado conhecido. Campo ausente é negado.

## Device e confiança

`DeviceTrustAssessment` avalia, para finalidade e instante delimitados, registro do Device, integridade disponível, versão mínima, proteção local, estado de revogação conhecido, vínculo, sinais de comprometimento e limitações.

Não representa segurança absoluta nem substitui Authorization. Root, jailbreak, versão insegura ou inventário inconsistente pode reduzir capacidades, exigir sincronização, quarentena ou bloquear captura segundo Policy.

A avaliação possui validade temporal e deve ser renovada conforme perfil. Device registrado com assessment expirado não é tratado como confiável. Revogação ocorrida durante upload é reavaliada antes de produzir efeito oficial.

Device perdido, revogado ou comprometido é bloqueado no servidor imediatamente para novas sincronizações. Cópias locais não são apagadas por suposição; remote wipe, quando suportado, produz resultado próprio e desconhecido permanece explícito.

## OfflineOperation

OfflineOperation é envelope append-only de uma intenção local e registra no mínimo:

- OperationId global e IdempotencyKey;
- OfflineSession, OfflineAuthorizationSnapshot e perfil usados;
- Actor, Organization, Device e capacidade alegados;
- tipo, contrato e versão;
- sequência local, dependências e correlation ID;
- `client_observed_at`, `server_received_at` quando existir, timezone e TimeConfidence;
- payload mínimo classificado ou referência local protegida;
- identidade semântica canônica e Digest da intenção;
- Evidences, Provenance, Digests e limitações;
- estado local e histórico de tentativas.

Editar uma operação cria nova operação correlacionada ou Correction permitida; não reescreve o envelope enviado. Segredo, token e credencial nunca integram o conteúdo.

Sequência local ordena somente operações daquele fluxo ou Device. Não prova ordem global, causalidade universal ou instante material do fato.

Reutilizar IdempotencyKey com identidade semântica diferente produz conflito e nunca recupera ou associa o resultado anterior. Dependências referenciam OperationId e tipo esperado; posição física no lote não cria causalidade. Ciclo de dependências é SynchronizationConflict explícito.

## Armazenamento local

Dados locais usam armazenamento aprovado pela plataforma, criptografia em repouso, chaves protegidas, menor exposição e bloqueio de backup inseguro conforme perfil.

DataClassification e RetentionAssignment determinam campos, prazo, exportabilidade, screenshots quando controláveis, logs, caches e disposição após sincronização. PII não é duplicada quando Identifier opaco for suficiente.

Chave local, PIN e material de recuperação não são persistidos com os dados que protegem. Logs locais não contêm payload, token, secret ou atributo pessoal.

Falha de armazenamento, espaço insuficiente ou perda de chave é apresentada antes de confirmar captura. O cliente não declara persistência concluída quando o resultado for desconhecido.

## SynchronizationBatch

SynchronizationBatch transporta conjunto delimitado de OfflineOperations e preserva `BatchId`, `BatchVersion`, `OperationManifest`, `OperationCount`, `ManifestDigest`, `SequenceBoundary` e `CreatedAtDevice`.

O manifesto identifica OperationId, identidade semântica, Digest individual, posição física e dependências declaradas. Permite detectar remoção, duplicação, substituição e alteração sem transformar ordem física em causalidade. Integridade ou assinatura do lote não substitui a integridade individual.

O lote não é unidade atômica de negócio. Cada operação recebe SynchronizationResult individual. Aceitação parcial preserva operações pendentes e permite retomada pelo mesmo BatchId ou por lote correlacionado, sem alterar IdempotencyKey.

Compressão, paginação ou divisão não muda ordem declarada nem escopo do Digest. Elemento omitido, duplicado ou fora da fronteira é informado.

## SynchronizationBatchResult

Resultado agregado e reconstruível do processamento de um SynchronizationBatch.

Estados iniciais: `RECEBIDO`, `VALIDADO_PARCIALMENTE`, `PROCESSADO_PARCIALMENTE`, `PROCESSADO`, `EM_RECONCILIACAO`, `REJEITADO_ESTRUTURALMENTE`, `RESULTADO_INDETERMINADO`.

Preserva manifesto, operações esperadas e examinadas, contagens por SynchronizationResult, lacunas, tentativas e limitações. Estado agregado nunca substitui ou reduz a precisão dos resultados individuais. Lote recebido ou processado pode conter operações rejeitadas, duplicadas, conflitantes, em quarentena ou pendentes.

## Recepção e revalidação

Na recepção, o servidor valida:

- contrato, formato, tamanho, Digest e identidade do Device;
- duplicidade, sequência e dependências;
- identidade e estado atual de User ou ServiceIdentity;
- Membership, capacidade, Permission e OrganizationContext;
- grants, restrições, Purpose, FieldScope e DataContract;
- DataClassification, ProcessingActivity, RetentionPolicy e LegalHold;
- Policy atual e histórica relevante, versão esperada e concorrência;
- Evidence, Provenance, freshness, relógio e conflitos;
- status de Device, OfflineSession e perfil.

Revalidação usa o contexto atual para autorizar o efeito, mas preserva o contexto alegado e conhecido no momento da captura. Conhecimento posterior não reescreve OfflineOperation.

Token expirado, vínculo encerrado, grant revogado, Policy alterada ou Device bloqueado pode impedir aceitação. Isso não prova fraude nem elimina a evidência de captura.

## SynchronizationResult

Estados públicos iniciais em português:

- `ACEITA`;
- `REJEITADA`;
- `DUPLICADA`;
- `CONFLITANTE`;
- `DEPENDENCIA_PENDENTE`;
- `EM_QUARENTENA`;
- `RESULTADO_DESCONHECIDO`.

O resultado preserva OperationId, tentativa, instante, estado, ReasonCodes, objetos oficiais produzidos, conflitos, dependências, limitações e Evidence.

Confirmação de transporte ou aceitação do lote não significa aceitação da operação. `ACEITA` exige commit do efeito e do resultado auditável na mesma fronteira transacional aplicável.

O resultado aceito deve permanecer recuperável por OperationId e IdempotencyKey. Efeito sem resultado recuperável ou resultado sem efeito comprometido viola a fronteira transacional e exige reconciliação, nunca `ACEITA`.

Falha após commit e antes da resposta produz resultado desconhecido no cliente. Retry com a mesma IdempotencyKey deve recuperar o resultado sem repetir o efeito.

`RESULTADO_DESCONHECIDO` descreve o conhecimento de um participante em um instante. O servidor pode conhecer um efeito que o cliente ainda não confirmou. O estado não implica ausência, sucesso ou falha e exige estratégia e prazo de reconciliação.

## Conflitos e dependências

SynchronizationConflict distingue versão divergente, ordem causal, dependência ausente, autorização alterada, Policy incompatível, Evidence conflitante e relógio insuficiente.

Conflito não é resolvido por last-write-wins, maior timestamp do Device ou último lote recebido. A resolução pode aceitar, rejeitar, solicitar Evidence, produzir Correction, exigir revisão ou criar nova operação autorizada.

Operação dependente não é executada antes da dependência aceita. Dependência rejeitada, desconhecida ou em conflito mantém estado explícito; não é tratada como inexistente. Ciclo ou identidade de dependência divergente produz conflito em vez de pendência indefinida.

## Relógio e temporalidade

O cliente preserva horário observado, horário alegado do fato, timezone, monotonic clock quando disponível, sua continuidade, último horário de servidor, offset estimado e TimeConfidence.

Servidor registra recebimento sem substituir o instante alegado. Divergência, relógio retrocedendo ou precisão insuficiente gera limitação ou conflito.

Horário do Device não comprova vigência normativa, prazo, precedência ou existência em determinado instante. Operações que exigem prova temporal externa aguardam mecanismo aprovado.

Relógio monotônico pode sustentar ordem relativa somente dentro da continuidade registrada. Reinicialização ou perda de continuidade impede comparar os intervalos e nunca produz horário civil ou precedência global.

## Auditoria e acesso local

Cliente registra marcos locais mínimos para captura, apresentação e envio conforme SensitiveAccessProfile. Sincronização cria marcos separados de recepção, validação e resultado.

Rejeição no servidor não prova que dado nunca foi visualizado, exportado ou materializado localmente. Transparência aplica AccessTransparencyPolicy e informa limitações da telemetria offline.

ServiceIdentity de sincronização não substitui Actor originador. Administração, recuperação ou replay registram seus próprios participantes.

## Disposição e perda

Aceitação confirmada pode tornar cópia local elegível para avaliação de disposição conforme RetentionPolicy; não autoriza exclusão imediata. Pendência, conflito, resultado desconhecido, LegalHold, ausência de receipt auditável ou reconciliação bloqueiam descarte quando aplicável.

DispositionReceipt local é Evidence somente após validação aplicável. Remote wipe aceito pelo serviço do Device não comprova destruição física ou ausência de cópias.

## Testabilidade

Testes futuros devem cobrir:

- operação sem perfil ou fora de Purpose, FieldScope e prazo;
- sessão expirada, Device revogado e Membership encerrada;
- criação ou ampliação de grant offline;
- token ou PII vazando em operação, log ou batch;
- relógio alterado, retrocedendo e timezone divergente;
- duplicidade após timeout antes e depois do commit;
- mesma IdempotencyKey com identidade semântica diferente;
- efeito sem resultado recuperável ou resultado sem efeito comprometido;
- lote truncado, reordenado, parcialmente aceito e retomado;
- lote processado ocultando operações conflitantes;
- manifesto alterado entre retomadas;
- ordem física do lote usada como causalidade;
- dependência ausente, cíclica, rejeitada ou desconhecida;
- conflito resolvido por last-write-wins;
- Policy ou autorização alterada entre captura e sync;
- falha de armazenamento apresentada como captura concluída;
- perda de conexão durante upload e resposta;
- revogação do Device durante upload ou trust assessment expirado;
- rejeição eliminando a OfflineOperation;
- prévia local apresentada como Decision oficial;
- prévia local usando identidade visual oficial ou omitindo freshness;
- remote wipe apresentado como destruição comprovada;
- DispositionReceipt aceito sem validar Device e Evidence;
- rejeição do servidor apresentada como ausência de acesso local.
- replay administrativo ocultando seu operador;
- resultado desconhecido sem estratégia ou prazo de reconciliação.

## Fronteiras arquiteturais

Domain define perfis, sessões, snapshots, prévias locais, operações, lotes, resultados e conflitos; não conhece SQLite, sistema operacional, push, protocolo de sync ou SDK de Device.

Application autoriza captura e revalida sincronização, ordena casos de uso, resolve conflitos e produz efeitos oficiais.

Infrastructure implementa armazenamento local, criptografia, transporte, retry, telemetria, detecção disponível e adapters de plataforma.

Presentation distingue claramente pendente local, enviado, aceito, rejeitado, conflitante, em quarentena e desconhecido.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Captura resiliente; retomada idempotente; autoridade central preservada; conflitos e temporalidade explicáveis |
| Negativas | Estado local protegido; perfis adicionais; UX de conflitos; testes de falha e reconciliação mais complexos |

## Critérios de aceitação

A ADR pode ser aceita quando:

- offline não autenticar remotamente nem ampliar autoridade;
- toda operação possuir OfflineCapabilityProfile aplicável;
- sessão e autorização materializadas forem curtas, delimitadas e versionadas;
- Access Token e Refresh Token não integrarem OfflineOperation;
- dados locais seguirem classificação, minimização, retenção e proteção;
- tempo do Device permanecer alegação com TimeConfidence;
- cada operação possuir resultado individual e idempotente;
- IdempotencyKey ser validada contra identidade semântica canônica;
- LocalPreview permanecer visual e semanticamente distinta de Decision;
- manifesto detectar remoção, substituição e duplicação sem criar causalidade;
- resultado agregado do lote não substituir resultados individuais;
- estados públicos de sincronização estiverem em português;
- parcialidade, conflito, dependência e desconhecido permanecerem distintos;
- servidor revalidar contexto atual sem reescrever captura histórica;
- Decision, grant e mudança regulatória oficiais não forem produzidos offline;
- rejeição preservar operação, Evidence e acessos locais conhecidos;
- Device perdido ou comprometido possuir bloqueio e tratamento explícitos;
- DeviceTrustAssessment possuir validade temporal e reavaliação;
- testes reproduzirem interrupção, duplicidade, retomada e mudança concorrente;
- nenhuma tecnologia de cliente, banco local ou protocolo seja escolhida.

## O que esta ADR não decide

Esta ADR não escolhe:

- sistema operacional, framework móvel, banco local ou biblioteca criptográfica;
- formato físico, endpoint ou protocolo de sincronização;
- MDM, push, attestation ou mecanismo de remote wipe;
- período universal de validade offline;
- conjunto concreto de operações da vertical Livestock;
- estratégia de resolução automática para conflitos de negócio.

## Plano de reversão

Antes da implementação, esta proposta pode ser substituída. Depois da adoção, nova decisão preserva OfflineCapabilityProfiles, OfflineSessions, OfflineAuthorizationSnapshots, DeviceTrustAssessments, OfflineOperations, lotes, tentativas, resultados, conflitos, ReasonCodes e Evidences históricas.

Reversão não promove operação pendente a aceita, apaga captura rejeitada, transforma relógio local em prova temporal ou repete efeito já confirmado.
