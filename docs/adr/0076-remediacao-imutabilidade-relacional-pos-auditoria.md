# ADR-0076 — Imutabilidade relacional após auditoria adversarial

**Data:** 08/09/2026  
**Status:** ACEITA  
**Escopo:** FINDING-002; persistência e provisionamento de runtime  
**Autoridades:** DOMAIN.md §§2.3, 2.4 e Evidence; ARCHITECTURE.md, Persistência / Papéis e imutabilidade; ADR-0003.

## Contexto

A remediação adversarial foi autorizada, com um achado por vez e preservação dos contratos públicos. O FINDING-001 foi corrigido, validado e aceito. Esta ADR trata da decisão revelada pela investigação do FINDING-002, antes de implementar suas migrations.

O schema `core_audit` reúne história autoritativa, registros de ciclo de vida e projeções operacionais. O nome do schema não torna todas as tabelas imutáveis. Revogar toda atualização indiscriminadamente quebraria operações existentes; manter as concessões gerais atuais permite adulteração.

## Evidência no repositório e no PostgreSQL

1. `apps/provision_runtime_database_role.py` concede `SELECT, INSERT, UPDATE, DELETE` para todas as tabelas e como privilégios padrão. O catálogo local confirma concessões de UPDATE/DELETE para `titan_app`, inclusive nas tabelas históricas.
2. Em diagnóstico transacional com Organization e Evidence exclusivamente fictícias, `SET LOCAL ROLE titan_app` e contexto do proprietário, um UPDATE de `evidences.content_hash` alterou uma linha e DELETE removeu essa linha. A transação inteira foi revertida; nenhum dado preexistente foi alterado.
3. `packages/core_infrastructure/persistence/evidence.py::update` altera assinatura, validade, revogação e versão. `EvidenceService.verify_evidence`, `sign_evidence` e `revoke_evidence` utilizam esse método. Isso precisa ser reconciliado com “Registro imutável” e “Nova versão gera nova Evidence” de DOMAIN.md. Excluir Evidence do endurecimento deixaria o achado central aberto.
4. `animal_repository.py::update` atualiza `version` e reescreve `sex`, `breed`, `birth_date`. O serviço o utiliza para anexar e desativar identificadores. A projeção `animal_identifiers` é sincronizada por DELETE/INSERT. Proibir todo UPDATE em `animals` quebra esses fluxos; permitir alteração de atributos constitutivos é excessivo.
5. `movement_service.py::rebuild_stays_for_animal` recompõe `property_stays`; `projections.py` recompõe `reference_projection`. DELETE nessas projeções não é exclusão dos eventos autoritativos que as sustentam.
6. Há proteção anterior que a auditoria não distingue: `domain_events`, cadeia de integridade, checkpoints, timestamps, `evaluations`, `decisions`, `dossiers` e outros já têm policies apenas SELECT/INSERT. `idempotency_records` já possui trigger de transição restrita. ACL excessiva não implica que RLS permita todas as mutações em todas as tabelas.
7. As migrations reais ficam em `packages/core_infrastructure/persistence/migrations/versions/`; os caminhos `alembic/versions/...` citados na auditoria não são os caminhos vigentes.

Os 12 testes existentes de Evidence, Animal, API foundation, idempotência e append-only de provas Core passaram no diagnóstico. Eles demonstram os fluxos que devem continuar funcionando; não comprovam o endurecimento proposto.

## Opções e trade-offs

| Opção | Benefício | Custo ou problema |
|---|---|---|
| Bloquear UPDATE/DELETE em todo o schema | Mudança DDL curta | Quebra identificação, assinatura/revogação, idempotência, outbox e reconstrução de projeções; rejeitada |
| Proteger só tratamentos e movimentações | Reduz rapidamente parte do risco | Mantém Evidence adulterável e não encerra FINDING-002; insuficiente como solução final |
| Classificar tabelas, restringir operações e separar o ciclo de vida de Evidence | Preserva os contratos e protege a história | Exige migrations, adaptação da persistência de Evidence e testes de compatibilidade; recomendada |
| Reescrever toda persistência como event sourcing | Uniformiza a representação histórica | Refatoração transversal desnecessária para este incremento; rejeitada |

## Decisão proposta

Adotar a terceira opção, mantendo FINDING-002 aberto até terminar as duas partes sequenciais abaixo. Não iniciar FINDING-003 enquanto esse achado permanecer no incremento ativo. A proposta não altera DOMAIN.md para legitimar sobrescrita histórica.

