# Requisitos de Produção — Titan

**Status:** inventário evolutivo; não constitui autorização de implantação  
**Atualizado em:** 21 de julho de 2026  
**Base:** `VISION.md`, `DOMAIN.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md` e ADRs aceitas

## Objetivo

Registrar o que um ambiente de produção do Titan deverá possuir, quais responsabilidades precisam permanecer separadas e quais decisões ainda faltam. Este documento é um checklist operacional, não um manifesto pronto para copiar. O dimensionamento depende de testes de carga, volume de evidências, disponibilidade pretendida, RPO, RTO e jurisdições atendidas.

O `compose.yaml` atual é exclusivo de desenvolvimento. Ele não define TLS, alta disponibilidade, backup, restauração, hardening ou capacidade de produção.

## Princípios obrigatórios

- executar componentes em processos isolados e com identidades de serviço próprias;
- usar TLS nas conexões externas e internas conforme o perfil de risco;
- obter secrets de mecanismo próprio, nunca do repositório ou da imagem;
- aplicar menor privilégio, segregação de rede e negação por padrão;
- separar dados autoritativos do Titan, documentos e estado do OIDC Provider;
- manter backup, restauração testada, observabilidade e trilha de mudanças;
- fixar e atualizar versões por procedimento controlado;
- não usar `start-dev`, senhas locais ou portas administrativas públicas;
- registrar localização de dados, subprocessadores e acessos operacionais;
- não declarar prontidão enquanto itens “a definir” permanecerem materiais ao lançamento.

## Inventário de runtimes e serviços

| Componente | Referência atual | Responsabilidade | Estado para produção |
|---|---|---|---|
| Aplicação Titan | Python 3.12.10, FastAPI, SQLAlchemy 2.0, Alembic 1.18 e Psycopg 3.3 | API, casos de uso, conexão e migrations | Versões atuais; imagem e servidor ASGI de produção a definir |
| PostgreSQL/PostGIS do Titan | PostgreSQL 18.4 + PostGIS 3.6 | Estado transacional, auditoria, metadados e operações espaciais aprovadas | Separação obrigatória; topologia e capacidade a definir |
| MongoDB | MongoDB 8.0.26 | Bytes autorizados de documentos por GridFS | Uso condicionado à implementação do GridFS e avaliação operacional/licença |
| OIDC Provider | Keycloak 26.7.0 | Autenticação, credenciais, sessões e fatores | Produto decidido; configuração produtiva ainda não implementada |
| PostgreSQL do Keycloak | PostgreSQL 18.4 | Estado interno exclusivo do provider | Banco dedicado e separado do Titan |
| Message Broker | RabbitMQ 4.3 | Entrega assíncrona de mensagens | Produto decidido; topologia produtiva ainda não implementada |
| Workers | A definir com o broker | Execução assíncrona autorizada | Não selecionado |
| Valkey | Valkey 9.1 | Cache e coordenação efêmera | Standalone local implementado; topologia produtiva a definir; nunca autoritativo |
| Armazenamento de backup | A definir | Cópias protegidas e restauração | Obrigatório antes da produção |
| Gestão de secrets/chaves | A definir por perfil aprovado | Secrets, chaves e material criptográfico | Obrigatório antes da produção |
| Observabilidade | A definir | Métricas, logs, traces e alertas | Obrigatória, sem tokens, secrets ou PII indevida |

“Gratuito” significa ausência de licença ou assinatura obrigatória na configuração escolhida. Infraestrutura, operação, backup, domínio, certificados, mensagens, suporte e pessoal ainda geram custo.

## Separação de bancos e responsabilidades

### 1. PostgreSQL/PostGIS autoritativo do Titan

Deverá armazenar somente o estado transacional e os metadados aprovados do Titan, incluindo entidades, vínculos, Policies, Decisions, auditoria, Outbox/Inbox e referências de evidências conforme os passos que os implementarem.

Configuração mínima esperada:

- database e usuário próprios do Titan;
- PostGIS habilitado somente nas bases e schemas que necessitarem dele;
- migrations versionadas e executadas por identidade separada da aplicação quando possível;
- usuário de runtime sem privilégios de owner ou superuser;
- Row-Level Security e contexto de Organization quando implementados;
- criptografia em trânsito e em repouso conforme o perfil;
- backup com retenção, verificação de integridade e restauração testada;
- métricas de conexões, locks, replicação, armazenamento e consultas críticas;
- política de manutenção, atualização e recuperação documentada.

