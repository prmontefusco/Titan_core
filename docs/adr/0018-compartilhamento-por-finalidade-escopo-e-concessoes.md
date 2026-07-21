# ADR 0018 — Compartilhamento por finalidade, escopo e concessões
**Status:** Aceita  
**Data:** 21 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan possui Organizations relacionadas, RecordOwnerOrganization, Issuer, Publication, Sharing, AuthorizationGrant, Visibility e Authorization. O modelo excede multi-tenancy simples: uma Organization pode emitir, compartilhar, consultar ou ser afetada sem se tornar owner do registro.

Dados também possuem ProcessingActivity, DataContract, DataClassification, retenção e papéis jurídicos próprios. Nenhum desses conceitos concede acesso isoladamente.

## Problema

Definir:

- finalidade controlada e escopo imutável de concessão;
- beneficiários humanos, não humanos e institucionais;
- campos, representações, ações, tempo, condições e delegação;
- criação, renovação, suspensão, revogação e conflitos;
- autorização concreta, derivados, offline e cópias exportadas.

## Princípios

1. **Negação por padrão:** relação, identificador, contrato ou autenticação não concedem acesso.
2. **Finalidade validada:** valor do cliente é solicitação não confiável; servidor resolve propósito permitido.
3. **Menor privilégio:** grant delimita beneficiário, recurso, ações, campos, período e condições.
4. **Sem transferência implícita:** concessão não muda ownership, Issuer, Publication ou papel jurídico.
5. **Revogação prospectiva:** impede novos acessos controlados sem apagar uso ou cópia histórica.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| `tenant_id` e Role global | Simplicidade | Não representa relações, finalidade ou campos |
| ACL por registro | Controle direto | Explosão de entradas e pouca semântica de propósito |
| Scope livre fornecido pelo cliente | Flexibilidade | Injeção de escopo e decisões inconsistentes |
| Token carregar toda autorização | Menos consultas | Grants revogados ou alterados permanecem no token |
| Grants versionados e Authorization por operação | Explicação e revogação | Mais avaliações, cache e auditoria |

## Decisão

Manter AuthorizationGrant como conceito canônico produzido por Sharing e avaliado em cada operação protegida.

Adicionar AccessPurpose, GrantScope, FieldScope, SharingRequest, GrantAssessment e GrantConflictAssessment. OrganizationContext e Authorization são construídos pelo servidor a partir do estado interno vigente.

Grant restringe o acesso possível; não garante que operação concreta será permitida. DataContract restringe o fluxo; não concede acesso.

Os novos conceitos são candidatos arquiteturais e dependem de aprovação no `DOMAIN.md`.

## Distinções obrigatórias

```text
RecordOwnerOrganization
≠ Visibility
≠ Sharing
≠ Publication
≠ AuthorizationGrant
≠ Authorization
≠ DataContract
≠ LegalBasisReference
≠ ConsentRecord
≠ DataProcessingRole
```

RecordOwnerOrganization define responsabilidade interna pelo registro. Visibility define descobribilidade contextual. Sharing solicita e produz grant. Publication torna versão elegível para audiência. Authorization decide uma operação.

## AccessPurpose

Finalidade controlada, estável e versionada para acesso.

Preserva código em português, descrição, categoria, operações compatíveis, tipos de recurso, beneficiários, Organizations, requisitos de Evidence, DataClassifications permitidas, ProcessingActivities, validade, aprovação e limitações.

Valores iniciais candidatos: `CUIDADO_OPERACIONAL`, `ANALISE_PRE_CONTRATUAL`, `EXECUCAO_CONTRATUAL`, `INSPECAO_REGULATORIA`, `AUDITORIA`, `INVESTIGACAO_DE_RECALL`, `SUPORTE_AUTORIZADO`, `INVESTIGACAO_DE_SEGURANCA`.

Perfis de vertical acrescentam propósitos próprios. Mesmo nome textual não torna finalidades equivalentes. Purpose não é escolhido livremente pelo cliente e não substitui LegalBasisReference.

## GrantScope

Escopo imutável e versionado de AuthorizationGrant.

Delimita recursos ou tipos, IDs ou conjunto autorizado, Subjects, relações, período factual, Organization, ações, FieldScope, Purpose, audiência, canal, jurisdição, derivados, exportação, frequência, volume, condições e exclusões.

Scope expression é contrato controlado, versionado e validado pelo servidor. Expressão arbitrária fornecida pelo cliente é proibida.

Mudança de objeto, campo, ação, finalidade ou condição cria novo GrantScope e nova avaliação. Escopo não é ampliado por interpretação conveniente.

