# DOMAIN.md

**Versão:** 1.19  
**Status:** Visão de destino congelada  
**Projeto:** Titan Core

> ⚠️ Este é o documento normativo central da linguagem de domínio do Titan.
>
> Nenhum conceito de negócio deve ser implementado antes de estar definido neste documento.
>
> Em caso de conflito entre o código e este documento, o código deve ser considerado incorreto até que a divergência seja analisada e formalmente resolvida.

## Regra de congelamento

Este documento descreve a visão de destino e as invariantes do domínio. Ele não é backlog, plano de entrega nem exigência para implementar todo o Titan antes da validação do MVP.

Novos detalhes não são acrescentados durante a implementação ordinária. Alteração exige uma destas justificativas explícitas:

- corrigir contradição ou erro material;
- refletir ADR estrutural aceita;
- remover ambiguidade que bloqueie uma funcionalidade atual aprovada.

Funcionalidades, prioridades, experimentos, integrações e etapas pertencem ao plano ou backlog. Implementação incremental utiliza somente o subconjunto do domínio necessário ao incremento vigente, sem enfraquecer as invariantes aplicáveis.
>
> Toda alteração relevante neste documento deve ser tratada como decisão arquitetural e submetida à aprovação.

---

# 1. Objetivo

Este documento define a linguagem oficial do Titan Core.

Seu propósito é garantir que:

- os conceitos do domínio tenham significado único;
- o código utilize termos consistentes;
- decisões sejam reproduzíveis;
- registros sejam auditáveis;
- o Core permaneça independente das verticais;
- novos conceitos sejam aprovados antes da implementação.

O Titan Core não conhece conceitos específicos de pecuária, indústria florestal, peças, alimentos ou outras verticais.

Conceitos como `Animal`, `Veterinarian`, `Medication`, `GTA`, `SISBOV`, `Tree`, `Part` ou `Feed` pertencem exclusivamente às respectivas verticais.

---

# 2. Princípios fundamentais

## 2.1 O Titan não presume verdade

O Titan trabalha com declarações, registros, eventos, evidências, relações, avaliações, decisões e fontes identificáveis.

O Titan não afirma automaticamente que uma informação corresponde à realidade.

Ele registra:

- quem informou;
- em qual Organization;
- quando a informação foi declarada;
- quando o fato teria ocorrido;
- quando o registro foi criado;
- de qual fonte a informação veio;
- por qual canal ela chegou;
- quais evidências a sustentam;
- qual grau de confiança foi atribuído;
- quais políticas e regras foram aplicadas;
- quais avaliações e decisões utilizaram aquela informação.

## 2.2 Integridade não significa verdade

A integridade de um registro significa que seu conteúdo pode ser verificado, alterações indevidas podem ser detectadas e sua origem, autoria, versão e sequência podem ser confirmadas.

Integridade não garante que o conteúdo represente corretamente o mundo real.

## 2.3 Histórico não é sobrescrito

Eventos, evidências, políticas publicadas, regras publicadas, avaliações, decisões e dossiês históricos não são alterados silenciosamente.

Correções devem preservar o registro original, registrar justificativa, criar novo registro, indicar responsável e manter vínculo explícito com o registro corrigido.

## 2.4 Estado atual é uma projeção

O estado atual representa apenas uma visão conveniente do presente. Ele não substitui o histórico e deve, quando aplicável, ser reconstruível a partir dos eventos e relações históricas.

## 2.5 Isolamento por Organization

Toda operação protegida ocorre dentro de um contexto de Organization.

A existência de relação entre Organizations não concede acesso automaticamente. Compartilhamento, consulta cruzada e travessia entre Organizations exigem autorização explícita.

## 2.6 Core independente das verticais

O Titan Core fornece mecanismos universais. As verticais fornecem significado operacional.

O Core não importa módulos de verticais, não conhece regras específicas de mercado, não consulta tabelas internas de verticais, não interpreta payloads específicos de verticais e não contém campos como `animal_id`, `medication_id` ou `gta_id`.

---

# 3. Identidade e acesso

## Organization

Unidade principal de isolamento, responsabilidade e autorização da plataforma.

Todo registro protegido possui uma Organization responsável.

Um registro pode ser emitido por, referenciar, ser compartilhado com ou afetar outra Organization. Nenhuma dessas relações concede acesso automaticamente.

### Invariantes

- toda Organization possui identidade estável;
- uma Organization não pode acessar dados de outra sem autorização;
- toda operação protegida deve conhecer a Organization ativa;
- referências entre Organizations devem ser explícitas e auditáveis.

## RecordOwnerOrganization

Papel exercido pela Organization responsável por determinado registro dentro do Titan.

Determina responsabilidade pelo ciclo de vida do registro na plataforma, namespace padrão de autorização, política de compartilhamento aplicável e responsabilidade apresentada na auditoria.

Não determina automaticamente propriedade civil ou intelectual, posse, custódia física, responsabilidade regulatória, autoria, emissão ou papel jurídico na proteção de dados. Esses efeitos dependem de legislação, contrato, Policy e conceitos específicos da vertical.

### Invariantes

- todo registro protegido possui exatamente uma RecordOwnerOrganization;
- não existe copropriedade do registro no Titan;
- RecordOwnerOrganization não concede direito de alterar ou apagar histórico imutável;
- outras Organizations podem receber Visibility ou acesso sem se tornarem responsáveis pelo registro;
- transferência operacional não altera a responsabilidade por registros históricos;
- mudança excepcional deve ser explícita, autorizada, justificada e auditável;
- `owner` não pode possuir outro significado implícito no código, banco ou API.

## User

Pessoa autenticada ou identidade humana reconhecida pela plataforma.

Um User pode possuir vínculo com várias Organizations. Permissões nunca são atribuídas diretamente ao User.

O Titan não armazena no domínio a senha do provedor de identidade.

## AuthenticatedPrincipal

Identidade cuja autenticação foi validada pelo servidor.

Pode resolver para User ou ServiceIdentity. Não representa autorização, Organization ativa ou Permission.

Tokens, secrets e credenciais não são armazenados no domínio nem copiados para auditoria.

## ServiceIdentity

Identidade não humana reconhecida pelo Titan.

Pode representar serviço, sistema, integração, processo automatizado ou Device com identidade autenticável.

Deve possuir Identity estável, tipo, RecordOwnerOrganization, mecanismo de autenticação referenciado, estado, validade, finalidade permitida, concessões, responsável pela criação, revogação e auditoria de uso.

### Invariantes

- ServiceIdentity não possui Membership humano;
- não recebe acesso universal por seu tipo;
- credenciais não são armazenadas no domínio;
- rotação de credencial não muda sua Identity;
- revogação impede novas operações;
- Device só atua autonomamente com identidade autenticável e concessão explícita.

## Membership

Vínculo temporal entre um User e uma Organization.

Define Organization, User, período de validade, status, Roles atribuídos, origem e responsável pela concessão.

### Invariantes

- um User só atua em uma Organization com Membership válido;
- Membership representa vínculo humano;
- Membership pode ser suspenso, encerrado ou substituído sem apagar histórico;
- mudança de Role não reescreve atribuições passadas.

## Role

Conjunto nomeado de Permissions.

Exemplos genéricos: `OrganizationAdministrator`, `Operator`, `Reviewer`, `Auditor`, `IntegrationService`.

Papéis específicos pertencem às verticais.

## Permission

Autorização atômica para executar uma ação sobre recurso ou capacidade.

Permissions são atribuídas a Roles, nunca diretamente ao User.

## OrganizationContext

Contexto imutável construído e validado pelo servidor para executar uma operação protegida.

O cliente pode solicitar atuação em determinada Organization, mas não fornece contexto, Roles ou Permissions confiáveis.

Deve identificar, quando aplicável, Organization ativa, AuthenticatedPrincipal, Actor, PrincipalCapacityBinding, Membership ou autorização técnica equivalente, Roles, Permissions, AuthorizationGrants, AccessPurpose, EffectiveAuthorizationScope, recurso, autenticação, correlação e instante.

### Invariantes

- não pode ser escolhido livremente pelo cliente;
- trocar a Organization solicitada exige nova validação;
- não pode ser reutilizado entre Organizations;
- claims externas não substituem Membership, Role, Permission ou AuthorizationGrant do Titan;
- worker reconstrói contexto autorizado antes de executar caso de uso;
- OfflineOperation é revalidada durante Synchronization;
- falha de validação resulta em negação.

## Visibility

Possibilidade, calculada para um contexto e operação, de descobrir a existência ou visualizar determinada parte de um registro.

Visibility não é Permission de alteração e não concede acesso por si só. Conhecer um Identifier não implica Visibility. Visibilidade de metadados não implica acesso ao conteúdo.

## Issuer

Papel exercido pelo Actor ou pela Organization que emite, publica, certifica ou atesta determinada informação.

Issuer pode ser diferente de RecordOwnerOrganization. Emissão não transfere responsabilidade pelo registro e não garante veracidade.

## Publication

Ato versionado e auditável pelo qual um Issuer torna um recurso elegível para consumo por audiência e finalidade delimitadas.

Registra recurso e versão, RecordOwnerOrganization, Issuer, audiência, finalidade, momento, validade, condições, estado, substituição ou Revocation, justificativa e hash, quando aplicável.

### Invariantes

- Publication não transfere ownership;
- não significa acesso público irrestrito;
- não concede Permission de alteração;
- recurso publicado e versão são imutáveis;
- alteração exige nova versão;
- Revocation não remove utilizações históricas;
- Authorization continua sendo avaliada no consumo.

## Sharing

Processo auditável pelo qual uma Organization concede acesso delimitado a outra Organization ou Actor.

Sharing produz AuthorizationGrant. Não transfere responsabilidade pelo registro, não muda Issuer e não surge automaticamente de uma relação entre Organizations.

## AccessPurpose

Finalidade controlada, estável e versionada para acesso.

Preserva código em português, descrição, categoria, operações, recursos, beneficiários, Organizations, Evidence, DataClassifications, ProcessingActivities, validade, aprovação e limitações. Purpose textual do cliente é solicitação não confiável e não substitui LegalBasisReference.

## GrantScope

Escopo imutável e versionado de AuthorizationGrant.

Delimita recursos, IDs ou conjuntos, Subjects, relações, período, Organization, ações, FieldScope, AccessPurpose, audiência, canal, jurisdição, derivados, exportação, volume, condições e exclusões. Expressão é contrato controlado pelo servidor.

## GrantScopeResolution

Resolução imutável de GrantScope em modo `CONJUNTO_FIXO`, `CRITERIO_DINAMICO` ou `SNAPSHOT_AUTORIZADO`.

Preserva critério e versão, instante, objetos ou conjunto, Digest, quantidade, limites, exclusões e resultado. Conjunto fixo não cresce; critério dinâmico é reavaliado em cada Authorization.

## FieldScope

Conjunto versionado de campos, projeções ou representações autorizadas.

Preserva permitidos, proibidos e condicionais, redactions, agregações, precisão, metadados, derivados, formato, audiência e limitações. Ausência é negação.

Digest, Identifier, nome, metadado, Provenance e existência de anexo também são protegidos. Leitura não implica exportação, derivação, inferência, IA ou redistribuição.

## PrincipalCapacityBinding

Vínculo imutável do beneficiário à capacidade utilizada pelo grant.

Preserva principal interno, Membership, ServiceIdentity ou vínculo institucional, Organization, capacidade, validade, Evidence e condições. Perda de vínculo ou competência torna o grant não utilizável sem apagar história.

## SharingRequest

Solicitação imutável de emissão, renovação, redução, suspensão ou revogação.

Preserva solicitante, concedente alegado, beneficiário, AccessPurpose, GrantScope, período, condições, justificativa, Evidence, correlação, DataClassification e IdempotencyKey. Não cria Visibility ou grant.

## GrantAssessment

Avaliação imutável anterior à emissão ou alteração de AuthorizationGrant.

Preserva request, participantes, autoridade, owner, Purpose, scope, Permissions, DataContract, ProcessingActivity, fundamentos aplicáveis, classificação, retenção, conflitos, riscos, aprovações, códigos e limitações.

Resultados iniciais: `AUTORIZAVEL`, `REDUCAO_NECESSARIA`, `APROVACAO_ADICIONAL_NECESSARIA`, `REVISAO_NECESSARIA`, `REJEITADA`, `INDETERMINADA`. Não concede acesso.

## AuthorizationGrant

Registro explícito, auditável e revogável de concessão de acesso.

Preserva SharingRequest, GrantAssessment, RecordOwnerOrganization, concedente, PrincipalCapacityBinding beneficiário, AccessPurpose, GrantScope, Permissions, validade, condições, aprovações, delegação, correlação, estado, Revocation e histórico.

Estados iniciais: `PLANEJADA`, `ATIVA`, `SUSPENSA`, `EXPIRADA`, `REVOGADA`, `SUBSTITUIDA`.

### Invariantes

- ausência de concessão resulta em negação quando o acesso depender de Sharing;
- concessão não excede Permissions do concedente;
- não transfere responsabilidade pelo registro;
- é avaliada para cada operação;
- suspensão, expiração ou Revocation impedem nova operação;
- utilizações anteriores permanecem auditáveis;
- escopo não pode ser ampliado silenciosamente.

Delegação é proibida por padrão. Subgrant referencia pai e não excede scope, Purpose, condições, prazo ou profundidade; suspensão ou término do pai impede novo uso dos descendentes.

## AccessRestriction

Restrição negativa, explícita e versionada aplicável a principal, capacidade, Organization, recurso, ação, campo, AccessPurpose, período ou condição.

Participa da Authorization e não é ignorada por grant positivo. Exceção exige autoridade e decisão próprias.

## GrantConflictAssessment

Avaliação imutável de grants, AccessRestrictions e Policies aplicáveis à mesma operação.

Preserva candidatos, scopes, Purposes, precedência configurada, condições, conflitos, decisão, códigos e limitações. Grants não são somados entre finalidades ou Organizations e conflito não é resolvido pelo mais recente.

## EffectiveAuthorizationScope

Resultado imutável da interseção restritiva entre Permission, AccessPurpose, grants, GrantScopeResolutions, FieldScopes, AccessRestrictions, DataContract, DataClassification, Policy e condições vigentes.

Preserva recurso e versão, operação, contexto, instante, grants, restrições, Purpose, campos, representações, derivados, escopo solicitado e autorizado, validade e códigos.

Dimensões incompatíveis falham fechado. Autorização parcial declara redução e não é apresentada como resposta integral.

## Authorization

Decisão realizada para operação concreta considerando principal, Actor, capacidade, OrganizationContext, owner, Permission, AccessPurpose, grants e cadeia, scopes resolvidos, AccessRestrictions, Visibility, recurso e versão, DataContract, classificação, Policy, validade e condições.

Resultados iniciais: `PERMITIDA`, `NEGADA`, `INDETERMINADA`.

Preserva EffectiveAuthorizationScope quando aplicável, grants e versões considerados, códigos, instante e correlação. Negação relevante é auditável sem revelar indevidamente existência do recurso.

## Actor

Pessoa, serviço, sistema ou dispositivo responsável por uma ação, declaração ou registro.

Actor não é sinônimo de Source.

Actor pode referenciar User, ServiceIdentity, sistema interno explicitamente identificado ou Device autorizado.

AuthenticatedPrincipal identifica quem foi autenticado; Actor identifica quem realizou ou assumiu a ação; Source identifica a origem; Issuer identifica quem emitiu ou atestou; RecordOwnerOrganization identifica quem responde pelo registro no Titan. Esses papéis podem coincidir, mas não são equivalentes.

---

# 4. Identidade de entidades

## Subject

Elemento sobre o qual Events, Evidences, relações, Evaluations ou Decisions podem ser registrados.

Pode ser Asset, Organization, Batch, Document, Process ou conceito específico de uma vertical.

## Asset