### Parte A — Proteção compatível com as representações atuais

- Criar migration nova, sem reescrever migrations aplicadas, com lista explícita de tabelas históricas e operações negadas.
- Nas tabelas históricas, negar UPDATE, DELETE e TRUNCATE ao runtime, manter RLS por operação e adicionar triggers PostgreSQL que rejeitem mutação. A proteção deve continuar eficaz se uma concessão DML indevida for reintroduzida em uma role ordinária.
- Corrigir o provisionamento para revogar privilégios anteriores excessivos, retirar defaults permissivos e conceder somente as operações necessárias por tabela. Reexecutar o provisionador deve ser idempotente e não reabrir mutações históricas. Roles de runtime configuradas devem ser reprovisionadas explicitamente; não presumir que qualquer role administrativa encontrada no catálogo seja runtime.
- Em `animals`, preservar identidade, proprietário, criação e atributos constitutivos. Permitir somente a atualização de versão necessária aos fluxos de identificação, removendo a reescrita redundante desses atributos no repositório. DELETE/TRUNCATE continuam proibidos. Testar a coerência da transição de versão, sem redesenhar o sistema de identificadores.
- Nas projeções e estados operacionais, conceder apenas as operações e colunas comprovadamente usadas. Essa exceção não autoriza mutar seus eventos-fonte nem reclassificar registros históricos como projeções por conveniência.
- Manter o contrato de idempotência e o trigger de conclusão existentes. Não introduzir TTL, retenção, novos grants interorganizacionais ou alterações de `core_messaging` neste achado.

Inventário de candidatos históricos, agrupado para revisão; a lista final da migration deve ser confrontada com os repositórios e testes, não inferida apenas pela ausência de métodos UPDATE:

| Fronteira | Tabelas |
|---|---|
| Eventos e integridade Core | `domain_events`, `domain_event_integrity`, `integrity_checkpoints`, `integrity_checkpoint_events`, `timestamp_attempts`, `timestamp_validations`, `temporal_anchors` |
| Provas e governança registrada | `evaluations`, `decisions`, `dossiers`, `recalls`, `evidence_verifications`, `attachments`, `decision_authority_profiles`, `decision_proposals`, `decision_reviews`, `decision_overrides`, `decision_contestations`, `rule_identities`, `rule_timeline_events`, `shared_policy_access_log` |
| Transporte e resultados históricos | `outbox_messages`, `outbox_publication_attempts`, `offline_operations`, `synchronization_results` |
| História Livestock | `animal_movements`, `animal_movement_items`, `animal_exits`, `reproductive_events`, `reproductive_event_offspring`, `treatment_applications`, `transformation_events`, `traceable_items` |
| Registros sanitários | `medications`, `medication_batches`, `prescriptions`, `prescription_targets`, `sanitary_campaigns`, `medication_classification_assertions`, `coverage_contributions` |
| Declarações e artefatos | `received_transfer_artifacts`, `imported_livestock_facts`, `establishment_qualifications`, `qualification_source_artifacts`, `establishment_qualification_assertions`, `property_environmental_embargo_assertions`, `external_source_capture_artifacts`, `external_source_capture_association_reviews`, `territorial_source_captures` |
| Auditoria das consultas | `market_supply_query_audit_records`, `ai_explanation_audit_records` |
| Cadastros ou versões sem edição implementada | `rural_properties`, `external_counterparties`, `property_geometries`, `internal_test_normative_bases`; não introduzir edição futura implícita |

Exceções que precisam de regras específicas, em vez de trigger irrestrito:

| Estruturas | Operação vigente a preservar |
|---|---|
| `animals`, `animal_identifiers` | Incremento de versão e projeção dos identificadores, com eventos registrados |
| `property_stays`, `reference_projection` | Reconstrução de projeção; somente estas e a projeção de identificadores têm exclusão identificada como necessária neste levantamento |
| `lot_memberships` | Encerramento de vínculo; campos constitutivos permanecem protegidos |
| `livestock_lots`, `veterinarians`, `entity_type_requests` | Estado cadastral/operacional ou decisão; respeitar ports existentes e limitar colunas |
| `idempotency_records`, `outbox_publication_state`, `synchronization_batches` | Conclusão, tentativas, lease e processamento |
| `authorization_grants`, `key_registry`, `nonconformities`, `shared_decisions` | Ciclo de vida existente; identidade e histórico não ganham permissão genérica de alteração |
| `policies`, `rules` | Distinguir rascunho de material publicado; não autorizar reescrita de conteúdo publicado |
| `relations`, `rule_adoptions` | Restringir a mutação ao contrato existente e conferir preservação de eventos/versionamento; não declarar a linha atual prova histórica imutável |
| `evidences` | Conflito central, resolvido na parte B; não é uma exceção permanente |

