# Plano de Implementação Validado — Titan

**Status:** em execução — Passo 3.2 concluído e aprovado; próximo incremento: Passo 3.3
**Data:** 21 de julho de 2026  
**Estratégia:** MVP por incrementos verticais coesos, com autonomia em mudanças rotineiras e validação proporcional ao risco  
**Escopo inicial:** Titan Core completo e comprovado antes da primeira vertical

O estado operacional, as evidências e a validação manual de cada passo são mantidos em `docs/CHECKLIST_DE_IMPLEMENTACAO.md`.

## Checkpoint de progresso — 21 de julho de 2026

Os Passos 0.1 a 1.6 foram concluídos e aprovados. O Passo 1.6 adicionou um workflow GitHub Actions com permissões mínimas, teve execução remota bem-sucedida e bloqueou uma falha controlada em branch temporária.

Concluído e aprovado:

- ADRs 0001 a 0029 aceitas em `docs/adr/`;
- `DOMAIN.md` versão 1.19, congelado como visão de destino;
- `ARCHITECTURE.md` versão 1.32, congelado como visão de destino;
- decisões sobre estrutura, Organizations, bancos, OIDC, mensageria, integridade, chaves, assinaturas, verificação externa, fundamentação normativa, sustentabilidade, classificação, retenção, Provenance, validação e confiança;
- workspace, qualidade Python, API mínima e infraestrutura local até 1.4E implementados; nenhuma migration, pacote de domínio ou worker iniciado.

Ponto exato de continuidade:

1. reler os documentos de autoridade antes da próxima alteração;
2. conectar o repositório ao GitHub mediante autorização específica;
3. observar uma execução verde e uma falha controlada em branch de teste;
4. manter o executor de workers fora do escopo até decisão própria.

Este checkpoint não autoriza alterar ADR aceita, adotar serviço gerenciado ou iniciar implementação sem aprovação específica.

## 1. Objetivo do plano

Conduzir a construção greenfield do Titan como uma plataforma de decisões auditáveis, seguindo o monólito modular. O MVP evolui por incrementos verticais verificáveis orientados à validação do produto. Mudanças rotineiras, reversíveis e dentro do escopo aprovado não dependem de portão manual entre cada tarefa.

Não será construído frontend de produto durante o Core. Os testes serão feitos prioritariamente por testes automatizados, API, OpenAPI/Swagger, comandos reproduzíveis e fixtures fictícias. Um console web técnico poderá ser criado como passo independente apenas quando visualização de grafos, progresso ou comportamento offline não puder ser validado adequadamente por esses meios.

Este plano autoriza progressão autônoma dentro de um incremento aprovado. Confirmação prévia permanece obrigatória para mudança de arquitetura, domínio ou escopo, risco elevado, incompatibilidade pública, custo externo ou ação irreversível.

## 2. Fontes examinadas e precedência

As referências históricas principais da ideia do produto são:

1. `docs/Titan_Arquitetura_e_Dominio_v2.md`;
2. `docs/Plano_Implementacao_Titan_Greenfield_v3.md`.

Também foram examinados os demais arquivos existentes na raiz e em `docs`:

1. `AGENTS.md`;
2. `VISION.md`;
3. `DOMAIN.md`;
4. `ARCHITECTURE.md`;
5. `DEVELOPMENT.md`;
6. `README.md`;
7. `markdown.md.txt`;
8. este `docs/PLANO_DE_IMPLEMENTACAO_VALIDADO.md`, como plano operacional vigente, e não como fonte histórica de si próprio.

Para execução, a ordem de autoridade será:

1. `DOMAIN.md` para linguagem e regras de negócio;
2. `VISION.md` para objetivo e limites do produto;
3. `ARCHITECTURE.md` para arquitetura vigente;
4. `DEVELOPMENT.md` e `AGENTS.md` para processo de trabalho;
5. documentos de `docs`, `README.md` e `markdown.md.txt` como referências históricas e de requisitos, somente quando não conflitarem com os documentos anteriores.

Nenhum conceito de negócio ausente em `DOMAIN.md` será implementado. Sua inclusão exigirá decisão arquitetural e aprovação prévia.

## 3. Conflitos e lacunas que bloqueiam a implementação

Antes de criar código, o Passo 0 deve resolver formalmente:

| Tema | Direção aprovada | Formalização vigente |
|---|---|---|
| Documentos | MongoDB/GridFS para conteúdo binário; metadados e hashes no PostgreSQL | ADR-0004 |
| Estrutura | `apps/` para executáveis e `packages/` para módulos | ADR-0001 |
| ADRs | `docs/adr/` | ADR-0001 e `AGENTS.md` harmonizado |
| Isolamento | `Organization` em domínio, banco e contratos | ADRs 0002 e 0003 |
| Banco | PostgreSQL transacional; PostGIS no caminho crítico para evidência geoespacial vetorial | ADRs 0003 e 0026 |
| Filas/workers | PostgreSQL Outbox e Message Broker; produto e executor exigem decisão própria | ADR-0006 |
| Cache | Valkey; nenhum dado definitivo apenas em cache | ADR-0025 |
| Autenticação | OIDC Provider via OIDC/OAuth2; autorização pertence ao Titan | ADR-0005 |
| Confiança criptográfica | Integridade Titan, assinatura institucional, prova temporal e assinatura qualificada são níveis distintos | ADRs 0007 a 0010 |
| Offline | Protocolo obrigatório com idempotência, retomada e conflito explícito | ADR-0021 |
| Status | Termos apresentados em português e conceitos distintos para regra, decisão e bloqueio | `DOMAIN.md` 1.19 |
| Licenças | Dependências e serviços exigem inventário, permissões compatíveis e análise de custo e portabilidade | ADRs 0012, 0020 e 0024; revisão contínua |
| Estratégia | Core primeiro; Livestock somente após a prova completa do Core | Plano validado e critérios dos marcos |

