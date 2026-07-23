# CLAUDE.md

As instruções de desenvolvimento deste repositório vivem em **[AGENTS.md](AGENTS.md)**, que é a fonte única e vale integralmente aqui. Leia-o antes de implementar qualquer coisa.

Este arquivo existe apenas porque o Claude Code carrega `CLAUDE.md` automaticamente e o `AGENTS.md` não. Não duplique conteúdo aqui: regra nova entra no `AGENTS.md`.

## Documentos de autoridade

Leia antes de implementar, nesta ordem: `VISION.md`, `DOMAIN.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md`. Eles têm prioridade sobre qualquer instrução implícita. Havendo conflito entre esses documentos e o código, interrompa e apresente o conflito.

O progresso por passo é registrado em `docs/CHECKLIST_DE_IMPLEMENTACAO.md` e `docs/PLANO_DE_IMPLEMENTACAO_VALIDADO.md`. Decisões arquiteturais ficam em `docs/adr/`.

## Comandos

Subir o ambiente e aplicar as migrations antes de rodar testes de integração:

```bash
docker compose up -d
```

```bash
python -m uv run --locked alembic upgrade head
```

Portão de verificação completo:

```bash
python -m uv run --locked pytest
```

```bash
python -m uv run --locked ruff check .
```

```bash
python -m uv run --locked mypy
```

```bash
python -m uv run --locked alembic check
```

Os testes de integração leem `TITAN_DATABASE_URL`; sem ela, usam o PostgreSQL local do `compose.yaml` por padrão.

## Armadilhas do ambiente

- O `uv` é módulo do Python, não executável no PATH: use `python -m uv`, nunca `uv` direto.
- O usuário `titan` do PostgreSQL local é **superusuário e ignora RLS**. Teste que afirma isolamento entre organizações precisa criar role temporário `NOLOGIN NOSUPERUSER NOBYPASSRLS`, dar os GRANTs, `SET LOCAL ROLE` e depois `RESET ROLE`. O padrão está em `tests/integration/test_organization_postgresql.py`.
- Inserções em `core_identity.organizations` usam `(organization_id, record_owner_organization_id)`; a tabela não tem colunas `name` ou `slug`.
- `set_config('titan.organization_id', ...)` exige o UUID como texto: passe `str(org_id.value)`.
- O repositório autoritativo é `C:\programing\Titan`. Traceback apontando para `OneDrive\Projects\Titan` vem de cópia obsoleta e deve ser investigado, não seguido.
