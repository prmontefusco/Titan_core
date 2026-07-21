# ADR 0005 — Autenticação com OIDC Provider
**Status:** Aceita  
**Data:** 20 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan
## Contexto

O Titan precisa autenticar Users e ServiceIdentities sem armazenar senhas, implementar protocolo proprietário ou acoplar o Core a fornecedor específico.

O domínio já separa AuthenticatedPrincipal, Actor, OrganizationContext, Membership, Permission, AuthorizationGrant e Authorization. O provedor confirma identidade; o Titan decide se essa identidade pode executar uma operação em determinada Organization.

O frontend de produto não integra o escopo inicial, mas API, Swagger ou console técnico podem precisar iniciar autenticação durante testes.

## Problema

Definir:

- protocolo de autenticação;
- fronteira entre provider e Titan;
- fluxos de User e ServiceIdentity;
- validação de tokens;
- vínculo entre identidade externa e interna;
- MFA, recuperação, sessões e logout;
- indisponibilidade e rotação de chaves;
- operação offline;
- critérios gratuitos e independência de fornecedor.

## Princípios

1. **Autenticação não é Authorization:** token válido não concede acesso de domínio.
2. **Protocolo aberto:** integração ocorre por OIDC/OAuth, não por SDK proprietário obrigatório.
3. **Menor privilégio:** tokens possuem audience, escopos e validade delimitados.
4. **Negação por padrão:** falha de validação interrompe a operação.
5. **Sem credenciais no domínio:** senhas, secrets e tokens não são persistidos como entidades Titan.
6. **Identidade estável:** vínculo usa issuer e subject, não email ou nome mutável.
7. **Fornecedor substituível:** trocar provider não altera Domain ou contratos públicos do Core.
8. **Auditoria segura:** eventos de segurança não registram tokens ou credenciais.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Autenticação própria | Controle integral | Alto risco, senhas, MFA, recovery e protocolos sob responsabilidade do Titan |
| Serviço SaaS proprietário | Operação simplificada | Custo, dependência externa e lock-in |
| SDK específico no domínio | Integração rápida | Acopla Core e contratos ao fornecedor |
| OIDC Provider auto-hospedado | Padrão aberto, controle operacional e substituição | Exige atualização, backup, disponibilidade e segurança operados pelo projeto |

## Decisão

Adotar **OIDC Provider auto-hospedado**, sem assinatura comercial obrigatória, integrado por OpenID Connect e OAuth 2.0.

A escolha do produto será registrada separadamente após avaliação de licença, manutenção, exportação, backup, MFA, recuperação e conformidade com os requisitos desta ADR.

O OIDC Provider é componente operacional externo ao processo, banco e ciclo de release do monólito Titan, ainda que seja administrado pela mesma organização.

## Fronteira de responsabilidades

### OIDC Provider

- autentica identidade;
- administra credenciais;
- aplica política de senha quando houver;
- executa MFA e recuperação de acesso;
- mantém sessões de autenticação;
- emite, renova e revoga tokens conforme capacidades suportadas;
- publica discovery metadata e chaves;
- audita eventos próprios de identidade.

### Titan

- vincula identidade externa a User ou ServiceIdentity;
- mantém Organization, Membership, Role, Permission e AuthorizationGrant;
- constrói OrganizationContext;
- executa Authorization por operação;
- registra auditoria de uso no Titan;
- suspende vínculo interno independentemente do provider;
- nunca armazena senha do provider.

Claims de Role, grupo ou Organization recebidas do provider não substituem os vínculos internos do Titan.

## Identidade externa

O vínculo canônico é o par imutável:

```text
(issuer, subject)
```

Email, username, telefone e display name são atributos mutáveis e não identificadores de segurança.

O vínculo ExternalIdentity registra, conceitualmente:

- issuer;
- subject;
- tipo do principal;
- identificador do principal interno;
- estado;
- instante e responsável pelo vínculo;
- último instante de autenticação, quando necessário operacionalmente.

Regras:

- mesmo subject de issuers diferentes representa vínculos diferentes;
- troca de provider exige processo explícito de relink;
- vínculo duplicado é proibido;
- desativação interna bloqueia acesso mesmo com token externo válido;
- criação automática de User, se permitida, exige política e auditoria próprias;
- convite para Membership é separado da criação de User e do vínculo de ExternalIdentity;
- posse do mesmo email em dois issuers não autoriza vínculo automático;
- relink e account linking exigem fluxo autenticado, aprovação apropriada e auditoria;
- remoção no provider não apaga histórico do User ou Actor.