Essas decisões estão aprovadas e os documentos de autoridade estão harmonizados até a ADR-0027. Qualquer futura adoção de serviço gerenciado exige avaliação e decisão explícitas.

## 4. Protocolo obrigatório para cada passo

Antes de cada incremento:

1. reler os documentos de autoridade afetados;
2. inspecionar somente os arquivos necessários;
3. apresentar escopo, arquivos previstos, critérios de aceitação e riscos;
4. obter confirmação somente quando a mudança estiver nas categorias de aprovação obrigatória;
5. se surgir decisão arquitetural importante, parar e propor uma ADR antes do código.

Durante cada incremento:

1. entregar uma única capacidade;
2. manter uma funcionalidade coesa e um diff revisável, sem limite arbitrário de linhas;
3. não modificar APIs públicas nem arquivos alheios ao passo;
4. preservar imutabilidade, isolamento por Organization, autoria e auditabilidade;
5. criar ou atualizar testes sem remover testes existentes.

Ao finalizar cada passo, o agente deverá:

1. executar somente os testes relacionados;
2. executar Ruff;
3. executar Mypy;
4. executar a checagem específica da camada alterada, quando houver;
5. revisar o diff e confirmar que a alteração permanece coesa, revisável e restrita à capacidade do incremento;
6. informar arquivos modificados, comandos, resultados, riscos e pendências;
7. fornecer validação proporcional ao risco, automatizada sempre que possível;
8. parar e aguardar o resultado do usuário.

Aprovação manual explícita é reservada às categorias obrigatórias definidas em `AGENTS.md` e `DEVELOPMENT.md`. Resultado reprovado bloqueia somente o incremento afetado e sua correção.

## 5. Sequência de implementação

### Marco 0 — Alinhamento vinculante

#### Passo 0.1 — Confirmar fronteira do Titan Core

**Entrega:** definição vinculante dos módulos, responsabilidades e contratos do Core, sem conceitos de verticais. Recall, não conformidades, genealogia e sincronização integram o Core; regras e fatos pecuários não integram.

**Não inclui:** código, telas ou banco.

**Validação manual:** revisar cada módulo e confirmar que nenhum termo como animal, GTA, medicamento, peça ou alimento está presente no Core.

**Portão:** sem aprovação do escopo, não seguir.

#### Passo 0.2 — Consolidar linguagem do domínio

**Entrega:** proposta de atualização do `DOMAIN.md` para conceitos indispensáveis e hoje ausentes, como Membership, Permission, Rule, Evaluation, Provenance, NonConformity, relações universais, idempotência, sincronização e estados em português.

**Validação manual:** revisão termo a termo, incluindo significado, invariantes e exemplos; confirmar que `Organization` é o termo canônico e que nenhum sinônimo foi introduzido.

**Portão:** alterações de domínio são decisões arquiteturais e exigem aprovação específica.

#### Passo 0.3 — Resolver arquitetura e registrar ADRs

**Entrega:** uma ADR por decisão, sem agrupar decisões independentes: estrutura `apps/` + `packages/`, PostgreSQL, MongoDB/GridFS, OIDC Provider, Message Broker/executor, Valkey, Organization, eventos/integridade, checkpoints/timestamp, gestão de chaves, assinatura/certificados, verificação externa, contratos públicos, offline, licenças e diretório `docs/adr/`.

**Validação manual:** comparar alternativas, consequências e aderência a `ARCHITECTURE.md`; aprovar cada ADR separadamente.

**Portão:** atualizar os documentos conflitantes antes de iniciar a fundação.

#### Passo 0.4 — Tornar comandos de desenvolvimento reproduzíveis

**Entrega:** preencher e harmonizar comandos oficiais de instalação, execução, teste específico, Ruff, Mypy, frontend e Docker, sem implementar funcionalidade.

**Validação manual:** confirmar que cada comando possui responsável e marco de disponibilidade. A execução em máquina limpa ocorre no passo que criar o respectivo manifesto ou alvo; comando indisponível não pode ser apresentado como executável.

**Resultado:** concluído e aprovado. `DEVELOPMENT.md` é a referência canônica; comandos Python usam ambiente e lockfile gerenciados por `uv`; API, Docker e frontend permanecem indisponíveis até seus passos próprios.

### Marco 1 — Fundação técnica mínima

#### Passo 1.1 — Criar o workspace Python mínimo

**Entrega:** somente `pyproject.toml`, lockfile e metadados mínimos do workspace Python. Nenhum app, package funcional ou diretório futuro é criado antecipadamente.

**Validação manual:** instalar o workspace a partir do lockfile em ambiente limpo ou equivalente e confirmar que nenhum app, package, framework ou conceito de vertical foi antecipado.

**Resultado:** concluído e aprovado com Python 3.12.10, compatibilidade `>=3.12,<3.13`, `uv` 0.11.30 e lockfile sem dependências de runtime.

#### Passo 1.2 — Configurar qualidade Python

**Entrega:** configuração mínima de pytest, Ruff e Mypy, com teste de sanidade e verificador arquitetural inicial. Dependências devem ser justificadas individualmente. Apps e packages continuam surgindo somente quando possuírem capacidade atual e consumidor real.