### Parte B — Evidence preservada e ciclo de vida registrado separadamente

Separar a Evidence original de registros append-only de assinatura, verificação e revogação, compondo a leitura do estado aplicável sem sobrescrever o registro original. Uma correção do conteúdo deve continuar gerando nova Evidence, como determina DOMAIN.md.

O desenho deve preservar os identificadores e respostas já consumidos. O contador de ciclo de vida hoje apresentado como `version` não pode ser silenciosamente confundido com uma nova versão do conteúdo. Sua correspondência com os registros novos e com a projeção de leitura deve ser explicitada e testada antes do BUILD dessa parte; esta ADR não aceita a violação apenas renomeando a tabela ou seu papel.

A migration deve preservar o estado legado conhecido, incluindo assinatura/revogação já existentes. História que nunca foi armazenada não pode ser reconstruída ou declarada comprovada. Novos registros exigem owner, vínculo verificável à Evidence, sequência/coerência temporal, autor quando aplicável e integridade transacional. Reutilizar os registros de verificação existentes; não duplicar essa capacidade.

Após adaptar leitura e escrita, `evidences` também recebe bloqueio integral de UPDATE/DELETE/TRUNCATE. Não remover campos REST, apagar registros existentes, criar política de retenção ou trocar o mecanismo criptográfico neste achado.

## Plano de implementação e critérios de aceite

1. A decisão foi aprovada pelo responsável pelo produto em 08/09/2026. Fechar a correspondência do ciclo de vida de Evidence antes de implementar a parte B. Executar partes A e B em sequência, com commits e verificação próprios quando houver aceite; registrar entregas efetivas exclusivamente no checklist.
2. Implementar grants/migrations/repositórios restritos às tabelas afetadas. Não modificar fronteiras do Core para importar conceitos Livestock; a aplicação de proteção das tabelas da vertical continua infraestrutura.
3. Testar por tabela e operação com role ordinária não owner/NOBYPASSRLS e contexto do tenant correto: INSERT/SELECT permitidos, mutação histórica negada, tenant alheio e contexto ausente negados.
4. Testar triggers separadamente com role ordinária dotada deliberadamente de DML. Caso contrário, um teste que para na ACL não demonstra que o trigger protege o histórico. TRUNCATE exige proteção própria, pois não é protegido por RLS.
5. Provar que reprovisionar uma role anteriormente permissiva retira concessões indevidas e que não há restauração por defaults, PUBLIC ou privilégios herdados relevantes.
6. Preservar anexação/desativação de identificadores, movimentação/reconstrução de permanências, encerramento de lote, idempotência, outbox, publicação de políticas e ciclo de vida de Evidence. Testar rollback para que falha de auditoria ou persistência não deixe atualização parcial.
7. Testar migration em banco descartável, com dados legados fictícios e conservação dos registros. Não fazer downgrade destrutivo de história criada após a migração; reversão de código não autoriza apagá-la.
8. Entregar roteiro executável em `apps/validacao` para os fluxos observáveis alterados, com descoberta de IDs, requisição/resposta, preflight e `--pausar`.
9. Executar em cada parte a suíte canônica completa: pytest, Ruff check, Ruff format check, Mypy e Alembic check. FINDING-002 só pode ser encerrado quando Evidence e demais registros históricos do escopo estiverem protegidos e os fluxos compatíveis aprovados.

## Limites da garantia

ACL, RLS e triggers protegem contra a role ordinária da aplicação e erros de DML, inclusive concessões DML excessivas testadas. Não tornam o banco inviolável contra superuser ou administrador que possa remover triggers, alterar ownership ou restaurar dados. Separação de papéis e controles administrativos permanecem necessários; assinatura/ancoragem externa não integra este achado.

Triggers rejeitam a operação e sua transação quando o erro não é tratado. Não existe promessa de uma exceção SQL universalmente impossível de capturar. Não incluir bypass genérico de runtime para facilitar testes ou migrations.

## Decisão registrada

A proteção por categoria e a separação do ciclo de vida de Evidence foram aprovadas em 08/09/2026. A aprovação autoriza as migrations e adaptações descritas, preservando a execução sequencial, os contratos públicos e os gates de verificação. FINDING-002 permanece aberto até a conclusão das partes A e B.
