# ADR 0014 — Retenção, descarte controlado e legal hold
**Status:** Aceita  
**Data:** 21 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan preserva Evidence, Events, Decisions, Publications e Dossiers auditáveis, mas também processa conteúdo pessoal, sigiloso, licenciado e operacional sujeito a finalidades e ciclos de vida distintos.

Append-only impede alteração silenciosa; não significa retenção ilimitada. Eliminar um payload também não deve apagar a prova mínima e não identificável de que a operação autorizada ocorreu.

A ADR 0013 definiu classificação, payload separável, propagação, bloqueio e disposição conceitual, deixando prazos, RetentionPolicy, legal hold e execução física para esta decisão.

## Problema

Definir:

- como uma política determina início, duração, revisão e ação final;
- como impedimentos e legal holds suspendem disposição sem ampliar outros usos;
- como executar e comprovar ações em cópias, derivados e sistemas distintos;
- como conciliar descarte com histórico, restauração, offline, exportação e falhas parciais.

## Princípios

1. **Retenção justificada e delimitada:** prazo deriva de finalidade, categoria, perfil e fundamento versionados; conveniência não é justificativa.
2. **Preservar não é utilizar:** legal hold bloqueia disposição no escopo, mas não concede acesso, compartilhamento ou novo propósito.
3. **Descarte explicável e recuperável somente quando autorizado:** ação é avaliada, aprovada, executada e reconciliada; resultado desconhecido nunca é mascarado.
4. **Histórico mínimo sem conteúdo descartado:** permanece prova da decisão e execução, não cópia, segredo ou identificador reversível do dado eliminado.
5. **Falha fechada:** conflito, prazo indeterminado, hold desconhecido ou cópia não reconciliada impedem conclusão automática.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Nunca descartar | Auditoria simples | Retenção indevida, custo e exposição crescentes |
| TTL técnico por tabela | Automação rápida | Ignora fundamento, holds, derivados e relações |
| Apagar agregado completo | Implementação aparente simples | Destrói Provenance, decisões e explicação histórica |
| Política única global | Administração central | Não representa categorias, jurisdições e finalidades distintas |
| Políticas versionadas e disposição orquestrada | Controle, rastreabilidade e reconciliação | Exige inventário, processos privilegiados e testes de restauração |

## Decisão

Adotar RetentionPolicy versionada, aplicada a escopos classificados, com avaliação explícita de vencimento, impedimentos, LegalHold e ação final.

Disposição é processo privilegiado, assíncrono, idempotente e auditável, separado do runtime ordinário. O runtime da aplicação não recebe `DELETE`, `TRUNCATE`, acesso a chaves de destruição ou permissão para contornar retenção.

Esta ADR define semântica e controles. Não fixa prazos legais, schema, scheduler, storage, KMS, fornecedor, procedimento jurídico ou implementação de exclusão.

Os novos conceitos são candidatos arquiteturais e dependem de aprovação no `DOMAIN.md`.

## RetentionPolicy

Política imutável e versionada que determina o ciclo de vida de uma categoria de dados em contexto delimitado.

Contém, no mínimo:

- identidade, versão, estado, Organization responsável e perfil aplicável;
- DataClassifications, categorias, finalidades, ProcessingActivities e DataContracts cobertos;
- jurisdição, LegalBasisReferences, NormativeBasis e Evidence de aprovação;
- evento inicial, regra de cálculo, duração, unidade, calendário e timezone;
- condições de revisão, prazo máximo quando aplicável e ação ao vencimento;
- requisitos de legal hold, aprovação, segregação, reconciliação e relatório;
- tratamento de derivados, backups, caches, índices, dispositivos, integrações e exportações;
- validade, substituição, limitações e Actor aprovador.

Prazo não é string livre. O início depende de evento verificável, como encerramento de relação, término da finalidade, última operação autorizada ou decisão específica. Evento ausente ou ambíguo produz revisão, não estimativa silenciosa.

Nova versão não recalcula ou elimina histórico automaticamente. Impacto sobre objetos existentes exige avaliação registrada.

## RetentionClock

Cálculo temporal imutável de uma RetentionAssignment. Preserva trigger Event, instante e Source, calendário, timezone, método, períodos de pausa, retomadas, expiração calculada, TimeConfidence e limitações.

TimeConfidence considera autoridade temporal, sincronização, divergências e incerteza. Relógio de cliente ou servidor isolado não constitui prova suficiente. Inconsistência temporal produz revisão, não descarte automático.

Pausa ou retomada exige previsão na política, evento verificável e auditoria. Suspensão contratual não congela prazo por presunção.

## RetentionAssignment

Vínculo imutável entre objeto ou conjunto delimitado, DataClassification e RetentionPolicy aplicável.