Entidade identificável cuja existência, condição, posse, localização ou Transformation é acompanhada ao longo do tempo.

Nem todo Subject é um Asset.

## Identity

Continuidade conceitual de uma entidade ao longo do tempo.

Permanece estável mesmo quando atributos ou Identifiers mudam.

## Identifier

Valor utilizado para reconhecer, localizar ou referenciar uma Identity.

Pode ser atribuído, substituído, expirado, revogado ou reutilizado conforme regra da vertical. Alterar um Identifier não cria necessariamente nova Identity.

## SubjectReference

Referência tipada e estável para um Subject.

Deve conter, quando aplicável, tipo, identificador, Organization e versão do contrato, sem expor detalhes internos da implementação.

---

# 5. Declarações, fatos e eventos

## Claim

Afirmação registrada por um Actor ou sistema sobre algo que teria ocorrido, existe ou possui determinada condição.

Uma Claim não é considerada verdadeira automaticamente.

Deve registrar, quando aplicável, identificador, Organization, Actor, Subject, conteúdo, momento da declaração, momento alegado do fato, Source, Channel, Device, versão do contrato, Evidences associadas, estado de verificação e IdempotencyKey.

Pode ser confirmada, contestada, corrigida, expirada ou revogada sem apagar histórico.

## Fact

Representação aceita de uma informação para finalidade delimitada.

Pode ser derivado de Claims, Sources e Evidences.

A aceitação de um Fact não o transforma em verdade absoluta. Deve preservar origem, contexto, validade e confiança.

## Event

Registro imutável de algo relevante que ocorreu no domínio ou de mudança reconhecida pelo sistema.

Deve indicar, quando aplicável, identificador, Organization, Subject ou agregado, tipo, versão, Actor, Source, ocorrido em, registrado em, correlação, causação, versão esperada, payload versionado, Evidences, referência de correção, hash anterior e hash atual.

### Regras

- Event nunca é editado;
- Event nunca é apagado pelas interfaces de domínio;
- correções geram novos Events;
- Event não contém senhas, tokens ou secrets.

## DomainEvent

Event produzido pelo domínio como consequência de operação válida.

É independente de FastAPI, SQLAlchemy, PostgreSQL ou infraestrutura.

## Correction

Novo registro que corrige ou complementa registro anterior.

Indica registro corrigido, justificativa, Actor, timestamp, novo conteúdo, Evidences e efeito esperado. Não apaga nem substitui fisicamente o original.

Correction referencia CorrectionAssessment autorizada e preserva ChangeKind, CorrectionScope, conteúdo novo, temporalidade, autoridade, Evidence, códigos, IdempotencyKey e versão esperada.

Atualiza CurrentProjection sem reescrever Event, Evidence, Evaluation ou Decision histórica. Quando disposição autorizada exigir remoção do valor anterior, permanece somente envelope mínimo sem conteúdo pessoal recuperável.

## Revocation

Registro que declara que informação, Evidence, autorização ou Document deixou de ser válido para determinada finalidade.

Não remove o histórico de utilização anterior.

## ChangeKind

Natureza controlada da mudança: `CORRECAO_DE_ERRO`, `COMPLEMENTACAO`, `NOVA_EVIDENCIA`, `ATUALIZACAO_METODOLOGICA`, `ATUALIZACAO_NORMATIVA`, `RECLASSIFICACAO`, `REVOGACAO`, `SUBSTITUICAO_PARA_NOVOS_EFEITOS`, `REPUBLICACAO`.

Não determina sozinho operação ou efeito. Nova Evidence ou evolução não implica erro anterior.

## CorrectionRequest

Solicitação imutável de mudança sobre objeto e versão específicos.

Preserva solicitante, OrganizationContext, ChangeKind alegado, CorrectionScope, motivo, conteúdo proposto, Evidence, finalidade, urgência, DataClassification, correlação e IdempotencyKey. Cliente não escolhe efeito ou versão corrente como confiáveis.

## CorrectionScope

Escopo imutável da mudança, delimitando objeto, versão, campos ou relações, período factual, finalidade, Organization, exclusões e dependências conhecidas.

Alteração exige nova request. Correção parcial não alcança campo fora do escopo.

## CorrectionAssessment

Avaliação imutável anterior à Correction, Revocation, nova versão ou SupersessionRelation.

Preserva request, original, ChangeKind, scope, Evidence admitida e rejeitada, Provenance, conflitos, autoridade, temporalidade, impacto preliminar, operação, códigos e limitações.

Resultados iniciais: `AUTORIZAVEL`, `EVIDENCIA_ADICIONAL_NECESSARIA`, `REVISAO_NECESSARIA`, `REJEITADA`, `INDETERMINADA`. Não altera registro, Projection ou State.

## SupersessionRelation

Relação imutável, direcional e acíclica entre versões ou registros.

Tipos iniciais: `CORRIGE`, `COMPLEMENTA`, `SUBSTITUI_PARA_NOVOS_EFEITOS`, `REVOGA_PARA_NOVOS_EFEITOS`, `REPUBLICA`, `RECLASSIFICA`.

Preserva origem, destino, finalidade, escopo, efetividade, autoridade, Evidence, códigos e limitações. Não transfere ownership, Visibility ou declara falsidade automática.

## Temporalidade da correção

Mudança distingue `occurred_at`, `recorded_at`, `discovered_at`, `requested_at`, `corrected_at`, `effective_from` e `known_at`, com Source, timezone e TimeConfidence aplicáveis.

Efeito anterior à correção não reescreve quando o Titan conheceu a mudança nem produz retroatividade automática.

## CurrentProjection

Projection reconstruível que resolve versão aplicável por objeto, finalidade, instante, OrganizationContext e Policy.

Considera SupersessionRelations, efetividade, Revocations, escopo, conflitos e Authorization, não apenas o timestamp mais recente. Ambiguidade, ciclo ou bifurcação não resolvida produz `INDETERMINADA` ou revisão.

---

# 6. Evidências, fontes e proveniência

## Evidence

Registro imutável utilizado para sustentar, contestar ou contextualizar Claim, Fact, Event, relação, Identity, Evaluation, Decision ou ação corretiva.

Deve registrar, quando aplicável, identificador, Organization, Actor ou emissor, Source, EvidenceOriginType, momento de produção, momento de registro, tipo, Digest, Signature, Validity, VerificationStatus, ConfidenceAssessment, versão e Document ou Artifact relacionado.

Nova versão gera nova Evidence.

## EvidenceReference

Referência estável a uma Evidence, sem conteúdo binário ou detalhes internos de armazenamento.

## Source

Origem responsável ou declarada da informação.

Exemplos: sistema governamental, ERP, laboratório, certificadora, Organization ou serviço externo.

Source não é sinônimo de Actor, Channel, Device ou formato de arquivo.

Integridade do conteúdo, identidade da Source, autoridade da Source e oficialidade são dimensões independentes. Digest válido confirma a cópia verificada, não sua oficialidade ou força normativa.

## NormativeInstrument

Identidade estável de lei, decreto, regulamento, instrução, resolução, portaria, norma técnica, licença, contrato, protocolo ou outra fonte que possa fundamentar Policy ou Rule.

Deve indicar tipo controlado, identificador e título oficiais, jurisdição, autoridade emissora e relações conhecidas.

### Invariantes

- não contém Rules executáveis;
- alteração de conteúdo não muda sua Identity;
- não presume aplicabilidade, interpretação ou autoridade;
- identificador oficial não é substituído por versão inventada pelo Titan.

## NormativeInstrumentVersion

Expressão imutável do conteúdo de um NormativeInstrument.

Preserva identificador próprio não reutilizável, versão ou expressão oficial, emissão, publicação, vigência e aplicabilidade declaradas, instante e método de captura, Source, publicador declarado, identificador da publicação, conteúdo ou Artifact, Digest, Signature e Evidence, idioma, jurisdição, estado e limitações.

`official_status_declared` registra a alegação recebida. `official_status_verified` registra verificação sustentada por Evidence. Nenhum deles substitui análise de aplicabilidade.

Nova publicação, correção ou conteúdo distinto gera nova versão e preserva a anterior.

## NormativeProvision

Dispositivo identificado dentro de uma NormativeInstrumentVersion, como artigo, inciso, seção, cláusula ou anexo.

Sua referência deve ser estável dentro da versão e preservar texto, localização canônica ou Digest suficiente para identificar o conteúdo utilizado.

## NormativeRelation

Relação tipada, direcional e auditável entre instrumentos, versões ou dispositivos.

Tipos iniciais: `ALTERA`, `REVOGA`, `SUBSTITUI`, `CONSOLIDA`, `CORRIGE`, `REGULAMENTA`, `REFERENCIA`.

Deve preservar vigência, dispositivos relacionados, Source e Evidence. A relação não permite inferir automaticamente efeito jurídico total, retroatividade ou aplicabilidade.

## NormativeReference

Referência imutável a NormativeInstrumentVersion e, quando possível, a NormativeProvision.

Preserva identificação oficial, versão, dispositivo, Digest, Source e Evidence necessários para localizar e verificar o conteúdo utilizado.

## Channel

Meio pelo qual a informação chegou ao Titan, como API, importação, interface web, aplicativo móvel, integração assíncrona ou leitura de dispositivo.

## Device

Equipamento que produziu, capturou ou transmitiu informação.

## Artifact

Objeto material ou digital que contém informação, como CSV, PDF, imagem, vídeo, certificado ou relatório.

## Provenance

Capacidade de explicar origem e uso de uma informação.

O Core deve permitir navegar, quando aplicável:

```text
Source → Claim → Evidence → Event → Fact → Evaluation → Decision → Dossier
```

Para fundamentação normativa, deve permitir também:

```text
NormativeInstrumentVersion → NormativeReference → NormativeBasis
→ Policy → Rule → Evaluation → Decision → Dossier
```

Para sustentabilidade, deve permitir também:

```text
Source → Measurement → CalculatedMetric → SustainabilityAssertion
→ SustainabilityDisclosure → Publication
```

Para classificação e fluxo de dados, deve permitir também:

```text
ProcessingActivity → DataContract → DataClassification
→ ClassificationPropagation → objeto derivado
```

A navegação deve funcionar também no sentido inverso.

Mudança na validade ou integridade de uma Evidence não reescreve Decisions históricas, mas pode marcá-las como potencialmente afetadas.

Provenance é representada por ProvenanceLinks. ProvenancePath é resultado reconstruível e autorizável do grafo, não fonte autoritativa paralela.

## ConfidenceLevel

Classificação explicável da confiança disponível em Evidence, Claim ou Fact.

Capabilities iniciais:

- `AUTODECLARADA`;
- `EVIDENCIA_ANEXADA`;
- `ASSINATURA_VERIFICADA`;
- `FONTE_CONFIRMADA`;
- `CORROBORADA`.

Descrevem suporte disponível e não formam escala ordinal universal. Podem considerar autoria, integridade, validade, confiabilidade da Source, corroborabilidade e atualidade.

Signature não implica maior veracidade. Source oficial não implica atualização automática.

## Validity

Período ou condição durante a qual um registro pode ser utilizado para determinada finalidade.

Expiração não apaga histórico.

## VerificationStatus

Estado de verificação de Claim, Evidence ou Fact.

Estados iniciais: `NAO_VERIFICADO`, `VERIFICACAO_PENDENTE`, `VERIFICADO`, `CONTESTADO`, `CONFLITANTE`, `EXPIRADO`, `INVALIDO`, `REVOGADO`.

Fonte indisponível e resultado desconhecido pertencem à ValidationAttempt. Rejeição por Policy pertence à EvidenceAdmissibilityAssessment.

## EvidenceOriginType

Tipo controlado da forma de entrada ou produção da informação.

Valores iniciais: `DECLARACAO_DE_USUARIO`, `DOCUMENTO_RECEBIDO`, `EXTRACAO_DE_DOCUMENTO`, `FONTE_OFICIAL`, `TERCEIRO_AUTORIZADO`, `CAPTURA_DE_DISPOSITIVO`, `OBSERVACAO`, `CONFIRMACAO_MANUAL`, `RESULTADO_DERIVADO`.

Descreve origem, não qualidade, autoridade ou confiança.

## SourceProfile

Perfil versionado de Source para finalidade delimitada.

Preserva identidade declarada e verificada, Organization responsável, tipos de dado, jurisdição, autoridade alegada, contratos, métodos, disponibilidade, freshness, validade, Evidence e limitações. Não torna a Source confiável universalmente.

## SourceSnapshot

Estado imutável observado de Source em instante delimitado.

Preserva SourceProfile, instantes, contrato, ValidationScope, request e response Digests, referência opaca ao material permitido, atualização declarada, resultado técnico e limitações. Comprova observação sustentada por Evidence, não verdade material.

## ProvenanceLink

Relação imutável e tipada entre objeto de origem e objeto produzido, capturado, transformado, validado ou utilizado.

Preserva objetos e versões, relação, EvidenceOriginType, Source, Actor, Channel, Device, instantes, método, DataContract, DataClassification, RetentionAssignment, Digest, correlação e limitações. Não transfere ownership, concede Visibility ou prova causalidade.

## ProvenancePath

Resultado reconstruível e autorizável da navegação por ProvenanceLinks.

Preserva direção, filtros, versões, Authorization, lacunas, ciclos, objetos inacessíveis, completude e limitações. Quando preservado, é snapshot imutável do caminho conhecido naquele instante.

## ValidationScope

Escopo imutável de validação: `CAMPO`, `OBJETO`, `COLECAO`, `RELACAO` ou `DOCUMENTO`.

Delimita versões, campos incluídos e excluídos, período, relações e critérios. Alteração exige nova ValidationRequest; resultado não é ampliado implicitamente.

## ValidationRequest

Solicitação imutável de validação com ValidationScope, SourceProfile, método, finalidade, instante, FreshnessProfile, contextos, DataContract, correlação e IdempotencyKey.

O servidor resolve perfil e escopo autorizado. A solicitação não concede acesso.

## ValidationAttempt

Tentativa operacional correlacionada à ValidationRequest.

Estados iniciais: `PENDENTE`, `CONCLUIDA`, `FONTE_INDISPONIVEL`, `RESULTADO_DESCONHECIDO`, `NAO_SUPORTADA`, `FALHA_TRANSITORIA`, `FALHA_PERMANENTE`.

Preserva executor, instantes, contrato, Digests, referência opaca, retry e limitações. Resultado desconhecido não equivale a sucesso ou falha confirmada.

## ValidationAssessment

Avaliação imutável do que tentativas e Evidences permitem concluir.

Preserva ValidationScope, campos confirmados, divergentes, ausentes e não avaliados, método, SourceProfile, Evidences, instante, freshness, ConfidenceAssessment, VerificationStatus, assessor, motor e limitações. Resultado não se estende a campo não avaliado.

## ConfidenceAssessment

Avaliação explicável da confiança disponível para objeto, finalidade e instante.

Preserva dimensões, Evidence, método, SourceProfile, cobertura, atualidade, incerteza, conflitos, limitações e ConfidenceLevel. Não representa probabilidade de verdade, precisão estatística, fraude ou certeza material.

## FreshnessProfile

Perfil versionado de exigência de atualidade por informação, finalidade, Source, jurisdição e Policy.

Define referência, tolerância, evento de atualização, requisitos temporais, comportamento de indisponibilidade, aprovação e limitações. O Core não fixa janela universal.

## FreshnessAssessment

Avaliação imutável da atualidade para finalidade e instante delimitados.

Registra Source, consulta, atualização declarada, validade, FreshnessProfile, TimeConfidence, resultado e limitações. Fonte indisponível não renova freshness anterior.

## EvidenceAdmissibilityAssessment

Decisão imutável de Policy sobre uso de Evidence ou ValidationAssessment em Evaluation específica.

Resultados iniciais: `ACEITA`, `ACEITA_COM_RESTRICOES`, `REVISAO_NECESSARIA`, `REJEITADA_POR_POLITICA`, `INDETERMINADA`.