O número de instâncias, réplicas, zonas e recursos não será definido sem testes de carga, RPO/RTO e requisitos de disponibilidade.

### 2. PostgreSQL exclusivo do Keycloak

Deverá armazenar apenas o estado interno do OIDC Provider: realms, clientes, usuários externos ao modelo interno do Titan, credenciais, sessões e configurações próprias do produto.

Regras:

- não reutilizar o database, schema, usuário ou migration do Titan;
- não acessar esse banco diretamente a partir da Application ou do Domain;
- não publicar sua porta à internet;
- permitir rede apenas entre instâncias autorizadas do Keycloak, administração aprovada e rotinas de backup;
- usar credenciais, backup, retenção e restauração próprios;
- testar conjuntamente a recuperação do banco e do provider;
- não tratar tabelas internas do Keycloak como API estável.

Separação lógica por database é o mínimo. Para reduzir blast radius, manutenção acoplada e disputa de recursos, a adoção de cluster/instância também separada deverá ser decidida no desenho de implantação.

### 3. MongoDB/GridFS

Deverá armazenar somente bytes de documentos autorizados e estruturas técnicas necessárias ao GridFS. PostgreSQL continuará autoritativo para ownership, classificação, Provenance, retenção, autorização, Digest e relações de domínio.

Regras:

- autenticação obrigatória e usuário de aplicação com menor privilégio;
- sem exposição pública direta;
- replicação, write concern e capacidade definidos a partir dos requisitos de durabilidade;
- backup consistente com os metadados autoritativos e procedimento de reconciliação;
- criptografia, limites de tamanho, antimalware e validação de formato conforme o caso de uso;
- retenção e descarte coordenados com PostgreSQL, LegalHold e Evidence;
- nenhuma URL ou identificador do MongoDB deve conceder acesso por si só.

## Aplicação Python

Em produção, Python não deverá ser instalado e alterado manualmente no servidor como processo artesanal. A implantação deverá usar artefato imutável e reproduzível, preferencialmente imagem de container, construído a partir do lockfile aprovado.

O artefato deverá conter:

- versão exata do Python compatível com `.python-version`;
- dependências resolvidas por `uv.lock` sem instalação ad hoc;
- usuário de sistema não privilegiado;
- health/readiness separados conforme as dependências reais;
- limites de CPU, memória, processos e tempo;
- encerramento gracioso e correlação de requisições;
- configuração por ambiente e secrets externos;
- SBOM, varredura de vulnerabilidades e origem verificável da imagem;
- migrations fora do início concorrente de cada réplica da API.

Quantidade de workers ASGI, réplicas e limites serão definidos por medição. O servidor de desenvolvimento do Uvicorn e reload automático não são configuração de produção.

## Keycloak em produção

O modo `start-dev` é proibido. A configuração produtiva deverá incluir:

- modo de produção, hostname e proxy headers explicitamente configurados;
- HTTPS na borda e relação de confiança com o proxy documentada;
- console e endpoints administrativos restritos por rede e identidade;
- conta bootstrap removida ou protegida após provisionamento controlado;
- realms e clientes exportáveis/reproduzíveis sem secrets no repositório;
- redirect URIs exatas, PKCE S256 e clientes separados por aplicação/ambiente;
- MFA, recuperação, SMTP e políticas de brute force aprovadas;
- rotação de chaves com sobreposição e cache de JWKS controlado;
- tokens de curta duração segundo o risco;
- backup e teste de restauração do banco e das configurações;
- métricas, logs de administração, alertas e atualização de segurança;
- capacidade e alta disponibilidade definidas por teste e RPO/RTO.

O Keycloak autentica. Membership, OrganizationContext, grants, permissions e decisões de autorização continuam pertencendo ao Titan.

## Rede e exposição

Somente a entrada pública aprovada deverá alcançar a API e os endpoints públicos necessários do OIDC Provider. Bancos, broker, Valkey, portas de gerenciamento e métricas permanecem em redes privadas.

Deverão existir regras explícitas para:

