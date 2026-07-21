# ADR 0013 — Classificação e ciclo de vida de dados
**Status:** Aceita  
**Data:** 21 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan preserva histórico auditável e pode processar dados pessoais, sensíveis, sigilosos, técnicos e públicos em registros, Evidences, Documents, Events, mensagens, offline, relatórios e exportações. Imutabilidade não autoriza retenção ilimitada; descarte também não apaga silenciosamente a evidência da operação.

RecordOwnerOrganization não define papel jurídico de tratamento. Métricas sociais, denúncias, saúde, força de trabalho e comunidades dependem desta decisão.

## Problema

Definir:

- classificação, avaliação e fronteira entre atributos e registros;
- propagação, contratos, minimização e canais técnicos;
- pseudonimização, anonimização, papéis, impacto, histórico e descarte.

## Princípios

1. **Classificar, minimizar e referenciar:** dado desconhecido é restrito; registro usa referência opaca; pseudônimo permanece protegido.
2. **Anonimização e histórico contextuais:** meios razoáveis são avaliados; imutabilidade vale durante retenção; prova do descarte não contém o dado.
3. **Proteção propagada e falha fechada:** derivação mantém restrições; ownership não define papel jurídico; vault, tecnologia e prazo exigem decisões próprias.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Dados pessoais em cada agregado | Simplicidade local | Replicação, descarte e autorização inconsistentes |
| Vault central decidido agora | Separação aparente | Alto acoplamento, concentração de risco e tecnologia prematura |
| Nunca eliminar | Histórico máximo | Retenção indevida e incompatibilidade com ciclo de vida |
| Apagar registros completos | Descarte simples | Destrói Provenance, integridade e relações |
| Referências opacas e payload separável | Minimização e descarte controlado | Exige inventário, resolução autorizada e reconciliação |

## Decisão

Adotar classificação multidimensional, propagada e versionada, combinada com referências opacas a atributos pessoais mantidos em fronteira protegida.

Registros não são alterados ou descartados silenciosamente durante retenção aplicável. Conteúdo pessoal separável pode ser bloqueado, anonimizado ou eliminado por processo autorizado, preservando envelope histórico mínimo e não identificável da operação.

Esta ADR define contratos e invariantes, não mecanismo físico. `IdentityVault`, schema, banco, criptografia, prazos, localização e fluxos jurídicos concretos permanecem para decisões posteriores.

Os conceitos são candidatos arquiteturais e dependem de aprovação no `DOMAIN.md`.

## DataClassification

Classificação versionada aplicada a elemento, campo, payload, Artifact, registro ou conjunto de dados.

Preserva IdentifiabilityLevel, DataSensitivity, categoria, titular, finalidade, ProcessingContext, jurisdição, papéis, compartilhamento, audiência, retenção, legal hold, localização, transferência, proteção, logging, exportação, derivação, agregação, fonte, versão, aprovação e limitações.

Classificação não é string livre. Mudança cria versão, Actor, justificativa, Evidence e análise de impacto.

## ClassificationAssessment

Avaliação imutável que registra DataClassification, ClassificationOrigin, ClassificationConfidence, Evidence, método, assessor, instante, revisão prevista e limitações.

ClassificationOrigin distingue `MANUAL`, `AUTOMATICA`, `INFERIDA`, `IMPORTADA`, `HERDADA`, `PROVISORIA`. ClassificationConfidence distingue `CONFIRMADA`, `PROVAVEL`, `INCERTA`, `DESCONHECIDA` sem produzir score universal.

Incerteza nunca reduz proteção. Resultado automático, importado ou inferido preserva origem e revisão exigida.

## ClassificationPropagation

Lineage imutável entre objeto de origem e derivado, contendo classificações, regra versionada, transformação, resultado, justificativa, responsável, revisão e limitações.

Toda derivação relevante registra propagação. Redução exige Policy e aprovação; regra ausente aplica proteção mais restritiva ou revisão. Mudança posterior da regra não reclassifica histórico silenciosamente.

## IdentifiabilityLevel

Nível de associação a pessoa natural: `DIRETAMENTE_IDENTIFICAVEL`, `PSEUDONIMIZADO`, `ANONIMIZADO`, `AGREGADO`.

Pseudonimização mantém dado pessoal quando informação adicional ou correlação permite associação. Agregação não implica anonimização. Classificação pode ser elevada quando contexto ou meios razoáveis alterarem o risco.

Redução para `ANONIMIZADO` exige AnonymizationAssessment aprovada; remoção de nome, hash previsível, troca de identificador ou restrição de acesso não bastam.

## DataSensitivity

Sensibilidade e IdentifiabilityLevel são dimensões independentes.