Preserva Policy, finalidade, assessments, conflitos, códigos de razão, Actor ou motor e limitações. Não altera VerificationStatus nem declara verdade material.

## ConflictAssessment

Avaliação imutável de divergências entre Claims, Evidences, campos, versões ou Sources.

Preserva temporalidade, hipóteses, resolução, Actor e limitações. Não escolhe silenciosamente último valor ou Source mais oficial; resolução não apaga o conflito.

## ConflictMaterialityAssessment

Avaliação contextual do impacto de ConflictAssessment para finalidade, Policy, Evaluation ou Decision.

Preserva diferenças, dependentes, thresholds, impacto potencial, revisão, Evidence e limitações. Não é severidade universal.

## CurrentValidationAssessment

Avaliação atual correlacionada a ValidationAssessment histórica.

Explica mudança de Source, Evidence, método ou estado sem substituir o resultado anterior ou projetar conhecimento posterior sobre Decision histórica.

---

# 7. Governança, classificação e ciclo de vida de dados

## DataClassification

Classificação versionada aplicada a campo, payload, Artifact, registro ou conjunto de dados.

Preserva IdentifiabilityLevel, DataSensitivity, categoria, titular, finalidade, ProcessingContext, jurisdição, papéis, compartilhamento, audiência, retenção referenciada, legal hold conhecido, localização, transferência, proteção, logging, exportação, derivação, agregação, fonte, versão, aprovação e limitações.

Não é string livre. Mudança cria versão, Actor, justificativa, Evidence e análise de impacto. Classificação ausente, conflitante, expirada ou indeterminada recebe tratamento mais restritivo ou revisão conforme Policy.

## ClassificationOrigin

Origem controlada da classificação: `MANUAL`, `AUTOMATICA`, `INFERIDA`, `IMPORTADA`, `HERDADA`, `PROVISORIA`.

## ClassificationConfidence

Confiança específica da classificação: `CONFIRMADA`, `PROVAVEL`, `INCERTA`, `DESCONHECIDA`.

Não é score universal nem substitui ConfidenceLevel de Claim, Evidence ou Fact. Incerteza não reduz proteção.

## ClassificationAssessment

Avaliação imutável que registra DataClassification, ClassificationOrigin, ClassificationConfidence, Evidence, método, assessor, instante, revisão prevista e limitações.

Resultado automático, importado, inferido ou provisório preserva origem e revisão exigida.

## ClassificationPropagation

Lineage imutável entre objeto de origem e derivado.

Preserva objetos, classificações, regra e versão, transformação, resultado, justificativa, responsável, revisão e limitações.

Toda derivação relevante registra propagação. Redução exige Policy e aprovação; regra ausente aplica restrição mais forte ou revisão. Mudança posterior não reclassifica histórico silenciosamente.

OCR, visão, modelo estatístico ou de linguagem, prompt, output, embedding, vetor, índice, feature, dataset, cache ou model artifact não removem classificação, finalidade, papel, licença ou restrição. Policy considera reconstrução, memorização e inferência.

## IdentifiabilityLevel

Nível de associação a pessoa natural: `DIRETAMENTE_IDENTIFICAVEL`, `PSEUDONIMIZADO`, `ANONIMIZADO`, `AGREGADO`.

Pseudonimização permanece protegida quando correlação permite associação. Agregação não implica anonimização. Contexto ou novos meios podem elevar a classificação.

## DataSensitivity

Sensibilidade independente de IdentifiabilityLevel.

Categorias iniciais: `PUBLICO`, `INTERNO`, `CONFIDENCIAL`, `RESTRITO`, `DADO_PESSOAL`, `DADO_PESSOAL_SENSIVEL`, `SEGREDO_TECNICO`, `CREDENCIAL`, `MATERIAL_CRIPTOGRAFICO`.

Categoria pública não elimina licença, integridade ou finalidade. Credencial e material criptográfico não entram no Domain, Events, Outbox, logs ou auditoria.

## DataSubjectReference

Referência opaca, tipada e estável à pessoa natural relacionada ao tratamento. Não contém atributo diretamente identificável.

## PersonalDataReference

Referência tipada a atributo ou conjunto pessoal mantido em fronteira protegida.

Resolução exige OrganizationContext, Permission, finalidade, ProcessingContext, papel e auditoria. Referência não concede Visibility nem comprova existência ao solicitante.

## ProcessingContext

Contexto imutável que explica tratamento declarado.

Identifica finalidade, operação, Organization atuante, DataProcessingRoleAssignments, fundamentos, período, DataClassifications, titulares, destinatários, audiência, restrições, autorização usada, correlação e instante.

Não é OrganizationContext e não autoriza operação. Finalidade do cliente é solicitação não confiável validada pelo servidor.

## LegalBasisReference

Referência versionada à fundamentação declarada para operação e finalidade.

Preserva NormativeBasis, dispositivo, jurisdição, finalidade, período, interpretação, Evidence e limitações. Não é string livre e não constitui conclusão jurídica automática.

## ConsentRecord

Registro de manifestação do titular quando consentimento for fundamento aplicável.

DataClassification, LegalBasisReference, ConsentRecord e AuthorizationGrant são distintos. ConsentRecord não substitui fundamento, ProcessingActivity ou Authorization. Obtenção, retirada, renovação e efeitos dependem de decisão própria.

## ProcessingActivity

Registro versionado da atividade de tratamento.

Preserva identidade, propósito, operações, LegalBasisReferences, DataProcessingRoleAssignments, categorias de dados e titulares, Sources, destinatários, DataContracts, transferências, retenção referenciada, segurança, sistemas, estado, validade e aprovação.

Cada categoria liga-se a propósito e fundamento. Mudança de finalidade exige avaliação. Destinatário listado não recebe acesso. Atividade não substitui Authorization, e execução deve ser reconciliável com o registro.

## DataProcessingRole

Tipo controlado por perfil jurisdicional para papel declarado de Organization em tratamento, como `CONTROLADOR`, `CONTROLADOR_CONJUNTO`, `OPERADOR` ou `SUBOPERADOR`.

RecordOwnerOrganization, Issuer, armazenamento, contrato técnico ou posse dos bytes não determinam papel jurídico.

## DataProcessingRoleAssignment

Atribuição temporal de DataProcessingRole a Organization em ProcessingActivity.

Preserva jurisdição, período, finalidade, contrato ou NormativeBasis, Evidence, aprovação e limitações. Registra qualificação declarada, não conclusão jurídica definitiva.

## DataContract

Contrato lógico versionado de intercâmbio de dados.

Preserva produtor, consumidores, schema ou payload, campos permitidos e proibidos, DataClassifications, regras de propagação, propósitos, LegalBasisReferences, DataProcessingRoleAssignments, transformações, retenção, localização, publicação, disposição, incidentes, compatibilidade e validade.

Restringe fluxo, mas não concede acesso nem substitui ProcessingActivity, AuthorizationGrant ou Authorization. Cliente não o escolhe livremente. Campo, finalidade, consumidor ou transformação incompatível bloqueia produção ou consumo. Mudança incompatível cria versão.

## AnonymizationAssessment

Avaliação imutável da alegação de anonimização para conjunto, finalidade, contexto e instante.

Preserva técnica, informação adicional, separação e acesso, meios razoáveis, adversários, singularização, ligação, inferência, amostragem, validação, responsável, aprovação, limitações e revisão.

Remoção de nome, hash previsível, troca de identificador, restrição de acesso ou agregação não bastam. Nova capacidade de correlação pode exigir reclassificação sem reescrever avaliação histórica.

## PrivacyImpactAssessment

Avaliação versionada de impacto à privacidade.

Preserva ProcessingActivity, gatilho, escopo, método, dados e titulares, necessidade, proporcionalidade, riscos, controles, risco residual, opiniões divergentes, revisor, aprovação, revisão prevista e limitações.

É elaborada antes de tratamento de alto risco quando aplicável e revista após mudança relevante. Aprovação não prova conformidade. Somente perfil jurídico específico pode apresentá-la como relatório regulatório; versões interna e pública podem possuir escopos distintos.

## RetentionPolicy

Política imutável e versionada que define ciclo de vida para categorias e contextos delimitados.

Preserva DataClassifications, finalidades, ProcessingActivities, DataContracts, jurisdição, fundamentos, trigger, regra temporal, ação final, revisões, derivados, cópias, aprovações, validade e limitações. Não concede Authorization e não contém prazo universal do Core.

## RetentionClock

Cálculo temporal imutável de uma RetentionAssignment.

Preserva trigger Event, instante e Source, calendário, timezone, método, períodos de pausa, retomadas, expiração calculada, TimeConfidence e limitações. Pausa ou retomada exige previsão na política e evento verificável.

## TimeConfidence

Confiança delimitada na fonte e no cálculo temporal.

Considera autoridade temporal, sincronização, divergência e incerteza. Relógio isolado de cliente ou servidor não constitui prova suficiente; inconsistência impede conclusão temporal automática.

## RetentionAssignment

Vínculo imutável entre objeto ou conjunto delimitado, DataClassification e versão de RetentionPolicy.

Registra DispositionScope, RetentionClock, fontes, exceções, prioridade, estado e revisão. Múltiplas obrigações podem coexistir sem tornar o objeto automaticamente descartável.

## RetentionConflictAssessment

Avaliação imutável de políticas, fundamentos, prioridades, impedimentos e Evidence em conflito.

Registra decisão, Actor e limitações. Não presume que o maior ou menor prazo sempre prevalece; resultado indeterminado exige preservação restrita e revisão.

## RetentionReview

Revisão imutável iniciada por nova Policy, Evidence, mudança normativa, conflito, evento ou review due.

Preserva objetos, assignments, versão anterior, impacto, conclusão e próxima revisão sem recalcular ou eliminar histórico automaticamente.

## LegalHold

Ordem versionada que suspende disposição em DispositionScope determinado.

Preserva autoridade, fundamento, Evidence, motivo protegido, início, estado, responsável, revisão, condições de liberação e limitações. Impede disposição abrangida, mas não amplia Visibility, finalidade, audiência, compartilhamento ou Authorization.

## DispositionScope

Escopo imutável compartilhado por avaliação, decisão, operação, receipts e reconciliação.

Delimita objetos, Organizations, intervalo temporal, DataClassifications, ProcessingActivities, derivados e exclusões justificadas. Mudança de escopo exige nova versão e avaliação.

## DispositionAssessment

Avaliação imutável de elegibilidade e impedimentos antes da disposição.

Considera assignments, clocks, conflitos, LegalHolds, inventário, cópias, derivados, contratos, impacto, ação, autoridade e limitações. Resultado inicial: `AUTORIZADA`, `NEGADA`, `ADIADA`, `REVISAO_NECESSARIA` ou `INDETERMINADA`, com códigos de razão.

## LogicalDisposition

Bloqueio autorizado de resolução, uso e novos acessos dentro do DispositionScope.

Não prova remoção material, não apaga história e não amplia finalidade.

## PhysicalDisposition

Remoção autorizada de material nos alvos inventariados.

Pode eliminar, anonimizar, destruir chave exclusiva ou arquivar restritivamente conforme perfil. Resultado parcial, backup pendente ou cópia externa não é apresentado como destruição concluída.

## DispositionOperation

Operação privilegiada, idempotente e correlacionada que executa ação autorizada em DispositionScope imutável.

Distingue Actor solicitante, aprovador, ServiceIdentity executora e operador de reconciliação. Resultado desconhecido permanece explícito e recuperável.

## DispositionReceipt

Registro operacional imutável e versionado do resultado informado por um sistema-alvo.

Não é Evidence automaticamente. Referencia ou produz Evidence verificável com Provenance, Digest, Signature quando exigida, resultado e limitações, sem conter payload descartado ou segredo de reconstrução.

## DispositionReconciliation

Comparação imutável entre alvos esperados, concluídos, ausentes, desconhecidos e inconsistentes.

Usa DispositionScope e receipts, registrando conclusão, limitações, responsável e instante. Executor isolado não define conclusão global.

## DispositionReport

Relatório imutável da avaliação, operação, Evidence e reconciliação da disposição.

Expõe resultados por alvo, falhas, limitações, material mínimo preservado e alcance da conclusão. Não afirma inexistência absoluta de cópias além do inventário e Evidence disponíveis.

## Invariantes de ciclo de vida

Registro operacional usa DataSubjectReference ou PersonalDataReference e evita replicar atributos pessoais. Exceção exige necessidade, classificação, finalidade, autorização, retenção e teste.

DataClassification acompanha bancos, object storage, caches, projeções, backups, Events, Evidences, Documents, mensagens, observabilidade, analytics, Dossiers, VerificationBundles, relatórios, exportações, dispositivos, offline e integrações.

Transformação mantém ou eleva proteção por padrão. Redução exige operação aprovada. Classificação composta respeita o componente mais restritivo salvo regra formal.

Events, mensagens, logs e traces usam identificadores opacos e conteúdo mínimo. Payload, token, secret, documento e atributo pessoal não são registrados por padrão. OfflineOperation não contém credencial e aplica minimização e proteção local.

O histórico separa envelope mínimo de payload pessoal. Disposição exige DispositionAssessment autorizada, escopo imutável, operação privilegiada, receipts e reconciliação. Evento nunca contém o dado eliminado ou valor recuperável.

LegalHold bloqueia disposição sem conceder acesso. Vencimento, solicitação do titular, revogação de consentimento ou nova Policy iniciam avaliação ou revisão, não eliminação automática.

EncryptionKey, Data, Digest e Evidence são distintos. Destruir chave não elimina cópia em claro; rotação não muda classificação; recuperação não restaura autorização. Crypto-shredding exige chave exclusiva e considera backup, escrow e cópias.

Restore reaplica bloqueios e disposições antes do uso. Dado eliminado que reapareça não retorna ao processamento ordinário.

DataMinimizationAssessment permanece capacidade futura multidimensional, sem score universal, até decisão própria.

---

# 8. Documentos e assinaturas

## Document

Artifact digital armazenado ou referenciado pela plataforma.

Possui Identity, hash, metadados, versão, Organization responsável e pode possuir autor, emissor, Validity e Signature.

Document nunca é alterado. Nova versão gera novo Document.

## DocumentReference

Referência estável a um Document. O conteúdo binário pertence à infraestrutura, não ao domínio.

## Signature

Comprovação criptográfica de autoria, integridade ou aprovação.

Nunca deve ser confundida com autenticação.

---

# 9. Relações, genealogia e transformação

## UniversalRelation

Relação genérica, temporal e auditável entre dois Subjects.

Deve registrar origem, destino, tipo, início e fim de validade, Organization responsável, Event criador, Evidences, ConfidenceLevel, quantidade, unidade e metadados versionados, quando aplicável.

Não concede acesso entre Organizations.

## Genealogy

Rede temporal de UniversalRelations entre Subjects.

Responde de onde veio, para onde foi, quem participou, quando, em qual quantidade, qual Event criou a relação, quais Evidences sustentam o vínculo e quais lacunas existem.

Genealogy nunca é perdida.

## Transformation

Tipo de UniversalRelation em que um ou mais Subjects originam outros Subjects.

Deve preservar entradas, saídas, quantidades, perdas, momento, responsáveis, Events, Evidences e Genealogy.

## Batch

Agrupamento lógico ou operacional de Subjects.

Possui Identity própria, finalidade, Organization responsável, composição variável e histórico temporal de entradas e saídas.

Não implica necessariamente propriedade física.

## BatchMembership

Relação temporal entre Subject e Batch.

Registra início, fim, quantidade, Event de inclusão, Event de remoção, Evidences e Organization, quando aplicável.

---

# 10. Políticas, regras e avaliações

## Policy

Conjunto versionado de Rules utilizado para finalidade definida.

Deve indicar código, versão, finalidade, escopo, autoridade, NormativeBasis quando houver fundamentação normativa, vigência, status, estratégia de agregação, Rules incluídas e versão do contrato.

