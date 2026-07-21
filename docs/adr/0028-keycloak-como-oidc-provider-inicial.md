# ADR 0028 — Keycloak como OIDC Provider inicial

**Status:** Aceita  
**Data:** 21 de julho de 2026  
**Decisores:** fundador e responsável pela arquitetura do Titan

## Contexto

A ADR-0005 exige um OIDC Provider gratuito, auto-hospedado e externo ao processo, banco e ciclo de release do monólito. O Passo 1.4C precisa selecionar um produto concreto para o ambiente local sem transformar esse produto em contrato do Core.

O provider deve suportar OpenID Connect, OAuth 2.0, discovery, JWKS, Authorization Code com PKCE S256, Client Credentials, MFA, recuperação, sessões, logout e administração auditável. A primeira implantação deve ser reproduzível, persistente e sem assinatura comercial obrigatória.

## Alternativas consideradas

### Keycloak

- protocolos OIDC, OAuth 2.0 e SAML amplamente suportados;
- conformidade OIDC publicada pelo projeto;
- imagem oficial e operação auto-hospedada;
- MFA, recuperação, sessões, federação e administração;
- uma aplicação principal, com PostgreSQL externo;
- licença Apache 2.0 no projeto comunitário.

### authentik

- edição open source com OIDC e boa experiência administrativa;
- instalação oficial envolve servidor, worker, PostgreSQL e gestão de secret próprio;
- maior quantidade inicial de componentes e superfície operacional.

### ZITADEL

- OIDC/OAuth2, organizações e service accounts bem modelados;
- auto-hospedagem suportada sobre PostgreSQL;
- implantação e login atuais possuem mais componentes e configuração para o escopo local inicial;
- oferta e licenciamento comercial exigiriam nova avaliação para cada modo de uso.

## Decisão

Adotar **Keycloak 26.7.0** como implementação operacional inicial do contrato de OIDC Provider.

Esta decisão não altera a linguagem do Core:

- Domain e Application não conhecem Keycloak;
- contratos internos continuam expressos como OIDC Provider, ExternalIdentity e AuthenticatedPrincipal;
- integração futura utiliza discovery e endpoints padronizados;
- claims, roles e estruturas proprietárias não substituem User, ServiceIdentity, Membership, Permission, AuthorizationGrant ou OrganizationContext do Titan;
- troca de produto permanece possível mediante migração explícita conforme ADR-0005.

## Topologia inicial

O ambiente local contém:

- processo Keycloak separado do monólito;
- PostgreSQL dedicado ao Keycloak, sem porta publicada no host;
- volume próprio para o banco do provider;
- porta HTTP do Keycloak publicada somente em `127.0.0.1`;
- health check no endpoint de gerenciamento;
- versões e imagens fixadas por tag e digest;
- credenciais fictícias substituíveis, proibidas fora do desenvolvimento.

O banco autoritativo do Titan não armazena estado interno do Keycloak. O banco dedicado do provider não armazena entidades de domínio do Titan.

## Perfil local

O Passo 1.4C utiliza `start-dev` exclusivamente para desenvolvimento e validação local. Esse modo possui padrões inseguros e é proibido em produção.

Antes de qualquer implantação não local será necessária decisão operacional contendo ao menos:

- HTTPS e hostname definitivo;
- reverse proxy e headers confiáveis;
- secrets protegidos e rotação;
- backup e restauração testados;
- SMTP e recuperação;
- política de MFA;
- atualização e resposta a vulnerabilidades;
- observabilidade e limites de recursos;
- alta disponibilidade e recuperação, quando exigidas;
- configuração endurecida e imagem otimizada.

## Segurança

- a porta pública local permanece no loopback;
- a porta de gerenciamento não é publicada no host;
- o PostgreSQL do provider não publica porta;
- health check avalia readiness e conexão com o banco;
- senha bootstrap cria o administrador somente na primeira inicialização;
- credenciais locais nunca são reutilizadas em ambiente compartilhado ou produtivo;
- nenhum realm, client, User ou segredo real é incluído nesta ADR;
- configuração de realm, clientes, PKCE, MFA e integração da API pertence ao Passo 3.5.

## Reversibilidade

Antes da integração do Passo 3.5, a reversão consiste em remover os serviços e o volume local do provider, preservando esta ADR como histórico.

Depois da integração, substituição exige exportação e migração explícitas de realms, clients, ExternalIdentities, sessões e políticas aplicáveis. `(issuer, subject)` não pode ser reescrito silenciosamente.

## Consequências

### Positivas

- autenticação especializada sem implementar senhas no Titan;
- ambiente local gratuito e reproduzível;
- suporte aos fluxos exigidos pela ADR-0005;
- separação física do processo e banco do monólito;
- contrato do Core permanece independente do produto.

### Negativas

- o projeto assume atualizações, hardening, backup, disponibilidade e recuperação;
- dois containers e um volume adicionais aumentam consumo local;
- modo local não representa configuração produtiva;
- migração futura de issuer e subject exige processo controlado.

## Critérios de aceite

- imagem Keycloak e PostgreSQL dedicado fixadas por digest;
- PostgreSQL do provider sem porta publicada;
- Keycloak acessível somente por loopback;
- readiness saudável e discovery OIDC acessível;
- estado administrativo persistente após `down` e novo `up`;
- credencial inválida não autentica no token endpoint;
- nenhum tipo Keycloak atravessa para Domain ou Application;
- `start-dev` documentado como proibido em produção;
- testes, Ruff e Mypy aprovados.

## Referências

- [Keycloak — OpenID Connect](https://www.keycloak.org/securing-apps/oidc-layers), consultada em 21 de julho de 2026.
- [Keycloak — especificações implementadas](https://www.keycloak.org/securing-apps/specifications), consultada em 21 de julho de 2026.
- [Keycloak — execução em container](https://www.keycloak.org/server/containers), consultada em 21 de julho de 2026.
- [Keycloak — health checks](https://www.keycloak.org/observability/health), consultada em 21 de julho de 2026.
- [Keycloak 26.7.0](https://www.keycloak.org/2026/07/keycloak-2670-released), consultada em 21 de julho de 2026.