Registra escopo, versão da política, evento inicial, instante calculado, fontes temporais, exceções, prioridade, revisão e Provenance. Um objeto pode possuir múltiplas obrigações simultâneas.

Conflito produz RetentionConflictAssessment com políticas, fundamentos, prioridades, impedimentos, decisão, Actor e Evidence considerados. Não prevalece automaticamente o prazo maior ou menor. Sem regra segura, aplica-se preservação restrita e revisão obrigatória.

RetentionAssignment não concede Authorization nem torna lícito tratamento incompatível.

## RetentionReview

Revisão imutável iniciada por nova Policy, Evidence, mudança normativa, conflito, evento ou review due. Registra objetos, assignments, versão anterior, impacto, conclusão e próxima revisão sem alterar prazo ou histórico automaticamente.

## Estado de retenção

O estado é controlado e suas transições são auditadas. Estados conceituais iniciais:

- `EM_RETENCAO`;
- `REVISAO_NECESSARIA`;
- `BLOQUEADO_POR_HOLD`;
- `ELEGIVEL_PARA_DISPOSICAO`;
- `DISPOSICAO_EM_EXECUCAO`;
- `DISPOSICAO_PARCIAL`;
- `DISPOSICAO_CONCLUIDA`;
- `RESULTADO_DESCONHECIDO`.

Estado não substitui o relatório de avaliação. Vencimento cronológico não torna o objeto automaticamente descartável.

## LegalHold

Ordem versionada e auditável que suspende disposição para escopo específico devido a litígio, investigação, auditoria, obrigação ou outra autoridade reconhecida por perfil.

Registra autoridade solicitante, base, Evidence, escopo, motivo protegido, início, estado, responsável, revisão prevista, condições de liberação e limitações.

O cliente não escolhe ou remove hold livremente. Aplicação, alteração e liberação exigem Actor competente, Permission, segregação de funções e auditoria.

Hold pode abranger objetos, sujeitos, períodos, Organizations, categorias ou relações, mas deve ser determinístico e pesquisável. Escopo excessivamente aberto exige revisão; ausência de data final não elimina revisão periódica.

LegalHold:

- impede somente a disposição abrangida;
- não amplia Visibility, finalidade, audiência ou compartilhamento;
- não restaura acesso anteriormente revogado;
- não altera Evidence ou Decision histórica;
- não é removido porque a RetentionPolicy mudou.

Liberação torna o escopo novamente avaliável; não executa descarte automaticamente.

## DispositionAssessment

Avaliação imutável anterior à execução que confirma:

- objeto, cópias e derivados localizados por Provenance;
- RetentionAssignments e versões aplicáveis;
- finalidade encerrada e evento inicial verificável;
- impedimentos, LegalHolds, investigações, contratos e Publications;
- DataContracts, ProcessingActivities e DataProcessingRoles relevantes;
- impacto em Events, Evidence, Decisions, Dossiers e VerificationBundles;
- ação proposta, autoridade, aprovações e riscos;
- sistemas não alcançáveis, exportações e limitações conhecidas.

Todas as etapas compartilham DispositionScope imutável: objetos, Organizations, intervalo temporal, DataClassifications, ProcessingActivities, derivados e exclusões justificadas. Ampliação ou redução cria novo escopo e nova avaliação.

Solicitação de titular, vencimento ou revogação de consentimento inicia avaliação; não determina exclusão automática.

Resultado conceitual: `AUTORIZADA`, `NEGADA`, `ADIADA`, `REVISAO_NECESSARIA` ou `INDETERMINADA`, sempre com códigos de razão.

Códigos permanentes iniciais incluem `RETENCAO_NAO_ENCERRADA`, `LEGAL_HOLD_ATIVO`, `POLITICAS_CONFLITANTES`, `INVENTARIO_DESCONHECIDO`, `COPIA_EXTERNA`, `BACKUP_PENDENTE`, `RECONCILIACAO_NECESSARIA`, `AUTORIZACAO_AUSENTE` e `CONFIANCA_TEMPORAL_INSUFICIENTE`. Código não substitui explicação nem Evidence.

## Ações de disposição

A ação é valor controlado por perfil:

- `ELIMINAR`: remover payload do escopo inventariado;
- `ANONIMIZAR`: produzir resultado aprovado por AnonymizationAssessment;
- `DESTRUIR_CHAVE`: executar crypto-shredding quando a chave for exclusiva e o inventário permitir;
- `ARQUIVAR_RESTRITO`: mover para ambiente e finalidade de conservação delimitados;
- `REVISAO_OBRIGATORIA`: impedir automação até decisão competente.

Arquivamento restrito não renova finalidade original nem significa retenção permanente. Anonimização não é simples remoção de identificador. Destruição de chave não prova eliminação de cópias em claro.

Uma política pode exigir ações diferentes por componente, sem apresentar disposição parcial como completa.