Policy em rascunho pode ser alterada. Policy publicada é imutável; alterações geram nova versão.

Policy nunca modifica Facts ou Evidences.

## Rule

Critério versionado e determinístico aplicado a Facts, Claims, Evidences ou relações.

Deve indicar código, versão, descrição, condição, vigência, severidade, Evidences requeridas, NormativeBasis ou NormativeReferences quando aplicáveis, justificativa, ação corretiva recomendada e resultados possíveis.

Rule publicada é imutável.

## NormativeBasis

Interpretação identificável e versionada que vincula Policy ou Rule a NormativeReferences.

Deve registrar finalidade, escopo, jurisdição, contexto de aplicabilidade, `interpreted_by`, `approved_by`, Organization, `approval_authority`, capacidade declarada do aprovador, Evidence de competência, justificativa, `approved_at`, `valid_from`, `valid_until`, estado, `intended_use`, versão, divergências, exceções, limitações, base anterior e motivo da mudança.

### Invariantes

- não é anotação textual livre nem Rule executável;
- aprovação identifica Actor, capacidade, finalidade e autoridade declarada;
- aprovação privada não é apresentada como entendimento oficial sem Evidence específica;
- extração automatizada exige validação, autoria e aprovação antes do uso;
- mudança de interpretação gera nova versão;
- conflito ou lacuna não é resolvido por suposição.

Razões iniciais de indeterminação: `POLITICA_APLICAVEL_AUSENTE`, `MULTIPLAS_POLITICAS_APLICAVEIS`, `CONFLITO_NORMATIVO`, `LACUNA_TEMPORAL`, `JURISDICAO_INDETERMINADA`, `AUTORIDADE_INDETERMINADA`.

## NormativeBasisSnapshot

Fotografia imutável da fundamentação normativa utilizada por Evaluation ou Decision.

Preserva NormativeBasis, NormativeReferences, versões, dispositivos, Digests, jurisdição, condições de aplicabilidade, Policy, Rules, instantes de referência e conhecimento, Actor aprovador, Evidence, lacunas, conflitos, exceções e limitações.

Um mapa de códigos e versões não substitui este conceito. O snapshot é correlacionado ao snapshot dos fatos e não muda quando fonte, interpretação ou Policy evoluem.

## RuleResult

Resultado individual da execução de uma Rule.

Registra Rule e versão, Subject, resultado, Facts, Evidences, justificativa, severidade, ações recomendadas, timestamp e hash das entradas relevantes.

Resultados iniciais: `ATENDIDA`, `NAO_ATENDIDA`, `PENDENTE`, `NAO_APLICAVEL`, `INDETERMINADA`.

## Evaluation

Execução registrada de uma Policy e suas Rules sobre snapshot delimitado de informações.

Preserva identificador, Organization, Subject, finalidade, Policy e versão, Rules e versões, NormativeBasisSnapshot quando aplicável, Facts, Claims, Evidences, RuleResults, EvaluationOutcome, momento, versão do motor, hash do snapshot e Actor ou mecanismo executor.

Evaluation histórica nunca é alterada. Mudanças futuras produzem nova Evaluation.

## Decision

Conclusão registrada produzida a partir de uma Evaluation.

Preserva ou referencia Subject, finalidade, Evaluation, DecisionProposal quando aplicável, Policy e versão, NormativeBasisSnapshot, RuleResults, snapshot, DecisionResult, DecisionReasons, ações, autoridade, método de emissão, aprovações, restrições, validade, correlação, momento, motor e Digest.

Decision histórica nunca muda. Nova informação exige nova Evaluation e nova Decision.

Uma Evaluation pode existir sem Decision oficial publicada quando o fluxo exigir revisão humana.

## DecisionResult

Resultado agregado da Decision.

Estados iniciais: `APROVADA`, `REJEITADA`, `APROVADA_COM_RESTRICOES`, `INDETERMINADA`.

Resultado específico de vertical pertence a perfil próprio. Revisão necessária é estado do processo, não resultado final.

## EvaluationOutcome

Resultado técnico agregado da Evaluation antes da emissão de Decision.

Estados iniciais: `CONDICOES_SATISFEITAS`, `CONDICOES_NAO_SATISFEITAS`, `INFORMACAO_INSUFICIENTE`, `EVIDENCIA_CONFLITANTE`, `VALIDACAO_EXTERNA_PENDENTE`, `REVISAO_HUMANA_NECESSARIA`, `INDETERMINADO`.

Não autoriza operação, publica conclusão ou substitui DecisionResult.

## DecisionProposal

Proposta imutável derivada de Evaluation para emissão automática autorizada ou revisão humana.

Preserva Evaluation, outcome, resultado proposto, DecisionReasons, ações, restrições, autoridade e aprovações requeridas, validade, motor e limitações. Não é Decision, não altera State e não é apresentada como conclusão oficial.

## DecisionReason

Razão estruturada e versionada de EvaluationOutcome, DecisionProposal, Decision ou review.

Preserva código estável em português, Rule, condição, campo, valor e unidade autorizados, condição esperada, EvidenceReferences, ValidationAssessments, severidade contextual, ações, limitações e mensagem humana.

Código é contrato; mensagem pode ser traduzida. Redaction não amplia ou inverte a razão.

## DecisionAuthorityProfile

Perfil versionado de autoridade para emitir, revisar, contestar, aprovar override ou publicar Decision.

Preserva finalidade, tipo de Decision, Organization, Roles ou grants, Permission, competência declarada, Evidence, autenticação, segregação, limites, validade e aprovações. O servidor resolve o perfil; cargo, Membership, claim ou ownership isolado não comprovam autoridade.

## DecisionReview

Caso identificado que coordena revisão de Evaluation, DecisionProposal ou Decision.

Preserva objeto, motivo, escopo, solicitante, OrganizationContext, autoridade, revisor, prazos, Evidence adicional, conflitos, atividades, conclusão e correlação.

Estados iniciais: `ABERTA`, `EM_TRIAGEM`, `AGUARDANDO_EVIDENCIA`, `EM_ANALISE`, `DECIDIDA`, `ENCERRADA`, `CANCELADA`. Transições, concorrência, reabertura e múltiplas revisões dependem de Policy.

## DecisionChallenge

Contestação imutável e autorizada contra escopo específico de Evaluation ou Decision.

Preserva fundamento, DecisionReasons, Evidence, resultado pretendido, representação, prazo, DataClassification e limitações. Não suspende, revoga ou invalida Decision automaticamente.

## ReviewEvidenceSubmission

Submissão imutável de Evidence ou referência durante DecisionReview.

Preserva remetente, capacidade, Source, Provenance, instante, finalidade, DataContract, classificação, validação e admissibilidade. Anexo não se torna Evidence aceita e não altera snapshot original.

## ReviewAssessment

Avaliação imutável do material e das questões de DecisionReview.

Resultados iniciais: `MANTER`, `REAVALIAR`, `OVERRIDE_ELEGIVEL`, `EVIDENCIA_ADICIONAL_NECESSARIA`, `INDETERMINADO`.

Preserva razões examinadas, Evidence admitida e rejeitada, conflitos, Policy, autoridade, divergências, limitações e códigos. Não é nova Decision.

## DecisionOverride

Autorização excepcional e imutável para emitir nova Decision divergente dentro de escopo delimitado.

Preserva DecisionAuthorityProfile, Actor, justificativa, Evaluation, RuleResults não atendidos, DecisionReasons, Evidence, risco, condições, escopo, validade, aprovações e Decisions correlacionadas.

Não altera RuleResult, Fact, Evidence ou Decision anterior e não declara condição satisfeita. Expiração pode iniciar reavaliação, nunca reversão histórica automática.

## Reevaluation

Solicitação e execução correlacionadas que produzem nova Evaluation com snapshot, Evidence, Policy, Rules e motor identificados.

Motivos iniciais: `NOVA_EVIDENCIA`, `CORRECAO`, `CONFLITO_RESOLVIDO`, `VALIDACAO_CONCLUIDA`, `POLITICA_ATUALIZADA`, `REVISAO`, `OVERRIDE_EXPIRADO`, `REAVALIACAO_AUTORIZADA`.

`VALIDACAO_CONCLUIDA` não significa resultado positivo. Reevaluation não se confunde com HistoricalReproduction, HistoricalComplianceAssessment, CounterfactualSimulation ou CurrentReevaluation.

## DecisionRelation

Relação imutável entre Decisions sem substituição física.

Tipos iniciais: `CONFIRMA`, `SUBSTITUI_PARA_NOVOS_EFEITOS`, `RESTRINGE`, `REVOGA_PARA_NOVOS_EFEITOS`, `RESULTA_DE_REVISAO`, `RESULTA_DE_OVERRIDE`, `RESULTA_DE_REAVALIACAO`.

Preserva escopo, efetividade, autoridade, Evidence e razões. Efeito histórico anterior não é apagado.

## Invariantes de revisão e efeito

Suspensão, restrição ou manutenção provisória durante review exige decisão autorizada, temporal e separada. Challenge não produz efeito provisório implicitamente.

Método de emissão distingue `AUTOMATICA_AUTORIZADA`, `HUMANA`, `HUMANA_ASSISTIDA` e `OVERRIDE_AUTORIZADO`. Assistência automatizada não é apresentada como decisão puramente humana.

IA pode produzir Claim ou resultado derivado, não autoridade. Revisão humana exige acesso às informações materiais e conclusão própria.

## DecisionEngine

Componente de aplicação responsável por coordenar seleção de Policy, coleta de Facts, execução de Rules, criação de Evaluation e produção de DecisionProposal ou Decision automática autorizada.

Não altera dados de origem, não interpreta conceitos específicos de vertical e deve ser determinístico para entradas equivalentes.

## HistoricalReproduction

Reexecução de snapshot, Policy, Rules, NormativeBasisSnapshot e versão do motor originais para verificar reprodutibilidade técnica.

Produz relatório imutável. Divergência é registrada e investigada; Evaluation e Decision originais não são substituídas.

## HistoricalComplianceAssessment

Nova Evaluation que examina a correspondência de Decision com a base considerada aplicável em instante histórico.

Conhecimento posterior, interpretação revisada ou fonte recuperada devem ser separados do conhecimento original. O resultado não conclui automaticamente validade jurídica, fraude, culpa ou responsabilidade.

## CounterfactualSimulation

Aplicação hipotética de Policy, Rules ou NormativeBasis alternativas a snapshot declarado.

Produz relatório de simulação, não altera estado operacional, Evaluation ou Decision e não se apresenta como resultado existente no passado.

## CurrentReevaluation

Avaliação autorizada com fatos e regras aplicáveis ao contexto atual.

Pode produzir nova Evaluation e nova Decision correlacionadas às anteriores, preservando diferenças de fatos, Policy, Rules, fundamentação, motor e resultado.

`Replay` não é termo universal para HistoricalReproduction, HistoricalComplianceAssessment, CounterfactualSimulation ou CurrentReevaluation.

## AssertionType

Classificação controlada da natureza de uma afirmação produzida pelo Titan:

- `FATUAL`: descreve registros e resultados observáveis;
- `COMPUTACIONAL`: descreve resultado de Rule, Policy e motor identificados;
- `PROVENIENCIA`: descreve origem, transformação, aprovação e dependências;
- `NORMATIVA`: descreve interpretação adotada por Policy aprovada;
- `JURIDICA`: declara aplicabilidade, legalidade, responsabilidade, fraude, sanção, obrigação ou efeito jurídico.

O motor genérico não emite afirmação `JURIDICA` sem perfil especializado, autoridade competente e revisão e aprovação registradas. Afirmação `NORMATIVA` não transforma interpretação privada em entendimento oficial.

## AssertionScope

Escopo imutável que acompanha toda afirmação produzida pelo Titan.

Registra, quando aplicável, AssertionType, objeto, Subject, Organization, finalidade, período, instante de referência, jurisdição, Policy, Rules, motor, versões, dados e Evidences considerados ou excluídos, limitações, lacunas, códigos de razão e autoridade declarada.

API, interface, relatório, Publication e Dossier preservam tipo e escopo. Afirmação sem escopo não pode ser apresentada como conclusão do Titan.

---

# 11. Sustentabilidade, métricas e divulgações

O Core fornece conceitos genéricos para informações de sustentabilidade. Tópicos, indicadores, fatores, metodologias e regras concretas pertencem a verticais ou perfis aprovados.

A cadeia conceitual é:

```text
Measurement → CalculatedMetric → avaliação especializada
→ SustainabilityAssertion → SustainabilityDisclosure → Publication
```

AssuranceStatement pode avaliar escopo delimitado da cadeia. Nenhum desses objetos é semanticamente intercambiável.

## MetricNature

Natureza controlada do resultado representado por uma métrica.

Valores iniciais: `ATIVIDADE`, `INSUMO`, `PRODUTO_DIRETO`, `RESULTADO`, `IMPACTO`, `RISCO`, `OPORTUNIDADE`, `CONFORMIDADE`, `COMPROMISSO`, `PROGRESSO`, `EXPOSICAO`.

Uma natureza não é convertida automaticamente em outra. Atividade não prova impacto; conformidade não prova desempenho superior; meta não prova progresso; correlação não prova causalidade.

## ValueOrigin

Origem controlada de um valor: `MEDIDO`, `OBSERVADO`, `CALCULADO`, `ESTIMADO`, `MODELADO`, `PREMISSA`, `IMPORTADO`, `PROXY`.

Origem da saída e composição das entradas permanecem separadas. Estimativa, modelo, premissa ou proxy nunca são apresentados como medição.

## MetricDefinition

Definição versionada de métrica.

Preserva código, versão, MetricNature, propósito, grandeza, unidade, período, limites permitidos, metodologia, dados exigidos, qualidade, incerteza, agregação, arredondamento, Evidence e perfis aplicáveis.

Versão publicada é imutável. Mesmo nome não torna definições equivalentes.

## Measurement

Observação ou valor de entrada registrado segundo MetricDefinition.

Preserva Subject, Organization, período, instante, valor e unidade originais, ReportingBoundary, método de obtenção, ValueOrigin, Source, Actor, Evidence, Provenance, VerificationStatus, UncertaintyStatement, cobertura, lacunas e limitações.

Valor sem definição, unidade, período ou limite não é métrica publicável. Conversão preserva regra, unidade original, precisão e arredondamento.

## UncertaintyStatement

Declaração estruturada sobre incerteza.

Tipos iniciais: `INCERTEZA_DE_MEDICAO`, `INCERTEZA_DE_MODELO`, `INCERTEZA_DE_FATOR`, `INCERTEZA_DE_COBERTURA`, `INCERTEZA_DE_CLASSIFICACAO`, `DESCONHECIDA`.

Registra origem, limites, confiança quando aplicável, distribuição ou método, propagação, sensibilidade, arredondamento e limitações. Ausência de base quantitativa não autoriza intervalo inventado.

## DataQualityAssessment

Avaliação versionada de qualidade para finalidade e perfil delimitados.

Pode considerar completude, atualidade, precisão, consistência, representatividade, rastreabilidade, validação, cobertura e proporção estimada. O Core não produz score universal de qualidade.

## CalculationMethod

Método versionado e imutável que define fórmula, entradas, unidades, conversões, fatores, precedência, ausências, estimativas, incerteza, tolerância e arredondamento.

Adequação científica, normativa ou jurídica depende de perfil, Policy e aprovação; reprodutibilidade técnica não a comprova.

## CalculatedMetric

Resultado computado por CalculationMethod identificado.

Preserva MetricDefinition, entradas e Digests, unidades, conversões, método, fatores, versões, ReportingBoundary, período, intermediários necessários, ausências, ValueOrigins, UncertaintyStatement, motor, tolerância, warnings, Actor e AssertionScope.

Reprodução confirma resultado equivalente dentro da tolerância para o mesmo material e método. Componente novo produz simulação ou reavaliação.

