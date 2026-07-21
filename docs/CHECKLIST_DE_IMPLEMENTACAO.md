# Checklist de Implementação — Titan

**Atualizado em:** 21 de julho de 2026  
**Fonte dos passos:** `docs/PLANO_DE_IMPLEMENTACAO_VALIDADO.md`  
**Próximo passo planejado:** Passo 2.2 — relógio e datas

## Como manter este checklist

Ao finalizar cada passo:

1. marcar a implementação e as validações automáticas aplicáveis;
2. registrar data, arquivos e comandos usados como evidência;
3. manter a validação manual pendente até a manifestação do responsável;
4. após aprovação manual, marcar o passo como concluído e atualizar o próximo passo;
5. registrar reprovação ou ressalva sem apagar o resultado anterior.

Estados utilizados:

- `[ ]` não iniciado ou validação pendente;
- `[x]` concluído ou validação aprovada;
- `IMPLEMENTADO` pronto para validação manual;
- `EM ANDAMENTO` passo dividido em subtarefas, com pelo menos uma em execução ou validação;
- `CONCLUÍDO` implementação validada;
- `BLOQUEADO` impedimento registrado;
- `NÃO INICIADO` nenhum trabalho realizado.

## Visão geral

| Passo | Entrega | Estado | Validação manual |
|---|---|---|---|
| 0.1 | Confirmar fronteira do Titan Core | CONCLUÍDO | Aprovada |
| 0.2 | Consolidar linguagem do domínio | CONCLUÍDO | Aprovada |
| 0.3 | Resolver arquitetura e registrar ADRs | CONCLUÍDO | Aprovada |
| 0.4 | Tornar comandos de desenvolvimento reproduzíveis | CONCLUÍDO | Aprovada |
| 1.1 | Criar o workspace Python mínimo | CONCLUÍDO | Aprovada |
| 1.2 | Configurar qualidade Python | CONCLUÍDO | Aprovada |
| 1.3 | Criar aplicação FastAPI com health check | CONCLUÍDO | Aprovada |
| 1.4 | Configurar infraestrutura local incremental | CONCLUÍDO — subtarefas 1.4A a 1.4E | Aprovada |
| 1.5 | Configurar migrations e conexão PostgreSQL | CONCLUÍDO | Aprovada |
| 1.6 | Configurar CI mínimo | IMPLEMENTADO | Pendente no GitHub |
| 2.1–2.4 | Primitivas técnicas do Core | NÃO INICIADO | Pendente |
| 3.1–3.7 | Identidade, autorização e isolamento | NÃO INICIADO | Pendente |
| 4.1–4.8 | Auditoria, integridade e confiabilidade | NÃO INICIADO | Pendente |
| 5.1–5.8 | Evidence, criptografia e Provenance | NÃO INICIADO | Pendente |
| 6.1–6.6 | Policy, Rule, Evaluation e Decision | NÃO INICIADO | Pendente |
| 7.1–7.10 | Relações, recall, dossiê e prova do Core | NÃO INICIADO | Pendente |
| 8.1–8.5 | Fundação Titan Livestock | NÃO INICIADO | Pendente |
| 9.1–9.6 | Medicamentos e elegibilidade | NÃO INICIADO | Pendente |
| 10.1–10.6 | Demonstração vertical verificável | NÃO INICIADO | Pendente |

## Registro dos passos executados

### Passo 0.1 — Confirmar fronteira do Titan Core

- [x] Entrega concluída.
- [x] Revisão documental realizada.
- [x] Validação manual aprovada.
- **Estado:** CONCLUÍDO.
- **Evidências:** `VISION.md`, `DOMAIN.md` e histórico de aprovação do plano.

### Passo 0.2 — Consolidar linguagem do domínio

- [x] Entrega concluída.
- [x] Revisão documental realizada.
- [x] Validação manual aprovada.
- **Estado:** CONCLUÍDO.
- **Evidências:** `DOMAIN.md` versão 1.19 e histórico de aprovação.