LogicalDisposition bloqueia resolução, uso e novos acessos no escopo aprovado. PhysicalDisposition remove material dos alvos inventariados. Bloqueio lógico não é apresentado como destruição física; cópia física pendente permanece restrita e reconciliável.

## DispositionOperation

Operação lógica idempotente criada após avaliação autorizada. Preserva operation ID, IdempotencyKey, DispositionScope, política, avaliação, ação, Actor autorizador, executor, sistemas-alvo, estado e correlação.

Cada executor usa ServiceIdentity própria e menor privilégio. O processo distingue Actor solicitante, aprovador, serviço executor e operador de reconciliação.

Claim ou lease abandonado deve expirar ou ser recuperável. Repetição preserva identidade lógica e não cria descarte fora do escopo aprovado.

Falha de comunicação pode produzir `RESULTADO_DESCONHECIDO`. Esse estado não equivale a sucesso ou falha e exige inspeção ou reconciliação antes de nova conclusão.

## DispositionReceipt e relatório

Cada sistema-alvo produz DispositionReceipt imutável e versionado com operação, escopo opaco, ação tentada, executor, início, término, resultado, contagens, limitações e erros seguros.

DispositionReceipt é registro operacional e não se torna Evidence automaticamente. Ele referencia ou produz Evidence verificável com Provenance, Digest, Signature quando exigida e perfil aplicável.

## DispositionReconciliation

Reconciliação imutável compara expected targets, completed targets, missing targets, unknown targets e inconsistências definidos pelo DispositionScope. Registra receipts usados, conclusão, limitações, responsável e instante.

Cada executor informa resultado local; nenhum executor define isoladamente a conclusão global.

O DispositionReport agrega a reconciliação e apresenta separadamente:

- avaliação e aprovações;
- cópias previstas, alcançadas, pendentes e desconhecidas;
- derivados atualizados ou bloqueados;
- ação e resultado por sistema;
- falhas parciais, retries e reconciliações;
- material histórico mínimo preservado;
- limitações sobre cópias externas ou não inventariadas.

Receipt ou relatório nunca contém payload eliminado, hash previsível, chave, recovery share ou segredo capaz de reconstrução.

Conclusão `DISPOSICAO_CONCLUIDA` exige DispositionReconciliation do inventário aprovado. Evidence comprova o procedimento nos locais conhecidos; não afirma inexistência absoluta de cópias desconhecidas.

## Histórico append-only

Event, Evaluation, Decision e Evidence permanecem append-only durante a retenção aplicável. Correction, Revocation, bloqueio e disposição criam novos registros.

Quando o payload pessoal for separável e sua eliminação autorizada, permanece envelope mínimo com identidade opaca da operação, política e versão, ação, instantes, Actors autorizados quando permitido, resultado e Provenance não reversível.

O envelope não preserva valor eliminado, texto livre revelador, Digest de dado previsível ou referência ainda resolvível.

Decision, Dossier ou Publication dependente não é reescrito. É marcado como potencialmente afetado quando aplicável e recebe análise de impacto. Disposição não transforma automaticamente decisão histórica em inválida.

## Cópias e derivados

O inventário considera PostgreSQL, GridFS, object storage futuro, réplicas, backups, caches, índices, analytics, observabilidade, Message Broker, Inbox, quarentena, dispositivos offline, arquivos temporários, suporte e exportações controladas.

Classificação e RetentionAssignment propagam-se a derivados. Cópia temporária não recebe prazo ilimitado. Cache ou índice não se torna fonte autoritativa.

Conteúdo entregue legitimamente a terceiro, publicado ou exportado pode estar fora do controle físico do Titan. O relatório registra destinatário, contrato, instante, escopo e limitação; não promete apagar cópia externa sem mecanismo e autoridade próprios.

Revogar VerificationCode, Sharing ou Publication impede novos acessos controlados quando aplicável, mas não apaga bundle ou arquivo já obtido nem revoga sua evidência criptográfica.

## Backups e restauração

Backups possuem DataClassification, finalidade, acesso, região, criptografia, inventário e política próprios.

Não se presume edição pontual segura de backup imutável. A política pode usar expiração previsível combinada com bloqueio de reintrodução, desde que o prazo e a limitação sejam declarados.

Antes de liberar restore, o processo reaplica LegalHolds, bloqueios, disposições e restrições vigentes. Conteúdo anteriormente eliminado que reapareça fica isolado e não retorna ao uso ordinário.

Teste de restauração verifica reconciliação entre PostgreSQL, GridFS, caches, índices e ledger de disposição.

## Mensageria, offline e integrações

Outbox, Message Broker, Inbox, retry e quarentena obedecem à retenção definida no DataContract e não se tornam arquivo histórico por conveniência.

Mensagem de disposição contém referências opacas e escopo mínimo. Consumidores validam versão, autorização técnica e idempotência, sem decidir obrigação jurídica.

