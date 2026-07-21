# Desenvolvimento do Titan

Este documento é a referência canônica dos comandos de desenvolvimento.

Um comando somente é considerado disponível depois que seu manifesto, configuração e alvo existirem e tiverem sido validados no passo responsável. Documentar um comando não autoriza antecipar aplicação, pacote, frontend ou infraestrutura.

---

# Regra número 1

Nunca implemente grandes funcionalidades.

---

# Fluxo

Planejar

↓

Implementar

↓

Testar

↓

Corrigir

↓

Revisar

↓

Commit

---

# Cada tarefa deve

Possuir testes.

Ser reversível.

Gerar um único commit.

Durante o MVP não existe limite fixo de linhas. Cada tarefa continua limitada a uma funcionalidade coesa e deve produzir diff revisável. Dividir quando houver responsabilidades independentes, risco distinto ou possibilidade de validação separada.

O Codex implementa autonomamente o incremento aprovado, incluindo código, testes relacionados, fixtures fictícias, correções decorrentes da própria alteração e documentação diretamente afetada.

---

# Commits

feat:

fix:

refactor:

docs:

test:

ci:

chore:

---

# Antes de editar

Ler apenas os arquivos necessários.

Não alterar código fora do escopo.

Explicar resumidamente mudanças não triviais.

Mudanças rotineiras, reversíveis e pertencentes ao escopo aprovado podem prosseguir sem portão manual intermediário.

Exigem confirmação prévia:

- ADR ou mudança de arquitetura, domínio ou escopo;
- migration destrutiva ou alteração incompatível de dados;
- autenticação, autorização, criptografia ou isolamento;
- dependência, serviço externo ou custo recorrente novo;
- API pública incompatível;
- publicação, implantação, comunicação externa ou ação irreversível.

---

# Execução autônoma

Depois que o objetivo e o escopo de um incremento estiverem aprovados, o Codex pode prosseguir até alcançar os critérios de aceite ou encontrar bloqueio real.

Não é necessária nova confirmação para:

- criar implementação interna compatível com os contratos vigentes;
- criar testes positivos, negativos, de autorização e de erro;
- executar e repetir testes relacionados;
- executar Ruff, Mypy e verificações arquiteturais;
- corrigir código ou teste introduzido pelo incremento;
- atualizar documentação operacional diretamente afetada;
- inspecionar logs e resultados locais sem dados reais;
- delegar tarefas independentes a agentes de IA.

O Codex interrompe e solicita decisão somente quando a continuação exigir uma categoria de confirmação prévia, houver conflito entre documentos e código, faltar requisito que altere materialmente o resultado ou a correção exigir ampliar o escopo.

## Coordenação de agentes

O agente principal de cada incremento:

1. decompõe somente quando existirem tarefas realmente independentes;
2. atribui ownership de arquivos ou módulos sem sobreposição;
3. fornece contratos, proibições e critérios de aceite;
4. recebe e revisa os resultados;
5. integra alterações sequencialmente;
6. executa a validação final do conjunto;
7. relata riscos, limitações e falhas preexistentes.

Agentes podem trabalhar paralelamente em implementação, testes, pesquisa e revisão. Dois agentes não editam simultaneamente o mesmo arquivo ou fronteira. O agente revisor não modifica silenciosamente a solução revisada; registra achados ou recebe tarefa explícita de correção.

---

# Depois

Executar apenas os testes relacionados.

Rodar Ruff.

Rodar Mypy.

Revisar Diff.

Falhas relacionadas ao incremento devem ser corrigidas e verificadas novamente de forma autônoma. Falhas preexistentes ou fora do escopo são registradas sem refatoração oportunista.

---

# Comandos oficiais

Todos os comandos são executados a partir da raiz do repositório.

## Disponibilidade