### Passo 0.3 — Resolver arquitetura e registrar ADRs

- [x] Entrega concluída.
- [x] ADRs 0001 a 0029 revisadas e aceitas.
- [x] Validação manual aprovada.
- **Estado:** CONCLUÍDO.
- **Evidências:** `ARCHITECTURE.md` versão 1.32 e `docs/adr/`.

### Passo 0.4 — Tornar comandos de desenvolvimento reproduzíveis

- [x] Entrega concluída.
- [x] Comandos e disponibilidade documentados.
- [x] Validação manual aprovada.
- **Estado:** CONCLUÍDO.
- **Evidências:** `DEVELOPMENT.md`.

### Passo 1.1 — Criar o workspace Python mínimo

- [x] `.python-version` criado com Python 3.12.10.
- [x] `pyproject.toml` criado sem dependências de runtime.
- [x] `uv.lock` criado.
- [x] `uv` fixado em 0.11.30.
- [x] Lockfile verificado com `python -m uv lock --check`.
- [x] Ambiente sincronizado com `python -m uv sync --locked`.
- [x] Python efetivo validado como 3.12.10.
- [x] TOML validado.
- [x] Ausência de `apps/`, `packages/`, `tests/` e `infra/` confirmada.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Data da aprovação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO.
- **Evidências:** `.python-version`, `pyproject.toml`, `uv.lock`, `README.md`, `DEVELOPMENT.md` e `docs/PLANO_DE_IMPLEMENTACAO_VALIDADO.md`.
- **Risco residual:** futuras atualizações de Python ou `uv` devem ser deliberadas e acompanhadas de novo lockfile.

### Passo 1.2 — Configurar qualidade Python

- [x] pytest 9.1.1 adicionado como dependência de desenvolvimento para executar testes.
- [x] Ruff 0.15.22 adicionado como dependência de desenvolvimento para lint e formatação.
- [x] Mypy 2.3.0 adicionado como dependência de desenvolvimento para análise estática.
- [x] Versões diretas fixadas e dependências transitivas registradas em `uv.lock`.
- [x] Configurações mínimas registradas em `pyproject.toml`.
- [x] Teste de sanidade do manifesto criado.
- [x] Verificador arquitetural inicial criado para impedir dependência de packages em apps e do Core em verticais.
- [x] `python -m uv lock --check` executado com sucesso.
- [x] `python -m uv run --locked pytest` executado: 3 testes aprovados.
- [x] `python -m uv run --locked ruff check .` executado com sucesso.
- [x] `python -m uv run --locked ruff format --check .` executado com sucesso.
- [x] `python -m uv run --locked mypy` executado sem erros em 2 arquivos.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Data da aprovação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO.
- **Evidências:** `pyproject.toml`, `uv.lock`, `tests/test_smoke.py`, `tests/architecture/test_dependency_boundaries.py` e `DEVELOPMENT.md`.
- **Risco residual:** os verificadores cobrem somente as fronteiras que já podem ser expressas; novos módulos exigirão ampliação incremental dos alvos e regras.

### Passo 1.3 — Criar aplicação FastAPI com health check

- [x] FastAPI 0.139.2 adicionada para composição HTTP.
- [x] Uvicorn 0.51.0 adicionado para execução ASGI local.
- [x] HTTPX2 2.7.0 adicionado somente ao grupo de desenvolvimento para testes HTTP.
- [x] Aplicação executável criada em `apps/api` sem regras de domínio.
- [x] `GET /health` criado fora de `/api/v1` como exceção técnica da ADR-0027.
- [x] Resposta saudável limitada a `{"status":"ok"}`.
- [x] Rota inexistente retorna RFC 9457 em `application/problem+json`.
- [x] OpenAPI identifica o health check com a tag `técnico`.
- [x] Testes relacionados aprovados.
- [x] Suíte completa aprovada: 6 testes.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado em 6 arquivos.
- [x] Servidor iniciado pelo comando oficial e consultado com `curl.exe`.
- [x] Processo temporário encerrado após a validação.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Data da aprovação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO.
- **Evidências:** `apps/api/main.py`, `tests/api/test_health.py`, `pyproject.toml`, `uv.lock` e `DEVELOPMENT.md`.
- **Risco residual:** o health check comprova apenas que o processo responde; dependências externas serão acrescentadas e verificadas somente nos passos de infraestrutura.