## ReportingBoundary

Limite versionado de Organization, operações, Subjects, período, território, cadeia de valor, consolidação, inclusões, exclusões e critérios.

Limites organizacional, operacional, geográfico e de cadeia são distintos. RecordOwnerOrganization não determina controle operacional, responsabilidade jurídica ou inclusão em divulgação.

## Baseline

Referência versionada para comparação de uma MetricDefinition dentro de ReportingBoundary, período, método e perfil declarados.

## RebaseliningAssessment

Avaliação autorizada da necessidade de restabelecer Baseline por correção, mudança metodológica, melhoria de dados, alteração de limite ou evento relevante.

Preserva baseline anterior, motivo, diferença, método, período, objetos potencialmente afetados, Evidence e aprovação.

## RestatedBaseline

Nova Baseline correlacionada à anterior e sustentada por RebaseliningAssessment.

Não altera divulgações históricas. Resultado anterior continua vinculado à Baseline original salvo republicação explícita.

## Target

Meta versionada que define MetricDefinition, valor, unidade, período, ReportingBoundary, Baseline, trajetória, responsável, aprovação, validade e perfil.

## ProgressAssessment

Avaliação de Measurement ou CalculatedMetric contra Target por método identificado.

Meta, desempenho observado, previsão, progresso e atingimento permanecem separados. Meta não atingida não é NonConformity sem Policy aplicável.

## MaterialityAssessment

Avaliação versionada de materialidade para tipo, perfil, tópico, stakeholders, Organization, cadeia de valor, período, método, thresholds, Evidence e aprovação declarados.

Pode tratar materialidade de impacto, financeira, dupla, regulatória ou contratual. Resultado de um tipo ou perfil não é convertido automaticamente em outro. Evidence insuficiente produz `INDETERMINADA` ou revisão, nunca omissão silenciosa.

## ComparabilityAssessment

Avaliação de compatibilidade entre métricas ou divulgações.

Considera definição, MetricNature, ReportingBoundary, período, método, fatores, unidade, DataQualityAssessment, cobertura, ValueOrigin, incerteza e ajustes.

Resultados: `COMPARAVEL`, `COMPARAVEL_COM_AJUSTES`, `PARCIALMENTE_COMPARAVEL`, `NAO_COMPARAVEL`, `INDETERMINADA`.

## DisclosureProfile

Perfil versionado que mapeia definições, materialidade, períodos, limites, unidades, omissões, métodos, validações e alegações permitidas para referencial, jurisdição, contrato ou audiência.

O Core não presume perfil universal nem converte automaticamente resultados entre perfis.

## SustainabilityAssertionKind

Finalidade controlada de SustainabilityAssertion.

Valores iniciais: `RESULTADO_MEDIDO`, `RESULTADO_CALCULADO`, `CONFORMIDADE_METODOLOGICA`, `CONFORMIDADE_DA_DIVULGACAO`, `COMPROMISSO_DE_META`, `PROGRESSO_DA_META`, `ALEGACAO_COMPARATIVA`, `REFERENCIA_DE_ASSEGURACAO`, `REFERENCIA_DE_CERTIFICACAO`, `ALEGACAO_DE_IMPACTO`.

Não substitui AssertionType. Alegação comparativa exige ComparabilityAssessment; alegação de impacto exige método adequado à associação, atribuição ou causalidade declarada.

## SustainabilityAssertion

Afirmação autorizada sobre sustentabilidade.

Preserva AssertionType, SustainabilityAssertionKind, AssertionScope, métricas, período, ReportingBoundary, DisclosureProfile, método, Evidence, UncertaintyStatement, omissões, aprovação e limitações.

Não declara automaticamente que Organization, produto ou cadeia é sustentável.

## DisclosureAudience

Audiência controlada de divulgação: `INTERNA`, `CONTRATUAL`, `CLIENTE`, `AUDITOR`, `REGULATORIA`, `PUBLICA`.

Autorização para uma audiência não permite reutilização em outra.

## SustainabilityDisclosure

Snapshot imutável preparado para divulgação de sustentabilidade.

Identifica Organization, escopo, período, DisclosureAudience, canal, jurisdição, idioma, DisclosureProfile, índice de conteúdo, Assertions, métricas, métodos, fatores, limites, Baseline, Targets, progresso, cobertura, ValueOrigins, lacunas, omissões, incerteza, comparabilidade, aprovações, AssuranceStatements, Publication, Digests, correções e versões correlacionadas.

SustainabilityDisclosure não é Publication. Tradução cria Artifact correlacionado com idiomas, processo, revisão, Digest e versão prevalente definida pelo perfil.

## AssuranceStatement

Declaração de asseguração sobre escopo delimitado.

Preserva provedor, identidade, competência declarada, padrão e versão, código e rótulo do nível, conclusão, período, procedimentos, amostragem, material, limitações, relacionamento com o Subject, interesse financeiro, outros serviços, conflito declarado, base de independência, Signature e Evidence.

Nível somente é interpretado dentro do padrão. Independência é afirmação sustentada, não conclusão automática. Asseguração parcial não cobre toda Organization ou divulgação.

## CertificationReference

Referência imutável a certificado ou esquema de certificação, contendo esquema, titular, organismo, escopo, validade, auditoria, suspensão, uso de marca e Evidence.

## CertificationStatus

Estado temporal e verificável da CertificationReference para instante e fonte declarados.

Certificação, CertificationStatus e AssuranceStatement são conceitos distintos. Nenhum comprova sustentabilidade universal.

## LicenseConstraint

Restrição versionada de uso de conteúdo, registrando titular ou provider, licença, usos permitidos, exportação, redistribuição, limite de citação, validade e restrições.

Digest não concede licença. Direito de armazenar não implica direito de exportar ou redistribuir.

## Lacunas, agregação e mudanças

Razões iniciais de lacuna: `NAO_COLETADO`, `INDISPONIVEL`, `NAO_APLICAVEL`, `FORA_DO_ESCOPO`, `ACESSO_RESTRITO`, `FONTE_INDISPONIVEL`, `METODOLOGIA_NAO_SUPORTADA`. Lacuna não é zero; omissão preserva razão e efeito potencial.

Agregação preserva componentes, origem, unidades, conversões, ReportingBoundaries, cobertura, estimativas, lacunas, qualidade e dupla contagem possível. Tópicos heterogêneos não são compensados ou normalizados em score sem DisclosureProfile explícito, método, pesos, ausências, aprovação e warnings.

Motivos de mudança distinguem `CORRECAO_DE_DADOS`, `ATUALIZACAO_DE_METODO`, `ATUALIZACAO_DE_FATOR`, `MUDANCA_DE_LIMITE`, `MUDANCA_DE_PERFIL`, `REESTABELECIMENTO_DE_BASELINE`, `NOVA_EVIDENCIA`, `ESTIMATIVA_SUBSTITUIDA`. Evolução não implica fraude ou greenwashing anterior.

---

# 12. Não conformidades

## NonConformity

Registro auditável de falha, lacuna ou condição que exige tratamento.

Pode ser causada por RuleResult com falha, Evidence ausente ou inválida, divergência entre Sources, sequência impossível de Events, quebra de integridade, conflito de sincronização ou descumprimento de processo.

Deve registrar identificador, Organization, Subject, origem, severidade, período afetado, responsável, prazo, ação corretiva, Evidence da correção, reavaliação, estado, encerramento e histórico.

Ciclo de vida inicial:

```text
DETECTADA → CLASSIFICADA → ATRIBUIDA → EM_CORRECAO → PRONTA_PARA_REAVALIACAO → ENCERRADA
```

Encerramento nunca remove histórico.

---

# 13. Dossiês

## Dossier

Snapshot auditável, imutável e autocontido de Decision, Evaluation ou processo de conformidade.

Pode conter Subject, finalidade, Facts, Claims, Evidences, Sources, SourceSnapshots, ProvenancePaths, ValidationAssessments, EvidenceAdmissibilityAssessments, Events, Corrections, SupersessionRelations, ImpactAssessments, relações, Policy e versão, Rules e versões, NormativeBasisSnapshot, Evaluation, DecisionProposal, Decision, DecisionReasons, Reviews, Challenges, Overrides, DecisionRelations, AssertionScopes, métricas, cálculos, ReportingBoundaries, MaterialityAssessments, SustainabilityAssertions, SustainabilityDisclosures, AssuranceStatements, CertificationReferences, DataClassifications, ProcessingActivity, PrivacyImpactAssessment, RetentionAssignments, LegalHolds ou DispositionReports referenciados, lacunas, limitações de exportação, incertezas, NonConformities, ações corretivas, versões, timestamps, hash, Signature e código de verificação.

Dossier não incorpora automaticamente atributos pessoais apenas porque referencia classificação, atividade ou titular.

Deve permitir compreender e verificar a Decision sem depender de consultas posteriores ao banco, quando tecnicamente viável.

PDF é representação do Dossier, não sua fonte primária.

---

# 14. Auditoria, integridade e linha do tempo

## Audit

Capacidade de reconstruir quem realizou ação, em qual Organization, quando, com qual origem, versão e dados, quais alterações ocorreram e quais Decisions foram produzidas.

Audit não é apenas log técnico.

## SensitiveAccessProfile

Perfil versionado de obrigação de Audit por recurso e operação.

Preserva DataClassifications, operações, Purposes, Actors, capacidades, Organizations, FieldScopes, canais, ambientes, milestones, granularidade, sincronismo, integridade, retenção, transparência, aprovação e limitações. Perfis aplicáveis compõem-se restritivamente.

## AccessOperation

Intenção lógica imutavelmente identificada de acesso. Preserva AccessOperationId, IdempotencyKey, correlação, origem e contexto.

## AccessAttempt

Tentativa técnica identificada de executar AccessOperation.

Retry preserva a operação lógica e recebe AccessAttemptId próprio. Timeout ou resultado desconhecido não cria nova operação automaticamente.

## DataAccessRecord

Registro imutável de exatamente um AccessMilestone.

Preserva operação, attempt, MilestoneId, principal, Actor, DecisionAuthority quando houver, capacidade, ServiceIdentity executora, destinatário, Organizations, recurso e versão ou referência segura, Purpose, scopes, grants, Authorization, Channel, Device, ambiente, instantes, correlação, BulkAccessScope, Evidences, códigos e limitações.

Não acumula status nem copia payload, token, secret, query arbitrária ou atributo protegido por conveniência.

## AccessMilestone

Marco observado: `SOLICITADO`, `NEGADO`, `AUTORIZADO`, `EXECUCAO_INICIADA`, `EXECUCAO_CONCLUIDA`, `DADOS_NAO_ENCONTRADOS_NO_ESCOPO`, `RESPOSTA_PRODUZIDA`, `ENTREGA_TECNICA_CONFIRMADA`, `ENTREGA_TECNICA_INDETERMINADA`, `APRESENTACAO_A_USUARIO_CONFIRMADA`, `FALHA`.

Marco posterior não é inferido do anterior. Apresentação comprova somente interação técnica definida, nunca leitura, compreensão, concordância ou efeito jurídico.

## AccessTrace

Projection reconstruível dos DataAccessRecords de AccessOperation.

Preserva attempts, sequência, branches, lacunas, duplicações, milestones obrigatórios, estado técnico, completude e limitações. Não é fonte autoritativa paralela.

## BulkAccessScope

Escopo imutável de acesso a múltiplos objetos.

Preserva critério e versão, snapshot ou cursor, recursos, período, Organizations, FieldScope, Purpose, limites, contagens esperada, examinada, retornada, omitida, inacessível, indeterminada e não examinada, Digest com cobertura, truncamento e limitações.

## BulkAccessCompletionStatus

Conclusão controlada do lote: `COMPLETO`, `PARCIAL_POR_LIMITE`, `PARCIAL_POR_AUTORIZACAO`, `PARCIAL_POR_FALHA`, `PARCIAL_POR_TIMEOUT`, `PARCIAL_POR_CANCELAMENTO`, `INDETERMINADO`.

## PrivilegedAccessSession

Sessão imutavelmente identificada para acesso privilegiado ou emergencial.

Preserva Purpose controlado, solicitante, aprovadores, autoridade, justificativa, escopo, ambiente, início, expiração, autenticação, segregação, operações, records, Evidence, alertas, comportamento ao expirar e revisão.

É negada por padrão, mínima e temporal. Não cria Purpose novo nem acesso universal.

## AuditCompletenessAssessment

Avaliação imutável da suficiência de Audit para escopo, período e finalidade declarados.

Preserva perfil, fontes, sequências, lacunas, duplicações, falhas, relógios, checkpoints, método, Actor e limitações; avalia separadamente completude estrutural, de fontes, temporal, de perfil e integridade.

Resultados: `COMPLETA`, `COMPLETA_COM_LIMITACOES`, `INCOMPLETA`, `INDETERMINADA`. Limitação que impede conclusão não permite `COMPLETA_COM_LIMITACOES`; ausência de record não prova ausência de acesso.

## AuditTier

Nível controlado: `TIER_0_NEGOCIO`, `TIER_1_ACESSO_A_AUDIT`, `TIER_2_ADMINISTRACAO_E_VERIFICACAO`.

Policy limita recursão material. Último tier mantém integridade, segregação e controle sem autorreferência infinita.

## AccessTransparencyPolicy

Policy versionada de metadados de acesso reveláveis a audiência específica.

Preserva elegibilidade, recursos, Purposes, consultantes, campos, granularidade, atraso, agregação, redaction, exceções, investigações, segurança, segredos, terceiros, validade e limitações.

Identidade usa `IDENTIDADE_COMPLETA`, `ORGANIZACAO_APENAS`, `CATEGORIA_DO_CONSULTANTE`, `PSEUDONIMIZADA` ou `NAO_REVELADA`. Atraso possui motivo, prazo e revisão.

## AccessTransparencyReport

Relatório imutável e versionado derivado de DataAccessRecords sob AccessTransparencyPolicy e Authorization.

Preserva audiência, report scope, source record scope, excluded scope, coverage boundary, período, records ou agregados, redactions, omissões, AuditCompletenessAssessment, Digest e limitações.

Tipos: `RELATORIO_COMPLETO_DO_PERIODO`, `RELATORIO_INCREMENTAL`, `RELATORIO_DE_CORRECAO`, `RELATORIO_DE_ATUALIZACAO_DE_POLITICA`. Ausência de consultante não prova ausência de acesso.

## Timeline

Projeção cronológica de Events, Claims, Corrections, relações e mudanças relevantes.

Não é fonte de verdade independente e deve ser reconstruível a partir do histórico.

## Integrity

Capacidade de detectar alteração indevida e verificar encadeamento dos registros por serialização canônica, hashes, cadeia de hashes, algoritmos versionados, checkpoints, Signatures ou armazenamento externo imutável.

Integrity não significa veracidade.

## CanonicalSerialization

Representação determinística e versionada usada para hashes e Signatures.

Entradas semanticamente equivalentes devem produzir a mesma representação canônica.

---

# 15. Confiabilidade operacional

## IdempotencyKey

Identificador que impede efeitos duplicados.

Mesma chave com mesmo conteúdo produz o mesmo efeito lógico. Mesma chave com conteúdo diferente gera conflito.

## OptimisticConcurrency

Mecanismo que impede perda silenciosa de atualização concorrente.

Conflitos devem ser explícitos.

## OutboxMessage

Registro transacional de mensagem a ser publicada para processamento assíncrono.

Preserva identificador, Organization, tipo, payload versionado, correlação, causação, tentativas, status e timestamps.

Estado definitivo nunca deve existir apenas no broker.

## Projection

Estrutura de leitura derivada de Events e registros imutáveis.

Não é fonte de verdade, não contém regra de negócio própria, respeita Organization e deve ser reconstruível.

---

# 16. Localização e transferência de dados

## DataLocationProfile