Categorias iniciais: `PUBLICO`, `INTERNO`, `CONFIDENCIAL`, `RESTRITO`, `DADO_PESSOAL`, `DADO_PESSOAL_SENSIVEL`, `SEGREDO_TECNICO`, `CREDENCIAL`, `MATERIAL_CRIPTOGRAFICO`.

Categoria pública não elimina licença, integridade, finalidade ou restrição jurídica. Credencial e material criptográfico não entram no Domain, Events, Outbox, logs ou auditoria.

## DataSubjectReference

Referência opaca, tipada e estável à pessoa natural relacionada ao tratamento.

Não contém nome, documento, e-mail, telefone, endereço ou atributo diretamente identificável.

## PersonalDataReference

Referência tipada para conjunto ou atributo pessoal mantido em fronteira protegida.

Resolução exige OrganizationContext, Permission, finalidade, ProcessingContext, DataProcessingRole e auditoria. A referência não concede Visibility nem comprova existência ao solicitante.

Implementação física da fronteira não integra este contrato.

## ProcessingContext

Contexto imutável para operação de tratamento.

Identifica finalidade, operação, Organization atuante, DataProcessingRoles, fundamento ou Policy, período, DataClassifications, titulares ou categorias, destinatários, audiência, restrições, autorização, correlação e instante.

Finalidade fornecida pelo cliente é solicitação não confiável e deve ser validada pelo servidor.

DataClassification, LegalBasisReference, ConsentRecord e AuthorizationGrant são conceitos distintos. Dado pessoal não implica consentimento. LegalBasisReference aponta para NormativeBasis, dispositivo, jurisdição, finalidade, período, interpretação, Evidence e limitações; não é string livre.

ConsentRecord registra manifestação quando o consentimento for a base aplicável, sem substituir fundamento, Authorization ou ProcessingActivity. Seu ciclo completo depende de ADR própria.

## ProcessingActivity

Registro versionado da atividade de tratamento, contendo identidade, propósito, operações, LegalBasisReferences, DataProcessingRoleAssignments, categorias de dados e titulares, Sources, destinatários, DataContracts, transferências, retenção referenciada, segurança, sistemas, estado, validade e aprovação.

Cada categoria liga-se a propósito e fundamento. Mudança de finalidade exige avaliação. Destinatário listado não recebe acesso; registro não substitui Authorization. Tratamento protegido sem atividade aplicável falha conforme Policy, e execução deve ser reconciliável com o registro.

## DataProcessingRole

Papel contextual e declarado exercido por Organization em tratamento específico.

Pode representar controlador, operador ou outra capacidade reconhecida por perfil aplicável. A mesma Organization pode exercer papéis diferentes em operações distintas.

RecordOwnerOrganization, Issuer, local de armazenamento, contrato técnico ou posse dos bytes não determinam automaticamente DataProcessingRole. Reconhecimento jurídico exige NormativeBasis, Evidence e revisão apropriadas.

DataProcessingRole é tipo controlado por perfil jurisdicional, como `CONTROLADOR`, `CONTROLADOR_CONJUNTO`, `OPERADOR` ou `SUBOPERADOR`.

DataProcessingRoleAssignment vincula Organization, papel, ProcessingActivity, jurisdição, período, finalidade, contrato ou NormativeBasis, Evidence, aprovação e limitações. Registra qualificação declarada, não conclusão jurídica definitiva.

## DataContract

Contrato lógico versionado de intercâmbio, contendo produtor, consumidores, schema ou payload, campos permitidos e proibidos, DataClassifications, regras de propagação, propósitos, LegalBasisReferences, DataProcessingRoleAssignments, transformações, retenção, localização, publicação, descarte, incidentes, compatibilidade e validade.

DataContract restringe o fluxo, mas não concede acesso nem substitui ProcessingActivity, AuthorizationGrant ou Authorization. Cliente não o escolhe livremente; campo, finalidade, consumidor ou transformação incompatível bloqueiam produção ou consumo. Mudança incompatível cria versão e revogação impede novos fluxos sem apagar histórico.

## Fronteira de atributos pessoais

O modelo conceitual é:

```text
registro operacional
    ↓ DataSubjectReference / PersonalDataReference
fronteira protegida de atributos pessoais
```

Registro operacional preserva Actor ou referência interna necessária, não replica nome, documento, contato ou endereço. Exceção exige finalidade, DataClassification, necessidade, autorização, retenção e teste explícitos.

A fronteira aplica menor privilégio, criptografia proporcional, acesso auditado, inventário, backup, recuperação, bloqueio e descarte. Isso não decide produto ou topologia.

## Propagação da classificação

DataClassification acompanha bancos, object storage, caches, projeções, backups, Events, Evidences, Documents, Artifacts, mensagens, observabilidade, analytics, Dossiers, VerificationBundles, relatórios, exportações, dispositivos, offline e integrações.