**Validação manual:** instalar o projeto e executar teste, Ruff e Mypy a partir da raiz.

**Resultado:** concluído e aprovado com pytest 9.1.1, Ruff 0.15.22, Mypy 2.3.0, três testes aprovados e verificações estáticas sem erros.

#### Passo 1.3 — Criar aplicação FastAPI com health check

**Entrega:** aplicação inicial e um endpoint autenticável no futuro, limitado a informar saúde técnica, sem expor dados de domínio.

**Validação manual:** subir a API, consultar o health check e verificar resposta de erro para rota inexistente.

**Contrato:** toda rota de domínio posterior e toda resposta de erro seguem a ADR-0027. O health check técnico somente permanece fora de `/api/v1` enquanto não expuser contrato ou dado de domínio.

**Resultado:** concluído e aprovado com FastAPI 0.139.2, Uvicorn 0.51.0 e HTTPX2 2.7.0 para testes. Seis testes, Ruff e Mypy passaram; a execução real retornou `200` no health check e `404` em Problem Details para rota inexistente.

#### Passo 1.4 — Configurar infraestrutura local incremental

**Entrega:** adicionar um serviço por subtarefa validada: PostgreSQL com PostGIS, MongoDB, OIDC Provider, Message Broker e Valkey. Cada serviço terá versão fixada, configuração externa, health check e persistência apenas quando necessária. O runtime local também deverá ser gratuito segundo a política aprovada.

**Validação manual:** subir, verificar saúde, reiniciar e derrubar o ambiente sem perda ou erro inesperado.

**Resultado da subtarefa 1.4A:** concluída e aprovada com PostgreSQL 18.4 e PostGIS 3.6.4, imagem `postgis/postgis:18-3.6` fixada por digest, porta local, health check e volume persistente. Persistência comprovada após `down`/`up`; oito testes, Ruff e Mypy passaram. MongoDB, OIDC Provider, Message Broker e Valkey não foram iniciados.

**Resultado da subtarefa 1.4B:** concluída e aprovada com MongoDB 8.0.26, imagem oficial fixada por digest, autenticação, porta local, health check e volume persistente. Escrita anônima foi rejeitada e persistência comprovada após `down`/`up`; dez testes, Ruff e Mypy passaram. GridFS, driver e integração com a aplicação não foram iniciados.

**Resultado da subtarefa 1.4C:** concluída e aprovada com Keycloak 26.7.0 e PostgreSQL 18.4 dedicado, ambos fixados por digest. O provider fica em loopback, o banco não publica porta, readiness e discovery OIDC foram verificados, cliente inválido foi rejeitado e o estado persistiu após `down`/`up`. Realm e clientes Titan, PKCE, MFA e integração com a API permanecem no Passo 3.5.

**Resultado da subtarefa 1.4D:** concluída e aprovada com RabbitMQ 4.3.3, imagem oficial com management fixada por digest, autenticação, vhost dedicado, portas em loopback, health check e volume persistente. Publicação roteada, consumo com requeue/redelivery, rejeição de credencial inválida e persistência da topologia após `down`/`up` foram comprovados. Publisher, Outbox, filas funcionais e workers não foram iniciados.

**Resultado da subtarefa 1.4E:** concluída e aprovada com Valkey 9.1.0 fixado por digest, autenticação, porta em loopback, health check, limite de 128 MB e eviction `allkeys-lfu`. RDB, AOF e volume estão ausentes por desenho. Acesso anônimo foi rejeitado e a perda total após recriação foi comprovada. Integração Python, CacheProfiles e topologia produtiva não foram iniciados.

**Portão:** antes de adicionar os respectivos serviços, ADRs próprias devem escolher o produto concreto de OIDC Provider e o produto concreto de Message Broker, com versão, licença, operação local, segurança, reversibilidade e custo avaliados. A aprovação dos protocolos nas ADRs 0005 e 0006 não constitui escolha de produto.

#### Passo 1.5 — Configurar migrations e conexão PostgreSQL

**Entrega:** mecanismo de migration vazio/inicial e conexão por configuração externa, sem tabela de negócio.

**Validação manual:** aplicar, consultar estado, reverter com segurança em ambiente descartável e reaplicar a migration.

**Resultado:** implementado com SQLAlchemy 2.0.51, Alembic 1.18.5 e Psycopg 3.3.4. A configuração exige `TITAN_DATABASE_URL`; a migration inicial cria somente `alembic_version`. Conexão, upgrade, consulta, downgrade e reaplicação passaram em banco descartável, posteriormente removido. Validação manual pendente.

#### Passo 1.6 — Configurar CI mínimo

**Entrega:** pipeline com testes, Ruff, Mypy e checagem arquitetural já existentes.

**Validação manual:** acompanhar uma execução bem-sucedida e uma falha intencional controlada em branch de teste.

**Resultado:** implementado localmente em GitHub Actions com runner Ubuntu fixo, actions por SHA, token somente leitura, checkout sem credencial persistida, lockfile, pytest, verificações arquiteturais, Ruff e Mypy. Nenhum deploy, publicação ou secret foi adicionado. Validação remota pendente.

### Marco 2 — Shared Kernel e contratos universais

Cada item abaixo é um passo independente; não devem ser implementados juntos.

#### Passo 2.1 — Identificadores tipados e referências

**Entrega:** IDs tipados e referências universais aprovadas, sempre associadas à `Organization` quando aplicável, sem termos pecuários.

