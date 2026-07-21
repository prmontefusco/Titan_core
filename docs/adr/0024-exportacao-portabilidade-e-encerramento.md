# ADR 0024 — Exportação, portabilidade e encerramento
**Status:** Aceita  
**Data:** 21 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

Organizations, titulares e parceiros poderão solicitar exportações, portabilidade, migração ou encerramento de relação com o Titan. Esses pedidos não são equivalentes: uma exportação pode servir auditoria; uma portabilidade pode decorrer de direito ou contrato; uma migração pode transferir operação; o encerramento pode exigir retenção, devolução, bloqueio, descarte e preservação simultaneamente.

O Titan já distingue Authorization, DataContract, DataClassification, LicenseConstraint, VerificationBundle, DataLocationProfile, RetentionPolicy, LegalHold e disposição. Falta definir como avaliar escopo exportável, produzir pacote verificável, registrar entrega, tratar cópias externas e concluir offboarding sem apagar história ou manter acesso indevido.

A LGPD prevê portabilidade mediante requisição expressa, observada a regulamentação aplicável e segredos comercial e industrial. O Core registra o fundamento e o assessment, mas não presume que toda solicitação seja juridicamente exigível ou que todo dado seja portável.

## Problema

Definir:

- diferenças entre consulta, exportação, portabilidade, backup, Publication e VerificationBundle;
- quem pode solicitar, aprovar, gerar, receber e verificar;
- como delimitar dados próprios, compartilhados, de terceiros, derivados e licenciados;
- como preservar schema, Provenance, versões, Digests, relações e limitações;
- como evitar vazamento por arquivo, manifesto, metadado ou inferência;
- como retomar exportações grandes sem duplicar ou trocar conteúdo;
- como encerrar serviço, acessos, integrações, chaves e cópias;
- como comprovar entrega e reconciliar remanescentes sem prometer controle externo.

## Princípios

1. **Exportar é ação própria:** leitura não autoriza exportação, redistribuição ou portabilidade.
2. **Portabilidade não é exportação genérica:** finalidade, solicitante, fundamento, destinatário e escopo são avaliados.
3. **Componente por componente:** acesso ao envelope não concede acesso a todos os anexos.
4. **Formato aberto não remove semântica:** versões, unidades, relações, Provenance e limitações acompanham os dados.
5. **Entrega não transfere ownership automaticamente:** papéis, direitos e responsabilidades permanecem explícitos.
6. **Encerramento não é exclusão imediata:** retenção, LegalHold, incidentes e contratos podem exigir destinos diferentes.
7. **Cópia entregue sai do controle técnico:** revogação não apaga arquivo já recebido.
8. **Desconhecido permanece visível:** entrega, importação ou disposição incerta exige reconciliação.
9. **Sem aprisionamento artificial:** o Titan oferece contratos documentados e verificáveis dentro do escopo autorizado.

## Invariantes adicionais

- ExportAuthorization nunca é inferida de autorização de leitura;
- cada componente possui decisão individual de exportabilidade;
- ExportManifest descreve exatamente o conteúdo produzido;
- chunk retomado preserva identidade semântica e conteúdo;
- entrega confirmada não implica importação, leitura ou uso;
- portabilidade não altera RecordOwnerOrganization ou ownership histórico;
- offboarding não elimina objetos sob retenção, LegalHold ou auditoria;
- ExitInventory representa estado observado, não apenas pretendido;
- remanescente desconhecido impede encerramento completo.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Dump do banco | Simples e completo fisicamente | Expõe schemas, secrets, terceiros e estruturas internas |
| CSV universal | Amplo suporte | Perde relações, tipos, Provenance e Evidence |
| PDF como portabilidade | Legível | Não é interoperável nem preserva semântica completa |
| API apenas | Controle contínuo | Dependência do Titan e baixa preservação independente |
| Pacote versionado com manifesto | Verificável e importável | Exige perfis, adapters e compatibilidade |

## Decisão

Adotar fluxo:

`ExportRequest → ExportAssessment → ExportAuthorization → ExportOperation → ExportPackage → ExportDeliveryAssessment → ExportReconciliation`

Portabilidade acrescenta `PortabilityAssessment` e perfil próprio. Encerramento utiliza `OffboardingPlan`, `ExitInventory`, ações delimitadas e `OffboardingReconciliation`.

Os conceitos são candidatos arquiteturais e somente entram no `DOMAIN.md` após aprovação.

## Vocabulário

