# CLAUDE.md

As instruções de desenvolvimento deste repositório vivem em **[AGENTS.md](AGENTS.md)**, que é a fonte única e vale integralmente aqui. Leia-o antes de implementar qualquer coisa.

Este arquivo existe apenas porque o Claude Code carrega `CLAUDE.md` automaticamente e o `AGENTS.md` não. Não duplique conteúdo aqui: regra nova entra no `AGENTS.md`.

## Documentos de autoridade

Leia antes de implementar, nesta ordem: `VISION.md`, `DOMAIN.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md`. Eles têm prioridade sobre qualquer instrução implícita. Havendo conflito entre esses documentos e o código, interrompa e apresente o conflito.

O progresso por passo é registrado em `docs/CHECKLIST_DE_IMPLEMENTACAO.md` — único documento de status; nenhuma trilha paralela de plano/progresso deve ser criada sem consolidar o resultado ali. Decisões arquiteturais ficam em `docs/adr/`.

## Comandos

Subir o ambiente e aplicar as migrations antes de rodar testes de integração:

```powershell
docker compose up -d postgres
```

```powershell
$env:TITAN_MIGRATION_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
$env:TITAN_RUNTIME_DATABASE_PASSWORD="titan_local_runtime_password"
python -m uv run --locked python -m apps.provision_runtime_database_role
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan_app:titan_local_runtime_password@127.0.0.1:5432/titan"
python -m uv run --locked python -m alembic upgrade heads
python -m uv run --locked python -m alembic -c packages/asset_infrastructure/persistence/migrations/alembic.ini upgrade heads
```

Asset tem ambiente Alembic próprio (`-c packages/asset_infrastructure/persistence/migrations/alembic.ini`), separado do de Core+Livestock — ver `docs/architecture/MIGRATION_CONCURRENCY_STRATEGY.md`.

Portão de verificação completo. **`TITAN_DATABASE_URL` aqui é a conexão administrativa (`titan`), não a
`titan_app` usada para subir a API/worker** — ver "Armadilhas do ambiente" abaixo:

```powershell
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
$env:TITAN_REQUIRE_INTEGRATION_DB="1"
python -m uv run --locked pytest
```

```powershell
python -m uv run --locked ruff check .
```

```powershell
python -m uv run --locked ruff format --check .
```

```powershell
python -m uv run --locked mypy
```

```powershell
$env:TITAN_MIGRATION_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked python -m alembic check
python -m uv run --locked python -m alembic -c packages/asset_infrastructure/persistence/migrations/alembic.ini check
```

Os testes de integração leem `TITAN_DATABASE_URL`. Sem ela, os testes de integração
são pulados para permitir execução local sem Docker; não existe fallback silencioso
para o PostgreSQL do `compose.yaml`. Em gate completo/release, defina
`TITAN_REQUIRE_INTEGRATION_DB=1` para transformar ausência de banco em erro de
configuração.

## Armadilhas do ambiente

- O `uv` é módulo do Python, não executável no PATH: use `python -m uv`, nunca `uv` direto.
- O usuário `titan` do PostgreSQL local é **superusuário e ignora RLS**. Teste que afirma isolamento entre organizações precisa criar role temporário `NOLOGIN NOSUPERUSER NOBYPASSRLS`, dar os GRANTs, `SET LOCAL ROLE` e depois `RESET ROLE`. O padrão está em `tests/integration/test_organization_postgresql.py`.
- Inserções em `core_identity.organizations` usam `(organization_id, record_owner_organization_id)`; a tabela não tem colunas `name` ou `slug`.
- `set_config('titan.organization_id', ...)` exige o UUID como texto: passe `str(org_id.value)`.
- O repositório autoritativo é `C:\programing\Titan`. Traceback apontando para `OneDrive\Projects\Titan` vem de cópia obsoleta e deve ser investigado, não seguido.
- **Para rodar a suíte de testes, `TITAN_DATABASE_URL` precisa ser a conexão administrativa (`titan`), nunca a `titan_app` usada para subir a API/worker de verdade.** `tests/integration/conftest.py` semeia cada `Ambiente` (inclusive inserções multi-linha em `core_identity.organizations`) pela conexão recebida em `TITAN_DATABASE_URL` e só troca para `SET LOCAL ROLE titan_app` na transação, por requisição HTTP, via `dependency_overrides`. Se `TITAN_DATABASE_URL` já for `titan_app`, a própria semeadura roda sob RLS restrito e falha — sintoma: dezenas de testes completamente alheios uns aos outros (`property`, `rule`, `policy`, `worker_e2e`, toda a vertical Asset) quebram de uma vez com `InsufficientPrivilege`/`row-level security policy`, parecendo uma regressão ampla quando na verdade é só a variável de ambiente errada para este uso específico. Corrigido no comando de "Portão de verificação completo" acima; se copiar os comandos da seção "Comandos" em sequência para outro fim, lembre de reexportar `TITAN_DATABASE_URL` para o valor administrativo antes de rodar `pytest`.
