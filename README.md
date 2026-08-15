# Titan Technologies

Titan Technologies é uma plataforma de confiança para decisões auditáveis em
cadeias reguladas. Ela registra evidências, relações, políticas, avaliações e
decisões de modo temporal, explicável e verificável.

A premissa central é simples: o Titan não afirma que algo é verdadeiro. O Titan
registra que uma decisão foi tomada com determinadas evidências, sob determinada
política, em determinado momento, com razões e limitações explícitas.

O Titan não é ERP, sistema financeiro, sistema fiscal ou sistema de RH. Esses
sistemas podem ser integrados, mas não definem a fronteira do produto.

## Estado Atual

Este repositório contém uma implementação ativa, não apenas documentação.

A plataforma inclui hoje:

- monólito modular Python com API FastAPI, worker e frontend React;
- identidade Core com Organizations, Users, Memberships, Roles e Permissions;
- operações protegidas por `OrganizationContext` construído pelo servidor;
- persistência PostgreSQL/PostGIS com migrations Alembic e Row-Level Security;
- eventos de auditoria append-only, cadeia de hashes e checkpoints;
- capacidades de Evidence, Policy, Rule, Evaluation, Decision, Dossier e
  VerificationBundle;
- infraestrutura Outbox/Inbox com RabbitMQ e suporte a worker;
- autenticação OIDC local com Keycloak usando Authorization Code + PKCE;
- Valkey local somente para cache e coordenação efêmera;
- MongoDB local provisionado para a fronteira futura de documentos, sem ser fonte
  de verdade de domínio;
- roteiros manuais executáveis em `apps/validacao/`;
- testes automatizados de domínio, aplicação, API, integração, infraestrutura,
  arquitetura e frontend.

A vertical implementada é o **Titan Livestock**, focada em rastreabilidade
pecuária, conformidade sanitária, evidência territorial, elegibilidade por
mercado, revisão de decisão e dossiês reproduzíveis.

A fotografia factual das capacidades está em `docs/product/CAPABILITY_MAP.md`.
O ledger oficial de entregas, evidências de validação e lacunas conhecidas está
em `docs/CHECKLIST_DE_IMPLEMENTACAO.md`.

## Estrutura do Repositório

```text
apps/
  api/          executável FastAPI
  worker/       executável de processamento assíncrono
  web/          frontend React/Vite
  validacao/    roteiros executáveis de validação manual

packages/
  core_*        domínio, aplicação e infraestrutura do Titan Core
  livestock_*   domínio, aplicação e infraestrutura da vertical Livestock
  shared_kernel identificadores, referências, tempo e serialização
  testing/      suporte de testes

docs/
  adr/          Architecture Decision Records
  plans/        discoveries e design packages
  product/      mapas factuais de capacidades
  specs/        documentos do lifecycle de decisão de produto
```

A direção de dependência é para dentro:

```text
Presentation / Infrastructure
  -> Application
    -> Domain
```

O Core não depende das verticais. As verticais dependem apenas de contratos
aprovados do Core.

## Documentos de Autoridade

Antes de implementar, leia estes documentos nesta ordem:

1. `VISION.md` — direção e filosofia do produto;
2. `DOMAIN.md` — linguagem canônica e invariantes de domínio;
3. `ARCHITECTURE.md` — fronteiras e decisões arquiteturais;
4. `DEVELOPMENT.md` — fluxo, comandos e portões de qualidade;
5. `AGENTS.md` — regras operacionais para agentes de IA;
6. `docs/CHECKLIST_DE_IMPLEMENTACAO.md` — estado entregue, evidências e próximos
   incrementos.

As ADRs em `docs/adr/` registram decisões arquiteturais. Planos e Design Packages
não substituem os documentos de autoridade. `docs/specs/README.md` define o
lifecycle `IDEA -> DISCOVERY -> DECISION -> SPEC -> PLAN -> BUILD -> VERIFY ->
ACCEPT`.

## Desenvolvimento Local

Use Python via `uv` como módulo, sempre com o ambiente travado:

```powershell
python -m uv sync --locked
```

Prepare o PostgreSQL e aplique as migrations:

```powershell
docker compose up --detach --wait postgres
$env:TITAN_MIGRATION_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
$env:TITAN_RUNTIME_DATABASE_PASSWORD="titan_local_runtime_password"
python -m uv run --locked python -m apps.provision_runtime_database_role
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan_app:titan_local_runtime_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
```

Execute a API:

```powershell
python -m uv run --locked uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

Execute o frontend:

```powershell
cd apps/web
npm install
npm run dev
```

Para o fluxo web autenticado, suba também o Keycloak e configure o realm/client
OIDC local conforme `DEVELOPMENT.md`. As credenciais padrão do Docker Compose são
exclusivas de desenvolvimento local; nunca as reutilize fora desse ambiente.

## Portões de Qualidade

Verificações do backend e do repositório:

```powershell
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
$env:TITAN_MIGRATION_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic check
```

Verificações do frontend:

```powershell
cd apps/web
npm run test
npm run lint
npm run build
```

O workflow de qualidade do GitHub Actions executa testes, Ruff, format check,
Mypy e Alembic check em `push` e `pull_request`.

## Princípios de Desenvolvimento

O Titan evolui por incrementos pequenos e auditáveis. Uma feature começa como
Discovery, não como código. Código é consequência de uma decisão de produto com
comportamento, escopo, riscos, testes e documentação afetada bem definidos.

Não altere silenciosamente arquitetura, conceitos de domínio, tenancy,
autenticação, autorização, criptografia, contratos públicos, migrations ou
comportamento irreversível. Decisões arquiteturais materiais exigem ADR.

Não duplique regras de negócio no frontend. A UI representa capacidades
autorizadas, solicita operações ao backend e mostra estado, razões e limitações.
Os contratos do backend permanecem autoritativos.

## Referências Úteis

- `docs/product/CAPABILITY_MAP.md` — fotografia atual das capacidades;
- `docs/plans/ADMIN_UI_CAPABILITY_MAP.md` — Discovery atual da Admin UI;
- `docs/plans/TITAN_UI_ARCHITECTURE_V1_DESIGN_PACKAGE.md` — orientação
  arquitetural aprovada para UI;
- `DEVELOPMENT.md` — referência completa de comandos locais;
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md` — ledger oficial de entrega.