## Fluxo de User

Clientes interativos usam **Authorization Code Flow com PKCE S256**.

Obrigatório:

- redirect URIs previamente registradas e comparadas exatamente;
- `state` e `nonce` únicos e vinculados à transação quando aplicáveis;
- PKCE obrigatório, inclusive para clientes públicos;
- código trocado somente no endpoint correto;
- TLS fora de desenvolvimento local controlado;
- tokens não aparecem em URL, log ou armazenamento inseguro;
- Implicit Flow e Resource Owner Password Credentials são proibidos.

RFC 9700 recomenda PKCE também para clientes confidenciais e exige seu uso para clientes públicos. O método permitido é `S256`.

Swagger e console técnico são registrados como clientes próprios, com redirect URIs exatas, permissões mínimas e credenciais separadas das utilizadas em produção.

## Tipos de token

A API protegida do Titan aceita somente **Access Tokens** emitidos para o Resource Server correspondente.

**ID Tokens** contêm afirmações sobre a autenticação do User destinadas ao cliente OIDC. Não são utilizados como credencial de acesso à API, mesmo quando emitidos para Swagger, frontend ou outro cliente.

**Refresh Tokens** permanecem sob responsabilidade do cliente autorizado e do OIDC Provider. Não são enviados à API de domínio nem armazenados no domínio Titan.

Essa separação impede confusão entre tokens com finalidades e destinatários distintos.

## Validação de Access Token

O Titan mantém configuração explícita para cada issuer confiável. O conteúdo do token não é considerado confiável antes da validação criptográfica completa ou da resposta autenticada de introspection.

Validação deve conferir, no mínimo e conforme formato e provider:

- assinatura criptográfica ou introspection autenticada;
- algoritmo em allowlist;
- issuer exato e previamente permitido;
- audience do Resource Server Titan;
- expiração;
- início de validade, quando presente;
- issued-at dentro de tolerância aprovada;
- formato, tipo, finalidade e uso esperados do token;
- chave válida publicada pelo issuer e correspondente ao token;
- escopos técnicos necessários;
- claims mínimas, incluindo identidade externa não vazia;
- client identity, quando exigida pelo endpoint;
- status interno do vínculo.

Algoritmo não configurado, inclusive `none`, token destinado a outro recurso, assinatura inválida, chave desconhecida, issuer não permitido ou finalidade incompatível resultam em rejeição. A implementação não confia automaticamente no algoritmo declarado pelo próprio token.

Access token identifica AuthenticatedPrincipal. Ele não escolhe OrganizationContext nem comprova Permission de domínio.

## JWT, tokens opacos e chaves

O formato do Access Token não integra o contrato de domínio. Esta ADR não exige que ele seja JWT. O adapter de Infrastructure suporta o mecanismo aprovado pelo provider:

- JWT validado localmente por metadata e JWKS; ou
- token opaco validado por introspection autenticada.

Para JWT:

- metadata e JWKS vêm de endpoints OIDC configurados;
- issuer esperado é fixado, não descoberto a partir do token recebido;
- valores presentes no token não podem direcionar a API para URLs arbitrárias de metadata, chaves ou certificados;
- chaves são armazenadas em cache por período controlado;
- `kid` desconhecido provoca atualização limitada, protegida contra repetição excessiva, e nova validação;
- rotação suporta sobreposição controlada entre chaves antigas e novas;
- chaves antigas não permanecem confiáveis indefinidamente apenas por estarem em cache;
- falha persistente resulta em negação.

## Contrato interno de autenticação

Após validar o protocolo, Infrastructure produz um AuthenticatedPrincipal normalizado contendo apenas os dados necessários:

- referência à ExternalIdentity;
- tipo de principal;
- issuer confiável e subject;
- momento da autenticação, quando disponível;
- identidade do cliente, quando relevante;
- escopos técnicos validados;
- evidências de autenticação exigidas para operações sensíveis.

Token bruto, JWT, JWKS, authorization code, PKCE, Refresh Token, introspection, client secret e redirect URI não atravessam a fronteira para Domain.