**Validação manual:** criar referências válidas e rejeitar tipo, ID ou Organization inválidos; revisar a ausência de conceitos de vertical.

**Resultado:** concluído e aprovado em `packages/shared_kernel` com `TypedId`, `OrganizationId` e `UniversalReference` imutáveis, validação de UUID, tipo lógico, Organization e versão de contrato, sem dependências externas ou conceitos de vertical.

#### Passo 2.2 — Relógio e datas

**Entrega:** relógio injetável e regra única para timestamps/timezone.

**Validação manual:** congelar o tempo em teste e confirmar distinção entre momento do fato e momento do registro.

**Resultado:** concluído e aprovado no Shared Kernel com contrato `Clock`, `SystemClock`, `FixedClock`, validação obrigatória de UTC e `RecordTimestamps` imutável distinguindo ocorrência de registro.

#### Passo 2.3 — Serialização canônica

**Entrega:** serialização determinística e versionada para estruturas estritamente delimitadas.

**Validação manual:** serializar a mesma informação em ordens diferentes e confirmar bytes/hash idênticos; testar valores inválidos.

**Resultado:** concluído e aprovado como `titan-json-v1`, com envelope versionado, tipos inequívocos, mapas ordenados, listas ordenadas semanticamente, Unicode NFC, decimais canônicos, timestamps UTC e rejeição explícita de estruturas ambíguas ou não suportadas.

#### Passo 2.4 — Contrato de evento de domínio

**Entrega:** evento imutável com identidade, Organization, agregado, versão, ocorrido/registrado, ator, origem, correlação, causação e payload versionado.

**Validação manual:** construir evento válido, tentar mutá-lo, validar schema e confirmar ausência de dependências de FastAPI/SQLAlchemy.

**Resultado:** concluído e aprovado em `packages/core_domain` com identidade e referências tipadas, coerência de Organization, temporalidade UTC, correlação e causação, versões positivas e payload obrigatório capturado em bytes canônicos versionados. Teste arquitetural protege a independência de frameworks e infraestrutura.

### Marco 3 — Identity & Access

#### Passo 3.1 — Organization

**Entrega:** modelo de domínio e persistência de `Organization`, com migration e testes de invariantes.

**Validação manual:** criar e consultar uma Organization; rejeitar dados inválidos e confirmar migration reversível.

**Resultado:** concluído e aprovado com modelo mínimo imutável, persistência SQLAlchemy Core, schema modular, tabela `PROTECTED`, auto-ownership, RLS e `FORCE RLS`, policies de leitura/inserção por contexto transacional e migration reversível. Teste com role temporária sem `BYPASSRLS` comprovou criação, consulta, isolamento e negação sem contexto.

#### Passo 3.2 — User

**Entrega:** identidade do usuário sem armazenamento de senha em claro e sem associação direta de permissão.

**Validação manual:** criar usuário válido, rejeitar duplicidade/inválidos e inspecionar persistência para confirmar ausência de credencial sensível.

**Resultado:** concluído e aprovado. A ADR 0030 define o `User` global como registro owned pela Organization operadora; o modelo e a tabela preservam somente `user_id` e `record_owner_organization_id`, sem credenciais ou permissões diretas. A migration `20260721_0003`, RLS, chave estrangeira e testes comprovam isolamento, duplicidade e owner obrigatório.

#### Passo 3.3 — Membership

**Entrega:** vínculo temporal entre User e Organization.

**Validação manual:** associar um usuário a duas organizações, selecionar organização ativa e impedir operação sem vínculo.

#### Passo 3.4 — Role e Permission

**Entrega:** permissões atribuídas exclusivamente por papéis, nunca diretamente ao User.

**Validação manual:** conceder/remover papel e confirmar mudança de acesso; tentar atribuição direta e confirmar rejeição.

#### Passo 3.5 — Autenticação com OIDC Provider

**Entrega:** OIDC Provider auto-hospedado, cliente OIDC, Authorization Code com PKCE para eventual cliente web, validação de token na API e proteção de uma rota de teste. O OIDC Provider autentica; Titan mantém User, Organization, Membership, Role e Permission.

**Validação manual:** testar credencial válida, ausente, expirada e adulterada; confirmar que logs não contêm segredos.

#### Passo 3.6 — Isolamento por Organization

**Entrega:** enforcement na aplicação e infraestrutura, sem consulta cruzada implícita.

**Validação manual:** repetir consultas e mutações com duas organizações e tentar enumeração de IDs; nenhum dado deve atravessar fronteiras.

#### Passo 3.7 — Perfis mínimos de bootstrap

**Entrega:** processo explícito, versionado e auditável para criar somente os perfis mínimos exigidos pelos casos de uso já implementados. Cada seed ou comando administrativo deve registrar origem, versão, autoridade, ambiente e resultado, sem criar permissões universais nem relaxar o comportamento fail-closed.

**Validação manual:** inicializar ambiente vazio, comprovar que operações protegidas falham antes do bootstrap, aplicar o conjunto mínimo autorizado de forma idempotente e confirmar que perfis ausentes continuam produzindo negação ou resultado indeterminado conforme a Policy.

**Portão:** o conjunto concreto de perfis nasce dos casos de uso aprovados até este passo; este plano não antecipa valores, permissões ou políticas de domínio.

### Marco 4 — Auditoria e integridade

#### Passo 4.1 — Registro append-only

**Entrega:** armazenamento imutável de eventos com sequência por agregado e autoria.

**Validação manual:** registrar eventos, consultar a ordem e tentar update/delete pelas interfaces da aplicação; ambos devem ser recusados.