- ingress, egress e resolução DNS;
- administração privilegiada e suporte remoto;
- comunicação API → bancos/provider/broker/cache;
- acesso de observabilidade sem leitura indiscriminada de dados;
- rate limiting, proteção contra abuso e limites de payload;
- segregação completa entre desenvolvimento, homologação e produção.

## Persistência, backup e recuperação

Antes do primeiro ambiente produtivo, cada armazenamento deverá possuir:

- owner operacional e inventário de dados;
- RPO, RTO, periodicidade, retenção e localização aprovados;
- backup criptografado com chaves separadas;
- restauração testada, não apenas backup concluído;
- reconciliação entre PostgreSQL, MongoDB, broker e derivados;
- tratamento de LegalHold, retenção e descarte;
- evidência do teste e das limitações encontradas.

Restauração técnica não reativa automaticamente grants, secrets, sessões ou autorizações revogadas.

## Secrets e chaves

Devem ficar fora de código, Compose, imagem, logs e banco de configuração comum:

- senhas de bancos;
- credenciais administrativas do Keycloak;
- client secrets OIDC;
- chaves de assinatura, criptografia e backup;
- credenciais de SMTP, integrações e observabilidade;
- tokens de automação e administração.

O mecanismo concreto de secrets/KMS/HSM, perfis de chave, rotação, recuperação e segregação de funções permanece sujeito às ADRs e perfis aplicáveis. Chaves privadas não devem ser armazenadas no PostgreSQL ou MongoDB apenas por conveniência.

## Observabilidade e operação

O ambiente deverá disponibilizar, com retenção e acesso controlados:

- métricas técnicas e de capacidade;
- logs estruturados com correlation ID;
- trilhas administrativas e de segurança;
- alertas de indisponibilidade, saturação, falha de backup e autenticação abusiva;
- inventário de versões, dependências e patches;
- runbooks de incidente, recuperação, rotação e rollback;
- relógio confiável e monitoramento de desvio temporal.

Tokens, secrets, documentos, PII desnecessária e payloads sensíveis não devem aparecer em telemetria.

## Ambientes mínimos

| Ambiente | Finalidade | Dados |
|---|---|---|
| Desenvolvimento local | Construção e testes rápidos | Sintéticos; Compose local permitido |
| Homologação | Migrations, integração, segurança e restauração | Sintéticos ou anonimizados, nunca cópia livre de produção |
| Produção | Operação autorizada | Dados reais segundo classificação e localização |

Credenciais, bancos, realms, chaves, redes e volumes não são compartilhados entre ambientes.

## Decisões ainda necessárias

- arquitetura de hospedagem e regiões;
- SLO, disponibilidade, RPO e RTO;
- dimensionamento inicial e critérios de escala;
- topologia produtiva do RabbitMQ e produto do executor de workers;
- topologia, capacidade, TLS e ACL produtivos do Valkey;
- mecanismo de secrets, KMS/HSM e certificados TLS;
- estratégia de backup externo e disaster recovery;
- observabilidade, retenção de telemetria e plantão;
- configuração produtiva do Keycloak e provisionamento dos clientes;
- topologia MongoDB e avaliação da licença para o modelo comercial;
- CDN/WAF, e-mail, TSA e integrações externas quando entrarem no escopo;
- perfis de localização, transferências e subprocessadores.

Cada decisão arquitetural material exige ADR e aprovação antes da implementação.

## Checklist antes da primeira implantação

- [ ] arquitetura de implantação e threat model aprovados;
- [ ] todos os itens “a definir” materiais resolvidos;
- [ ] ambientes e redes segregados;
- [ ] secrets externos e rotacionáveis;
- [ ] TLS e hostnames validados;
- [ ] usuários de banco sem privilégios administrativos;
- [ ] migrations testadas em homologação;
- [ ] backup e restauração comprovados;
- [ ] RPO, RTO, SLO e alertas aprovados;
- [ ] testes funcionais, segurança, isolamento e carga aprovados;
- [ ] Keycloak em modo de produção, sem bootstrap inseguro;
- [ ] logs revisados quanto a secrets e dados pessoais;
- [ ] inventário de dados, localização e subprocessadores completo;
- [ ] plano de incidente, rollback e offboarding testado;
- [ ] licenças e custos operacionais revisados.