## GrantScopeResolution

Resolução imutável de GrantScope em modo `CONJUNTO_FIXO`, `CRITERIO_DINAMICO` ou `SNAPSHOT_AUTORIZADO`.

Preserva critério controlado e versão, instante, objetos ou conjunto resolvido, Digest, quantidade, limites, exclusões e resultado. Conjunto fixo não cresce; critério dinâmico é reavaliado em cada Authorization e não aceita expressão arbitrária do cliente.

## FieldScope

Conjunto versionado de campos, projeções ou representações autorizadas.

Preserva campos permitidos, proibidos e condicionais, redactions, agregações, precisão, metadados, material derivado, formato, audiência e limitações.

Autorizar existência, metadado, resumo, Dossier, Document ou payload integral são decisões distintas. Campo ausente do scope permanece negado.

FieldScope não remove DataClassification e não apresenta pseudônimo ou agregado como anônimo automaticamente.

Digest, Identifier, nome, metadado, Provenance e existência de anexo também são campos protegidos. Ausência no FieldScope é negação, não omissão interpretável.

Leitura não implica exportação, derivação, inferência, treinamento de IA ou redistribuição; cada ação exige previsão própria.

## Beneficiário e concedente

Beneficiário pode ser Organization, User por vínculo aplicável, ServiceIdentity, autoridade institucional, auditor, integração ou Device autenticável.

Grant identifica principal interno estável, tipo, Organization beneficiária quando aplicável e capacidade. E-mail, client ID, token subject ou nome não são beneficiários canônicos isolados.

Concedente registra Organization, Actor, capacidade, Permission, autoridade sobre o recurso, DecisionAuthorityProfile quando aplicável e Evidence.

RecordOwnerOrganization pode definir política padrão, mas não é automaticamente a única entidade juridicamente capaz de conceder. Perfil, contrato ou autoridade aplicável resolve competência sem alterar owner.

## PrincipalCapacityBinding

Vínculo imutável do beneficiário à capacidade usada pelo grant, preservando principal interno, Membership, ServiceIdentity ou vínculo institucional, Organization, capacidade, validade, Evidence e condições.

Perda de vínculo, capacidade ou competência torna o grant não utilizável sem apagar o histórico. Mesmo User não reutiliza grant emitido para outra capacidade.

## SharingRequest

Solicitação imutável de nova concessão, renovação, redução, suspensão ou revogação.

Preserva solicitante, concedente alegado, beneficiário, AccessPurpose, GrantScope, período, condições, justificativa, Evidence, correlação, DataClassification e IdempotencyKey.

Request não cria Visibility, não reserva acesso e não é grant. Cliente não fornece Permission, competência, status ou cadeia de delegação confiáveis.

## GrantAssessment

Avaliação imutável anterior à emissão ou alteração de AuthorizationGrant.

Preserva request, identidade e estado dos participantes, autoridade do concedente, owner, Purpose, scope, Permissions, DataContract, ProcessingActivity, LegalBasisReferences quando aplicáveis, classificação, retenção, conflitos, riscos, aprovações, ReasonCodes e limitações.

Resultados iniciais: `AUTORIZAVEL`, `REDUCAO_NECESSARIA`, `APROVACAO_ADICIONAL_NECESSARIA`, `REVISAO_NECESSARIA`, `REJEITADA`, `INDETERMINADA`.

Assessment não concede acesso. Resultado autorizável ainda exige emissão explícita do grant.

## AuthorizationGrant

Grant emitido preserva request e assessment, concedente, beneficiário, AccessPurpose e versão, GrantScope, Permissions, início, expiração, condições, estado, aprovações, delegação permitida, correlação e histórico.

Estados iniciais: `PLANEJADA`, `ATIVA`, `SUSPENSA`, `EXPIRADA`, `REVOGADA`, `SUBSTITUIDA`.

Transições são autorizadas e auditáveis. Grant suspenso, expirado, revogado ou substituído não autoriza nova operação. Reativação exige transição prevista ou novo grant.

Grant não amplia Permissions do concedente, não transfere ownership, não cria Membership e não determina DataProcessingRole.

## Delegação e subgrant

Delegação é proibida por padrão. Grant delegável declara explicitamente beneficiários elegíveis, Purpose, scope máximo, profundidade, prazo, aprovações e responsabilidade.

Subgrant referencia grant pai e não excede sua menor restrição. Suspensão, expiração, revogação ou redução do pai torna descendentes não utilizáveis até avaliação.

Cadeia é acíclica, navegável e limitada. Beneficiário não se torna concedente apenas porque recebeu acesso.