#### Passo 4.2 — Cadeia de hashes

**Entrega:** hash anterior/atual com algoritmo versionado e verificador independente.

**Validação manual:** verificar cadeia íntegra, adulterar uma cópia em ambiente de teste e confirmar detecção exata do ponto de quebra.

#### Passo 4.3 — Checkpoint verificável

**Entrega:** checkpoint imutável de cadeia ou lote, com algoritmo, escopo, intervalo, raiz verificável e material necessário à prova de inclusão. Árvore de Merkle será utilizada somente se aprovada e justificada pelo volume real.

**Validação manual:** recalcular o checkpoint e a prova usando ferramenta independente; adulterar um item e confirmar falha sem consultar estado mutável do Titan.

#### Passo 4.4 — TimestampProvider

**Entrega:** porta substituível para carimbo do tempo independente, distinguindo instante observado pelo Titan de prova temporal externa. Falha da TSA preserva checkpoint pendente e permite retry ou provider equivalente, sem retroagir ou fabricar carimbo.

**Validação manual:** obter e validar token de provider falso; simular indisponibilidade, confirmar estado pendente e concluir depois com o mesmo hash; rejeitar token cuja assinatura, imprint, política, cadeia ou validade esteja incorreta.

**Portão:** provider self-hosted ou falso é aceito somente para desenvolvimento. Uso jurídico exige perfil de confiança, prestador e jurisdição aprovados.

#### Passo 4.5 — Correção sem sobrescrita

**Entrega:** evento corretivo que referencia o original e preserva ambos.

**Validação manual:** corrigir um fato e reconstruir a timeline mostrando original, justificativa e correção.

#### Passo 4.6 — Idempotência

**Entrega:** chave de idempotência e resultado reproduzível para uma operação delimitada.

**Validação manual:** repetir a mesma requisição e confirmar um único efeito; reutilizar a chave com conteúdo diferente e confirmar conflito.

#### Passo 4.7 — Concorrência otimista

**Entrega:** versão de agregado e erro explícito para atualização desatualizada.

**Validação manual:** executar duas alterações concorrentes e confirmar que uma é aceita e outra retorna conflito sem perda silenciosa.

#### Passo 4.8 — Outbox

**Entrega:** gravação transacional de evento e mensagem de outbox no PostgreSQL, seguida em subtarefas independentes por publicação no Message Broker aprovado e consumo idempotente pelo executor de workers aprovado.

**Validação manual:** simular falha após a transação, reiniciar e confirmar que a mensagem permanece disponível sem duplicar o evento.

**Portão:** publicação exige a ADR do produto concreto de Message Broker; consumo exige ADR própria do executor de workers. A ADR-0006 define a semântica e as garantias, mas não escolhe esses produtos.

### Marco 5 — Evidência e proveniência

#### Passo 5.1 — Evidence e Source

**Entrega:** evidência imutável com campos obrigatórios de `ARCHITECTURE.md`: identificador, origem, autor, timestamp, hash, versão, assinatura e ConfidenceLevel.

**Validação manual:** registrar evidência manual e documental, tentar alterá-las e confirmar que correção exige nova evidência.

#### Passo 5.2 — ConfidenceLevel

**Entrega:** níveis consolidados no `DOMAIN.md`, sem confundir confiança, integridade e verdade.

**Validação manual:** classificar exemplos reais e confirmar que o sistema explica por que recebeu o nível, sem afirmar veracidade.

#### Passo 5.3 — Validade, verificação e revogação

**Entrega:** histórico de validade/verificação/revogação sem exclusão.

**Validação manual:** avaliar uma evidência antes, durante e depois da validade; revogá-la e preservar decisões históricas.

#### Passo 5.4 — Contratos criptográficos

**Entrega:** portas substituíveis `SigningProvider`, `KeyProvider` e `TrustValidator`, sem HSM, KMS, TSA, certificadora ou tipos de fornecedor no Domain. Profiles distinguem integridade interna, assinatura institucional e assinatura qualificada por jurisdição.

**Validação manual:** substituir providers falsos sem alterar Domain/Application; confirmar que cada resultado informa perfil, algoritmo, chave/certificado, instante, escopo e estado `VÁLIDA`, `INVÁLIDA` ou `INDETERMINADA`.

#### Passo 5.5 — Gestão e rotação de chaves

**Entrega:** identificador e finalidade de chave, criptoperíodo, ativação, rotação, revogação, auditoria e referência a armazenamento protegido. Chave privada não será persistida no PostgreSQL, MongoDB, código ou log.

**Validação manual:** rotacionar a chave, assinar novo artefato e continuar verificando o histórico com a chave pública anterior; simular comprometimento, bloquear novas assinaturas e localizar artefatos potencialmente afetados.

**Portão:** produção exige mecanismo de proteção aprovado. Keystore local ou SoftHSM é restrito a desenvolvimento e testes.

#### Passo 5.6 — Assinatura de Evidence

**Entrega:** Signature opcional e vinculada ao perfil exigido pela Policy, preservando bytes/snapshot, algoritmo, `key_id`, certificado ou cadeia, material de validação e timestamp quando aplicável. Signature comprova escopo criptográfico, não veracidade.

**Validação manual:** validar assinatura íntegra, adulterar conteúdo, testar certificado expirado/revogado e confirmar resultados explicados sem apagar a Evidence original.

#### Passo 5.7 — Documento e anexo

**Entrega:** upload conforme ADR, hash verificável, metadados, autorização e nova versão como novo documento.

