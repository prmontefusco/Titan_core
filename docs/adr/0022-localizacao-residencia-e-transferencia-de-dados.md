# ADR 0022 — Localização, residência e transferência de dados
**Status:** Aceita  
**Data:** 21 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan armazenará e processará dados em PostgreSQL, GridFS, backups, logs, observabilidade, dispositivos offline, integrações e exportações. A localização efetiva não se limita ao banco principal: suporte remoto, subprocessadores, recuperação de desastre, CDN, email, telemetria e cópias temporárias também podem movimentar ou tornar dados acessíveis em outras jurisdições.

DataClassification e DataContract já preservam localização e transferência como restrições. RetentionPolicy já exige inventário de cópias. Falta definir como declarar perfis, atribuir objetos, avaliar movimentos e comprovar a localização efetivamente observada.

No Brasil, a Resolução CD/ANPD nº 19/2024 regulamenta mecanismos de transferência internacional de dados pessoais. O Titan registra mecanismo, fundamento e Evidence aplicáveis, mas não conclui automaticamente validade jurídica de uma transferência.

## Problema

Definir:

- diferenças entre localização, residência, processamento, acesso e transferência;
- como expressar restrições por categoria, Organization, contrato e cliente;
- quais armazenamentos, cópias, serviços e operadores integram o inventário;
- como avaliar e autorizar transferência antes do movimento;
- como tratar replicação, backup, suporte, observabilidade e offline;
- como detectar, reconciliar e responder a localização desconhecida ou divergente;
- como trocar infraestrutura sem reescrever histórico ou regras de domínio.

## Princípios

1. **Localização é propriedade verificável:** região configurada não prova localização efetiva.
2. **Residência não é soberania universal:** estar em um país não resolve sozinho jurisdição, acesso ou conformidade.
3. **Acesso remoto pode ser transferência:** ausência de cópia persistente não elimina avaliação jurídica e contratual.
4. **Menor restrição prevalece:** perfil, classificação, contrato, Organization, titular, cliente e Policy compõem o limite efetivo.
5. **Movimento exige decisão prévia:** destino não é escolhido livremente por payload, operador ou fallback.
6. **Histórico permanece:** mudança de região cria novos registros; não altera onde o dado esteve.
7. **Desconhecido é restritivo:** localização não comprovada não é tratada como local permitido.
8. **Core não decide direito:** mecanismos jurídicos são referências versionadas sustentadas por Evidence.

## Invariantes

- localização configurada, declarada, observada e juridicamente avaliada são dimensões distintas;
- ausência de observação externa não comprova residência local quando a cobertura for incompleta;
- autorização de backup não autoriza restore, processamento, teste ou suporte em qualquer região;
- mudança de perfil produz efeitos prospectivos e não altera localizações históricas;
- derivados com múltiplas origens não recebem perfil menos restritivo sem assessment explícito;
- acesso remoto, administração e controle de chaves são avaliados mesmo sem cópia persistente conhecida;
- região comercial do provider não é jurisdição canônica e exige tradução versionada;
- movimento técnico concluído não comprova mecanismo jurídico válido, e mecanismo registrado não comprova execução conforme suas condições;
- localização desconhecida, inventário incompleto ou Evidence vencida não são convertidos em localização permitida.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Fixar toda a plataforma no Brasil | Regra simples | Pode impedir clientes e recuperação legítima; não cobre suporte e terceiros |
| Confiar na região do provedor | Baixo esforço | Não inventaria réplicas, logs, acessos ou subprocessadores |
| Configuração por serviço | Flexível | Regras ficam dispersas e sem explicação histórica |
| Perfil versionado e avaliação por movimento | Auditável e substituível | Exige inventário, reconciliação e Evidence |

## Decisão

Adotar `DataLocationProfile` versionado, atribuído por `DataLocationAssignment` a objetos ou conjuntos delimitados. Toda transferência ou novo acesso transfronteiriço relevante exige `DataTransferAssessment` antes da autorização técnica.

`DataLocationInventory` registra onde cada categoria pode estar e onde foi observada. `DataMovementRecord` preserva movimentos efetivos ou tentados. Configuração, intenção, observação e conclusão jurídica permanecem dimensões distintas.

Os conceitos são candidatos arquiteturais e somente entram no `DOMAIN.md` após aprovação.

## Vocabulário