| Capacidade | Disponível após | Estado atual |
|---|---|---|
| Ambiente Python e lockfile | Passo 1.1 | Disponível |
| Testes, Ruff e Mypy | Passo 1.2 | Disponível |
| API | Passo 1.3 | Disponível |
| Docker Compose — PostgreSQL/PostGIS | Passo 1.4A | Disponível |
| Docker Compose — MongoDB | Passo 1.4B | Disponível |
| Docker Compose — Keycloak e banco dedicado | Passo 1.4C | Disponível |
| Docker Compose — RabbitMQ | Passo 1.4D | Disponível |
| Docker Compose — Valkey | Passo 1.4E | Disponível |
| Conexão PostgreSQL e Alembic | Passo 1.5 | Disponível |
| GitHub Actions — qualidade | Passo 1.6 | Disponível e validado remotamente |
| Shared Kernel — identificadores e referências | Passo 2.1 | Disponível e aprovado |
| Shared Kernel — relógio e datas UTC | Passo 2.2 | Disponível e aprovado |
| Shared Kernel — serialização canônica | Passo 2.3 | Disponível e aprovado |
| Core Domain — contrato de evento | Passo 2.4 | Disponível e aprovado |
| Core Identity — Organization protegida por RLS | Passo 3.1 | Disponível e aprovado |
| Interface técnica de validação | Passo próprio autorizado | Condicionada à necessidade de teste |
| Frontend de produto | Marco próprio aprovado | Indisponível |

Ausência de manifesto ou alvo produz indisponibilidade, não permissão para improvisar outro comando.

## Python

O ambiente Python será gerenciado por `uv` e reproduzido pelo lockfile.

Bootstrap da versão aprovada da ferramenta:

```text
python -m pip install --user "uv==0.11.30"
```

Sincronização do workspace:

```text
python -m uv sync --locked
```

Não instalar dependências do projeto diretamente com `pip`. Nova dependência exige justificativa, alteração do manifesto e atualização deliberada do lockfile.

## Testes

Quando um teste comprovar proibição numerada de `DOMAIN.md`, seu nome, marcador ou documentação deve citar o respectivo identificador `P-NNN`. Uma proibição pode exigir vários testes e um teste pode cobrir várias proibições. Ausência de teste deve permanecer visível; não se presume cobertura por intenção.

Suíte relacionada:

```text
python -m uv run --locked pytest <caminho>
```

Teste específico:

```text
python -m uv run --locked pytest <arquivo>::<teste>
```

Suíte completa, somente quando o passo ou portão exigir:

```text
python -m uv run --locked pytest
```

## Ruff

```text
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
```

Correções e formatação não são executadas automaticamente durante revisão. Qualquer alteração produzida por ferramenta deve permanecer dentro do escopo aprovado.

## Mypy

O alvo vigente é definido em `pyproject.toml` e cresce somente com os pacotes reais:

```text
python -m uv run --locked mypy
```

Os alvos definitivos devem corresponder aos pacotes reais criados nos incrementos posteriores.

## API

Inicialização local da API:

```text
python -m uv run --locked uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

Validação técnica:

```text
curl.exe --include http://127.0.0.1:8000/health
curl.exe --include http://127.0.0.1:8000/rota-inexistente
```

O endpoint `/health` informa somente a saúde do processo e não expõe domínio. Encerre o servidor com `Ctrl+C`.

## Docker Compose

Após a criação de `compose.yaml` no Passo 1.4:

```text
docker compose config
docker compose up --detach
docker compose ps
docker compose down
```

OIDC Provider local:

```text
docker compose up --detach --wait keycloak
docker compose ps
curl.exe http://localhost:8080/realms/titan/.well-known/openid-configuration
docker compose exec --no-TTY keycloak /opt/keycloak/bin/kc.sh --version
```

O realm local `titan` é importado com clientes separados `titan-api` e `titan-swagger`. O Swagger usa Authorization Code com PKCE S256. Para executar a API protegida:

```powershell
$env:TITAN_OIDC_ISSUER = "http://localhost:8080/realms/titan"
$env:TITAN_OIDC_AUDIENCE = "titan-api"
python -m uv run --locked uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