**Validação manual:** enviar, baixar com permissão, negar sem permissão, adulterar cópia e detectar hash divergente.

#### Passo 5.8 — Proveniência

**Entrega:** encadeamento consultável Source → Evidence → Event, limitado ao que já existe.

**Validação manual:** partir de um evento e chegar à fonte; partir da evidência e identificar todos os usos autorizados.

### Marco 6 — Políticas, regras, avaliações e decisões

#### Passo 6.1 — Policy versionada

**Entrega:** ciclo de vida aprovado para rascunho, publicação, substituição e revogação; versão publicada imutável.

**Validação manual:** publicar, tentar editar, criar nova versão e consultar a versão histórica.

#### Passo 6.2 — Rule versionada

**Entrega:** regra com código, versão, vigência, fonte normativa, severidade, evidências requeridas, justificativa e ação corretiva.

**Validação manual:** validar bordas de vigência, tentar editar versão publicada e confirmar seleção da versão correta por data.

#### Passo 6.3 — Contrato de fatos da vertical

**Entrega:** interface pela qual o Core recebe fatos, sem acessar banco ou tipos do Livestock.

**Validação manual:** usar provider falso e confirmar que o Core funciona sem importar qualquer módulo pecuário.

#### Passo 6.4 — Execução de uma regra pura

**Entrega:** avaliação determinística de uma única regra sobre snapshot de fatos/evidências.

**Validação manual:** executar casos de sucesso, falha, pendência e não aplicável; repetir entrada e confirmar resultado/hash iguais.

#### Passo 6.5 — Agregação em Evaluation

**Entrega:** execução de uma Policy e preservação do snapshot completo, sem ainda gerar dossiê.

**Validação manual:** alterar fatos depois da avaliação e confirmar que a avaliação passada permanece reproduzível.

#### Passo 6.6 — Decision explicável

**Entrega:** resultado agregado com política/versão, regras/resultados, sujeitos afetados, evidências, motivos e ações corretivas.

**Validação manual:** reconstruir manualmente a decisão usando o snapshot e confirmar igualdade; verificar que não existe resultado sem justificativa.

### Marco 7 — Genealogia, não conformidades, recall, dossiê e sincronização

#### Passo 7.1 — Relação universal e temporal

**Entrega:** contrato genérico de relação entre referências, com origem, destino, tipo, período, evento, evidências, Organization, confiança e quantidade opcional.

**Validação manual:** construir grafo fictício sem termos de vertical, consultar relações em datas diferentes e rejeitar travessia não autorizada entre Organizations.

#### Passo 7.2 — Projeções reconstruíveis

**Entrega:** projeção de leitura e referências reversas reconstruíveis a partir dos eventos, sem regras de negócio próprias.

**Validação manual:** apagar somente a projeção em ambiente descartável, reconstruí-la e comparar o resultado; a fonte histórica deve permanecer intacta.

#### Passo 7.3 — NonConformity Core

**Entrega:** detecção, severidade, sujeitos/período afetados, responsável, prazo, ação corretiva, evidência de correção, reavaliação e encerramento sem apagar histórico.

**Validação manual:** abrir por falha de regra, corrigir, reavaliar e encerrar; navegar até todos os fatos, eventos e evidências justificadores.

#### Passo 7.4 — Recall Core

**Entrega:** navegação retrospectiva e prospectiva, janela temporal, controle de ciclos/profundidade, simulação/incidente e localização de decisões afetadas.

**Validação manual:** usar grafo fictício, encontrar origem e destinos, explicar cada caminho, impedir acesso indevido e declarar lacunas como resultado inconclusivo.

#### Passo 7.5 — Dossier Core

**Entrega:** snapshot canônico JSON com sujeito, finalidade, política, regras, fatos, evidências, não conformidades, decisão, ações, versões, timestamps e hash. PDF será uma representação posterior e independente.

**Validação manual:** validar schema, recalcular hash e compreender/reproduzir a decisão sem consultar o banco.

#### Passo 7.6 — VerificationBundle

**Entrega:** pacote autossuficiente com snapshot canônico, versão da serialização, hashes, provas de cadeia/checkpoint, assinaturas, timestamps, certificados, material de revogação, manifesto e política de verificação. O pacote não depende de segredo ou acesso ao banco Titan.

**Validação manual:** verificar o pacote com ferramenta independente e sem Titan; remover material necessário e confirmar resultado `INDETERMINADA`; adulterar conteúdo e confirmar `INVÁLIDA` com ponto exato da falha.

#### Passo 7.7 — API de verificação externa

**Entrega:** contrato público que separa integridade, cadeia, assinatura, timestamp, revogação, perfil de confiança, lacunas e instante da verificação. Resultado nunca usa um único booleano nem afirma veracidade do conteúdo.

**Validação manual:** verificar artefato íntegro, inválido e incompleto; confirmar que a resposta explica escopo, âncora de confiança, material utilizado, warnings e primeira falha detectada.

#### Passo 7.8 — Representação PDF verificável

**Entrega:** PDF continua sendo representação do Dossier. PAdES-LT/LTA e assinatura qualificada somente entram quando um perfil jurídico aprovado exigir; validação do PDF não é apresentada como validação integral da cadeia Titan.

**Validação manual:** validar PDF e VerificationBundle separadamente; confirmar que cada resultado declara seu escopo e que ausência de reconhecimento entre jurisdições produz resultado limitado ou indeterminado.

**Portão:** ICP-Brasil não é apresentada automaticamente como assinatura qualificada eIDAS. Qualquer alegação jurídica exige revisão da legislação, prestador e jurisdição aplicáveis.