Dispositivo offline não executa legal hold, liberação ou disposição definitiva. Na sincronização, o servidor reavalia identidade, Policy, RetentionAssignment, holds, conflitos e estado atual.

Integração externa recebe pedido de disposição somente quando contrato, autoridade e confirmação forem definidos. Resultado desconhecido permanece reconciliável.

## Segurança e segregação

O plano de controle cria e aprova operações; executores técnicos acessam apenas o escopo autorizado. Nenhum administrador isolado deve solicitar, aprovar, executar e atestar operação sensível quando o perfil exigir segregação.

Credenciais, chaves e permissões de disposição são separadas por ambiente. Logs usam IDs opacos e códigos seguros. Acesso de emergência é temporário, justificado e auditado.

Suspensão de serviço, incidente ou falha de dependência interrompe novas operações sem transformar trabalho parcial em sucesso.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Retenção justificável; hold delimitado; descarte reconciliável; histórico mínimo; restore seguro |
| Negativas | Inventário amplo; operação privilegiada; tratamento de falhas parciais; custo de reconciliação e testes |

## Riscos e controles

| Risco | Controle |
|---|---|
| TTL eliminar dado sob hold | Avaliação obrigatória antes da execução |
| Hold ampliar acesso | Separação entre preservação, Authorization e finalidade |
| Exclusão parcial apresentada como completa | Receipts por sistema e reconciliação do inventário |
| Restore ressuscitar payload | Ledger de disposição aplicado antes da liberação |
| Evidência permitir reconstrução | Envelope mínimo e proibição de hash previsível |
| Operador apagar fora do escopo | Segregação, menor privilégio, IdempotencyKey e escopo imutável |
| Cópia externa permanecer | Limitação explícita, DataContract e registro de destinatário |

## Verificação automatizada

Testes futuros devem cobrir:

- vencimento sem evento inicial verificável;
- conflito entre políticas, hold ativo, liberação e revisão periódica;
- cliente tentando escolher política, ação ou remover hold;
- runtime ordinário tentando `DELETE`, destruir chave ou acessar executor;
- retry, claim abandonado, resultado desconhecido, TimeConfidence insuficiente e falha parcial;
- disposição sem inventário ou com derivado não reconciliado;
- DispositionScope divergente, reconciliação incompleta ou receipt contendo dado, hash previsível ou segredo;
- backup restaurando conteúdo eliminado ao uso ordinário;
- anonimização sem assessment e chave não exclusiva em crypto-shredding;
- revogação de código apresentada como eliminação de cópia exportada.

## Critérios de aceitação

A ADR pode ser aceita quando:

- RetentionPolicy, RetentionClock, RetentionAssignment, RetentionReview, LegalHold e Authorization forem distintos;
- prazos dependerem de eventos e perfis versionados, sem número universal no Core;
- conflitos, pausas, fontes temporais e TimeConfidence permanecerem explícitos;
- vencimento iniciar avaliação, não exclusão automática;
- DispositionScope for imutável e ações usarem processo privilegiado e idempotente;
- holds bloquearem descarte sem ampliar acesso ou finalidade;
- disposição lógica e física não forem confundidas;
- receipts, Evidence, resultados parciais e desconhecidos permanecerem distintos e reconciliáveis;
- histórico mínimo não contiver o payload ou mecanismo de reconstrução;
- derivados, mensagens, offline, integrações, exportações, backups e restore forem considerados;
- conclusão não prometer eliminação além do inventário e Evidence disponível;
- nenhuma migration, API, scheduler, grant ou rotina física seja criada por esta ADR.

## Referência normativa inicial

Perfis jurídicos versionam fontes, interpretações, prazos e exceções. Como referência brasileira inicial, os arts. 15 e 16 da Lei nº 13.709/2018 tratam do término do tratamento e das hipóteses de conservação.

O Core não conclui obrigação jurídica, não fixa prazo universal e não substitui avaliação profissional ou determinação de autoridade.

Fonte oficial: `https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm`.

## O que esta ADR não decide

Esta ADR não escolhe:

- prazos concretos, interpretação jurídica, autoridade ou procedimento de litígio;
- schema, tabela, scheduler, fila, worker, storage, KMS ou algoritmo;
- IdentityVault, fluxo completo de direitos do titular ou localização de dados;
- edição física de backup, exclusão em terceiro ou garantia absoluta de destruição.

## Plano de reversão

Antes da implementação, esta proposta pode ser substituída. Depois da adoção, nova decisão preserva versões de políticas, clocks, assignments, reviews, holds, assessments, escopos, operações, receipts, reconciliações e relatórios.

Reversão não reintroduz payload descartado, remove hold silenciosamente, reduz retenção retroativamente ou apresenta resultado parcial como concluído.