### Passo 1.4A — PostgreSQL com PostGIS local

- [x] Docker 29.6.1 e Docker Compose 5.3.0 verificados.
- [x] Imagem oficial `postgis/postgis:18-3.6` fixada também por digest.
- [x] PostgreSQL limitado a `127.0.0.1` por padrão.
- [x] Banco, usuário, senha e porta substituíveis por variáveis de ambiente.
- [x] Credenciais padrão identificadas como exclusivamente locais.
- [x] Volume nomeado persistente montado no caminho do PostgreSQL 18.
- [x] Health check com `pg_isready` configurado.
- [x] `docker compose config` validado.
- [x] Testes estruturais do Compose criados e aprovados.
- [x] Container iniciado e estado `healthy` confirmado.
- [x] PostgreSQL 18.4 confirmado no container.
- [x] PostGIS 3.6.4 confirmado no banco inicial.
- [x] Persistência comprovada após `docker compose down` e novo `up`.
- [x] Marcador técnico temporário removido.
- [x] Container e rede encerrados sem excluir o volume.
- [x] Suíte completa aprovada: 8 testes.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado em 7 arquivos.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Data da aprovação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO.
- **Evidências:** `compose.yaml`, `tests/infrastructure/test_compose_config.py`, `DEVELOPMENT.md` e volume local `titan_postgres_data`.
- **Risco residual:** credenciais padrão são adequadas somente ao desenvolvimento local; o health check comprova disponibilidade do banco, não migrations, RLS ou conexão da aplicação, que pertencem ao Passo 1.5.

### Passo 1.4B — MongoDB local para futuro GridFS

- [x] ADR-0004 relida e limites de responsabilidade confirmados.
- [x] Docker Official Image `mongo:8.0.26-noble` fixada também por digest.
- [x] Linha estável MongoDB 8.0 escolhida em vez das linhas rápidas.
- [x] MongoDB limitado a `127.0.0.1` por padrão.
- [x] Banco inicial, usuário root, senha e porta substituíveis por variáveis de ambiente.
- [x] Autenticação habilitada desde a inicialização.
- [x] Escrita sem credenciais rejeitada pelo MongoDB.
- [x] Volume nomeado persistente montado em `/data/db`.
- [x] Health check autenticado com `mongosh` configurado.
- [x] `docker compose config` validado.
- [x] Testes estruturais do Compose ampliados e aprovados.
- [x] Container iniciado e estado `healthy` confirmado.
- [x] MongoDB 8.0.26 confirmado no container.
- [x] Persistência comprovada após `docker compose down` e novo `up`.
- [x] Coleção e documento técnicos temporários removidos.
- [x] Container e rede encerrados sem excluir o volume.
- [x] PostgreSQL permaneceu parado durante a validação desta subtarefa.
- [x] Suíte completa aprovada: 10 testes.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado em 7 arquivos.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Data da aprovação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO.
- **Evidências:** `compose.yaml`, `tests/infrastructure/test_compose_config.py`, `DEVELOPMENT.md` e volume local `titan_mongo_data`.
- **Riscos residuais:** GridFS e driver ainda não foram implementados; credenciais padrão servem somente ao desenvolvimento; a licença SSPL do MongoDB exige avaliação antes de eventual oferta comercial hospedada.

### Passo 1.4C — Keycloak como OIDC Provider local