O serviço `keycloak` inicia também `keycloak-postgres`. O banco do provider não publica porta no host. `start-dev`, HTTP e credenciais padrão são permitidos somente para desenvolvimento local; não constituem configuração de produção. Nunca versionar User real, senha, token ou client secret.

Message Broker local:

```text
docker compose up --detach --wait rabbitmq
docker compose ps
docker compose exec --no-TTY rabbitmq rabbitmq-diagnostics server_version
curl.exe --user titan:titan_rabbitmq_local_dev_password http://127.0.0.1:15672/api/overview
docker compose down
```

AMQP e management são limitados a loopback. Usuário, senha, vhost e portas podem ser substituídos por `TITAN_RABBITMQ_USER`, `TITAN_RABBITMQ_PASSWORD`, `TITAN_RABBITMQ_VHOST`, `TITAN_RABBITMQ_AMQP_PORT` e `TITAN_RABBITMQ_MANAGEMENT_PORT`. Os padrões são exclusivamente locais.

Cache efêmero local:

```text
docker compose up --detach --wait valkey
docker compose ps
docker compose exec --no-TTY valkey sh -c 'VALKEYCLI_AUTH="$VALKEY_PASSWORD" valkey-cli ping'
docker compose exec --no-TTY valkey sh -c 'VALKEYCLI_AUTH="$VALKEY_PASSWORD" valkey-cli CONFIG GET maxmemory maxmemory-policy save appendonly'
docker compose rm --stop --force valkey
```

Senha, porta e limite de dataset podem ser substituídos por `TITAN_VALKEY_PASSWORD`, `TITAN_VALKEY_PORT` e `TITAN_VALKEY_MAXMEMORY`. Os padrões são exclusivamente locais. Valkey não possui volume nem persistence mode; sua perda total é comportamento esperado.

## PostgreSQL e migrations