Perfil imutável e versionado para armazenamento, processamento, backup, recuperação, suporte, acesso, chaves e transferência. Preserva categorias, jurisdições, Organizations, ProcessingActivities, Purposes, DataContracts, subprocessadores, proteções, validade, Evidence e limitações. Configuração não comprova localização efetiva ou validade jurídica.

## DataLocationAssignment

Vínculo imutável entre objeto ou escopo, DataClassification e DataLocationProfile. Acompanha cópias e derivados; múltiplas origens compõem todas as restrições, e redução exige assessment, fundamento, Evidence e aprovação.

## JurisdictionMappingVersion

Tradução imutável e versionada entre região nativa do provider e jurisdição canônica. Preserva provider, região, jurisdição, Source, vigência, método, Evidence e limitações. Região sem mapping vigente permanece desconhecida.

## DataLocationInventory

Inventário versionado de armazenamentos, processamentos, acessos, cópias e fluxos esperados e observados. Preserva cobertura, fontes, lacunas, freshness, regiões, providers, subprocessadores, retenção, ConfidenceAssessment e Evidence. Inventário parcial não comprova residência.

## DataTransferAssessment

Avaliação imutável de movimento ou acesso transfronteiriço delimitado. Resultados: `AUTORIZAVEL`, `AUTORIZAVEL_COM_RESTRICOES`, `REVISAO_JURIDICA_NECESSARIA`, `NAO_AUTORIZAVEL`, `INDETERMINADA`. Resultado técnico não é parecer jurídico.

## TransferAuthorization

Autorização imutável para movimento específico ou classe estritamente delimitada após DataTransferAssessment. Preserva origem, destino, campos, Purpose, volume, prazo, mecanismo, condições, autoridade, aprovações e revogação. Não substitui Authorization, LegalBasis ou ConsentRecord.

## DataMovementRecord

Registro append-only de movimento tentado, iniciado, concluído, parcial, negado ou desconhecido. Preserva autorização, objetos, origem e destino observados, Digests, transportador, ServiceIdentity, instantes, receipt, Evidence e limitações.

## TransferMechanismReference

Referência versionada a mecanismo jurídico ou contratual alegado para transferência. Preserva jurisdição, partes, período, documento, Source, Digest, aprovação e Evidence. Não comprova suficiência, aplicabilidade ou execução conforme as condições.

## SupportAccessSession

Sessão delimitada de suporte ou administração remota. Preserva Actor, ServiceIdentity, Organization, localização do operador, Purpose, ticket, escopo, prazo, grants, PrivilegedAccessSession, TransferAuthorization e DataAccessRecords.

## DataLocationObservation

Observação imutável de localização configurada, declarada ou tecnicamente observada. Preserva fonte, método, instante, cobertura, ConfidenceAssessment, Evidence e limitações; não constitui avaliação jurídica.

## DataLocationReconciliation

Comparação imutável entre assignments, inventário, observações e movimentos. Resultados: `CONFORME_PERFIL`, `DIVERGENTE`, `INCOMPLETA`, `LOCALIZACAO_DESCONHECIDA`, `EM_REMEDIACAO`. Divergência não move ou apaga dados automaticamente.

---

# 17. Resposta a incidentes e preservação forense

## IncidentSignal

Observação potencialmente relevante de segurança ou privacidade. Preserva Source, DetectionRule, instantes, escopo seguro, correlação, confiança operacional, Evidence e limitações. Sinal não é incidente confirmado.

## IncidentTriage

Assessment imutável que classifica sinal como `DESCARTADO_COM_JUSTIFICATIVA`, `MONITORAMENTO`, `CORRELACIONADO`, `CASO_ABERTO` ou `INDETERMINADO`. Descarte não elimina o sinal nem impede reabertura.

## IncidentCase

Agregado de coordenação de incidente potencial ou confirmado. Preserva Organizations, papéis, equipe, escopo, ativos, sinais, Evidence, decisões, ações, comunicações, holds, impactos, limitações e timeline.

## IncidentKnowledgeState

Snapshot imutável do conhecimento disponível em determinado instante: fatos confirmados, hipóteses, descartados, desconhecidos, escopo, impacto, causa, dados, titulares, obrigações, recuperação, Sources, confiança e limitações.

## IncidentAssessment

Avaliação imutável do incidente para escopo, snapshot e instante. Resultados: `NAO_CONFIRMADO`, `SUSPEITO`, `CONFIRMADO`, `INDETERMINADO`. Causa, autoria, culpa, fraude e responsabilidade não são inferidas da confirmação.

## IncidentSeverityProfile

Perfil versionado para avaliar impacto técnico, operacional, pessoal, regulatório, contratual e na cadeia. Não produz severidade universal sem escopo, cobertura e Evidence.

## ResponseDecision

Decisão autorizada para conter, preservar, investigar, comunicar, recuperar ou monitorar. Preserva authority, knowledge state, escopo, risco da ação, Evidence, prazo, dependências e rollback.

## ResponseAction

Execução append-only de ResponseDecision. Estados: `PENDENTE`, `EM_EXECUCAO`, `CONCLUIDA`, `PARCIAL`, `FALHOU`, `RESULTADO_DESCONHECIDO`, `CANCELADA`. Resultado técnico aceito não comprova efeito concluído.

## ForensicCollection

Coleta imutável e autorizada de material, com Source, método, ferramenta e versão, instantes, TimeConfidence, escopo, Digests, original, cópia de trabalho, erros, classificação, retenção e limitações.

## ChainOfCustody

Sequência append-only de custódias do Artifact original e derivados. Registra custodiantes, propósito, ação, local, instantes, proteção, receipt, autorização e Evidence. Não comprova admissibilidade jurídica automaticamente.

## IncidentPreservationScope

Escopo imutável de objetos, sistemas, períodos, Organizations, categorias, derivados e exclusões a preservar. LegalHold impede disposição sem ampliar Authorization.

## CommunicationAssessment

Assessment imutável por audiência, jurisdição, base e contrato sobre necessidade, conteúdo, canal e prazo. Resultados: `COMUNICACAO_NAO_EXIGIDA_NO_ESCOPO`, `COMUNICACAO_EXIGIDA`, `COMUNICACAO_VOLUNTARIA`, `REVISAO_JURIDICA_NECESSARIA`, `INDETERMINADA`.

## CommunicationProfile

Perfil versionado de fonte normativa, trigger, calendário, timezone, destinatário, conteúdo mínimo e modalidades preliminar, complementar e corretiva. O Core não fixa prazo universal.

## IncidentCommunication

Registro imutável de comunicação preparada, aprovada, enviada, aceita pelo canal, corrigida ou complementada. Envio não comprova entrega, leitura, compreensão ou efeito jurídico.

## CommunicationDeliveryAssessment

Avaliação imutável da entrega: `ENTREGA_COMPROVADA_NO_CANAL`, `ACEITACAO_PELO_CANAL`, `ENTREGA_PROVAVEL`, `ENTREGA_INDETERMINADA`, `FALHA_CONFIRMADA`.

## RecoveryAssessment

Avaliação imutável da prontidão para recuperar. Resultados: `APTA_PARA_RECUPERACAO`, `APTA_COM_RESTRICOES`, `RECUPERACAO_PARCIAL`, `NAO_APTA`, `INDETERMINADA`. Disponibilidade não comprova integridade, confidencialidade ou completude.

## IncidentClosure

Encerramento autorizado que reconcilia ações, comunicações, LegalHolds, impactos, recuperação, lacunas e riscos residuais. Não elimina possibilidade de reabertura nem apaga fechamento anterior.

## PostIncidentReview

Revisão imutável de timeline, hipóteses, causa conhecida, controles, gaps, métricas e lições. Não altera assessments históricos.

## ImprovementRecommendation

Recomendação pós-incidente sem efeito automático sobre Policy, retenção, configuração, Authorization, arquitetura ou fornecedor.

## ImprovementDecision

Decisão autorizada sobre ImprovementRecommendation. Quando aprovada, produz ActionPlan próprio com escopo, owner, dependências, prazo, validação e rollback.

## ActionPlan

Plano imutável e versionado para executar ImprovementDecision aprovada. Preserva ações, responsáveis, dependências, prazos, critérios de validação, riscos, rollback, estados, Evidence e limitações. Não altera controles apenas por existir.

---

# 18. Exportação, portabilidade e encerramento

## ExportRequest

Solicitação imutável de exportação com requester, capacidade, Organization, destinatário, Purpose, scope, formato, período, canal, fundamento e IdempotencyKey.

## ExportScope

Escopo imutável de objetos, versões, Subjects, Organizations, campos, relações, Provenance, anexos, derivados, formatos, exclusões e redactions. Expansão exige novo request.

## ExportAssessment

Assessment de exportabilidade por componente. Resultados: `AUTORIZAVEL`, `AUTORIZAVEL_COM_REDUCAO`, `REVISAO_NECESSARIA`, `NAO_AUTORIZAVEL`, `INDETERMINADA`.

## PortabilityAssessment

Assessment imutável da portabilidade para solicitante, destinatário, jurisdição, fundamento e instante. Preserva interoperabilidade, semântica, terceiros, licenças, contratos, Evidence e limitações; não é parecer jurídico.

## ExportAuthorization

Autorização própria e imutável para ExportScope, destinatário, Purpose, ExportProfile, canal, prazo, volume, downloads, condições e aprovadores. Nunca é inferida de autorização de leitura.

## ExportProfile

Perfil versionado de schema, vocabulário, serialização, unidades, timezone, relações, divisão, manifesto, Digests, Provenance, redactions, compatibilidade e validação.

## ExportOperation

Operação append-only e idempotente de geração. Preserva snapshot, versões, cursor, contagens, tentativas, executor, Digests, estado, Evidence e limitações.

## ExportPackage

Pacote lógico imutável, distinto de arquivo ou container, composto por ExportManifest, componentes, ExportChunks, assinaturas e material de verificação autorizados.

## ExportManifest

Descrição canônica e imutável do pacote: objetos, schemas, relações, componentes, ManifestDigest, PackageDigest, ChunkDigests, redactions, licenças, warnings, lacunas e limitações.

## LicenseEvidence

Evidence versionada do direito ou restrição alegada para exportar e redistribuir conteúdo licenciado. Não cria licença nem amplia permissão.

## ExportChunk

Parte imutável e retomável com PackageId, range, identidade semântica, tamanho, ChunkDigest, tentativa e conclusão. Retry não muda conteúdo.

## ExportDeliveryAssessment

Assessment da entrega: `ENTREGA_COMPROVADA_NO_CANAL`, `ACEITACAO_PELO_CANAL`, `ENTREGA_PROVAVEL`, `ENTREGA_INDETERMINADA`, `FALHA_CONFIRMADA`. Não comprova importação, leitura ou uso.

## ImportValidationReport

Relatório de validação estrutural, semântica e criptográfica do ExportPackage. Não confirma Authorization, verdade ou equivalência de negócio.

## ImportAssessment

Assessment da importabilidade para destino e Purpose delimitados. Resultados: `IMPORTAVEL`, `IMPORTAVEL_COM_RESTRICOES`, `IMPORTACAO_PARCIAL`, `INCOMPATIVEL`, `REVISAO_NECESSARIA`, `INDETERMINADA`.

## ExportReconciliation

Reconciliação entre componentes esperados, gerados, entregues, omitidos, falhos e desconhecidos. Arquivo existente não comprova conclusão.

## ExportedCopyRecord

Registro do conhecimento sobre pacote entregue, destinatário, finalidade, restrições, contrato e revogação. Não representa controle remoto da cópia.

## OffboardingPlan

Plano versionado de encerramento com serviços, principals, grants, Devices, integrações, credentials, keys, dados, exports, contratos, holds, incidentes, terceiros e dependências.

## ExitInventory

Inventário observado de dados, backups, exports, VerificationBundles, Audit, caches, offline, tokens, webhooks, jobs, filas, Devices, keys, domains e subprocessadores, com destino autorizado por item.

## OffboardingAssessment

Assessment da viabilidade do plano. Resultados: `EXECUTAVEL`, `EXECUTAVEL_COM_RESTRICOES`, `AGUARDANDO_DEPENDENCIAS`, `BLOQUEADO`, `INDETERMINADO`.

## OffboardingDecision

Decisão autorizada sobre plano, assessment, fases, riscos, dependências, exceções e critérios de conclusão. Exportar, revogar, transferir, preservar e dispor continuam ações distintas.

## HandoverRecord

Registro imutável de entrega de pacote, controle ou responsabilidade delimitada. Aceite não comprova importação, assunção jurídica universal ou eliminação na origem.

## OffboardingReconciliation

Reconciliação do ExitInventory com exports, handovers, revogações, holds, disposições, terceiros e desconhecidos. Remanescente desconhecido impede conclusão completa.

---

# 19. Sincronização e operação offline

## OfflineCapabilityProfile

Perfil versionado que classifica operação como `PERMITIDA_OFFLINE`, `PERMITIDA_OFFLINE_COM_LIMITES`, `CONEXAO_OBRIGATORIA` ou `PROIBIDA_OFFLINE`.

Preserva comando, Purpose, Organization, capacidade, FieldScope, DataContract, DataClassification, prazo, volume, dependências, Evidence, relógio, proteção local e sincronização. Ausência de perfil proíbe operação offline.

## OfflineSession

Sessão local previamente estabelecida online e vinculada a principal, ExternalIdentity, Actor, Device, Organization e capacidade.

Preserva início, expiração, último contato, AuthenticationAssurance, OfflineCapabilityProfile e encerramento. Não cria autorização permanente nem executa MFA remotamente.

## OfflineAuthorizationSnapshot

Snapshot imutável e curto da autorização materializada para Device, principal, capacidade, Organization, Permission, grants, AccessPurpose, FieldScope, DataContract, Policy, emissão, expiração e limitações.

Permite captura dentro da menor restrição aplicável, mas não garante aceitação futura nem cria, amplia, delega ou reativa grant.

## DeviceTrustAssessment

Avaliação temporal da confiança operacional disponível para Device, finalidade e instante delimitados.

Preserva registro, integridade disponível, versão, proteção local, revogação conhecida, vínculo, sinais de comprometimento, validade e limitações. Não representa segurança absoluta nem substitui Authorization.

## LocalPreview

Resultado orientativo local com estado `PREVIA_LOCAL_NAO_OFICIAL`, distinto de DecisionProposal e Decision.

Preserva OfflineOperation, Policy materializada, dados, Evidences, freshness, motor, resultado estimado e limitações. Não produz Publication, grant, elegibilidade oficial, efeito regulatório ou ação downstream.

## OfflineOperation

Operação criada em dispositivo ou cliente desconectado.

Registra identificador único, identidade semântica canônica, Organization, Actor, Device, sessão, autorização materializada, horário local, horário alegado do fato, TimeConfidence, sequência local, contrato, conteúdo mínimo, IdempotencyKey, dependências e Evidences.

OfflineOperation não produz Decision oficial no dispositivo.

## SynchronizationBatch

Conjunto delimitado de OfflineOperations enviado ao servidor. Preserva BatchId, versão, manifesto, contagem, Digest, fronteira de sequência e instante do Device.

Cada operação possui confirmação individual. Lote parcialmente aceito deve permitir retomada sem duplicação.

Integridade do lote não substitui integridade individual e ordem física não cria causalidade.

## SynchronizationBatchResult

Resultado agregado e reconstruível do lote.

Estados iniciais: `RECEBIDO`, `VALIDADO_PARCIALMENTE`, `PROCESSADO_PARCIALMENTE`, `PROCESSADO`, `EM_RECONCILIACAO`, `REJEITADO_ESTRUTURALMENTE`, `RESULTADO_INDETERMINADO`.

Preserva manifesto, operações esperadas e examinadas, contagens por resultado, lacunas, tentativas e limitações. Nunca substitui SynchronizationResults individuais.

## SynchronizationResult

Resultado da sincronização.