- [x] ADR-0028 criada, aceita e vinculada à arquitetura.
- [x] Keycloak 26.7.0 fixado por versão e digest.
- [x] PostgreSQL 18.4 exclusivo do provider fixado por versão e digest.
- [x] Estado do provider separado do banco autoritativo do Titan.
- [x] Banco do provider sem porta publicada no host.
- [x] Keycloak publicado apenas em `127.0.0.1` por padrão.
- [x] Configurações e credenciais locais substituíveis por variáveis de ambiente.
- [x] Readiness na porta de gerenciamento interna configurada.
- [x] Dependência do banco condicionada a `service_healthy`.
- [x] `docker compose config` validado.
- [x] Testes estruturais do Compose ampliados: 7 testes relacionados aprovados.
- [x] Container iniciado e estado `healthy` confirmado.
- [x] Keycloak 26.7.0 confirmado no container.
- [x] Discovery OIDC, issuer, authorization endpoint e JWKS confirmados.
- [x] Credencial de cliente inexistente rejeitada com HTTP 401.
- [x] Persistência do realm administrativo comprovada após `down`/`up`.
- [x] Container e rede encerrados sem excluir o volume.
- [x] Suíte completa aprovada: 13 testes.
- [x] Ruff lint aprovado e formatação aplicada ao teste alterado.
- [x] Mypy aprovado em 7 arquivos.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Data da aprovação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO.
- **Evidências:** `compose.yaml`, `tests/infrastructure/test_compose_config.py`, `docs/adr/0028-keycloak-como-oidc-provider-inicial.md`, `DEVELOPMENT.md` e volume local `titan_keycloak_postgres_data`.
- **Riscos residuais:** `start-dev`, HTTP e credenciais padrão são exclusivamente locais; realm e clientes Titan, PKCE, MFA, TLS, hardening, alta disponibilidade, backup e integração com a API não foram implementados nesta subtarefa.

## Próximo passo

### Passo 1.4D — RabbitMQ como Message Broker local

- [x] ADR-0029 aceita e vinculada à arquitetura.
- [x] RabbitMQ 4.3.3 com management fixado por versão e digest.
- [x] AMQP e management limitados a `127.0.0.1` por padrão.
- [x] Usuário, senha, vhost e portas substituíveis por variáveis de ambiente.
- [x] Usuário e vhost locais dedicados, sem uso da conta `guest` pela aplicação.
- [x] Hostname estável e volume nomeado configurados.
- [x] Health check verifica processo ativo e ausência de alarmes locais.
- [x] `docker compose config` validado.
- [x] Testes estruturais do Compose ampliados: 9 testes relacionados aprovados.
- [x] RabbitMQ 4.3.3 e vhost `titan` confirmados.
- [x] Acesso autenticado à API de management retornou HTTP 200.
- [x] Credencial inválida foi rejeitada com HTTP 401.
- [x] Publicação persistente foi roteada para topologia técnica temporária.
- [x] Requeue produziu redelivery da mesma mensagem.
- [x] Queue durável permaneceu disponível após `down`/`up`.
- [x] Exchange e queue técnicas temporárias foram removidas.
- [x] Containers e rede encerrados sem excluir o volume.
- [x] Suíte completa aprovada: 15 testes.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado em 7 arquivos.
- [x] Validação manual do responsável, incluindo interface de administração.
- **Data da implementação:** 21 de julho de 2026.
- **Data da aprovação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO.
- **Evidências:** `compose.yaml`, `tests/infrastructure/test_compose_config.py`, `docs/adr/0029-rabbitmq-como-message-broker-inicial.md`, `DEVELOPMENT.md` e volume local `titan_rabbitmq_data`.
- **Riscos residuais:** o nó único local não oferece alta disponibilidade; TLS, quorum queues, topologia funcional, publisher, Outbox, dead-letter, workers e integração Python pertencem a passos posteriores.

O Passo 1.4D foi aprovado. A próxima subtarefa de infraestrutura local é Valkey. A decisão do executor de workers permanece separada.