Transformação mantém ou eleva restrição por padrão. Redução exige operação aprovada, Evidence e avaliação do resultado. Classificação composta respeita o componente mais restritivo, salvo regra de composição formal.

Derivação preserva Provenance para localizar fontes e cópias. Ausência de propagação bloqueia persistência, publicação ou transmissão.

OCR, visão, modelo estatístico ou de linguagem, embedding, vetor, índice, feature, dataset, prompt, saída, cache ou model artifact não removem classificação, papel, finalidade, licença ou restrição. Policy considera reconstrução, memorização e inferência; provider, localização, retenção e uso para treinamento integram ProcessingActivity e DataContract.

## Canais técnicos

Payload usa identificadores opacos, finalidade técnica e referências autorizáveis com dados mínimos.

Nome, documento, contato, endereço, biometria, saúde, credencial ou conteúdo integral de Document não são copiados por padrão.

Exceção exige contrato versionado, classificação, necessidade, criptografia, consumidores delimitados, retenção e teste. Message Broker não se torna repositório de dados pessoais.

Inbox, quarentena, dead-letter e replay preservam classificação e não estendem retenção silenciosamente.

Observabilidade usa IDs opacos, correlação, códigos, categoria, resultado e razão segura.

Payload, token, secret, documento e atributo pessoal não são registrados por padrão. Redaction posterior não substitui prevenção na origem.

Debug privilegiado exige finalidade, prazo, ambiente, aprovação, acesso e descarte próprios. Métricas evitam labels com alta cardinalidade ou identificadores pessoais.

Dado pessoal offline exige finalidade permitida, minimização, proteção local, prazo operacional, inventário, bloqueio, sincronização segura e descarte após confirmação conforme Policy.

OfflineOperation não contém Access Token, Refresh Token ou credencial. Sincronização revalida identidade, Membership ou AuthorizationGrant, Permission, Organization, finalidade, DataClassification, Policy, versão, conflito e revogação.

Perda, roubo ou comprometimento do Device inicia resposta a incidente e análise de dados potencialmente expostos.

## AnonymizationAssessment

Avaliação imutável da alegação de anonimização para conjunto, finalidade, contexto e instante definidos.

Preserva técnica, informação adicional existente, separação e acesso, meios razoáveis, adversários considerados, singularização, ligação, inferência, amostragem, validação, responsável, aprovação, limitações e necessidade de reavaliação.

Anonimização é contextual. Novo dado, técnica ou capacidade de correlação pode exigir reclassificação e não reescreve a avaliação histórica.

## PrivacyImpactAssessment

Avaliação versionada para ProcessingActivity, gatilho, escopo, método, dados e titulares, necessidade, proporcionalidade, riscos, controles, risco residual, opiniões divergentes, revisor, aprovação, revisão prevista e limitações.

É preparada antes do tratamento de alto risco quando aplicável e revista após mudança relevante. Aprovação não prova conformidade. Somente perfil jurídico específico pode apresentá-la como RIPD; versões interna e pública podem possuir escopos distintos.

## Histórico, bloqueio e disposição

O modelo separa:

```text
envelope histórico mínimo
+ payload pessoal separável
```

O envelope pode preservar identificador opaco, tipo da operação, Actor autorizado quando permitido, instante, finalidade, política aplicada, resultado, correlação e Digest não reversível apropriado. Não preserva conteúdo descartado ou hash previsível que permita descoberta.

EncryptionKey, Data, Digest e Evidence são distintos. Destruição de chave não elimina cópia em claro; rotação não muda classificação; recuperação não restaura autorização. Crypto-shredding exige chave exclusiva e considera backup, escrow e cópias. O evento comprova o procedimento inventariado, não inexistência absoluta do dado.

Disposição valida solicitação, Actor, contexto, finalidade, retenção, legal hold e impedimentos; localiza cópias por Provenance; bloqueia concorrência; executa ação; atualiza derivados; registra evento mínimo, relatório, reconciliação e exceções.

Eventos candidatos: `DADO_PESSOAL_BLOQUEADO`, `DADO_PESSOAL_CORRIGIDO`, `DADO_PESSOAL_ELIMINADO`, `DADO_PESSOAL_ANONIMIZADO`, `CHAVE_DE_DADOS_DESTRUIDA`, `RETENCAO_ENCERRADA`, `LEGAL_HOLD_APLICADO`, `LEGAL_HOLD_LIBERADO`.

Evento de disposição nunca contém o dado eliminado, valor anterior recuperável ou segredo usado para reconstruí-lo.

Correção usa Correction: original permanece no histórico durante retenção aplicável, CurrentProjection aponta para o corrigido e Decisions ou Dossiers dependentes tornam-se potencialmente afetados. Quando eliminação do valor anterior for exigida, somente envelope mínimo da correção permanece.

## Backups, restauração e falhas seguras