Estados iniciais: `ACEITA`, `REJEITADA`, `DUPLICADA`, `CONFLITANTE`, `DEPENDENCIA_PENDENTE`, `EM_QUARENTENA`, `RESULTADO_DESCONHECIDO`.

`ACEITA` exige efeito oficial e resultado recuperável comprometidos na fronteira transacional aplicável. Resultado desconhecido representa conhecimento de um participante e permanece reconciliável.

Conflitos nunca são resolvidos silenciosamente.

## SynchronizationConflict

Conflito entre operação offline, estado atual, versão esperada ou Policy vigente.

Registra operação, motivo, estado observado, alternativas, Actor responsável, resolução e timestamp. Inclui reutilização divergente de IdempotencyKey, dependência incompatível e ciclo, sem last-write-wins.

---

# 20. Integrações

## Integration

Componente externo ao domínio responsável por comunicação com outros sistemas.

Não escreve diretamente em modelos de domínio. Produz Commands, Claims, Evidences ou Events por contratos públicos, deve ser idempotente e não pode contornar autorização ou isolamento.

## MappingVersion

Versão imutável da tradução entre contrato externo e contrato interno.

Preserva SourceProfile, schema externo, regras de transformação, parser compatível, validade, aprovação e Digest. Mudança de significado cria nova versão; correção não reescreve resultados históricos.

## ContractCompatibilityAssessment

Avaliação imutável da compatibilidade entre versões delimitadas de contrato e MappingVersion.

Resultados iniciais: `COMPATIVEL`, `PARCIAL`, `INCOMPATIVEL`, `DESCONHECIDA`. Preserva diferenças, campos afetados, SourceCapabilities, testes, Evidence, limitações, assessor e instante. Compatibilidade estrutural não comprova equivalência semântica.

## SourceCapabilities

Declaração versionada e sustentada por Evidence das capacidades técnicas de SourceProfile e contrato específicos.

Pode descrever snapshot consistente, paginação estável, filtros, assinatura, idempotência, consulta de status, callback, rate limit, freshness e limites. Capacidade não é presumida nem transferida entre versões ou Sources.

## ReplayProtectionEvidence

Evidence de execução de controle contra replay em interação externa delimitada.

Preserva identificador não secreto ou nonce, timestamp observado, Digest, janela aceita, mecanismo, resultado e limitações. Não comprova unicidade universal nem ausência de replay fora da janela observada.

## ParsingAssessment

Avaliação imutável da interpretação técnica de Artifact ou Document externo.

Preserva origem, parser e versão, MappingVersion, formatos esperado e detectado, campos produzidos, warnings, erros, conteúdo ignorado, limites, resultado e Evidence. Parsing bem-sucedido não confirma correção ou verdade do conteúdo.

---

# 21. Estado

## State

Representação atual derivada do histórico.

Pode ser atualizado ou recalculado, mas não substitui Events, não apaga Corrections e não altera Decisions passadas.

---

# 22. Recall

## Recall

Capacidade de navegar retrospectiva e prospectivamente pela Genealogy para identificar Subjects, Decisions e Dossiers potencialmente afetados.

Considera Organization, autorização, janela temporal, origem, destino, profundidade, ciclos, relações, Evidences e lacunas.

Resultado incompleto deve ser marcado como inconclusivo.

Mudança normativa pode iniciar análise autorizada para localizar objetos cuja Provenance cruza NormativeInstrumentVersion, NormativeProvision, NormativeBasis, Policy ou Rule afetada.

Correction, nova Evidence, fator, método, Baseline, ReportingBoundary, DisclosureProfile ou LicenseConstraint também podem iniciar análise autorizada sobre Measurements, CalculatedMetrics, Targets, avaliações, SustainabilityAssertions, SustainabilityDisclosures, Publications e Dossiers dependentes.

ClassificationAssessment, ClassificationPropagation, DataContract, ProcessingActivity, DataProcessingRoleAssignment, ConsentRecord, AnonymizationAssessment ou PrivacyImpactAssessment novos ou alterados podem localizar objetos e fluxos potencialmente afetados sem invalidá-los automaticamente.

RetentionReview, LegalHold, DispositionAssessment ou DispositionReport podem localizar objetos, Decisions, Publications, Dossiers e fluxos potencialmente afetados sem invalidá-los ou iniciar Recall automaticamente.

SourceSnapshot, ValidationAssessment, CurrentValidationAssessment, ConflictAssessment ou EvidenceAdmissibilityAssessment novos podem localizar dependentes potencialmente afetados sem reescrever o conhecimento histórico ou iniciar Recall automaticamente.

DecisionReview, DecisionChallenge, DecisionOverride, Reevaluation, DecisionRelation ou nova Decision podem localizar State, NonConformities, Dossiers, Publications, Sharings e integrações potencialmente afetados sem invalidá-los ou iniciar Recall automaticamente.

O resultado `POTENCIALMENTE_AFETADO` indica necessidade potencial de revisão. Não significa inválido e não modifica Decision, Dossier, Publication, Signature ou Evidence.

Detecção técnica, avaliação regulatória, decisão de negócio, comunicação e execução são etapas distintas. Recall operacional exige caso de uso específico, Policy aprovada e Actor competente; alteração normativa não o inicia automaticamente.

## ImpactTrigger

Gatilho imutável de análise de impacto que referencia mudança e versão, ChangeKind, instante, solicitante, finalidade, escopo inicial, Authorization e códigos. Não prova impacto.

## ImpactScope

Escopo imutável de navegação por Provenance e relações.

Delimita direção, profundidade, período, objetos, dependências, Organizations, finalidade, DataClassifications, exclusões, Authorization, parada e truncamento. Alteração cria nova análise.

## ImpactAssessment

Avaliação imutável relativa a ImpactTrigger, ImpactScope, snapshot, Policy e instante declarados.

Preserva consistência temporal, ProvenancePaths, esperados, visitados, não avaliados, inacessíveis, profundidade, truncamentos, dependências, lacunas, ciclos, motor, Actor, códigos e limitações.

Estados por objeto: `NAO_AFETADO`, `NAO_AVALIADO`, `POTENCIALMENTE_AFETADO`, `AFETADO_CONFIRMADO`, `INDETERMINADO`, `INACESSIVEL`.

`NAO_AFETADO` exige avaliação suficiente. Ausência de caminho, inventário parcial, autorização insuficiente, limite ou método incompleto não provam ausência de dependência. Mudança concorrente exige snapshot novo ou resultado indeterminado.

## ImpactFinding

Achado imutável sobre dependência específica.

Preserva objeto e versão, caminho, tipo de dependência, campo ou pressuposto, estado, Evidence, materialidade contextual, confiança, limitações e ações candidatas.

Tipos iniciais: `DIRETA`, `INDIRETA`, `DERIVADA`, `SEMANTICA`, `NORMATIVA`, `TEMPORAL`, `OPERACIONAL`, sob vocabulário versionado. Caminhos correlacionados da mesma Source não aumentam confiança ou materialidade automaticamente.

## ImpactResponseDirective

Diretiva imutável dentro de ImpactResponseDecision para resposta, escopo e findings determinados.

Tipos iniciais: `NENHUMA_ACAO`, `MONITORAR`, `REAVALIAR`, `CORRIGIR`, `RESTRINGIR`, `REVOGAR_PARA_NOVOS_EFEITOS`, `REPUBLICAR`, `COMUNICAR`, `ABRIR_NAO_CONFORMIDADE`, `INICIAR_ANALISE_DE_RECALL`.

Estados iniciais: `PENDENTE`, `EM_EXECUCAO`, `CONCLUIDA`, `PARCIAL`, `FALHOU`, `RESULTADO_DESCONHECIDO`, `CANCELADA`. Preserva executor, prioridade, prazo, dependências, idempotência, resultado, Evidence e limitações.

## ImpactResponseDecision

Decisão autorizada sobre resposta a ImpactFindings.

Preserva AuthorityProfile, Policy, Actor, escopo, findings, razões, aprovações, diretivas e limitações. Cada diretiva usa caso de uso próprio; conclusão global exige reconciliação de todas elas.

ImpactFinding não executa ação. `AFETADO_CONFIRMADO` não significa inválido, fraudulento ou juridicamente ineficaz.

## RecallRequest

Solicitação delimitada de Recall, contendo Subject inicial, direção, janela temporal, profundidade máxima, tipos de relação, Organization e escopo de autorização.

## RecallResult

Resultado explicável contendo caminhos, Subjects potencialmente afetados, Events e Evidences sustentadores, lacunas, limites, Decisions e Dossiers potencialmente afetados, AssertionScope, códigos de razão e status de conclusão.

Não declara automaticamente obrigatoriedade, dispensa, culpa, fraude ou extensão final de recall.

---

# 23. Linguagem oficial

Os termos abaixo possuem significado reservado no Titan Core e não devem ser substituídos por sinônimos no código sem decisão formal:

- Organization
- RecordOwnerOrganization
- User
- AuthenticatedPrincipal
- ServiceIdentity
- Membership
- Role
- Permission
- OrganizationContext
- Visibility
- Issuer
- Publication
- Sharing
- AccessPurpose
- GrantScope
- GrantScopeResolution
- FieldScope
- PrincipalCapacityBinding
- SharingRequest
- GrantAssessment
- AuthorizationGrant
- AccessRestriction
- GrantConflictAssessment
- EffectiveAuthorizationScope
- Authorization
- Actor
- Subject
- Asset
- Identity
- Identifier
- SubjectReference
- Claim
- Fact
- Event
- DomainEvent
- Correction
- Revocation
- ChangeKind
- CorrectionRequest
- CorrectionScope
- CorrectionAssessment
- SupersessionRelation
- CurrentProjection
- Evidence
- EvidenceReference
- Source
- NormativeInstrument
- NormativeInstrumentVersion
- NormativeProvision
- NormativeRelation
- NormativeReference
- Channel
- Device
- Artifact
- Provenance
- ConfidenceLevel
- Validity
- VerificationStatus
- EvidenceOriginType
- SourceProfile
- SourceSnapshot
- ProvenanceLink
- ProvenancePath
- ValidationScope
- ValidationRequest
- ValidationAttempt
- ValidationAssessment
- ConfidenceAssessment
- FreshnessProfile
- FreshnessAssessment
- EvidenceAdmissibilityAssessment
- ConflictAssessment
- ConflictMaterialityAssessment
- CurrentValidationAssessment
- DataClassification
- ClassificationOrigin
- ClassificationConfidence
- ClassificationAssessment
- ClassificationPropagation
- IdentifiabilityLevel
- DataSensitivity
- DataSubjectReference
- PersonalDataReference
- ProcessingContext
- LegalBasisReference
- ConsentRecord
- ProcessingActivity
- DataProcessingRole
- DataProcessingRoleAssignment
- DataContract
- AnonymizationAssessment
- PrivacyImpactAssessment
- RetentionPolicy
- RetentionClock
- TimeConfidence
- RetentionAssignment
- RetentionConflictAssessment
- RetentionReview
- LegalHold
- DispositionScope
- DispositionAssessment
- LogicalDisposition
- PhysicalDisposition
- DispositionOperation
- DispositionReceipt
- DispositionReconciliation
- DispositionReport
- Document
- DocumentReference
- Signature
- UniversalRelation
- Genealogy
- Transformation
- Batch
- BatchMembership
- Policy
- Rule
- NormativeBasis
- NormativeBasisSnapshot
- RuleResult
- Evaluation
- Decision
- DecisionResult
- EvaluationOutcome
- DecisionProposal
- DecisionReason
- DecisionAuthorityProfile
- DecisionReview
- DecisionChallenge
- ReviewEvidenceSubmission
- ReviewAssessment
- DecisionOverride
- Reevaluation
- DecisionRelation
- DecisionEngine
- HistoricalReproduction
- HistoricalComplianceAssessment
- CounterfactualSimulation
- CurrentReevaluation
- AssertionType
- AssertionScope
- MetricNature
- ValueOrigin
- MetricDefinition
- Measurement
- UncertaintyStatement
- DataQualityAssessment
- CalculationMethod
- CalculatedMetric
- ReportingBoundary
- Baseline
- RebaseliningAssessment
- RestatedBaseline
- Target
- ProgressAssessment
- MaterialityAssessment
- ComparabilityAssessment
- DisclosureProfile
- SustainabilityAssertionKind
- SustainabilityAssertion
- DisclosureAudience
- SustainabilityDisclosure
- AssuranceStatement
- CertificationReference
- CertificationStatus
- LicenseConstraint
- NonConformity
- Dossier
- Audit
- SensitiveAccessProfile
- AccessOperation
- AccessAttempt
- DataAccessRecord
- AccessMilestone
- AccessTrace
- BulkAccessScope
- BulkAccessCompletionStatus
- PrivilegedAccessSession
- AuditCompletenessAssessment
- AuditTier
- AccessTransparencyPolicy
- AccessTransparencyReport
- Timeline
- Integrity
- CanonicalSerialization
- IdempotencyKey
- OptimisticConcurrency
- OutboxMessage
- Projection
- OfflineOperation
- OfflineCapabilityProfile
- OfflineSession
- OfflineAuthorizationSnapshot
- DeviceTrustAssessment
- LocalPreview
- SynchronizationBatch
- SynchronizationBatchResult
- SynchronizationResult
- SynchronizationConflict
- Integration
- MappingVersion
- ContractCompatibilityAssessment
- SourceCapabilities
- ReplayProtectionEvidence
- ParsingAssessment
- DataLocationProfile
- DataLocationAssignment
- JurisdictionMappingVersion
- DataLocationInventory
- DataTransferAssessment
- TransferAuthorization
- DataMovementRecord
- TransferMechanismReference
- SupportAccessSession
- DataLocationObservation
- DataLocationReconciliation
- IncidentSignal
- IncidentTriage
- IncidentCase
- IncidentKnowledgeState
- IncidentAssessment
- IncidentSeverityProfile
- ResponseDecision
- ResponseAction
- ForensicCollection
- ChainOfCustody
- IncidentPreservationScope
- CommunicationAssessment
- CommunicationProfile
- IncidentCommunication
- CommunicationDeliveryAssessment
- RecoveryAssessment
- IncidentClosure
- PostIncidentReview
- ImprovementRecommendation
- ImprovementDecision
- ActionPlan
- ExportRequest
- ExportScope
- ExportAssessment
- PortabilityAssessment
- ExportAuthorization
- ExportProfile
- ExportOperation
- ExportPackage
- ExportManifest
- LicenseEvidence
- ExportChunk
- ExportDeliveryAssessment
- ImportValidationReport
- ImportAssessment
- ExportReconciliation
- ExportedCopyRecord
- OffboardingPlan
- ExitInventory
- OffboardingAssessment
- OffboardingDecision
- HandoverRecord
- OffboardingReconciliation
- State
- Recall
- ImpactTrigger
- ImpactScope
- ImpactAssessment
- ImpactFinding
- ImpactResponseDirective
- ImpactResponseDecision
- RecallRequest
- RecallResult

---

# 24. Proibições de modelagem

O Titan Core não deve:

Cada proibição possui identificador estável para rastreabilidade em testes, revisões e critérios de aceite. Novas proibições recebem novos identificadores; identificadores existentes não são renumerados nem reutilizados.