### Passo 1.4E — Valkey para cache efêmero local

- [x] ADR-0025 relida e limites de responsabilidade confirmados.
- [x] Valkey 9.1.0 fixado por versão e digest da imagem mantida pelo projeto.
- [x] Serviço limitado a `127.0.0.1` por padrão.
- [x] Senha, porta e limite de dataset substituíveis por variáveis de ambiente.
- [x] Autenticação obrigatória desde a inicialização.
- [x] Acesso sem credencial rejeitado com `NOAUTH`.
- [x] Health check autenticado com `valkey-cli ping`.
- [x] Dataset limitado a 128 MB por padrão.
- [x] Política de eviction `allkeys-lfu` configurada.
- [x] RDB e AOF desativados explicitamente.
- [x] Nenhum volume associado ao serviço.
- [x] `docker compose config` validado.
- [x] Testes estruturais do Compose ampliados: 11 testes relacionados aprovados.
- [x] Valkey 9.1.0 e resposta `PONG` confirmados.
- [x] Configurações efetivas de memória, eviction e persistência verificadas.
- [x] Chave técnica temporária criada e consultada.
- [x] Perda total confirmada após remoção e recriação do container.
- [x] Container temporário removido ao final.
- [x] Suíte completa aprovada: 17 testes.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado em 7 arquivos.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Data da aprovação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO.
- **Evidências:** `compose.yaml`, `tests/infrastructure/test_compose_config.py`, `docs/adr/0025-valkey-para-cache-e-coordenacao-efemera.md` e `DEVELOPMENT.md`.
- **Riscos residuais:** não existem CacheProfile, integração Python, TLS, ACL nominal, Sentinel, Cluster ou réplica; o standalone local não representa topologia produtiva.

O Passo 1.4E e o Passo 1.4 completo foram aprovados. O próximo incremento é o Passo 1.5 — migrations e conexão PostgreSQL.

## Comandos para testar o Passo 1.4E

```text
docker compose config
docker compose up --detach --wait valkey
docker compose ps
docker compose exec --no-TTY valkey valkey-server --version
docker compose exec --no-TTY valkey sh -c 'VALKEYCLI_AUTH="$VALKEY_PASSWORD" valkey-cli ping'
docker compose exec --no-TTY valkey sh -c 'VALKEYCLI_AUTH="$VALKEY_PASSWORD" valkey-cli CONFIG GET maxmemory maxmemory-policy save appendonly'
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
docker compose rm --stop --force valkey
```

Resultado esperado: Valkey 9.1.0 saudável, `PONG` autenticado, `maxmemory` de 134217728 bytes, `allkeys-lfu`, `appendonly no`, `save` vazio e nenhuma chave preservada após recriar o container.

### Passo 1.5 — Configurar migrations e conexão PostgreSQL

- [x] SQLAlchemy 2.0.51 aprovado e fixado no manifesto e lockfile.
- [x] Alembic 1.18.5 aprovado e fixado no manifesto e lockfile.
- [x] Psycopg 3.3.4 com distribuição binária aprovado e fixado.
- [x] Adapter criado em `packages/core_infrastructure/persistence`.
- [x] URL obtida exclusivamente de `TITAN_DATABASE_URL`, sem fallback silencioso.
- [x] Backend restrito a PostgreSQL e driver restrito a Psycopg.
- [x] Credencial omitida da representação de `DatabaseSettings`.
- [x] Engine configurado com verificação de conexão antes do checkout.
- [x] Função técnica de conexão executa `SELECT 1`.
- [x] Alembic configurado sem URL ou secret no repositório.
- [x] Migration `20260721_0001` criada sem tabela de negócio.
- [x] Estrutura técnica classificada como global e sem dado de domínio.
- [x] Seis testes unitários relacionados aprovados.
- [x] Banco descartável `titan_migration_validation` criado para a validação.
- [x] Conexão real ao PostgreSQL confirmada.
- [x] `upgrade head` aplicado com revisão `20260721_0001`.
- [x] Somente a tabela técnica `alembic_version` foi criada.
- [x] `downgrade base` executado e estado de versão zerado.
- [x] Migration reaplicada até `head`.
- [x] Banco descartável removido após a validação.
- [x] Container PostgreSQL de teste removido sem excluir o volume principal.
- [x] Suíte completa aprovada: 23 testes.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado em 14 arquivos.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Data da aprovação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO.
- **Evidências:** `pyproject.toml`, `uv.lock`, `alembic.ini`, `packages/core_infrastructure/persistence/`, `tests/infrastructure/test_database.py` e `DEVELOPMENT.md`.
- **Riscos residuais:** não há Session, repositório, endpoint dependente do banco, papéis separados de migration/runtime ou tabela protegida; essas capacidades serão introduzidas somente com consumidor e módulo owner reais.