#### Passo 7.9 — Synchronization Core

**Entrega:** protocolo de operações offline com ID do dispositivo, Organization, ator, horários distintos, ordem local, idempotência, lotes, confirmação individual, retomada, rejeição e conflito explícito.

**Validação manual:** simular desconexão e reenvio pela API, processar lote parcial, retomar sem duplicação e confirmar que conflitos nunca são resolvidos silenciosamente.

#### Passo 7.10 — Prova completa do Core

**Entrega:** cenário fictício genérico executado por testes, API e Swagger: autenticação → Organization → evento → evidência → genealogia → regra → avaliação → decisão → não conformidade → recall → dossiê → sincronização.

**Validação manual:** substituir providers falsos sem alterar o Core, adulterar cópias para testar integridade, repetir operações e comprovar isolamento entre duas Organizations.

**Portão:** Titan Livestock não começa enquanto todos os contratos, testes arquiteturais e critérios do Core não forem aprovados.

### Marco 8 — Titan Livestock básico

#### Passo 8.1 — RuralProperty

**Entrega:** propriedade rural como conceito da vertical, sempre pertencente a uma Organization.

**Validação manual:** criar, consultar e impedir acesso cruzado; revisar identidade estável.

#### Passo 8.2 — Animal e Identity

**Entrega:** animal com identidade permanente e identificadores versionados, sem implementar movimentação.

**Validação manual:** cadastrar animal, tentar duplicar identidade e alterar identidade permanente; operações inválidas devem falhar.

#### Passo 8.3 — AnimalMovement e PropertyStay

**Entrega:** movimentação que produz permanências temporais sem sobrescrever o histórico.

**Validação manual:** mover entre propriedades, visualizar timeline e rejeitar intervalos impossíveis.

#### Passo 8.4 — LivestockLot e LotMembership

**Entrega:** lote com identidade própria e composição temporal.

**Validação manual:** incluir/remover animal, consultar composição em datas diferentes e preservar associações antigas.

#### Passo 8.5 — Veterinarian

**Entrega:** identidade profissional mínima necessária ao fluxo farmacológico, sem criar funcionalidades clínicas adicionais.

**Validação manual:** cadastrar e vincular ao ato autorizado; rejeitar registro profissional inválido conforme regra aprovada.

### Marco 9 — Fluxo farmacológico do MVP

#### Passo 9.1 — Medication e MedicationBatch

**Entrega:** medicamento e lote rastreável com dados estritamente necessários ao cálculo aprovado.

**Validação manual:** cadastrar lote, rejeitar duplicidade/validade inválida e rastrear fabricante/lote.

#### Passo 9.2 — VeterinaryPrescription

**Entrega:** prescrição imutável vinculada a veterinário, animal, medicamento, dose, via e evidência.

**Validação manual:** criar prescrição completa e rejeitar aplicação sem prescrição válida quando a regra exigir.

#### Passo 9.3 — TreatmentApplication

**Entrega:** aplicação como evento auditável com ator, momento, lote do medicamento e evidências.

**Validação manual:** registrar aplicação, tentar edição e confirmar correção por novo evento.

#### Passo 9.4 — WithdrawalPeriod

**Entrega:** cálculo determinístico de carência conforme regra de negócio previamente aprovada e versionada.

**Validação manual:** conferir manualmente datas-limite, timezone e casos de borda; confirmar preservação da versão da regra.

#### Passo 9.5 — Regra de elegibilidade farmacológica

**Entrega:** uma regra bloqueante que identifica animais em carência e sugere ação corretiva.

**Validação manual:** avaliar animal fora e dentro da carência; confirmar motivo, evidência, versão e sujeito afetado.

#### Passo 9.6 — Avaliação de lote e reavaliação

**Entrega:** lote bloqueado por animal em carência, remoção temporal do animal e nova avaliação, preservando ambas as decisões.

**Validação manual:** executar ponta a ponta o cenário `REJECTED → remoção → APPROVED` e comparar snapshots/hashes.

### Marco 10 — Adaptação Livestock, API e prova da vertical

#### Passo 10.1 — Timeline Livestock

**Entrega:** consulta cronológica reconstruída a partir dos eventos, sem usar estado atual como substituto do histórico.

**Validação manual:** consultar animal, lote e tratamento; confirmar ordem, correções, autoria e evidências.

#### Passo 10.2 — Template Livestock do Dossier JSON

**Entrega:** snapshot JSON canônico da decisão farmacológica com sujeito, finalidade, política, regras, fatos, evidências, decisão, ações, versões, timestamps e hash.

**Validação manual:** validar schema, recalcular hash e entender a decisão sem acesso ao banco.

#### Passo 10.3 — Dossier PDF

**Entrega:** representação fiel do snapshot, com template fornecido pela vertical e código público de verificação.

**Validação manual:** comparar JSON/PDF campo a campo, verificar legibilidade e recalcular a integridade usando o código.

#### Passo 10.4 — API mínima do fluxo aprovado

**Entrega:** endpoints estritamente necessários para operar o cenário já implementado, cada um com autenticação, autorização, teste positivo, negativo e tratamento de erro.

**Validação manual:** operar o fluxo via API com dois papéis e duas organizações; validar negações, erros e isolamento.

#### Passo 10.5 — Console técnico web opcional

**Entrega:** somente se a validação por API/Swagger for insuficiente, criar telas descartáveis ou evolutivas para explorar grafo de recall, progresso, conflitos offline e dossiê. Não inclui frontend de produto, dashboard ou design system.