- `Export`: produção de cópia delimitada para destinatário e finalidade;
- `Portability`: transferência estruturada de dados autorizados para continuidade ou exercício de direito aplicável;
- `Migration`: mudança coordenada de sistema ou operador técnico;
- `Handover`: entrega formal de pacote, responsabilidade ou controle delimitado;
- `Offboarding`: encerramento coordenado da relação e das capacidades associadas;
- `Backup`: cópia para continuidade, não mecanismo de exportação ou portabilidade;
- `Publication`: disponibilização a audiência aprovada, não entrega privada;
- `VerificationBundle`: pacote de verificação, não dump ou pacote universal de migração.

## ExportRequest

Solicitação imutável com requester, capacidade, Organization, destinatário, Purpose, ExportScope, formato desejado, período, prazo, canal, fundamento alegado e IdempotencyKey.

Cliente não define livremente owner Organization, campos, autorização ou classificação. Solicitação repetida com identidade semântica diferente produz conflito.

## ExportScope

Escopo imutável de objetos e versões, Subjects, Organizations, período, campos, relações, Provenance, anexos, derivados, formatos, exclusões e redactions.

Escopo distingue:

- dados fornecidos pelo solicitante;
- dados observados ou produzidos pelo Titan;
- dados de outras Organizations ou titulares;
- inferências, scores, Decisions e explicações;
- conteúdo licenciado ou segredo protegido;
- material técnico interno, credenciais e controles defensivos.

Ausência de campo é negação. Expansão cria novo request e assessment.

## ExportAssessment

Avaliação imutável da possibilidade de exportar cada componente.

Preserva Authorization, ownership, Visibility, Purpose, FieldScope, DataContracts, DataClassifications, ProcessingActivities, papéis, LegalBasisReferences, ConsentRecords, LicenseConstraints, retenção, LegalHolds, localização, terceiros, segredo, riscos de inferência, redactions, formato e limitações.

Resultados: `AUTORIZAVEL`, `AUTORIZAVEL_COM_REDUCAO`, `REVISAO_NECESSARIA`, `NAO_AUTORIZAVEL`, `INDETERMINADA`.

Resultado parcial declara campos e componentes excluídos e motivos seguros. Não revela a existência de objeto invisível.

## PortabilityAssessment

Assessment separado sobre pedido de portabilidade para solicitante, destinatário, jurisdição, produto ou serviço, fundamento e instante delimitados.

Preserva identidade e autoridade do solicitante, relação com titulares e Organizations, categorias, dados portáveis e não portáveis, segredos, direitos de terceiros, interoperabilidade, segurança do destinatário, mecanismo de transferência, NormativeBasis, contratos, Evidence e limitações.

Resultados: `PORTABILIDADE_ATENDIVEL`, `ATENDIVEL_COM_RESTRICOES`, `INFORMACAO_ADICIONAL_NECESSARIA`, `REVISAO_JURIDICA_NECESSARIA`, `NAO_ATENDIVEL`, `INDETERMINADA`.

PortabilityAssessment técnico não é parecer jurídico. Dado anonimizado, derivado ou mantido não é incluído ou excluído apenas pelo nome; aplica-se avaliação concreta. Portabilidade exige interoperabilidade e preservação semântica, não identidade do container ou schema físico interno.

## ExportAuthorization

Autorização imutável que vincula request, assessments, ExportScope efetivo, destinatário, Purpose, formato, canal, prazo, volume, condições, aprovadores e revogação.

Preserva requester, recipient, ExportProfile, duração, limites de download, entregas, autenticação exigida e DataTransferAssessment. Authorization de leitura nunca é promovida implicitamente a ExportAuthorization.

Não substitui DataTransferAssessment quando houver transferência aplicável. Revogação impede novas operações controladas, mas não apaga pacote entregue.

## ExportProfile

Perfil versionado de formato e semântica:

Preserva identificador, versão, media types, schema, vocabulários, serialização, encoding, unidades, calendários, timezone, precisão, identificadores, relações, paginação, divisão, ordem, manifesto, Digests, assinatura, Provenance, redactions, lacunas, limitações, compatibilidade e importação de referência.

Mudança incompatível cria nova versão. Formato aberto não autoriza redistribuição nem remove LicenseConstraint.

## ExportOperation

Operação append-only, idempotente e correlacionada para gerar pacote conforme ExportAuthorization.

Estados: `PENDENTE`, `EM_GERACAO`, `GERADO`, `PARCIAL`, `FALHOU`, `RESULTADO_DESCONHECIDO`, `CANCELADO`, `EXPIRADO`.