Eliminação instantânea de toda cópia de backup não é presumida. Backups são inventariados, protegidos, versionados e submetidos a retenção e acesso próprios.

Restore reaplica bloqueios, disposições e restrições antes de liberar uso operacional. Dado eliminado que reapareça durante recuperação não pode voltar ao processamento ordinário.

Expiração de backup é previsível e auditável. Cópia expirada não é conservada por conveniência. Evidência de destruição comprova procedimento nos locais inventariados, não inexistência absoluta de cópia desconhecida.

Classificação ausente, conflitante, expirada ou indeterminada produz bloqueio, tratamento temporário mais restritivo ou revisão obrigatória conforme Policy.

Cliente, payload, integração ou Source não reduz classificação. Erro de classificação é auditado e pode iniciar análise de impacto.

Exportação, Publication, Sharing, cálculo, indexação, logging ou transmissão falham fechados quando restrições não puderem ser determinadas.

## Sustentabilidade e agregação

Métricas sociais e dados sobre pessoas ou comunidades aplicam DataClassification antes de coleta, Calculation, DataQualityAssessment, agregação, SustainabilityDisclosure e Publication.

Agregação considera risco de singularização, ligação e inferência. Pequenos grupos, outliers e combinações de dimensões podem exigir supressão, generalização, ruído ou acesso restrito conforme perfil aprovado.

Lacuna causada por privacidade permanece explicada sem revelar o conteúdo protegido. DataQualityAssessment não autoriza exposição para melhorar completude.

DataMinimizationAssessment é capacidade futura multidimensional para campos desnecessários, duplicação, coleta excessiva, classificação ausente, finalidade incompatível, retenção e risco; o Core não produz score universal.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Minimização; referências opacas; descarte controlável; classificação propagada; base para privacidade e sustentabilidade |
| Negativas | Inventário e reconciliação; resolução autorizada; testes por canal; complexidade de backup e anonimização |

## Riscos e controles

| Risco | Controle |
|---|---|
| Vault prematuro | Contrato lógico sem tecnologia física |
| Pseudônimo tratado como anônimo | IdentifiabilityLevel e AnonymizationAssessment |
| PII replicada em mensagens | Referência opaca, minimização e teste de contrato |
| Log revelar conteúdo | Logging seguro na origem e debug controlado |
| Descarte destruir auditoria | Envelope mínimo sem payload pessoal |
| Restore ressuscitar dado | Reaplicação de disposição antes do uso |
| Agregado reidentificar pessoa | Avaliação contextual e controles de inferência |
| Ownership definir papel jurídico | DataProcessingRole contextual e Evidence |

## Verificação automatizada

Testes futuros devem cobrir:

- dado pessoal em canal técnico, contrato ou OfflineOperation sem necessidade;
- hash, pseudônimo, agregado, embedding ou derivado reidentificável como anônimo;
- classificação ausente, reduzida, não propagada ou ignorada por IA e vector store;
- DataContract ausente, campo proibido, finalidade incompatível ou reutilização pelo consumidor;
- consentimento como única base ou papel jurídico sem assignment e Evidence;
- PrivacyImpactAssessment apresentado como RIPD automático;
- disposição violando hold, crypto-shredding com cópia/escrow ou dado reaparecendo após restore;
- Correction reescrevendo história, grupo pequeno exposto ou debug fora do escopo.

## Critérios de aceitação

A ADR pode ser aceita quando:

- identificabilidade, sensibilidade, confiança, fundamento, consentimento e Authorization forem distintos;
- papéis jurídicos usarem assignments contextuais e ProcessingActivity versionada;
- registros usarem referências opacas e ClassificationPropagation acompanhar toda derivação;
- DataContract restringir campos e finalidades sem conceder acesso;
- IA, canais, offline, agregações e métricas sociais preservarem classificação e minimização;
- anonimização e PrivacyImpactAssessment forem contextuais e explicados;
- histórico, Correction, disposição, chaves, backup e restore preservarem limites e Evidence mínima;
- falha for restritiva e vault, retenção, localização, consentimento e direitos permanecerem posteriores.

## Referência normativa inicial

Interpretação jurídica não integra o motor. Perfis versionam fontes aplicáveis, inicialmente a Lei nº 13.709/2018, texto oficial em `https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm`.

## O que esta ADR não decide

Esta ADR não escolhe:

- IdentityVault, persistência, criptografia, KMS, prazo, RetentionPolicy, legal hold ou direitos concretos;
- região, fornecedor, segurança operacional, papel jurídico, métrica social ou vertical.

## Plano de reversão

Antes da implementação, esta proposta pode ser substituída por nova ADR. Depois da adoção, mudança preserva versões de classificação, ProcessingContexts, avaliações, eventos e relatórios de ciclo de vida. Migração não reintroduz dado descartado nem reduz proteção silenciosamente.