## GrantConflictAssessment

Avaliação imutável de grants, restrições e Policies aplicáveis à mesma operação.

Preserva candidatos, scopes, Purposes, precedência configurada, condições, conflitos, decisão, ReasonCodes e limitações.

Permissões não são somadas silenciosamente entre finalidades ou Organizations. Na ausência de regra segura, Authorization resulta `INDETERMINADA` ou `NEGADA` conforme Policy.

Restrição explícita e grant positivo não são resolvidos por ordem de criação ou “mais recente vence”.

## AccessRestriction

Restrição negativa, explícita e versionada aplicável a principal, capacidade, Organization, recurso, ação, campo, Purpose, período ou condição.

Participa da Authorization e não é ignorada por grant positivo. Exceção exige autoridade, decisão, escopo, validade e auditoria próprios.

## Authorization por operação

Application reconstrói OrganizationContext e avalia AuthenticatedPrincipal, Actor, Organization atuante, owner, Permission, AccessPurpose, grants, GrantScopes, FieldScopes, Visibility, recurso e versão, DataContract, Policy, validade, condições e restrições.

Authorization registra resultado `PERMITIDA`, `NEGADA` ou `INDETERMINADA`, grants e versões considerados, Purpose, escopo efetivo, campos, condições, ReasonCodes, instante e correlação.

Token, cache ou mensagem não substituem grants internos vigentes. Cache de autorização é derivado, curto, invalidável e falha fechado quando seu estado não puder ser confirmado.

Não revelar existência do recurso continua sendo parte do resultado autorizado.

## EffectiveAuthorizationScope

Resultado imutável da interseção restritiva entre Permission, AccessPurpose, grants, GrantScopeResolution, FieldScope, AccessRestrictions, DataContract, DataClassification, Policy e condições vigentes.

Preserva recurso e versão, operação, contexto, instante, grants e restrições considerados, Purpose, campos, representações, derivados, solicitado, autorizado, validade e ReasonCodes.

Dimensões incompatíveis não possuem “menor valor” presumido: conflito falha fechado. Autorização parcial declara redução de escopo e nunca é apresentada como resposta integral.

## Composição e derivados

Quando múltiplos grants forem necessários, cada um permanece identificável. Composição produz interseção segura ou regra explícita; nunca união implícita de privilégios.

Objeto derivado preserva Provenance, DataClassification, AccessPurpose e restrições de origem. Transformação, agregação, exportação, IA ou novo formato não removem FieldScope automaticamente.

Combinar dados de grants diferentes exige Purpose e DataContract compatíveis e avaliação de inferência. Resultado derivado não recebe audiência mais ampla que suas fontes sem decisão específica.

## Publication, Dossier e verificação

Publication pública deliberada pode dispensar grant individual somente para versão, audiência, Purpose e campos publicados. Não torna Evidence subjacente pública.

Dossier, VerificationBundle e Document aplicam Authorization por componente. Acesso ao envelope não concede acesso a todos os anexos ou ProvenancePaths.

VerificationCode resolve Publication e escopo mínimo; não é credencial geral, grant transferível ou bearer token de recursos privados.

## Revogação, suspensão e cópias

Suspensão interrompe novos acessos enquanto preserva possibilidade de revisão. Revocation encerra novos usos controlados no escopo e instante declarados.

Revogar grant não apaga acesso histórico, Decision produzida legitimamente, bundle, arquivo ou cópia já entregue. Impacto sobre uso futuro, retenção ou obrigação de devolução exige Policy, contrato e caso de uso próprios.

Notificações de revogação preservam destinatário, grant, versão, instante, ReasonCode e resultado. Aceitação pelo broker não comprova recebimento ou aplicação pelo destinatário.

## Offline

Criar, ampliar, delegar, reativar, suspender ou revogar grant é `ONLINE_REQUIRED` ou `FORBIDDEN_OFFLINE` conforme Policy.

Cliente offline pode usar autorização materializada somente para Device, capacidade, operações, Purpose, scope e prazo curtos definidos pelo perfil, preservando grants e versões, FieldScope, instante e limitações.

Sincronização revalida identidade, Membership ou ServiceIdentity, grant, cadeia, Purpose, Permission, scope, Visibility, Policy, versão, relógio e revogação. Operação rejeitada permanece auditável.

## Fronteiras arquiteturais

Domain define Purpose, scopes, request, assessment, grant, conflito e invariantes. Não conhece endpoint, token, cache, banco ou policy engine externo.

Application resolve contexto, participantes, autoridade, grants, restrições e Authorization concreta.