Preserva snapshot de origem, versões, cursor, contagens, tentativas, executor, Digests, resultado e Evidence. Alteração concorrente não mistura versões silenciosamente; pacote usa snapshot consistente ou declara limitações.

Retry mantém identidade lógica. Resultado desconhecido não é tratado como pacote ausente ou entregue.

## ExportPackage

Artifact imutável com ExportManifest protegido e componentes autorizados.

Preserva PackageId, ExportManifest, PackageDigest, ExportChunks, compressão, criptografia e versões, ExportProfile, produced_at, producer e schema version. Não é sinônimo de arquivo: pode compreender manifesto, múltiplos arquivos, chunks, assinaturas e material de verificação.

O manifesto preserva:

PackageId, ExportProfile e versões; ExportScope e snapshot; inventário, tipos, tamanhos e Digests; relações, ordem e cobertura; omissões, redactions e reason codes; Provenance e fontes; DataClassifications e restrições; assinaturas, certificados ou checkpoints; instruções e test vectors.

Manifesto íntegro comprova consistência do pacote, não verdade material, confiança jurídica, completude universal ou direito de uso.

Secrets, chaves privadas, tokens, hashes previsíveis sensíveis, credenciais, configuração defensiva e dados fora do scope nunca integram o pacote.

## ExportManifest

Descrição canônica e imutável do ExportPackage, independente do container físico.

Preserva versão, PackageId, ExportScope, objetos, schemas, relationships, unidades, timezone, componentes, ManifestDigest, PackageDigest, ChunkDigests, redactions, LicenseConstraints, LicenseEvidence, warnings, lacunas e limitações.

ManifestDigest protege o manifesto; ChunkDigest protege cada parte; PackageDigest protege a composição lógica. Mudança de ZIP, transporte ou compressão não altera silenciosamente a identidade lógica.

## LicenseEvidence

Evidence versionada do direito ou restrição alegada para exportar e redistribuir conteúdo licenciado. Preserva LicenseConstraint, titular ou provider, Source, documento, vigência, escopo, Digest e limitações. Não cria licença nem amplia permissão por si só.

## ExportChunk

Parte imutável e retomável de exportação grande. Preserva PackageId, número ou range, identidade semântica, tamanho, ChunkDigest, tentativa, conclusão e limitações.

Retry não muda conteúdo. Alteração de scope, snapshot, ExportProfile ou manifesto cria nova identidade.

## ExportDeliveryAssessment

Assessment imutável da entrega a destinatário delimitado.

Resultados: `ENTREGA_COMPROVADA_NO_CANAL`, `ACEITACAO_PELO_CANAL`, `ENTREGA_PROVAVEL`, `ENTREGA_INDETERMINADA`, `FALHA_CONFIRMADA`.

Preserva pacote e Digest, canal, criptografia de transporte, destinatário, tentativas, receipts, instantes e limitações. Upload ou aceite do canal não comprova download, importação, leitura ou capacidade de uso.

Marcos: `PACOTE_CRIADO`, `PACOTE_DISPONIVEL`, `DOWNLOAD_INICIADO`, `DOWNLOAD_CONCLUIDO`, `CANAL_CONFIRMOU`, `ENTREGA_CONFIRMADA`, `ENTREGA_DESCONHECIDA`. Um marco não permite inferir o seguinte.

## ImportValidationReport

Relatório produzido por validador de referência ou implementação independente sobre estrutura, Digests, schema, compatibilidade, cobertura e limitações do ExportPackage.

Validação de importação não escreve no Domain nem confirma autorização do destinatário, verdade dos dados ou equivalência de negócio. Importação real exige caso de uso e assessments próprios.

## ImportAssessment

Assessment imutável da possibilidade de importar ExportPackage para destino, Purpose, Organization, contrato e versão delimitados.

Resultados: `IMPORTAVEL`, `IMPORTAVEL_COM_RESTRICOES`, `IMPORTACAO_PARCIAL`, `INCOMPATIVEL`, `REVISAO_NECESSARIA`, `INDETERMINADA`. Preserva compatibilidade, schemas, relações, unidades, Provenance, licenças, conflitos, redactions, Evidence e limitações. Exportação ou entrega não produz resultado positivo automaticamente.

## ExportReconciliation

Compara componentes esperados, gerados, entregues, falhos, omitidos e desconhecidos. Preserva package versions, receipts, conclusão, limitações, responsável e instante.