Application resolve o principal interno, verifica seu estado e constrói OrganizationContext por meio dos vínculos e autorizações mantidos pelo Titan.

## ServiceIdentity

Serviços usam OAuth Client Credentials ou mecanismo OIDC/OAuth equivalente aprovado para workload identity.

Regras:

- client secret, chave privada ou certificado fica fora do domínio e do código;
- identidade externa vincula-se a ServiceIdentity interna;
- ServiceIdentity usa AuthorizationGrant e Permissions delimitadas;
- não possui Membership humano;
- credencial rotaciona sem alterar Identity;
- tokens de User não são reutilizados por worker;
- Message Broker não autentica o Actor perante o domínio;
- worker reconstrói contexto técnico autorizado.

Autenticação forte do cliente, como chave privada ou certificado, pode ser exigida por risco. A tecnologia concreta será decidida na configuração do provider.

## MFA e nível de autenticação

MFA e recuperação pertencem ao OIDC Provider. Titan pode exigir nível mínimo de autenticação para operação crítica usando claims padronizadas e allowlist de valores confiáveis.

Titan também pode exigir autenticação recente ou nível de garantia específico para operações sensíveis. Ausência da evidência exigida resulta em nova autenticação ou negação, mesmo que o Access Token seja suficiente para operações ordinárias. MFA não substitui Authorization nem Signature de domínio.

## Sessão, renovação e logout

- duração de tokens e sessões é configurada por risco;
- refresh token é tratado apenas pelo cliente autorizado e provider;
- Titan não armazena refresh token no domínio;
- logout local remove sessão e tokens do cliente;
- RP-Initiated Logout é usado quando suportado;
- redirect pós-logout é previamente registrado;
- logout não promete invalidar instantaneamente todo access token já emitido;
- operações críticas podem exigir revalidação adicional.

Logout, encerramento da sessão no provider, revogação de Refresh Token e revogação ou introspection de Access Token são mecanismos distintos.

Suspensão de User, ServiceIdentity, Membership ou vínculo externo bloqueia novas operações na autorização interna, ainda que um Access Token autoportante permaneça criptograficamente válido. Access Tokens possuem duração curta compatível com o risco.

## Indisponibilidade do provider

Falha do provider durante login, renovação, recuperação ou MFA impede essas operações.

Com JWT, API pode validar token ainda válido usando metadata e chaves confiáveis previamente obtidas, dentro de política controlada de cache e atualização. Não realiza novo login nem aceita token expirado.

Com token opaco ou operação que exige introspection/revalidação, indisponibilidade resulta em negação temporária.

Issuer desconhecido, chave indisponível, `kid` não resolvido ou impossibilidade de validar token opaco resultam em negação por padrão.

Nunca existe modo de emergência que aceite token sem validação. Contas administrativas de recuperação pertencem a procedimento operacional separado, protegido e auditado.

## Operação offline

- operação offline não realiza autenticação remota;
- primeiro login exige conexão com provider;
- cliente pode preservar sessão local previamente estabelecida e capturar OfflineOperations dentro dos limites definidos para o Device;
- captura preserva ExternalIdentity, Actor, Organization alegada, Device, timestamps e demais elementos exigidos pelo domínio;
- expiração offline não converte token em autorização permanente;
- Access Token e Refresh Token não integram OfflineOperation;
- sincronização revalida identidade, estado do principal, Membership ou AuthorizationGrant, Permissions, OrganizationContext, validade e conflitos;
- token expirado, vínculo suspenso ou autorização revogada podem impedir aceitação;
- operação original é preservada mesmo quando rejeitada;
- Decision oficial não é produzida offline;
- armazenamento local de tokens depende da plataforma e segue proteção aprovada.

## Discovery e configuração

Issuer, endpoints, client IDs, audiences, redirect URIs, algoritmos e timeouts são configuração externa versionada por ambiente.

Discovery metadata facilita interoperabilidade, mas não autoriza issuer dinâmico fornecido pelo usuário. Apenas providers previamente permitidos são aceitos.

Secrets nunca ficam no repositório, imagem, logs ou frontend público.

## Requisitos do OIDC Provider

O produto selecionado deve oferecer:

