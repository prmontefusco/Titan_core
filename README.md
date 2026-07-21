# Titan

Titan é uma plataforma de confiança para decisões auditáveis em cadeias reguladas.

O Titan Core é independente das verticais. A primeira vertical planejada é o Titan Livestock, que somente será iniciada após a comprovação das capacidades do Core.

## Estado atual

O projeto está na fundação documental.

- Passos 0.1 a 0.4 concluídos;
- ADRs 0001 a 0029 aceitas em `docs/adr/`;
- workspace Python mínimo criado, com API técnica, infraestrutura local incremental, conexão PostgreSQL e migration técnica inicial, ainda sem pacote de domínio;
- pytest, Ruff e Mypy configurados, com teste de sanidade e verificação arquitetural inicial;
- aplicação FastAPI mínima implementada com health check técnico e erros em Problem Details;
- PostgreSQL com PostGIS configurado no Docker Compose, com health check e volume persistente;
- MongoDB local configurado com autenticação, health check e volume persistente, ainda sem integração GridFS;
- Keycloak local configurado como OIDC Provider inicial, com PostgreSQL dedicado, readiness e persistência;
- RabbitMQ local configurado como Message Broker inicial, com autenticação, health check e persistência;
- Valkey local configurado como cache efêmero autenticado, sem persistência e com limite de memória;
- progresso e validações registrados em `docs/CHECKLIST_DE_IMPLEMENTACAO.md`;
- workflow de qualidade do GitHub Actions configurado, ainda pendente de execução remota;
- os comandos oficiais estão definidos em `DEVELOPMENT.md`, com disponibilidade vinculada aos passos que criarão seus manifestos e executáveis.

Não execute comandos antigos ou inferidos. Enquanto o respectivo manifesto não existir, o comando ainda não está disponível.

## Arquitetura aprovada

- monólito modular;
- executáveis em `apps/`;
- capacidades reutilizáveis em `packages/`;
- Python e FastAPI no backend;
- PostgreSQL como banco transacional autoritativo, com PostGIS para evidência geoespacial vetorial;
- MongoDB/GridFS somente para bytes de documentos autorizados;
- Valkey somente para cache e coordenação efêmera;
- OIDC Provider por contrato substituível;
- Message Broker por contrato substituível;
- React para eventual frontend;
- Docker Compose para o ambiente local incremental.

Keycloak e RabbitMQ são as implementações iniciais dos contratos substituíveis de OIDC Provider e Message Broker. O executor de workers ainda exige decisão própria antes da adoção.

## Documentos de autoridade

Leia, nesta ordem de trabalho:

1. `VISION.md`;
2. `DOMAIN.md`;
3. `ARCHITECTURE.md`;
4. `DEVELOPMENT.md`;
5. `docs/PLANO_DE_IMPLEMENTACAO_VALIDADO.md`.
6. `docs/CHECKLIST_DE_IMPLEMENTACAO.md`, para estado, evidências e validações de cada passo.

As ADRs registram as decisões e suas consequências. Documentos históricos em `docs/` não prevalecem sobre os documentos de autoridade.

## Próximo passo

Os Passos 1.4A a 3.3 estão concluídos e aprovados. O próximo incremento é o Passo 3.4 — Role e Permission.

## Executar a API

```text
python -m uv sync --locked
python -m uv run --locked uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

Em outro terminal:

```text
curl.exe --include http://127.0.0.1:8000/health
curl.exe --include http://127.0.0.1:8000/rota-inexistente
```

Os comandos completos de teste estão no checklist e em `DEVELOPMENT.md`.

## Executar PostgreSQL com PostGIS

```text
docker compose up --detach postgres
docker compose ps
docker compose exec --no-TTY postgres psql --username titan --dbname titan --command "SELECT postgis_full_version();"
docker compose down
```

`docker compose down` preserva o volume. Não utilize `--volumes` na verificação ordinária.

## Executar MongoDB

```text
docker compose up --detach mongo
docker compose ps
docker compose exec --no-TTY mongo mongosh --quiet --username titan_root --password titan_local_dev_password --authenticationDatabase admin --eval "db.version()"
docker compose down
```

## Executar o OIDC Provider local

```text
docker compose up --detach keycloak
docker compose ps
curl.exe http://localhost:8080/realms/master/.well-known/openid-configuration
docker compose down
```

O modo `start-dev` e as credenciais padrão do Compose são exclusivos do ambiente local. Realm, clientes, PKCE, MFA e integração com a API pertencem ao Passo 3.5.

Os requisitos e separações previstos para um futuro servidor estão inventariados em `docs/REQUISITOS_DE_PRODUCAO.md`.

## Executar o Message Broker local

```text
docker compose up --detach --wait rabbitmq
docker compose ps
docker compose exec --no-TTY rabbitmq rabbitmq-diagnostics server_version
curl.exe --user titan:titan_rabbitmq_local_dev_password http://127.0.0.1:15672/api/overview
docker compose down
```

A interface de administração e as credenciais padrão são exclusivamente locais. Publisher, Outbox, filas funcionais e executor de workers não foram implementados nesta subtarefa.

## Executar o cache efêmero local

```text
docker compose up --detach --wait valkey
docker compose ps
docker compose exec --no-TTY valkey sh -c 'VALKEYCLI_AUTH="$VALKEY_PASSWORD" valkey-cli ping'
docker compose rm --stop --force valkey
```

Valkey não possui volume e usa RDB/AOF desativados. Recriar o container elimina todas as chaves por desenho; nenhum dado autoritativo pode depender delas.

## Executar migrations PostgreSQL

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked alembic current
```

A revisão inicial cria somente `alembic_version`, estrutura técnica global sem dado de domínio. SQLAlchemy nunca cria schema automaticamente.

## Qualidade e CI

O workflow `.github/workflows/quality.yml` executa em `push` e `pull_request`:

```text
python -m uv lock --check
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
```

A validação remota depende de publicar ou conectar este repositório ao GitHub. Nenhum deploy ou publicação é executado pelo workflow.

O MongoDB permanece restrito à infraestrutura local; GridFS e integração com a API serão implementados somente em passos próprios.