A conexão autoritativa exige `TITAN_DATABASE_URL` no formato `postgresql+psycopg://`. A variável não possui fallback para impedir conexão silenciosa ao banco errado.

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked alembic current
```

Bootstrap mínimo da Organization operadora, após `alembic upgrade head`:

```powershell
$env:TITAN_OPERATOR_ORGANIZATION_ID="<uuid-estavel-da-organization-operadora>"
$env:TITAN_BOOTSTRAP_AUTHORITY_ACTOR_ID="<uuid-do-ator-administrativo>"
$env:TITAN_ENVIRONMENT="DESENVOLVIMENTO"
python -m uv run --locked python -m apps.bootstrap
```

Ambientes permitidos: `DESENVOLVIMENTO`, `TESTE`, `HOMOLOGACAO` e `PRODUCAO`. O comando não cria User, Membership, Role ou Permission. A primeira aplicação retorna `APLICADO`; repetições compatíveis retornam `JA_APLICADO`.

Teste reversível enquanto somente a revisão técnica inicial existir:

```powershell
python -m uv run --locked alembic downgrade base
python -m uv run --locked alembic current
python -m uv run --locked alembic upgrade head
```

Não execute `downgrade` em ambiente compartilhado ou com migrations posteriores sem plano e autorização específicos. Migrations são o único mecanismo autorizado para alterar schema; `create_all()` e equivalentes não são usados.

## Integração contínua

O workflow `.github/workflows/quality.yml` executa testes, verificações arquiteturais, Ruff e Mypy em `push` e `pull_request`.

Regras vigentes:

- actions de terceiros fixadas por commit SHA;
- permissão global limitada a `contents: read`;
- credencial do checkout não permanece configurada;
- Python, uv e dependências seguem `.python-version`, `pyproject.toml` e `uv.lock`;
- jobs não possuem secret, banco externo, deploy ou permissão de escrita;
- concorrência mais antiga da mesma referência pode ser cancelada.

Antes de aprovar o Passo 1.6, acompanhar no GitHub uma execução verde e uma falha intencional em branch de teste. A falha controlada não deve ser incorporada à branch principal.

Serviços serão adicionados e validados individualmente. `down` não deve usar `--volumes` durante a verificação ordinária de persistência.

O PostgreSQL/PostGIS autoritativo local é iniciado separadamente:

```text
docker compose up --detach postgres
docker compose ps
docker compose exec --no-TTY postgres psql --username titan --dbname titan --command "SELECT postgis_full_version();"
docker compose down
```

Os valores padrão são exclusivamente locais. Para substituí-los, defina `TITAN_POSTGRES_DB`, `TITAN_POSTGRES_USER`, `TITAN_POSTGRES_PASSWORD` e `TITAN_POSTGRES_PORT` no ambiente antes de executar o Compose. Não reutilize os valores locais fora do desenvolvimento.

O MongoDB local é iniciado separadamente:

```text
docker compose up --detach mongo
docker compose ps
docker compose exec --no-TTY mongo mongosh --quiet --username titan_root --password titan_local_dev_password --authenticationDatabase admin --eval "db.version()"
docker compose down
```

O comando acima utiliza somente as credenciais fictícias padrão. Se `TITAN_MONGO_ROOT_USERNAME` ou `TITAN_MONGO_ROOT_PASSWORD` forem substituídas, utilize os valores locais correspondentes no comando. MongoDB não está integrado à API e não armazena metadados ou entidades de domínio nesta etapa.

## Frontend

Não existe frontend nem manifesto JavaScript.

Uma interface técnica mínima pode ser criada em passo próprio autorizado quando API, Swagger, testes automatizados ou comandos não forem suficientes para validar adequadamente uma capacidade.

Finalidades permitidas incluem:

- teste funcional de fluxo completo;
- inspeção visual, responsividade e estados da interface;
- acessibilidade básica e navegação por teclado;
- autenticação, encerramento de sessão e expiração;
- autorização, `OrganizationContext`, Purpose e `FieldScope`;
- acessos permitidos, negados e parcialmente reduzidos;
- isolamento e ausência de vazamento entre Organizations;
- estados de carregamento, vazio, erro, indisponibilidade, offline e sincronização;
- comparação do resultado apresentado com a API e o Core.

A interface técnica:

- declara a hipótese e o critério de validação;
- contém somente apresentação e integração;
- não implementa, duplica ou corrige regra de negócio no navegador;
- não transforma ocultação visual em controle de autorização;
- não utiliza dados ou credenciais reais;
- pode ser descartável, desde que o resultado e as limitações do teste sejam registrados;
- não se torna frontend de produto sem decisão e escopo próprios.

Gerenciador de pacotes, comandos de desenvolvimento, testes, typecheck e build serão definidos no passo que autorizar a primeira interface. Depois de validados, passam a integrar a tabela de disponibilidade deste documento.

## Regra de publicação

Antes de marcar um comando como disponível:

1. criar o manifesto ou alvo no passo autorizado;
2. fixar versões e dependências necessárias;
3. executar o comando a partir da raiz;
4. registrar pré-requisitos e resultado esperado;
5. confirmar execução em ambiente limpo ou equivalente;
6. atualizar a tabela de disponibilidade neste documento.

---

# Nunca

Criar código morto.

Criar abstrações futuras.

Duplicar regras.

Ignorar testes.

Fazer refatorações oportunistas.

Adicionar dependências sem justificativa.

---

# Qualidade

Todo endpoint deve possuir:

teste positivo

teste negativo

autorização

tratamento de erro

---

# Banco

Toda alteração deve possuir migration.

Nunca alterar estrutura manualmente.

---

# Segurança

Nunca armazenar senha.

Nunca registrar tokens.

Nunca registrar secrets.

Nunca usar credenciais reais.

---

# Performance

Performance nunca é prioridade antes da corretude.

---

# Revisão

Todo código deve responder:

Está simples?

Está testável?

Está documentado?

Está desacoplado?
