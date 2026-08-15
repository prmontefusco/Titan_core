# Titan Technologies

Titan Technologies é uma plataforma de confiança para decisões auditáveis em cadeias reguladas. O produto registra evidências, relações, políticas, avaliações e decisões de modo explicável, temporal e verificável — sem afirmar automaticamente que uma informação é verdadeira.

O Titan Core permanece independente das verticais. A vertical implementada hoje é o **Titan Livestock**, voltada à rastreabilidade, conformidade sanitária e territorial, elegibilidade por mercado e proveniência na cadeia pecuária.

## Estado atual

O repositório contém uma implementação ativa, não apenas uma fundação documental:

- monólito modular Python com API FastAPI, worker e frontend React;
- Core com identidade, Organizations, autorização, auditoria append-only, integridade, evidências, políticas, regras, avaliações, decisões, dossiês e verificação independente;
- isolamento multi-tenant por `OrganizationContext`, autorização da aplicação e Row-Level Security (RLS) no PostgreSQL;
- persistência PostgreSQL/PostGIS com migrations Alembic; MongoDB está provisionado localmente para a fronteira de documentos, mas não é fonte de dados de domínio;
- Outbox/Inbox e RabbitMQ para entrega assíncrona, com worker para fluxos Livestock;
- capacidades de operação offline e sincronização segura no Core;
- Livestock: propriedades, animais, movimentações, lotes, reprodução, tratamentos, campanhas sanitárias, carência, elegibilidade de mercado, decisão humana, capturas externas e territoriais, rastreabilidade de transformação e integrações simuladas;
- geoespacial: geometrias de propriedades, PostGIS e adapter para o provider territorial configurável;
- frontend técnico para os fluxos Livestock e QA de captura territorial;
- validações manuais executáveis em `apps/validacao/`, sem cópia manual de identificadores;
- testes automatizados de domínio, aplicação, API, integração, infraestrutura, arquitetura e frontend; CI no GitHub Actions.

O estado detalhado de cada marco, evidência de validação e lacunas conhecidas está em `docs/CHECKLIST_DE_IMPLEMENTACAO.md`.

## Arquitetura

- monólito modular em monorepo;
- executáveis em `apps/`; capacidades reutilizáveis e limites de domínio em `packages/`;
- dependências para dentro: apresentação/infraestrutura → aplicação → domínio;
- Core não depende de verticais; Livestock depende somente de contratos públicos do Core;
- PostgreSQL/PostGIS é o banco transacional autoritativo; migrations são o único meio de alterar o schema;
- Keycloak é o provider OIDC local; RabbitMQ é o broker inicial; Valkey é cache e coordenação efêmera;
- Docker Compose fornece o ambiente local.

As fronteiras são verificadas automaticamente em `tests/architecture/`. A arquitetura de destino e os limites incrementais estão em `ARCHITECTURE.md`.

## Documentos de autoridade

Antes de implementar, leia nesta ordem:

1. `VISION.md` — direção do produto;
2. `DOMAIN.md` — linguagem e invariantes de domínio;
3. `ARCHITECTURE.md` — fronteiras e decisões técnicas;
4. `DEVELOPMENT.md` — fluxo, comandos e qualidade;
5. `AGENTS.md` — regras operacionais para agentes;
6. `docs/CHECKLIST_DE_IMPLEMENTACAO.md` — estado, evidências e próximos incrementos.

As ADRs em `docs/adr/` registram decisões arquiteturais. Documentos históricos e planos não prevalecem sobre os documentos de autoridade.

O workflow de desenvolvimento e o lifecycle de SPEC estão em
`DEVELOPMENT.md` e `docs/specs/README.md`. O mapa factual das capacidades está em
`docs/product/CAPABILITY_MAP.md`.

## Desenvolvimento local

Os comandos oficiais, pré-requisitos e regras de segurança estão em `DEVELOPMENT.md`. Em especial, use sempre `python -m uv` com `--locked`.

Para preparar o banco local:

```powershell
docker compose up --detach --wait postgres
$env:TITAN_MIGRATION_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
$env:TITAN_RUNTIME_DATABASE_PASSWORD="titan_local_runtime_password"
python -m uv run --locked python -m apps.provision_runtime_database_role
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan_app:titan_local_runtime_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
```

Para iniciar a API protegida, suba também o Keycloak, configure OIDC e o contexto da Organization conforme `DEVELOPMENT.md`. Os valores padrão do Compose são exclusivamente locais e nunca devem ser reutilizados fora do desenvolvimento.

## Qualidade

O workflow `.github/workflows/quality.yml` executa em `push` e `pull_request`:

```text
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

O frontend possui seus comandos e testes em `apps/web/`. Rotas e funcionalidades observáveis também devem possuir roteiro executável em `apps/validacao/`.

## Como evoluímos

O Titan Technologies evolui por incrementos pequenos, auditáveis e orientados a problemas de produto. Código é consequência da necessidade: antes de uma mudança significativa, o problema, o usuário, o comportamento esperado, os riscos, a estratégia de teste e a documentação afetada precisam estar claros.

Não altere arquitetura, domínio, tenancy, autenticação, autorização, criptografia, contratos públicos ou dados de forma incompatível sem decisão explícita e, quando aplicável, uma ADR.