- `DataLocation`: local físico ou lógico observado de armazenamento, processamento, trânsito, acesso ou administração;
- `DataResidency`: requisito de manter determinada categoria dentro de fronteira geográfica declarada;
- `DataProcessingLocation`: local em que operação de tratamento é executada;
- `DataAccessLocation`: local conhecido ou estimado do Actor, ServiceIdentity, suporte ou operador que acessa;
- `InternationalDataTransfer`: movimento ou disponibilização que se enquadra no perfil jurídico aplicável;
- `DataSovereignty`: conjunto de efeitos jurídicos alegados para jurisdição e contexto, nunca inferido apenas da região.

Esses termos não são intercambiáveis. Região de cloud não prova local do suporte, controlador, subprocessador ou chave.

## DataLocationProfile

Perfil imutável e versionado que define:

- jurisdições e regiões permitidas para armazenamento, processamento, backup, recuperação, suporte e chaves;
- categorias, IdentifiabilityLevel e DataSensitivity aplicáveis;
- ProcessingActivities, Purposes, DataContracts e Organizations;
- movimentos, acessos remotos e subprocessadores permitidos;
- mecanismos jurídicos e aprovações exigidos;
- criptografia, segregação, logging e Evidence;
- comportamento de fallback, indisponibilidade e localização desconhecida;
- validade, revisão e limitações.

Categorias iniciais de configuração, sem conclusão jurídica automática:

- `SOMENTE_BRASIL`;
- `BRASIL_PRIMARIO`;
- `TRANSFERENCIA_INTERNACIONAL_DELIMITADA`;
- `DEFINIDO_POR_CLIENTE`;
- `PUBLICO_NAO_PESSOAL`.

O código resume configuração; perfil e versão contêm a regra completa. `PUBLICO_NAO_PESSOAL` não elimina licença, segredo, contrato ou restrição de infraestrutura.

## DataLocationAssignment

Vínculo imutável entre objeto ou DispositionScope, DataClassification e DataLocationProfile.

Preserva owner Organization, ProcessingActivity, DataContract, período, herança para derivados, exceções, aprovação e limitações. Derivação, cópia, indexação, embedding, exportação ou backup não removem a atribuição automaticamente.

Conflitos entre assignments produzem assessment; não são resolvidos escolhendo a regra mais conveniente. Na ausência de resolução, aplica-se a restrição mais conservadora ou bloqueio conforme Policy.

Derivado com múltiplas origens compõe todos os assignments aplicáveis. Redução de restrição exige assessment, fundamento, Evidence e aprovação; não decorre de agregação, transformação ou escolha do perfil mais permissivo.

## JurisdictionMappingVersion

Tradução imutável e versionada entre região, zona ou localização declarada pelo provider e jurisdição canônica utilizada pelo Titan.

Preserva provider, identificador nativo, jurisdição resultante, fontes, vigência, método, Evidence, aprovação e limitações. Região desconhecida ou sem mapping vigente permanece `LOCALIZACAO_DESCONHECIDA`.

## DataLocationInventory

Inventário versionado de locais e fluxos esperados e observados.

Inclui, quando aplicável:

- PostgreSQL, GridFS e object storage;
- réplicas, snapshots, backups e disaster recovery;
- cache, busca, analytics e vector store;
- Message Broker, Inbox, Outbox e quarentena;
- logs, traces, métricas, error tracking e SIEM;
- email, CDN, arquivos temporários e exports;
- dispositivos offline e ferramentas de suporte;
- subprocessadores, integrações e ambientes de teste;
- chaves, escrow e material de recuperação.

Cada entrada preserva serviço, finalidade, categorias, região configurada, região observada, provider, subprocessadores, método de descoberta, última verificação, ConfidenceAssessment, retenção e Evidence.

Inventário vazio ou desatualizado não prova ausência de cópias.

O inventário declara fronteira de cobertura, fontes esperadas e examinadas, lacunas, freshness e última reconciliação. Inventário parcial nunca é apresentado como completo nem sustenta, isoladamente, residência comprovada.

## DataTransferAssessment

Assessment imutável anterior à autorização de uma transferência ou acesso transfronteiriço delimitado.

Preserva origem, destino, categorias, titulares, volume, Purpose, ProcessingActivity, DataProcessingRoleAssignments, DataContract, fornecedor, subprocessadores, DataLocationProfiles, classificação, retenção, segurança, mecanismo jurídico referenciado, NormativeBasis, aprovações, riscos, medidas, validade e Evidence.

Resultados iniciais:

- `AUTORIZAVEL`;
- `AUTORIZAVEL_COM_RESTRICOES`;
- `REVISAO_JURIDICA_NECESSARIA`;
- `NAO_AUTORIZAVEL`;
- `INDETERMINADA`.

Resultado técnico não é parecer jurídico. Mudança de destino, finalidade, categoria, provider, subprocessador, contrato ou mecanismo exige nova avaliação.