- OpenID Connect Discovery;
- Authorization Code e PKCE S256;
- JWKS e rotação de chaves;
- Client Credentials;
- MFA;
- recuperação segura;
- encerramento e revogação compatíveis com a política;
- RP-Initiated Logout ou comportamento equivalente documentado;
- logs administrativos;
- exportação, backup e restauração;
- operação auto-hospedada sem assinatura obrigatória;
- manutenção ativa e atualizações de segurança.

## Auditoria e privacidade

Titan registra resultado, issuer, subject interno referenciado, client, método geral, instante, correlação e motivo seguro de falha.

Não registra access token, ID token, authorization code, refresh token, client secret, senha, chave privada ou claims desnecessárias.

Mensagens externas não são devolvidas integralmente ao cliente. Erros evitam enumeração de User e detalhes de configuração.

## Consequências
| Tipo | Consequências |
|---|---|
| Positivas | Sem senhas no Titan; protocolo aberto; MFA/recovery especializados; provider substituível; Users e serviços autenticados |
| Negativas | Novo componente crítico; atualizações, hardening, proteção de chaves, SMTP, backups, disponibilidade, recuperação e observabilidade sob responsabilidade do projeto; logout/revogação complexos; testes de interoperabilidade obrigatórios; configuração insegura compromete todas as aplicações que confiam no issuer |

## Riscos e controles

| Risco | Controle |
|---|---|
| Token válido ser tratado como Permission | Authorization interna obrigatória |
| Email usado como identidade | Vínculo por issuer e subject |
| Código de autorização interceptado | Authorization Code, PKCE S256, state e nonce |
| Token destinado a outro recurso | Audience exata |
| Chave rotacionada | JWKS cacheado, refresh controlado e teste |
| Provider indisponível | Validação estrita, cache delimitado e fail closed |
| ServiceIdentity excessiva | Grants mínimos e rotação de credencial |
| Token exposto | Nunca persistir/logar; armazenamento seguro no cliente |
| Lock-in | Adapter OIDC e ausência de tipos do fornecedor no Core |

## Verificação automatizada

Testes devem cobrir:

- issuer, audience, assinatura, algoritmo, expiração e subject inválidos;
- ID token rejeitado como acesso à API;
- Access Token com tipo ou finalidade incorretos;
- token válido sem Membership ou Grant;
- Organization solicitada sem autorização;
- PKCE, state, nonce e redirect URI;
- rotação de chave e `kid` desconhecido;
- indisponibilidade com JWT e token opaco;
- vínculo por issuer/subject e mudança de email;
- relink e tentativa de linking somente por email;
- User suspenso internamente;
- ServiceIdentity e escopo insuficiente;
- token ou secret ausente em logs;
- logout e limite de revogação;
- sincronização depois de expiração offline.

## Licenciamento e custo

O provider deve ser auto-hospedável sem assinatura obrigatória. Licença, dependências, comunidade, atualizações e exportabilidade serão verificadas antes da escolha concreta; infraestrutura, backup, monitoramento e operação continuam tendo custo.

## O que esta ADR não decide
Produto concreto, versão, topologia, duração final de tokens, algoritmo final, autenticação social, federação LDAP, mecanismo de armazenamento no cliente e requisitos jurídicos permanecem para configuração ou decisões próprias.

## Critérios de aceitação

A ADR pode ser aceita quando:

- provider permanecer substituível;
- autenticação e Authorization estiverem separadas;
- User usar Authorization Code com PKCE S256;
- API usar access token de audience exata;
- ID Token não ser aceito como Access Token;
- JWT não ser obrigatório como formato de Access Token;
- vínculo externo usar issuer e subject;
- email não permitir linking automático;
- OrganizationContext for construído pelo Titan;
- ServiceIdentity possuir fluxo e concessão próprios;
- senhas e tokens não entrarem no domínio ou logs;
- offline não ampliar validade de autenticação;
- indisponibilidade resultar em comportamento seguro;
- Swagger ou console técnico possuir cliente isolado e permissões mínimas;
- produto concreto e configurações permanecerem fora do escopo.

## Plano de reversão

Antes da integração, esta decisão pode ser substituída por nova ADR. Depois disso, troca de provider exige migração explícita de vínculos externos, clients, sessões e políticas, preservando User, Actor, ServiceIdentity, AuthorizationGrant e auditoria histórica.