## Comandos para testar o Passo 1.5

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked alembic current
python -m uv run --locked alembic downgrade base
python -m uv run --locked alembic current
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
docker compose rm --stop --force postgres
```

Resultado esperado: `current` mostra `20260721_0001 (head)` após upgrade, fica vazio após downgrade e retorna ao head após reaplicação. O banco possui apenas `alembic_version` até a primeira migration de módulo.

### Passo 1.6 — Configurar CI mínimo

- [x] GitHub Actions aprovado como plataforma.
- [x] Workflow único criado em `.github/workflows/quality.yml`.
- [x] Execução configurada para `push` e `pull_request`.
- [x] Runner fixado em `ubuntu-24.04`.
- [x] Timeout do job limitado a 15 minutos.
- [x] Concorrência obsoleta da mesma referência cancelável.
- [x] Permissão global limitada a `contents: read`.
- [x] Checkout configurado sem persistir credencial.
- [x] `actions/checkout`, `actions/setup-python` e `astral-sh/setup-uv` fixados por SHA.
- [x] Python obtido de `.python-version`.
- [x] uv fixado em 0.11.30.
- [x] Cache limitado ao lockfile.
- [x] Lockfile verificado antes da sincronização.
- [x] Testes e verificações arquiteturais incluídos.
- [x] Ruff lint e formatação incluídos.
- [x] Mypy incluído.
- [x] Workflow sem deploy, publicação, banco externo ou secrets.
- [x] Dois testes estruturais do workflow aprovados.
- [x] Suíte completa aprovada: 25 testes.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado em 15 arquivos.
- [x] Execução bem-sucedida observada no GitHub Actions.
- [x] Falha intencional controlada observada em branch de teste.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências locais:** `.github/workflows/quality.yml`, `tests/infrastructure/test_ci_workflow.py` e `DEVELOPMENT.md`.
- **Evidências remotas:** execução bem-sucedida `29865934822`; falha controlada `29866081574` na etapa de testes; branch temporária removida após a validação.
- **Riscos residuais:** o teste controlado comprovou o bloqueio no `pytest`, mas não exercitou falhas isoladas de Ruff ou Mypy.

## Como validar o Passo 1.6

1. publicar ou conectar o repositório a um remoto GitHub autorizado;
2. enviar uma branch de teste e abrir um pull request;
3. confirmar que o job `Testes e análise estática` termina verde;
4. em outra alteração temporária da branch, introduzir uma asserção deliberadamente incorreta;
5. confirmar que o job falha no pytest;
6. remover a falha, reenviar e confirmar retorno ao estado verde;
7. não incorporar a falha controlada à branch principal.

### Passo 2.1 — Identificadores tipados e referências

- [x] Pacote real `packages/shared_kernel` criado sem camadas vazias.
- [x] `TypedId` opaco, imutável e associado a tipo lógico canônico.
- [x] `OrganizationId` distinto dos demais identificadores.
- [x] UUID nulo, texto inválido e tipo lógico não canônico rejeitados.
- [x] `UniversalReference` imutável com ID tipado, Organization opcional e versão do contrato.
- [x] Organization sem tipo específico rejeitada em runtime.
- [x] Versão do contrato inválida rejeitada.
- [x] Nenhuma dependência de framework, persistência, app ou vertical adicionada.
- [x] 15 testes relacionados aprovados.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/shared_kernel/` e `tests/shared_kernel/test_identifiers_and_references.py`.
- **Riscos residuais:** tipos lógicos ainda não possuem catálogo central; ele deve surgir apenas quando consumidores reais exigirem vocabulário controlado adicional.