Exportação não é concluída apenas porque arquivo existe. Conclusões: `CONCLUIDA`, `CONCLUIDA_COM_RESTRICOES`, `PARCIAL`, `FALHOU`, `INDETERMINADA`.

## Cópias externas e revogação

ExportedCopyRecord registra pacote, destinatário, finalidade, entrega conhecida, restrições comunicadas, contrato, prazo alegado, revogação e limitações.

É registro de conhecimento, não controle remoto. O Titan pode bloquear novos downloads, revogar VerificationCode ou comunicar obrigação; não afirma apagar, recolher ou impedir uso de cópia externa.

## OffboardingPlan

Plano imutável e versionado de encerramento para Organization, contrato, produto ou integração delimitados.

Preserva motivo, autoridade, effective date, serviços, principals, Memberships, grants, ServiceIdentities, Devices, integrações, credentials, keys, domains, dados, packages, Publications, exports, jobs, messages, billing references não financeiras, DataContracts, retenções, LegalHolds, incidents, localizações, terceiros, dependências, sequência, rollback e limitações.

Encerramento não transfere RecordOwnerOrganization nem apaga dados automaticamente.

## ExitInventory

Inventário versionado dos itens esperados no offboarding e seu destino autorizado:

- `MANTER_RESTRITO`;
- `EXPORTAR`;
- `TRANSFERIR_CONTROLE`;
- `REVOGAR_ACESSO`;
- `DESATIVAR`;
- `DISPOR_APOS_AVALIACAO`;
- `PRESERVAR_POR_HOLD`;
- `REVISAR`.

Inclui dados ativos, backups, exports, VerificationBundles, logs, Audit, caches, offline, integrações, secrets, contas, tokens, webhooks, jobs, filas, replicações, Devices, keys, domains e subprocessadores. Inventário parcial não sustenta conclusão completa.

## OffboardingAssessment

Assessment imutável da viabilidade e restrições do OffboardingPlan. Considera exports pendentes, retenção, LegalHolds, incidentes, ações judiciais alegadas, ownership, contratos, terceiros, localização, dependências, remanescentes e desconhecidos.

Resultados: `EXECUTAVEL`, `EXECUTAVEL_COM_RESTRICOES`, `AGUARDANDO_DEPENDENCIAS`, `BLOQUEADO`, `INDETERMINADO`. Plano não garante encerramento possível.

## OffboardingDecision e ações

OffboardingDecision aprova plano, inventário, fases, autoridade, riscos, comunicação, dependências, exceções e critérios de conclusão.

Cada ação produz resultado próprio. Revogar acesso, suspender conta, exportar, transferir, bloquear, dispor e preservar não são uma operação única nem possuem a mesma reversibilidade.

OffboardingStage: `PLANEJADO`, `EM_EXECUCAO`, `AGUARDANDO_TERCEIROS`, `AGUARDANDO_RETENCAO`, `AGUARDANDO_HOLD`, `CONCLUIDO`, `CONCLUIDO_COM_REMANESCENTES`.

Credenciais e sessões são revogadas prospectivamente; histórico de Actor e Audit permanece. Chave de assinatura não exportável não é prometida como portátil. Material público necessário à verificação histórica permanece conforme retenção.

## HandoverRecord

Registro imutável de entrega de pacote, controle ou responsabilidade delimitada. Preserva origem, destinatário, escopo, Artifact, Digests, condições, autoridade, instantes, receipts, aceite e limitações.

Aceite não prova importação correta, assunção jurídica universal ou eliminação na origem.

## OffboardingReconciliation

Compara ExitInventory com exportações, handovers, revogações, desativações, holds, disposições, cópias externas, subprocessadores e resultados desconhecidos.

Conclusões: `CONCLUIDO`, `CONCLUIDO_COM_RESTRICOES`, `PARCIAL`, `BLOQUEADO`, `INDETERMINADO`.

LegalHold, retenção obrigatória, incidente aberto, exportação indeterminada ou terceiro não reconciliado permanece explícito. Encerramento comercial não é apresentado como eliminação total.

Remanescentes: `REMANESCENTE_AUTORIZADO`, `REMANESCENTE_OBRIGATORIO`, `REMANESCENTE_DESCONHECIDO`, `REMANESCENTE_EM_DISPOSICAO`. Desconhecido impede conclusão completa; conclusão com remanescentes exige fundamento e Evidence.

## Segurança e privacidade

Geração ocorre em ambiente temporário restrito, com menor privilégio, quotas, expiração, criptografia e acesso auditado. Arquivo não é enviado por canal diferente do autorizado.