## TransferAuthorization

Autorização imutável para movimento específico ou classe estritamente delimitada de movimentos, produzida após DataTransferAssessment adequada.

Preserva assessment, autoridade, origem, destino, campos, Purpose, volume, prazo, condições, mecanismo, aprovações e revogação. Não substitui Authorization de acesso, LegalBasis ou ConsentRecord.

Autorização parcial reduz o movimento e declara a redução. Destino ausente é negação. Revogação impede novos movimentos controlados, mas não apaga cópias já transferidas.

## DataMovementRecord

Registro append-only de movimento tentado, iniciado, concluído, parcial, negado ou desconhecido.

Preserva TransferAuthorization, origem e destino observados, objetos e versões, campos, contagens, Digests, transportador, ServiceIdentity, instantes, resultado, receipt, correlação, Evidence e limitações.

Confirmação de transporte não comprova persistência, processamento, disponibilidade ao destinatário ou descarte na origem. Resultado desconhecido exige reconciliação e não é convertido em falha ou sucesso.

## Mecanismo de transferência

`TransferMechanismReference` identifica mecanismo jurídico ou contratual versionado alegado para o movimento, jurisdição, período, partes, documento, Source, Digest, aprovação e Evidence.

O Titan pode registrar decisão de adequação, cláusulas-padrão, cláusulas específicas, normas corporativas globais ou outro mecanismo previsto no perfil, sem concluir automaticamente validade, suficiência ou aplicabilidade.

Coincidência de texto, assinatura ou contrato não substitui análise de partes, escopo, vigência e operação concreta. Alteração normativa inicia revisão e impacto; não invalida movimentos históricos automaticamente.

## Acesso remoto e suporte

Acesso administrativo, suporte, investigação, observabilidade ou manutenção é avaliado por local do acesso, dados visíveis, finalidade, capacidade e sessão privilegiada.

VPN, VDI, mascaramento ou ausência de download podem reduzir risco, mas não removem automaticamente a transferência. SupportAccessSession registra Actor, ServiceIdentity, Organization, localização, Purpose, ticket, escopo, campos, prazo, aprovação e DataAccessRecords.

SupportAccessSession depende de AuthorizationGrant, PrivilegedAccessSession e TransferAuthorization aplicáveis. Sede da empresa prestadora não substitui localização observada ou declarada do operador.

Localização do operador desconhecida bloqueia acesso quando o perfil exigir comprovação. Emergência não cria bypass genérico; segue procedimento, autoridade, prazo e auditoria próprios.

## Backup, recuperação e continuidade

Região secundária e disaster recovery integram DataLocationProfile antes da replicação. Indisponibilidade da região primária não autoriza fallback para destino proibido. Restore é DataMovement próprio e exige destino, finalidade e autorização compatíveis.

Restore preserva assignments e bloqueia reintrodução em destino incompatível. Teste de recuperação usa dados sintéticos ou escopo autorizado e também integra o inventário.

Backups permanecem sujeitos a classificação, localização, retenção, acesso e reconciliação. Imutabilidade de backup não transforma armazenamento não autorizado em permitido.

## Chaves e criptografia

DataLocationProfile distingue localização dos dados, chave, provider criptográfico, backup da chave e operadores autorizados.

Criptografia não elimina localização, transferência ou acesso. Chave mantida no Brasil não torna automaticamente cópia estrangeira uma cópia brasileira; chave estrangeira pode criar dependência e acesso adicionais.

## Observação e reconciliação

`DataLocationObservation` registra localização observada, fonte, método, instante, cobertura, ConfidenceAssessment, Evidence e limitações.

Fontes podem incluir configuração assinada, inventário do provider, logs confiáveis, attestation, contrato ou inspeção. Declaração do provider é Evidence, não prova absoluta.

`DataLocationReconciliation` compara assignments, inventário esperado, observações e movements. Resultados: `CONFORME_PERFIL`, `DIVERGENTE`, `INCOMPLETA`, `LOCALIZACAO_DESCONHECIDA`, `EM_REMEDIACAO`.

Divergência não move ou apaga dados automaticamente. Pode bloquear novos acessos e movimentos, iniciar incidente, preservar Evidence e exigir autoridade para remediação.

## Data Contracts e derivados

DataContract declara produtores, consumidores, campos, transformações, localizações, transferências, subprocessadores, retenção e redistribuição.

OCR, IA, embedding, cache, índice, relatório, Dossier, VerificationBundle e Publication herdam restrições conforme ClassificationPropagation. Agregação ou anonimização somente muda perfil após assessment e Evidence; pseudonimização continua sendo dado pessoal quando reidentificável.