## Como validar o Passo 2.1

```text
.venv\Scripts\python.exe -m pytest -q tests/shared_kernel/test_identifiers_and_references.py
.venv\Scripts\python.exe -m pytest -q tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m ruff check packages/shared_kernel tests/shared_kernel
.venv\Scripts\python.exe -m ruff format --check packages/shared_kernel tests/shared_kernel
.venv\Scripts\python.exe -m mypy packages/shared_kernel tests/shared_kernel
```

Resultado esperado: 15 testes aprovados, Ruff sem erros, quatro arquivos já formatados e Mypy sem problemas.

## Comandos para testar o Passo 1.4D

```text
docker compose config
docker compose up --detach --wait rabbitmq
docker compose ps
docker compose exec --no-TTY rabbitmq rabbitmq-diagnostics server_version
docker compose exec --no-TTY rabbitmq rabbitmqctl list_vhosts name
curl.exe --user titan:titan_rabbitmq_local_dev_password http://127.0.0.1:15672/api/overview
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
docker compose down
```

Resultado esperado: serviço `rabbitmq` saudável, versão 4.3.3, vhost `titan`, API autenticada e volume `titan_rabbitmq_data` preservado após `down`.

## Comandos para testar o Passo 1.4C

```text
docker compose config
docker compose up --detach keycloak
docker compose ps
docker compose exec --no-TTY keycloak /opt/keycloak/bin/kc.sh --version
curl.exe http://localhost:8080/realms/master/.well-known/openid-configuration
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
docker compose down
```

Resultado esperado: `keycloak` e `keycloak-postgres` saudáveis, Keycloak 26.7.0, discovery com issuer `http://localhost:8080/realms/master`, banco sem porta publicada e volume `titan_keycloak_postgres_data` preservado após `down`.

## Comandos para testar o Passo 1.4B

```text
docker compose config
docker compose up --detach mongo
docker compose ps
docker compose exec --no-TTY mongo mongosh --quiet --username titan_root --password titan_local_dev_password --authenticationDatabase admin --eval "db.version()"
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
docker compose down
```

Resultado esperado: serviço `healthy`, MongoDB 8.0.26, dez testes aprovados e volume `titan_mongo_data` preservado após `down`.

## Comandos para testar o Passo 1.4A

```text
docker compose config
docker compose up --detach postgres
docker compose ps
docker compose exec --no-TTY postgres psql --username titan --dbname titan --command "SHOW server_version;"
docker compose exec --no-TTY postgres psql --username titan --dbname titan --command "SELECT postgis_full_version();"
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
docker compose down
```

Resultado esperado: serviço `healthy`, PostgreSQL 18.4, PostGIS 3.6.4, oito testes aprovados e volume `titan_postgres_data` preservado após `down`.

## Comandos para testar o Passo 1.3

Terminal 1:

```text
python -m uv sync --locked
python -m uv run --locked uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```text
curl.exe --include http://127.0.0.1:8000/health
curl.exe --include http://127.0.0.1:8000/rota-inexistente
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
```

Resultado esperado: `/health` retorna `200` e `{"status":"ok"}`; a rota inexistente retorna `404`, `application/problem+json` e `ROTA_NAO_ENCONTRADA`. Os seis testes e as verificações estáticas devem passar. Encerre o servidor no Terminal 1 com `Ctrl+C`.