Destinatário é validado sem usar email ou nome como identidade suficiente. Pacote grande usa partes autenticadas por manifesto; URL temporária é opaca, curta, revogável para novos acessos e não aparece em logs.

Redaction gera componente derivado com Provenance. Metadados, nomes de arquivo, contagens, erros e Digests também seguem FieldScope e análise de inferência.

## Fronteiras arquiteturais

Domain define requests, scopes, assessments, authorizations, packages, delivery, reconciliation e offboarding; não conhece ZIP, CSV, Parquet, S3, presigned URL, ferramenta ETL ou fornecedor.

Application resolve autorização, contrato, perfil, transferência, retenção e sequência. Infrastructure serializa, divide, cifra, entrega, valida, expira temporários e integra adapters. Presentation explica inclusões, exclusões e limitações.

## Testabilidade

Testes futuros devem cobrir:

- leitura reutilizada como exportação;
- objeto invisível revelado por manifesto, erro, contagem ou Digest;
- dados de outra Organization ou terceiro incluídos;
- LicenseConstraint ignorada;
- portabilidade tratada como dump integral;
- autorização parcial apresentada como pacote completo;
- ExportManifest divergindo dos componentes;
- chunk retomado produzindo conteúdo ou manifesto diferente;
- IdempotencyKey reutilizada com ExportScope distinto;
- snapshot misturando versões concorrentes;
- parte removida, duplicada ou substituída;
- package íntegro apresentado como verdade ou direito de uso;
- secret, token ou chave privada incluído;
- canal aceito apresentado como importação concluída;
- importação parcial apresentada como integral;
- retry gerando pacote semanticamente diferente sob mesma identidade;
- revogação apresentada como exclusão de cópia externa;
- término comercial eliminando dado sob LegalHold;
- conta encerrada mantendo sessões, grants ou ServiceIdentity;
- histórico de Actor removido com conta;
- chave não exportável prometida como portátil;
- backup, queue, Device ou subprocessador omitido do ExitInventory;
- token, webhook, key ou integração permanecendo ativa após conclusão;
- remanescente desconhecido tratado como inexistente;
- portabilidade alterando ownership histórico;
- offboarding parcial apresentado como concluído;
- importador independente incapaz de validar o pacote.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Saída verificável; menor lock-in; privacidade por componente; offboarding reconciliado |
| Negativas | Perfis e adapters; arquivos sensíveis; compatibilidade e inventário contínuos |

## Critérios de aceitação

A ADR pode ser aceita quando:

- exportação, portabilidade, migração, handover, backup e Publication forem distintos;
- cada componente passar por Authorization e assessment;
- formato preservar semântica, Provenance, versões e limitações;
- pacote possuir manifesto, Digests e validação independente;
- entrega não for confundida com importação ou leitura;
- cópia externa não for apresentada como controlável;
- offboarding separar exportação, revogação, hold, retenção e disposição;
- ExitInventory incluir dados e capacidades técnicas;
- histórico de Actor e Evidence sobreviver ao encerramento;
- conclusão exigir reconciliação e declarar restrições;
- nenhum formato, storage ou fornecedor seja escolhido.

## Referências

- ANPD, “Direito dos Titulares”: <https://www.gov.br/anpd/pt-br/assuntos/titular-de-dados-1/direito-dos-titulares>.
- Resolução CD/ANPD nº 19/2024, cláusulas-padrão e direitos aplicáveis a transferências: <https://www.gov.br/anpd/pt-br/acesso-a-informacao/institucional/atos-normativos/regulamentacoes_anpd/resolucao-cd-anpd-no-19-de-23-de-agosto-de-2024>.

Referências consultadas em 21 de julho de 2026. A implementação exige revisão da regulamentação vigente e do caso concreto.

## O que esta ADR não decide

Esta ADR não escolhe formato físico, storage, canal, ferramenta de migração, provedor ou prazo universal. Também não decide obrigação jurídica concreta, preço, condição comercial, transferência de propriedade, importador oficial ou procedimento físico de disposição.

## Plano de reversão

Antes da implementação, a proposta pode ser substituída. Depois da adoção, nova decisão preserva requests, assessments, authorizations, operations, packages, manifests, deliveries, reconciliations, copy records, plans, inventories, handovers e resultados históricos.

Reversão não apaga pacote entregue, amplia scope retroativamente, transforma encerramento em eliminação ou promete portabilidade de material não exportável.