- **P-001** — tratar Claim como verdade;
- **P-002** — tratar ConfidenceLevel como verdade;
- **P-003** — confundir Identity com Identifier;
- **P-004** — confundir Actor com Source;
- **P-005** — confundir Source com Channel;
- **P-006** — tratar Digest como prova de oficialidade ou autoridade;
- **P-007** — tratar Source oficial, SourceSnapshot, Signature ou Digest como verdade material;
- **P-008** — ampliar ValidationScope entre request, assessment e admissibilidade;
- **P-009** — apresentar ProvenancePath incompleto como grafo completo;
- **P-010** — tratar fonte indisponível ou resultado desconhecido como conteúdo inválido;
- **P-011** — converter resultado desconhecido de integração em inexistência, rejeição ou falha de negócio;
- **P-012** — acoplar Domain a provider, endpoint, protocolo, SDK ou payload externo;
- **P-013** — tratar compatibilidade estrutural como equivalência semântica;
- **P-014** — presumir SourceCapabilities ou reutilizá-las entre versões ou Sources;
- **P-015** — interpretar campo desconhecido como zero, vazio, falso ou confirmado;
- **P-016** — apresentar paginação, lote ou parsing parcial como completo;
- **P-017** — tratar ReplayProtectionEvidence como prova universal de ausência de replay;
- **P-018** — tratar ParsingAssessment bem-sucedida como verdade do conteúdo;
- **P-019** — confundir localização configurada, declarada, observada e juridicamente avaliada;
- **P-020** — tratar região de provider como jurisdição sem JurisdictionMappingVersion vigente;
- **P-021** — apresentar DataLocationInventory parcial como residência comprovada;
- **P-022** — escolher o DataLocationAssignment menos restritivo entre múltiplas origens;
- **P-023** — autorizar restore, teste, processamento ou suporte apenas porque backup foi autorizado;
- **P-024** — tratar criptografia como ausência de localização ou transferência;
- **P-025** — ignorar acesso remoto ou administração de chaves por não haver cópia conhecida;
- **P-026** — apresentar DataTransferAssessment técnico como parecer jurídico;
- **P-027** — tratar TransferMechanismReference como prova de validade ou execução conforme;
- **P-028** — converter localização desconhecida ou Evidence vencida em destino permitido;
- **P-029** — apresentar revogação de TransferAuthorization como eliminação de cópia entregue;
- **P-030** — promover IncidentSignal automaticamente a incidente confirmado;
- **P-031** — inferir autoria, culpa, fraude ou responsabilidade de IncidentAssessment;
- **P-032** — calcular severidade sem IncidentSeverityProfile, cobertura e Evidence;
- **P-033** — confundir contenção, isolamento, erradicação, mitigação, recuperação e encerramento;
- **P-034** — permitir LegalHold ou investigação ampliar Authorization;
- **P-035** — sobrescrever Artifact original durante ForensicCollection;
- **P-036** — ocultar lacuna de ChainOfCustody ou apresentá-la como admissibilidade jurídica;
- **P-037** — invalidar Decision, Dossier ou Publication apenas por dependência com incidente;
- **P-038** — aplicar resultado de CommunicationAssessment a outra audiência ou jurisdição;
- **P-039** — apresentar aceitação pelo canal como leitura humana;
- **P-040** — reescrever comunicação preliminar por complemento ou correção;
- **P-041** — restaurar grant, Purpose, classificação ou direito de uso apenas por restore técnico;
- **P-042** — apresentar disponibilidade restaurada como integridade ou confidencialidade comprovada;
- **P-043** — encerrar IncidentCase com resultados desconhecidos sem reconciliação;
- **P-044** — remover LegalHold automaticamente no IncidentClosure;
- **P-045** — reescrever IncidentKnowledgeState por nova Evidence;
- **P-046** — alterar Policy ou arquitetura diretamente por ImprovementRecommendation;
- **P-047** — inferir ExportAuthorization de autorização de leitura;
- **P-048** — incluir componente sem ExportAssessment e ExportAuthorization aplicáveis;
- **P-049** — apresentar ExportManifest divergente do pacote;
- **P-050** — retomar ExportChunk com identidade semântica ou conteúdo diferente;
- **P-051** — tratar entrega como importação, leitura ou uso;
- **P-052** — apresentar ImportAssessment parcial como importação integral;
- **P-053** — remover Provenance, unidade, timezone, licença ou limitação na exportação;
- **P-054** — tratar LicenseEvidence como criação ou ampliação de licença;
- **P-055** — alterar RecordOwnerOrganization ou ownership histórico por portabilidade;
- **P-056** — apresentar ExportedCopyRecord como controle remoto da cópia;
- **P-057** — tratar OffboardingPlan como exclusão automática;
- **P-058** — concluir offboarding com ExitInventory parcial ou remanescente desconhecido;
- **P-059** — remover Actor, Audit ou Evidence histórica no encerramento;
- **P-060** — prometer portabilidade de chave não exportável;
- **P-061** — estender validação de campo aos campos não avaliados;
- **P-062** — usar ConfidenceLevel como score ordinal universal;
- **P-063** — apresentar ConfidenceAssessment como probabilidade de verdade ou fraude;
- **P-064** — avaliar freshness sem FreshnessProfile aplicável;
- **P-065** — reescrever assessment histórico com CurrentValidationAssessment;
- **P-066** — resolver conflito pelo último valor ou pela Source mais oficial sem assessment;
- **P-067** — reutilizar ConflictMaterialityAssessment fora da finalidade avaliada;
- **P-068** — confundir VerificationStatus com admissibilidade da Policy;
- **P-069** — tratar aprovação privada como entendimento oficial;
- **P-070** — confundir NormativeInstrument, NormativeBasis, Policy e Rule;
- **P-071** — selecionar fundamentação apenas pela data da Decision;
- **P-072** — projetar conhecimento posterior como conhecimento original;
- **P-073** — apresentar CounterfactualSimulation como Decision histórica;
- **P-074** — apresentar DecisionProposal como Decision oficial;
- **P-075** — emitir Decision sem Evaluation ou DecisionAuthorityProfile aplicável;
- **P-076** — produzir DecisionReason sem código, Rule, Evidence ou limitação exigida;
- **P-077** — permitir que revisão altere RuleResult, Evaluation ou Decision histórica;
- **P-078** — suspender, revogar ou invalidar Decision automaticamente por DecisionChallenge;
- **P-079** — aceitar Evidence de review sem validação e admissibilidade aplicáveis;
- **P-080** — executar DecisionOverride sem autoridade, justificativa, escopo, validade ou aprovação;
- **P-081** — tratar override como condição satisfeita ou correção de dado;
- **P-082** — reescrever história quando override expirar;
- **P-083** — apresentar decisão assistida como puramente humana;
- **P-084** — permitir que IA ou cliente escolha resultado ou autoridade;
- **P-085** — iniciar ação downstream ou Recall automaticamente por review ou nova Decision;
- **P-086** — emitir afirmação sem AssertionType ou AssertionScope;
- **P-087** — classificar anomalia ou inconsistência automaticamente como fraude;
- **P-088** — tratar `POTENCIALMENTE_AFETADO` como inválido;
- **P-089** — iniciar recall automaticamente por alteração normativa;
- **P-090** — confundir DataClassification, LegalBasisReference, ConsentRecord e AuthorizationGrant;
- **P-091** — confundir ProcessingContext com OrganizationContext;
- **P-092** — tratar ProcessingActivity ou DataContract como autorização;
- **P-093** — inferir DataProcessingRole de ownership, armazenamento ou posse dos bytes;
- **P-094** — reduzir classificação sem Policy, Evidence e aprovação;
- **P-095** — remover classificação por OCR, IA, embedding, agregação ou transformação;
- **P-096** — tratar embedding, hash, pseudônimo ou agregado como anônimo automaticamente;
- **P-097** — produzir ou consumir campo ou finalidade fora de DataContract;
- **P-098** — apresentar PrivacyImpactAssessment como relatório regulatório sem perfil;
- **P-099** — tratar vencimento, solicitação ou revogação como descarte automático;
- **P-100** — permitir que cliente escolha política, ação ou remova LegalHold livremente;
- **P-101** — confundir LegalHold com Authorization ou nova finalidade;
- **P-102** — pausar RetentionClock sem regra e evento verificável;
- **P-103** — tratar LogicalDisposition como PhysicalDisposition concluída;
- **P-104** — apresentar resultado parcial, desconhecido ou não reconciliado como concluído;
- **P-105** — tratar DispositionReceipt como Evidence automaticamente;
- **P-106** — preservar payload descartado, hash previsível ou segredo de reconstrução no relatório;
- **P-107** — considerar crypto-shredding completo com cópia em claro, backup ou escrow acessível;
- **P-108** — corrigir projeção reescrevendo histórico;
- **P-109** — usar score universal de minimização;
- **P-110** — converter atividade, produto direto ou correlação em impacto automaticamente;
- **P-111** — apresentar estimativa, modelo, premissa ou proxy como medição;
- **P-112** — converter lacuna em zero ou ocultar omissão;
- **P-113** — tratar materialidade como booleano universal;
- **P-114** — comparar métricas sem compatibilidade de definição, limite, método e qualidade;
- **P-115** — alterar Baseline ou divulgação histórica silenciosamente;
- **P-116** — apresentar Target como progresso ou atingimento;
- **P-117** — compensar tópicos heterogêneos sem DisclosureProfile explícito;
- **P-118** — confundir SustainabilityDisclosure com Publication;
- **P-119** — ampliar DisclosureAudience sem nova autorização;
- **P-120** — confundir AssuranceStatement, CertificationReference e CertificationStatus;
- **P-121** — presumir independência do assegurador por seu tipo;
- **P-122** — apresentar tradução como original sem correlação e versão prevalente;
- **P-123** — tratar Digest como permissão de uso ou redistribuição;
- **P-124** — incorporar indicador específico de vertical ao Core;
- **P-125** — usar Document como sinônimo de Evidence;
- **P-126** — tratar Authorization permitida como acesso executado;
- **P-127** — acumular milestones em DataAccessRecord mutável;
- **P-128** — inferir marco posterior exclusivamente do anterior;
- **P-129** — tratar retry técnico como nova AccessOperation;
- **P-130** — copiar valor arbitrário, payload, token ou query para Audit;
- **P-131** — revelar existência de recurso por tentativa negada;
- **P-132** — apresentar lote parcial, truncado ou não examinado como completo;
- **P-133** — usar Digest sem declarar cobertura;
- **P-134** — ocultar Actor originador pela ServiceIdentity executora;
- **P-135** — executar acesso privilegiado sem Purpose, escopo, prazo, aprovação e revisão;
- **P-136** — permitir acesso sensível quando Audit obrigatória falhar silenciosamente;
- **P-137** — tratar ausência de record como prova de ausência de acesso;
- **P-138** — confundir completude estrutural com cobertura das fontes;
- **P-139** — apresentar IntegrityCheckpoint como prova de completude absoluta;
- **P-140** — acessar ou administrar Audit sem tier, autorização e Evidence aplicáveis;
- **P-141** — revelar consultante, investigação ou terceiro fora da AccessTransparencyPolicy;
- **P-142** — apresentar relatório parcial como universo completo;
- **P-143** — reescrever relatório quando surgir record tardio;
- **P-144** — tratar apresentação técnica como leitura ou compreensão;
- **P-145** — apresentar rejeição do servidor como prova de que acesso offline local não ocorreu;
- **P-146** — apresentar LocalPreview como Decision oficial ou omitir suas limitações;
- **P-147** — permitir operação offline sem OfflineCapabilityProfile aplicável;
- **P-148** — tratar OfflineAuthorizationSnapshot como garantia de aceitação futura;
- **P-149** — presumir Device confiável com DeviceTrustAssessment expirado;
- **P-150** — reutilizar IdempotencyKey para identidade semântica diferente;
- **P-151** — usar ordem física do lote como causalidade;
- **P-152** — apresentar resultado agregado do lote como resultado individual;
- **P-153** — tratar `RESULTADO_DESCONHECIDO` como ausência, sucesso ou falha;
- **P-154** — descartar cópia local apenas porque a operação foi aceita;
- **P-155** — alterar Event histórico;
- **P-156** — alterar Decision histórica;
- **P-157** — apagar Corrections;
- **P-158** — tratar toda evolução, nova Evidence ou método como Correction;
- **P-159** — aplicar Correction fora de CorrectionScope;
- **P-160** — criar SupersessionRelation cíclica, autorreferente ou sem autoridade;
- **P-161** — selecionar CurrentProjection apenas pelo timestamp mais recente;
- **P-162** — aceitar mudança concorrente por last-write-wins;
- **P-163** — apresentar análise truncada, parcial ou inacessível como completa;
- **P-164** — tratar objeto não avaliado ou inacessível como `NAO_AFETADO`;
- **P-165** — contar caminhos correlacionados da mesma Source como confirmações independentes;
- **P-166** — aplicar materialidade de ImpactFinding fora da finalidade avaliada;
- **P-167** — tratar `AFETADO_CONFIRMADO` como invalidação ou revogação automática;
- **P-168** — permitir que ImpactFinding execute ação;
- **P-169** — apresentar diretivas parciais ou desconhecidas como resposta concluída;
- **P-170** — apresentar aceitação pelo broker como recebimento pelo destinatário;
- **P-171** — usar Timeline como fonte independente;
- **P-172** — conceder acesso apenas porque existe relação entre Organizations;
- **P-173** — aceitar AccessPurpose, Permission, OrganizationContext ou scope fornecido pelo cliente como confiável;
- **P-174** — resolver beneficiário apenas por e-mail, nome, client ID ou token subject;
- **P-175** — emitir grant sem GrantAssessment ou autoridade;
- **P-176** — permitir crescimento de conjunto fixo ou critério dinâmico sem versão e limites;
- **P-177** — usar grant após perda de Membership, capacidade ou competência;
- **P-178** — apresentar autorização parcial como integral;
- **P-179** — revelar Digest, Identifier, metadado, Provenance ou anexo fora de FieldScope;
- **P-180** — reutilizar leitura para exportação, derivação, inferência, IA ou redistribuição sem autorização própria;
- **P-181** — ignorar AccessRestriction diante de grant positivo;
- **P-182** — somar grants entre AccessPurposes ou Organizations silenciosamente;
- **P-183** — permitir subgrant mais amplo ou utilizável após suspensão do pai;
- **P-184** — autorizar por cache baseado em Membership ou grant encerrado;
- **P-185** — tratar cache hit como existência, Authorization ou validade material atual;
- **P-186** — tratar cache miss como inexistência;
- **P-187** — permitir que TTL ou eviction executem retenção ou disposição;
- **P-188** — usar cache, lease ou lock como fonte de verdade ou autoridade para commit crítico;
- **P-189** — usar deduplicação efêmera como prova de efeito ou substituta de Inbox;
- **P-190** — aceitar fencing token sem validação no recurso autoritativo;
- **P-191** — transformar falha de cache em resposta vazia conclusiva;
- **P-192** — compartilhar cache entre Organizations, Purposes, ambientes ou versões;
- **P-193** — armazenar token, secret, PII ou payload bruto em cache ou key;
- **P-194** — tratar entrada restaurada como confiável sem nova admissão;
- **P-195** — tratar VerificationCode como grant privado;
- **P-196** — apresentar Revocation como eliminação de cópia já entregue;
- **P-197** — criar, ampliar ou reativar grant offline;
- **P-198** — distinguir externamente registro inexistente de registro invisível sem autorização;
- **P-199** — tratar RecordOwnerOrganization como propriedade jurídica automática;
- **P-200** — confundir ownership, Visibility, Publication, Sharing e Authorization;
- **P-201** — aceitar OrganizationContext, Roles ou Permissions fornecidos pelo cliente como confiáveis;
- **P-202** — conceder acesso universal a ServiceIdentity ou Actor de plataforma;
- **P-203** — tratar Membership humano como única forma possível de autorização;
- **P-204** — depender de conceitos específicos de uma vertical;
- **P-205** — armazenar senha, token ou secret no domínio;
- **P-206** — permitir que Integrations escrevam diretamente em entidades internas;
- **P-207** — usar State atual como substituto do histórico.

---

# 25. Regra de evolução

Antes de implementar novo conceito:

1. definir o nome canônico;
2. explicar o significado;
3. definir invariantes;
4. indicar relações com conceitos existentes;
5. confirmar se pertence ao Core ou a uma vertical;
6. registrar ADR quando houver impacto arquitetural;
7. obter aprovação;
8. somente então implementar.

Arquitetura descreve capacidades possíveis.

O plano de implementação determina quando cada capacidade passa a existir.