## Fronteiras arquiteturais

Domain define perfis, assignments, assessments, autorizações, movements, observações e reconciliações; não conhece AWS, Azure, GCP, região comercial, Terraform ou SDK.

Application resolve a restrição efetiva, coordena assessments e autoriza movimentos. Infrastructure aplica regiões, rotas, storage policies, chaves, inventário e Evidence. Presentation informa escopo e limitações sem expor topologia sensível.

## Testabilidade

Testes futuros devem cobrir:

- região configurada divergente da observada;
- região configurada apresentada como localização comprovada;
- log, backup, email ou suporte fora do inventário;
- backup existente fora do perfil ou usado em ambiente de teste;
- fallback automático para região proibida;
- restore realizado em região não autorizada;
- acesso remoto tratado como não transferência apenas por ausência de download;
- suporte autorizado pela sede, sem localização do operador;
- TransferAuthorization reutilizada para destino, Purpose ou subprocessador diferente;
- subprocessador novo herdando aprovação anterior;
- autorização parcial apresentada como integral;
- localização desconhecida tratada como permitida;
- dado derivado perdendo assignment;
- derivado com múltiplas origens recebendo perfil mais permissivo;
- restore reintroduzindo dado em local incompatível;
- criptografia apresentada como ausência de transferência;
- chave administrada em região incompatível;
- cópia pública apresentada como livre de licença ou contrato;
- movimento concluído sem receipt ou com resultado desconhecido;
- revogação apresentada como apagamento no destinatário;
- inventário desatualizado apresentado como universo completo;
- inventário parcial apresentado como completo;
- dispositivo offline, cache, CDN, email, log ou trace fora da jurisdição omitido;
- região do provider traduzida sem JurisdictionMappingVersion e Evidence;
- mecanismo jurídico vencido ou fora do escopo reutilizado;
- mecanismo registrado apresentado como validade jurídica concluída;
- exportação entregue apresentada como ainda controlável pelo Titan;
- mudança normativa invalidando movimento histórico automaticamente.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Regras substituíveis; inventário auditável; transfers explicáveis; cloud não contamina Domain |
| Negativas | Descoberta contínua; reconciliação; revisão jurídica; maior complexidade de suporte e DR |

## Critérios de aceitação

A ADR pode ser aceita quando:

- localização, residência, processamento, acesso e transferência permanecerem distintos;
- DataLocationProfile não estiver amarrado a fornecedor;
- assignments acompanharem cópias e derivados;
- inventário incluir dados fora do banco principal;
- transferência exigir assessment e autorização delimitados;
- mecanismo jurídico permanecer referência versionada, não conclusão automática;
- localização desconhecida falhar de forma restritiva;
- acesso remoto e suporte integrarem avaliação;
- backup, restore, DR, observabilidade e chaves forem considerados;
- movimento preservar resultado parcial e desconhecido;
- divergência produzir reconciliação e Evidence;
- mudança posterior não reescrever localização histórica;
- nenhuma região, cloud ou prazo universal seja escolhido.

## Referências normativas

- ANPD, “Transferência Internacional de Dados”: <https://www.gov.br/anpd/pt-br/assuntos/assuntos-internacionais/transferencia-internacional-de-dados>.
- Resolução CD/ANPD nº 19, de 23 de agosto de 2024, com indicação de retificação posterior no texto oficial: <https://www.gov.br/anpd/pt-br/acesso-a-informacao/institucional/atos-normativos/regulamentacoes_anpd/resolucao-cd-anpd-no-19-de-23-de-agosto-de-2024>.

As referências registram o contexto consultado em 21 de julho de 2026. Implementação e operação exigem revisão jurídica da versão vigente e da situação concreta.

## O que esta ADR não decide

Esta ADR não escolhe:

- cloud, datacenter, região, CDN, email ou ferramenta de observabilidade;
- mecanismo jurídico aplicável a uma transferência concreta;
- papel jurídico de cada Organization ou fornecedor;
- topologia, IaC, bucket, tabela ou política física;
- prazo universal, país adequado ou residência obrigatória para todo dado;
- procedimento completo de incidente ou offboarding.

## Plano de reversão

Antes da implementação, esta proposta pode ser substituída. Depois da adoção, nova decisão preserva DataLocationProfiles, assignments, inventories, assessments, TransferAuthorizations, movements, mechanism references, observations, reconciliations e Evidence histórica.

Reversão não altera onde dado esteve, converte localização desconhecida em permitida, apaga transferência anterior ou transforma configuração em prova de conformidade.