Infrastructure persiste e consulta grants, invalida caches, entrega notificações e aplica filtros técnicos. Não decide Purpose, autoridade, precedência ou acesso.

Presentation solicita Organization e Purpose, aplica FieldScope e não diferencia “inexistente” de “não visível” fora da resposta autorizada.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Compartilhamento delimitado; finalidade explícita; revogação; Organizations e serviços suportados |
| Negativas | Avaliação por operação; invalidação de cache; scopes versionados; cadeias de delegação |

## Riscos e controles

| Risco | Controle |
|---|---|
| Relação conceder acesso | Grant explícito e negação por padrão |
| Purpose do cliente ser confiado | Resolução e validação no servidor |
| Campos vazarem | FieldScope e representação autorizada |
| Subgrant ampliar acesso | Cadeia, interseção e profundidade |
| Token preservar grant revogado | Estado interno revalidado |
| Revogação prometer apagar cópia | Efeito prospectivo e limitação explícita |

## Verificação automatizada

Testes futuros devem cobrir:

- relação, Publication, Identifier ou ProvenancePath concedendo acesso implícito;
- Purpose, Permission, OrganizationContext ou scope aceitos do cliente;
- beneficiário resolvido apenas por e-mail, nome, client ID ou token subject;
- grant emitido sem assessment ou autoridade;
- acesso a campo ausente de FieldScope;
- conjunto fixo crescendo ou critério dinâmico sem versão e limites;
- grant usado após perda de Membership, capacidade ou competência;
- concedente competente apenas para parte dos campos emitindo scope integral;
- autorização parcial apresentada como integral;
- derivado revelando campo proibido por inferência;
- Digest, Identifier ou metadado revelando anexo protegido;
- leitura reutilizada para IA, exportação ou redistribuição sem Purpose próprio;
- AccessRestriction ignorada diante de grant positivo;
- metadata Visibility promovida a conteúdo integral;
- grants somados entre Purposes ou Organizations;
- precedência decidida pelo grant mais recente;
- subgrant excedendo pai, profundidade, prazo ou finalidade;
- pai revogado com descendente ainda autorizando;
- pai suspenso sem bloqueio dos subgrants ou filho herdando condição mais fraca;
- cache ou token autorizando grant revogado;
- cache baseado em Membership encerrada;
- derivado, agregação, IA ou exportação removendo restrição;
- envelope de Dossier expondo anexo não autorizado;
- VerificationCode usado como grant privado;
- revogação apresentada como eliminação de cópia;
- operação offline criando ou ampliando grant.
- operação offline após revogação remota com validade local excessiva;
- Purpose textual mapeado para código canônico incorreto;
- resposta permitindo distinguir inexistente de invisível.

## Critérios de aceitação

A ADR pode ser aceita quando:

- AuthorizationGrant permanecer conceito canônico produzido por Sharing;
- AccessPurpose, GrantScope e FieldScope forem controlados e versionados;
- scopes dinâmicos declararem modo, critério, versão, limites e resolução;
- capacidade de beneficiário e concedente for revalidada;
- restrições negativas participarem da decisão;
- EffectiveAuthorizationScope registrar a interseção e eventual redução;
- request e assessment não concederem acesso;
- concedente, beneficiário, owner, Issuer e Organization atuante forem distintos;
- grants humanos, institucionais, técnicos e de Device forem suportados;
- delegação for proibida por padrão e subgrant não exceder o pai;
- conflitos não forem resolvidos por união ou ordem temporal implícita;
- Authorization revalidar grants internos para cada operação;
- leitura, exportação, derivação, inferência, IA e redistribuição permanecerem ações distintas;
- derivados, Publication, Dossier e VerificationBundle preservarem scopes;
- revogação tiver efeito prospectivo sem prometer apagar cópia externa;
- criação e alteração de grants não ocorrerem offline;
- auditoria detalhada de leitura, API, schema, frontend e engine permanecerem fora.

## O que esta ADR não decide

Esta ADR não escolhe:

- tabela, schema, endpoint, UI, cache ou produto de autorização;
- formato de scope expression ou algoritmo de consulta;
- catálogo completo de Purposes de cada vertical;
- base jurídica concreta, contrato ou papel regulatório;
- transparência detalhada de acessos sensíveis, tratada em ADR posterior.

## Plano de reversão

Antes da implementação, esta proposta pode ser substituída. Depois da adoção, mudança preserva Purposes, Scopes, Requests, Assessments, Grants, delegações, conflitos, Authorizations e Revocations históricos.

Reversão não amplia scope, reativa grant, apaga uso anterior ou transforma cópia exportada em controlável.