**Validação manual:** comparar todos os resultados do console com a API e confirmar que nenhuma regra de negócio foi implementada no navegador.

#### Passo 10.6 — Cenário demonstrativo reproduzível

**Entrega:** fixtures fictícias e roteiro automatizado do fluxo completo, sem dados reais ou pessoais.

**Validação manual:** recriar o ambiente do zero e executar cadastro, tratamento, bloqueio, correção, reavaliação e dossiê.

### Marco 11 — Expansões posteriores, cada uma sujeita a novo plano

Os itens seguintes não estão autorizados por este plano. Após validação do MVP, cada tema deverá receber decomposição própria, confirmação de regras e portões manuais:

1. GTA e SISBOV sandbox;
2. PWA operacional offline da vertical;
3. RFID e dispositivos;
4. regras adicionais de recall e não conformidades Livestock;
5. motor de risco;
6. integração Omni-Data;
7. alimentação e demais insumos;
8. balanço;
9. portal de auditoria;
10. Titan Parts como prova de generalização do Core;
11. programa ou template de compartilhamento em escala para emissão governada de múltiplos grants equivalentes.

O item 11 reconhece uma necessidade futura do produto, mas não define novo conceito de domínio. Sua implementação exige validar o caso de uso, preservar assessments e grants individuais auditáveis e registrar decisão arquitetural própria antes de introduzir template, campanha, programa ou emissão em massa.

## 6. Critérios de conclusão por marco

| Marco | Evidência de conclusão |
|---|---|
| 0 | Documentos de autoridade coerentes e decisões aprovadas |
| 1 | Ambiente reproduzível, health check e CI verde |
| 2 | Contratos universais determinísticos, sem termos pecuários |
| 3 | Autenticação, papéis e isolamento comprovados com duas Organizations |
| 4 | Histórico append-only, adulteração detectável, checkpoints, prova temporal, idempotência e concorrência testadas |
| 5 | Evidências imutáveis, assinaturas por perfil, rotação de chaves e proveniência reconstruível |
| 6 | Decisão reproduzível e explicável a partir de política versionada |
| 7 | Genealogia, não conformidade, recall, dossiê, verificação externa e sincronização comprovados sem vertical |
| 8 | Identidade, movimentação e lotes pecuários com histórico temporal |
| 9 | Fluxo farmacológico bloqueia, corrige e reavalia sem apagar o passado |
| 10 | Vertical usa o Core sem contaminá-lo; API e dossiê são verificáveis |

## 7. Riscos e controles

| Risco | Controle no plano |
|---|---|
| Escopo grande demais | Um incremento vertical coeso; dividir quando responsabilidades ou riscos forem independentes |
| Core contaminado pela vertical | Contrato de provider e teste arquitetural |
| Dado de uma Organization exposto a outra | Testes negativos desde Identity & Access e em todo endpoint |
| “Imutabilidade” apenas convencional | Append-only, correções vinculadas e verificador de integridade |
| Relógio local apresentado como prova temporal | Instante observado separado de timestamp externo validado |
| TSA indisponível causar carimbo fabricado ou perda | Checkpoint pendente, retry e provider equivalente sem retroatividade |
| Chave privada armazenada junto aos dados | KeyProvider e armazenamento protegido externo ao banco e ao código |
| Rotação ou comprometimento apagar validade histórica | `key_id`, certificados públicos preservados, revogação e análise de impacto |
| Certificado self-signed apresentado como qualificado | Profiles explícitos e trust anchor declarado em cada verificação |
| Integridade ou assinatura confundida com verdade | Resultado explica escopo criptográfico e nunca certifica conteúdo material |
| ICP-Brasil apresentada como qualificação automática na UE | Perfil por jurisdição, Trusted Lists aplicáveis e revisão jurídica |
| Decisão impossível de reproduzir | Snapshots, serialização canônica, versões e hashes |
| Regra regulatória incorreta | Fonte normativa, aprovação humana, vigência e testes de borda |
| Dependência prematura de integração/hardware | Entrada manual e adaptadores somente quando necessários |
| Complexidade excessiva | Diff revisável; contratos genéricos só entram quando exigidos pelo incremento atual |
| “Gratuito” confundido com custo zero | Inventário de licenças e registro dos custos inevitáveis de infraestrutura e operação |
| Gratuidade incompatível com confiança acreditada | Core gratuito com providers substituíveis; serviços qualificados são opcionais e têm custo registrado |
| Core abstrato sem prova | Providers falsos, provas de contrato e cenário genérico completo antes da vertical |
| Divergência documental | Marco 0 obrigatório e releitura antes de cada passo |
| Validação manual subjetiva | Roteiro observável com resultados esperados em cada entrega |

## 8. Regra de interrupção

O trabalho deve parar imediatamente quando:

- houver conflito entre documento de autoridade e código;
- uma regra necessária não existir em `DOMAIN.md`;
- critérios de aceitação estiverem ambíguos;
- o incremento misturar funcionalidades ou responsabilidades independentes;
- surgir alteração de API pública não aprovada;
- uma dependência nova não tiver justificativa;
- um teste relacionado falhar;
- Ruff ou Mypy falhar;
- a validação manual for reprovada.

Após a interrupção, deve-se apresentar evidências e solicitar uma decisão; nunca escolher silenciosamente.

## 9. Próximo incremento

Os Passos 0.1 a 3.2 estão concluídos e aprovados. O próximo incremento é o **Passo 3.3 — Membership**.
