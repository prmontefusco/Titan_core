# Checklist de Implementação — Titan

**Atualizado em:** 22 de julho de 2026  
**Fonte dos passos:** `docs/PLANO_DE_IMPLEMENTACAO_VALIDADO.md`  
**Próximo passo planejado:** Passo 5.0 — Conclusão da Fase 4 / Fase 5






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
| 3.1–3.7 | Identidade, autorização e isolamento | EM ANDAMENTO — 3.1 a 3.6 aprovados | Pendente |
| 4.1–4.8 | Auditoria, integridade e confiabilidade | NÃO INICIADO | Pendente |
| 5.1–5.8 | Evidence, criptografia e Provenance | CONCLUÍDO (5.1 a 5.8 implementados) | Pendente |
| 6.1–6.6 | Policy, Rule, Evaluation e Decision | CONCLUÍDO — 6.1 a 6.6 implementados | Pendente |
| 7.1–7.10 | Relações, recall, dossiê e prova do Core | EM ANDAMENTO — 7.1 a 7.4 implementados | Pendente |
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

### Passo 2.2 — Relógio e datas

- [x] Contrato `Clock` injetável criado sem dependência externa.
- [x] `SystemClock` retorna instante consciente de timezone em UTC.
- [x] `FixedClock` permite congelamento determinístico em testes.
- [x] Instantes sem timezone ou fora de UTC são rejeitados.
- [x] `RecordTimestamps` distingue `occurred_at` de `recorded_at`.
- [x] Captura do registro utiliza somente o relógio injetado.
- [x] Objetos temporais são imutáveis.
- [x] Nenhuma prova temporal externa é inferida do relógio local.
- [x] 22 testes relacionados aprovados.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/shared_kernel/temporal.py` e `tests/shared_kernel/test_temporal.py`.
- **Riscos residuais:** precisão e fonte temporal avançadas pertencem aos perfis e aos passos de timestamp independente; este incremento garante somente representação UTC e injeção do relógio observado pelo Titan.

## Como validar o Passo 2.2

```text
.venv\Scripts\python.exe -m pytest -q tests/shared_kernel/test_temporal.py
.venv\Scripts\python.exe -m pytest -q tests/shared_kernel tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m ruff check packages/shared_kernel tests/shared_kernel
.venv\Scripts\python.exe -m ruff format --check packages/shared_kernel tests/shared_kernel
.venv\Scripts\python.exe -m mypy packages/shared_kernel tests/shared_kernel
```

Resultado esperado: 7 testes temporais e 22 testes relacionados aprovados, Ruff sem erros, seis arquivos já formatados e Mypy sem problemas.

### Passo 2.3 — Serialização canônica

- [x] `CanonicalSerializer` versionado como `titan-json-v1`.
- [x] Envelope inclui explicitamente a versão da serialização.
- [x] Ordem de mapas não altera os bytes produzidos.
- [x] Ordem de listas permanece semanticamente significativa.
- [x] Texto e chaves são normalizados em Unicode NFC.
- [x] Colisão de chaves após normalização é rejeitada.
- [x] Inteiros, decimais, booleanos, nulos, textos e timestamps possuem representação tipada.
- [x] Decimais equivalentes produzem a mesma representação.
- [x] Timestamps exigem representação UTC explícita.
- [x] Floats, decimais não finitos, chaves não textuais, ciclos e tipos desconhecidos são rejeitados.
- [x] Hashes calculados sobre bytes equivalentes são idênticos.
- [x] Nenhuma cadeia de hashes ou assinatura foi antecipada.
- [x] 36 testes relacionados aprovados.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/shared_kernel/serialization.py` e `tests/shared_kernel/test_serialization.py`.
- **Riscos residuais:** `titan-json-v1` suporta somente o subconjunto tipado aprovado; novos tipos exigem evolução deliberada e não podem alterar o significado da versão existente.

## Como validar o Passo 2.3

```text
.venv\Scripts\python.exe -m pytest -q tests/shared_kernel/test_serialization.py
.venv\Scripts\python.exe -m pytest -q tests/shared_kernel tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m ruff check packages/shared_kernel tests/shared_kernel
.venv\Scripts\python.exe -m ruff format --check packages/shared_kernel tests/shared_kernel
.venv\Scripts\python.exe -m mypy packages/shared_kernel tests/shared_kernel
```

Resultado esperado: 14 testes de serialização e 36 testes relacionados aprovados, Ruff sem erros, oito arquivos já formatados e Mypy sem problemas.

### Passo 2.4 — Contrato de evento de domínio

- [x] Pacote real `packages/core_domain` criado sem camadas vazias.
- [x] `DomainEvent` imutável com identidade tipada.
- [x] Organization obrigatória e coerente com a referência do agregado.
- [x] Versões do agregado, evento, contrato e payload validadas.
- [x] Ocorrência e registro preservados separadamente em UTC.
- [x] Actor e Source preservados como referências tipadas.
- [x] Correlação obrigatória e causação opcional tipadas.
- [x] Payload mínimo convertido obrigatoriamente em bytes canônicos versionados.
- [x] Payload original mutável não altera o snapshot capturado.
- [x] Chaves evidentes de secrets e credenciais são rejeitadas.
- [x] Construção de payload diretamente por bytes arbitrários é impedida.
- [x] Teste arquitetural impede framework, app, infraestrutura e vertical no Core Domain.
- [x] 14 testes do contrato e 51 testes relacionados aprovados.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/core_domain/events.py`, `tests/core_domain/test_domain_event.py` e `tests/architecture/test_dependency_boundaries.py`.
- **Riscos residuais:** minimização semântica e detecção de dados pessoais dependem dos schemas e Policies futuros; a lista defensiva de chaves proibidas não substitui classificação de dados.

## Como validar o Passo 2.4

```text
.venv\Scripts\python.exe -m pytest -q tests/core_domain/test_domain_event.py
.venv\Scripts\python.exe -m pytest -q tests/core_domain tests/shared_kernel tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m ruff check packages/core_domain packages/shared_kernel tests/core_domain tests/shared_kernel tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m ruff format --check packages/core_domain packages/shared_kernel tests/core_domain tests/shared_kernel tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m mypy packages/core_domain packages/shared_kernel tests/core_domain tests/shared_kernel tests/architecture/test_dependency_boundaries.py
```

Resultado esperado: 14 testes do contrato e 51 testes relacionados aprovados, Ruff sem erros, 12 arquivos já formatados e Mypy sem problemas.

### Passo 3.1 — Organization

- [x] Modelo `Organization` imutável criado no Core Domain.
- [x] Modelo contém somente identidade estável aprovada, sem atributos inventados.
- [x] Identificador diferente de `OrganizationId` é rejeitado.
- [x] Schema modular `core_identity` criado por migration.
- [x] Tabela `organizations` classificada como `PROTECTED` e atribuída ao módulo owner.
- [x] `organization_id` e `record_owner_organization_id` usam UUID e são obrigatórios.
- [x] Constraint garante que o registro inicial da Organization é auto-owned.
- [x] RLS e `FORCE ROW LEVEL SECURITY` habilitados.
- [x] Policies independentes de `SELECT` e `INSERT` negam contexto ausente ou divergente.
- [x] Acesso público ao schema e à tabela é revogado.
- [x] Contexto usa `set_config(..., true)` e exige transação ativa.
- [x] Repository cria e consulta Organization sem expor SQL ao Domain.
- [x] Migration aditiva `20260721_0002` possui downgrade validado.
- [x] Teste PostgreSQL com role temporária sem `BYPASSRLS` comprovou isolamento.
- [x] Upgrade, downgrade e reaplicação concluídos; banco terminou em `20260721_0002 (head)`.
- [x] `alembic check` confirmou metadata e schema sem operações pendentes.
- [x] Catálogo confirmou RLS, FORCE RLS, classificação, policies e zero linhas residuais.
- [x] 23 testes sem banco e um teste PostgreSQL relacionados aprovados.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/core_domain/organizations.py`, `packages/core_infrastructure/persistence/organizations.py`, migration `20260721_0002`, testes de domínio, contrato e integração.
- **Riscos residuais:** a role de runtime produtiva e seus grants serão provisionados por configuração operacional própria; o teste usa role transacional temporária. Organization ainda não possui Application use case nem API, que pertencem a passos posteriores.

## Como validar o Passo 3.1

```powershell
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/core_domain/test_organization.py tests/infrastructure/test_organization_persistence_contract.py
.venv\Scripts\python.exe -m pytest -q tests/integration/test_organization_postgresql.py
.venv\Scripts\python.exe -m alembic downgrade 20260721_0001
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_domain packages/core_infrastructure/persistence tests/core_domain tests/infrastructure/test_organization_persistence_contract.py tests/integration/test_organization_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_domain packages/core_infrastructure/persistence tests/core_domain tests/infrastructure/test_organization_persistence_contract.py tests/integration/test_organization_postgresql.py
```

Resultado esperado: seis testes de domínio/contrato e um teste PostgreSQL aprovados; migration retorna a `20260721_0002 (head)` após downgrade/upgrade; Ruff e Mypy não apresentam problemas. O teste PostgreSQL reverte a role e as Organizations temporárias.

### Passo 3.2 — User

- [x] ADR 0030 registra a Organization operadora como owner do `User` global.
- [x] Modelo `User` imutável criado com identidade tipada e owner obrigatório.
- [x] Senha, token, segredo, credencial e Permission direta não integram o modelo nem a persistência.
- [x] Tabela `core_identity.users` classificada como `PROTECTED`.
- [x] Chave estrangeira exige uma Organization owner existente.
- [x] RLS e `FORCE ROW LEVEL SECURITY` habilitados com negação por padrão.
- [x] Repository cria e consulta User somente em transação ativa.
- [x] Duplicidade, owner inexistente e contexto divergente são rejeitados pelos testes.
- [x] Migration aditiva `20260721_0003` possui downgrade validado.
- [x] Banco terminou em `20260721_0003 (head)` e `alembic check` não encontrou divergências.
- [x] 11 testes sem banco e um teste PostgreSQL aprovados.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** ADR 0030, `packages/core_domain/users.py`, `packages/core_infrastructure/persistence/users.py`, migration `20260721_0003` e testes de domínio, contrato e integração.
- **Riscos residuais:** a seleção segura da Organization operadora será responsabilidade do futuro caso de uso e de configuração confiável; Membership, identidade OIDC e API permanecem fora deste incremento.

## Como validar o Passo 3.2

```powershell
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/core_domain/test_user.py tests/infrastructure/test_user_persistence_contract.py
.venv\Scripts\python.exe -m pytest -q tests/integration/test_user_postgresql.py
.venv\Scripts\python.exe -m alembic downgrade 20260721_0002
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_domain/users.py packages/core_infrastructure/persistence/users.py tests/core_domain/test_user.py tests/infrastructure/test_user_persistence_contract.py tests/integration/test_user_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_domain/users.py packages/core_infrastructure/persistence/users.py tests/core_domain/test_user.py tests/infrastructure/test_user_persistence_contract.py tests/integration/test_user_postgresql.py
```

Resultado esperado: oito testes de domínio/contrato e um teste PostgreSQL aprovados; migration retorna a `20260721_0003 (head)` após downgrade/upgrade; Ruff e Mypy não apresentam problemas. O teste PostgreSQL reverte a role, a Organization e o User temporários.

### Passo 3.3 — Membership

- [x] Modelo `Membership` imutável criado como vínculo humano temporal.
- [x] Owner do registro é obrigatoriamente a própria Organization vinculada.
- [x] Status utiliza vocabulário controlado em português.
- [x] Intervalo temporal UTC é semiaberto e rejeita término anterior ou igual ao início.
- [x] Origem e Actor concedente são preservados por referências tipadas.
- [x] Roles e Permissions não foram antecipadas neste incremento.
- [x] Tabela `core_identity.memberships` classificada como `PROTECTED`.
- [x] Chaves estrangeiras exigem User e Organizations existentes.
- [x] Constraints protegem owner, intervalo e status.
- [x] RLS e `FORCE ROW LEVEL SECURITY` habilitados com negação por padrão.
- [x] Repository cria, consulta e lista vínculos válidos sob contexto transacional.
- [x] Mesmo User foi associado a duas Organizations sem permitir leitura cruzada.
- [x] Migration aditiva `20260721_0004` possui downgrade validado.
- [x] Banco terminou em `20260721_0004 (head)` e `alembic check` não encontrou divergências.
- [x] 12 testes sem banco e um teste PostgreSQL aprovados.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/core_domain/memberships.py`, `packages/core_infrastructure/persistence/memberships.py`, migration `20260721_0004` e testes de domínio, contrato e integração.
- **Riscos residuais:** transições de estado, substituição histórica e atribuição temporal de Roles exigem casos de uso próprios; a presença de Membership válido não constitui Authorization isoladamente.

## Como validar o Passo 3.3

```powershell
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/core_domain/test_membership.py tests/infrastructure/test_membership_persistence_contract.py
.venv\Scripts\python.exe -m pytest -q tests/integration/test_membership_postgresql.py
.venv\Scripts\python.exe -m alembic downgrade 20260721_0003
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_domain/memberships.py packages/core_infrastructure/persistence/memberships.py tests/core_domain/test_membership.py tests/infrastructure/test_membership_persistence_contract.py tests/integration/test_membership_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_domain/memberships.py packages/core_infrastructure/persistence/memberships.py tests/core_domain/test_membership.py tests/infrastructure/test_membership_persistence_contract.py tests/integration/test_membership_postgresql.py
```

Resultado esperado: nove testes de domínio/contrato e um teste PostgreSQL aprovados; migration retorna a `20260721_0004 (head)` após downgrade/upgrade; Ruff e Mypy não apresentam problemas. O teste PostgreSQL reverte todos os registros e a role temporária.

### Passo 3.4 — Role e Permission

- [x] ADR 0031 registra ownership e atribuição de papéis.
- [x] Permission canônica pertence ao `REFERENCE_CATALOG` da Organization operadora.
- [x] Role imutável pertence à Organization que a define.
- [x] Role referencia somente Permissions canônicas existentes.
- [x] MembershipRoleAssignment vincula Membership e Role da mesma Organization.
- [x] MembershipRoleRevocation remove efeito de forma append-only.
- [x] Nenhum contrato ou tabela atribui Permission diretamente ao User.
- [x] Resolução temporal exclui atribuições futuras, expiradas ou revogadas.
- [x] Tabelas organizacionais são `PROTECTED` com RLS e `FORCE RLS`.
- [x] Atribuição entre Organizations é rejeitada por constraint estrutural.
- [x] Migration `20260721_0005` possui downgrade validado.
- [x] Banco terminou em `20260721_0005 (head)` e `alembic check` não encontrou divergências.
- [x] 11 testes sem banco e um teste PostgreSQL aprovados.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** ADR 0031, `packages/core_domain/authorization.py`, `packages/core_infrastructure/persistence/authorization.py`, migration `20260721_0005` e testes relacionados.
- **Riscos residuais:** o bootstrap dos códigos canônicos e perfis mínimos pertence ao Passo 3.7; autoridade dos Actors concedente e revogador será validada na Application; Role não substitui Authorization por operação.

## Como validar o Passo 3.4

```powershell
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/core_domain/test_authorization.py tests/infrastructure/test_authorization_persistence_contract.py
.venv\Scripts\python.exe -m pytest -q tests/integration/test_authorization_postgresql.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_domain/authorization.py packages/core_infrastructure/persistence/authorization.py tests/core_domain/test_authorization.py tests/infrastructure/test_authorization_persistence_contract.py tests/integration/test_authorization_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_domain/authorization.py packages/core_infrastructure/persistence/authorization.py tests/core_domain/test_authorization.py tests/infrastructure/test_authorization_persistence_contract.py tests/integration/test_authorization_postgresql.py
```

Resultado esperado: oito testes de domínio/contrato e um teste PostgreSQL aprovados; banco em `20260721_0005 (head)`; nenhuma operação Alembic pendente; Ruff e Mypy aprovados.

### Passo 3.5 — Autenticação com OIDC Provider

- [x] PyJWT com suporte criptográfico adicionado e fixado no lockfile.
- [x] Realm local `titan` importável sem User ou segredo real.
- [x] Resource Server `titan-api` separado do cliente público `titan-swagger`.
- [x] Swagger configurado com Authorization Code e PKCE S256.
- [x] Implicit Flow e Password Grant desabilitados no cliente Swagger.
- [x] Audience `titan-api` emitida somente no Access Token.
- [x] Claim de finalidade `token_use=access` ausente no ID Token.
- [x] Validador usa issuer e audience exatos e allowlist `RS256`.
- [x] Assinatura, expiração, issued-at, subject, tipo e finalidade são validados.
- [x] ID Token, token adulterado, expirado ou destinado a outro recurso são rejeitados.
- [x] Infrastructure produz `AuthenticatedPrincipal` sem token bruto.
- [x] Rota `/technical/authentication` exige Bearer Access Token.
- [x] Token ausente retorna `401` com `WWW-Authenticate: Bearer`.
- [x] Discovery e JWKS do Keycloak real foram consultados com sucesso.
- [x] Credencial inválida foi rejeitada pelo token endpoint com `401`.
- [x] 25 testes relacionados aprovados.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** ADRs 0005 e 0028, `config/keycloak/titan-realm.json`, `packages/core_infrastructure/authentication.py`, `apps/api/main.py` e testes de autenticação/configuração.
- **Riscos residuais:** `start-dev` e HTTP são exclusivamente locais; User de teste deve ser criado manualmente no Keycloak e nunca versionado; vínculo persistente de ExternalIdentity e Authorization por Organization pertencem aos próximos incrementos; indisponibilidade, rotação e cache JWKS exigem testes operacionais adicionais antes de produção.

## Como validar o Passo 3.5

```powershell
docker compose up --detach --wait keycloak
curl.exe http://127.0.0.1:8080/realms/titan/.well-known/openid-configuration
curl.exe http://127.0.0.1:8080/realms/titan/protocol/openid-connect/certs
$env:TITAN_OIDC_ISSUER = "http://localhost:8080/realms/titan"
$env:TITAN_OIDC_AUDIENCE = "titan-api"
.venv\Scripts\python.exe -m pytest -q tests/core_domain/test_authentication.py tests/infrastructure/test_oidc_access_token.py tests/api/test_oidc_authentication.py tests/api/test_health.py tests/infrastructure/test_compose_config.py
.venv\Scripts\python.exe -m ruff check apps/api/main.py packages/core_domain/authentication.py packages/core_infrastructure/authentication.py tests/core_domain/test_authentication.py tests/infrastructure/test_oidc_access_token.py tests/api/test_oidc_authentication.py tests/infrastructure/test_compose_config.py
.venv\Scripts\python.exe -m mypy apps/api/main.py packages/core_domain/authentication.py packages/core_infrastructure/authentication.py tests/core_domain/test_authentication.py tests/infrastructure/test_oidc_access_token.py tests/api/test_oidc_authentication.py tests/infrastructure/test_compose_config.py
```

Resultado esperado: Keycloak saudável; discovery do issuer `http://localhost:8080/realms/titan`; JWKS com chaves; 26 testes relacionados aprovados; Ruff e Mypy sem problemas.

### Passo 3.6 — Isolamento por Organization

- [x] `ExternalIdentity` canônica usa `(issuer, subject)` e referencia User interno.
- [x] Email, nome, username, token e senha não integram o vínculo externo.
- [x] `OrganizationContext` é imutável e não contém token bruto.
- [x] Organization solicitada é tratada como entrada não confiável.
- [x] Application resolve identidade externa antes de consultar Membership.
- [x] Exatamente uma Membership válida é exigida para o contexto humano.
- [x] Roles e Permissions efetivas são calculadas após validar Membership.
- [x] Subject desconhecido e Organization sem vínculo falham com negação indistinguível.
- [x] Adapter PostgreSQL define internamente o contexto RLS da operadora e da Organization solicitada.
- [x] Tabela `external_identities` é `PROTECTED`, com RLS e `FORCE RLS`.
- [x] `(issuer, subject)` possui unicidade estrutural.
- [x] Migration `20260721_0006` possui downgrade validado.
- [x] Banco terminou em `20260721_0006 (head)` e `alembic check` não encontrou divergências.
- [x] Teste PostgreSQL comprovou acesso permitido e negação em outra Organization.
- [x] Teste arquitetural protege Application contra dependência de Infrastructure e apps.
- [x] Ruff lint e formatação aprovados.
- [x] Mypy aprovado no incremento.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/core_domain/organization_context.py`, `packages/core_application/organization_context.py`, `packages/core_infrastructure/organization_context.py`, migration `20260721_0006` e testes relacionados.
- **Riscos residuais:** suspensão/relink de ExternalIdentity exige caso de uso append-only próprio; ServiceIdentity e AuthorizationGrant ainda não integram este fluxo; finalidade e recurso serão adicionados quando existir caso de uso protegido concreto.

## Como validar o Passo 3.6

```powershell
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m pytest -q tests/core_domain/test_organization_context.py tests/application/test_organization_context_service.py tests/infrastructure/test_organization_context_persistence_contract.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m pytest -q tests/integration/test_organization_context_postgresql.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_domain/organization_context.py packages/core_application packages/core_infrastructure/organization_context.py packages/core_infrastructure/persistence/external_identities.py
.venv\Scripts\python.exe -m mypy packages/core_domain/organization_context.py packages/core_application packages/core_infrastructure/organization_context.py packages/core_infrastructure/persistence/external_identities.py
```

Resultado esperado: dez testes sem banco e um teste PostgreSQL aprovados; banco em `20260721_0006 (head)`; nenhuma operação Alembic pendente; Ruff e Mypy aprovados.

### Passo 3.7 — Perfis mínimos de bootstrap

- [x] ADR-0032 limita o bootstrap à Organization operadora.
- [x] Identifiers da Organization e da autoridade são configuração explícita.
- [x] Ambiente usa vocabulário controlado em português.
- [x] Perfil e versão são estáveis e registrados.
- [x] Recibo imutável registra origem, autoridade, ambiente, instante e resultado.
- [x] Execução repetida retorna `JA_APLICADO` sem duplicar registros.
- [x] Bootstrap não cria User, ExternalIdentity, Membership, Role ou Permission.
- [x] Configuração divergente falha fechada.
- [x] Tabela `bootstrap_receipts` é `PROTECTED`, com RLS e `FORCE RLS`.
- [x] Migration `20260721_0007` possui downgrade validado.
- [x] Banco terminou em `20260721_0007 (head)` e `alembic check` não encontrou divergências.
- [x] Testes relacionados, Ruff e Mypy aprovados.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** ADR-0032, `apps/bootstrap`, `packages/core_infrastructure/bootstrap.py`, migration `20260721_0007` e testes relacionados.
- **Riscos residuais:** o comando exige credencial administrativa; provisionamento de User, Membership, Role, Permission e demais perfis permanece negado até casos de uso próprios; o recibo comprova a aplicação registrada, não a guarda operacional da credencial usada.

## Como validar o Passo 3.7

Use Identifiers fictícios e estáveis exclusivos do seu ambiente local:

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
$env:TITAN_OPERATOR_ORGANIZATION_ID = "20000000-0000-4000-8000-000000000001"
$env:TITAN_BOOTSTRAP_AUTHORITY_ACTOR_ID = "20000000-0000-4000-8000-000000000002"
$env:TITAN_ENVIRONMENT = "DESENVOLVIMENTO"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m apps.bootstrap
.venv\Scripts\python.exe -m apps.bootstrap
.venv\Scripts\python.exe -m pytest -q tests/infrastructure/test_bootstrap.py tests/integration/test_bootstrap_postgresql.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check apps/bootstrap packages/core_infrastructure/bootstrap.py tests/infrastructure/test_bootstrap.py tests/integration/test_bootstrap_postgresql.py
.venv\Scripts\python.exe -m mypy apps/bootstrap packages/core_infrastructure/bootstrap.py tests/infrastructure/test_bootstrap.py tests/integration/test_bootstrap_postgresql.py
```

Resultado esperado: a primeira execução do comando retorna `APLICADO`; a segunda retorna `JA_APLICADO`; seis testes passam; o banco está em `20260721_0007 (head)`; Alembic, Ruff e Mypy não apresentam problemas. Se esse ambiente já tiver sido inicializado com os mesmos valores, ambas as execuções podem retornar `JA_APLICADO`.

### Passo 4.1 — Registro append-only

- [x] Application expõe somente registro append e consulta de versões.
- [x] `DomainEvent` preserva Organization, agregado, autoria, Source, correlação e payload canônico.
- [x] PostgreSQL mantém sequência contínua por agregado.
- [x] Lacuna ou versão repetida produz `VERSAO_DE_AGREGADO_CONFLITANTE`.
- [x] Consulta retorna eventos em ordem de versão do agregado.
- [x] Tabela `core_audit.domain_events` é `PROTECTED`, com RLS e `FORCE RLS`.
- [x] Papel de runtime sem `BYPASSRLS` não atravessa Organizations.
- [x] Papel de runtime possui somente `SELECT` e `INSERT` no teste controlado.
- [x] `UPDATE`, `DELETE` e `TRUNCATE` são recusados pelo PostgreSQL.
- [x] Hash anterior/atual não foi antecipado e permanece no Passo 4.2.
- [x] Migration `20260721_0008` possui downgrade validado.
- [x] Banco terminou em `20260721_0008 (head)` e `alembic check` não encontrou divergências.
- [x] 23 testes relacionados, Ruff e Mypy aprovados.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/core_application/event_log.py`, `packages/core_infrastructure/persistence/events.py`, migration `20260721_0008` e testes relacionados.
- **Riscos residuais:** cadeia criptográfica pertence ao Passo 4.2; correção, idempotência e concorrência simultânea pertencem respectivamente aos Passos 4.5, 4.6 e 4.7; privilégios definitivos do papel de produção ainda dependem do provisionamento operacional desse papel.

## Como validar o Passo 4.1

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/core_domain/test_domain_event.py tests/application/test_event_log_service.py tests/infrastructure/test_event_persistence_contract.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m pytest -q tests/integration/test_domain_events_postgresql.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_application packages/core_infrastructure/persistence/events.py tests/application/test_event_log_service.py tests/infrastructure/test_event_persistence_contract.py tests/integration/test_domain_events_postgresql.py
.venv\Scripts\python.exe -m ruff format --check packages/core_application packages/core_infrastructure/persistence/events.py tests/application/test_event_log_service.py tests/infrastructure/test_event_persistence_contract.py tests/integration/test_domain_events_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_application packages/core_infrastructure/persistence/events.py tests/application/test_event_log_service.py tests/infrastructure/test_event_persistence_contract.py tests/integration/test_domain_events_postgresql.py
```

Resultado esperado: 21 testes sem banco e dois testes PostgreSQL aprovados; banco em `20260721_0008 (head)`; nenhuma operação Alembic pendente; Ruff e Mypy aprovados. O segundo teste PostgreSQL tenta e confirma a recusa de `UPDATE`, `DELETE` e `TRUNCATE` sob papel de runtime restrito.

### Passo 4.2 — Cadeia de hashes

- [x] Cadeia possui escopo por agregado e não atravessa Organizations.
- [x] Perfil `titan-event-chain` e versão `1` são explícitos.
- [x] Algoritmo `SHA-256` e serialização `titan-json-v1` são explícitos.
- [x] Hash cobre bytes canônicos completos do evento e hash anterior.
- [x] Primeiro elo exige hash anterior ausente; elos posteriores exigem 32 bytes.
- [x] Evento e elo de integridade são persistidos na mesma transação.
- [x] Elo anterior ausente produz `ELO_ANTERIOR_INDISPONIVEL`, nunca validade presumida.
- [x] Verificador funciona sem banco, segredo ou provider externo.
- [x] Verificador distingue `VALIDA`, `INVALIDA` e `INDETERMINADA`.
- [x] Adulteração identifica exatamente a posição divergente.
- [x] Perfil não suportado produz `PERFIL_NAO_SUPORTADO`.
- [x] Tabela `core_audit.domain_event_integrity` é `PROTECTED`, com RLS e `FORCE RLS`.
- [x] Papel de runtime não pode alterar, apagar ou truncar elos.
- [x] Migration `20260721_0009` possui downgrade validado.
- [x] Banco terminou em `20260721_0009 (head)` e `alembic check` não encontrou divergências.
- [x] 27 testes relacionados, Ruff e Mypy aprovados.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/core_integrity/event_chain.py`, `packages/core_infrastructure/persistence/events.py`, migration `20260721_0009` e testes relacionados.
- **Riscos residuais:** a cadeia interna detecta divergências, mas ainda não possui checkpoint ou âncora externa; um administrador capaz de reescrever toda a cadeia só será confrontado por prova preservada fora dela nos Passos 4.3 e 4.4; eventos anteriores sem elo permanecem material insuficiente.

## Como validar o Passo 4.2

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/core_integrity/test_event_chain.py tests/core_domain/test_domain_event.py tests/infrastructure/test_event_persistence_contract.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m pytest -q tests/integration/test_domain_events_postgresql.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_integrity packages/core_infrastructure/persistence/events.py tests/core_integrity/test_event_chain.py tests/infrastructure/test_event_persistence_contract.py tests/integration/test_domain_events_postgresql.py
.venv\Scripts\python.exe -m ruff format --check packages/core_integrity packages/core_infrastructure/persistence/events.py tests/core_integrity/test_event_chain.py tests/infrastructure/test_event_persistence_contract.py tests/integration/test_domain_events_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_integrity packages/core_infrastructure/persistence/events.py tests/core_integrity/test_event_chain.py tests/infrastructure/test_event_persistence_contract.py tests/integration/test_domain_events_postgresql.py
```

Resultado esperado: 25 testes sem banco e dois testes PostgreSQL aprovados; banco em `20260721_0009 (head)`; nenhuma operação Alembic pendente; Ruff e Mypy aprovados. Os testes independentes confirmam determinismo, adulteração na posição exata e perfil não suportado como indeterminado.

### Passo 4.3 — Checkpoint verificável

- [x] Checkpoint ancora a cabeça completa de uma cadeia desde a sequência 1.
- [x] RecordOwnerOrganization e agregado do escopo são explícitos.
- [x] IDs, sequências e hashes dos eventos cobertos são preservados em ordem.
- [x] Primeira e última sequência, contagem, hash inicial e final são protegidos.
- [x] Perfil `titan-integrity-checkpoint` versão `1` é explícito.
- [x] Digest `SHA-256` cobre escopo, conjunto, algoritmos, versões, produtor e instante observado.
- [x] Application constrói e persiste o checkpoint uma única vez.
- [x] Verificador funciona sem banco, segredo ou estado mutável do Titan.
- [x] Verificador detecta omissão, alteração de digest, escopo divergente e perfil incompatível.
- [x] Prova inicial utiliza a cadeia completa; Merkle não foi antecipada.
- [x] Checkpoint não cria timestamp nem prova temporal externa.
- [x] Tabelas de checkpoint são `PROTECTED`, com RLS e `FORCE RLS`.
- [x] Papel de runtime não pode alterar, apagar ou truncar checkpoints.
- [x] Migration `20260721_0010` possui downgrade validado.
- [x] Banco terminou em `20260721_0010 (head)` e `alembic check` não encontrou divergências.
- [x] 16 testes relacionados, Ruff e Mypy aprovados.
- [x] Validação manual do responsável.
- **Data da implementação:** 21 de julho de 2026.
- **Estado:** CONCLUÍDO E APROVADO.
- **Evidências:** `packages/core_integrity/checkpoint.py`, `packages/core_application/integrity_checkpoint.py`, `packages/core_infrastructure/persistence/checkpoints.py`, migration `20260721_0010` e testes relacionados.
- **Riscos residuais:** a prova de inclusão inicial exige fornecer a cadeia completa; Merkle depende de volume e decisão futura; o instante observado não é prova temporal independente; TSA e TemporalAnchor pertencem ao Passo 4.4.

## Como validar o Passo 4.3

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/core_integrity/test_checkpoint.py tests/core_integrity/test_event_chain.py tests/application/test_integrity_checkpoint_service.py tests/infrastructure/test_checkpoint_persistence_contract.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m pytest -q tests/integration/test_checkpoints_postgresql.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_integrity packages/core_application packages/core_infrastructure/persistence/checkpoints.py tests/core_integrity/test_checkpoint.py tests/application/test_integrity_checkpoint_service.py tests/infrastructure/test_checkpoint_persistence_contract.py tests/integration/test_checkpoints_postgresql.py
.venv\Scripts\python.exe -m ruff format --check packages/core_integrity packages/core_application packages/core_infrastructure/persistence/checkpoints.py tests/core_integrity/test_checkpoint.py tests/application/test_integrity_checkpoint_service.py tests/infrastructure/test_checkpoint_persistence_contract.py tests/integration/test_checkpoints_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_integrity packages/core_application packages/core_infrastructure/persistence/checkpoints.py tests/core_integrity/test_checkpoint.py tests/application/test_integrity_checkpoint_service.py tests/infrastructure/test_checkpoint_persistence_contract.py tests/integration/test_checkpoints_postgresql.py
```

Resultado esperado: 15 testes sem banco e um teste PostgreSQL aprovados; banco em `20260721_0010 (head)`; nenhuma operação Alembic pendente; Ruff e Mypy aprovados. Os testes confirmam cobertura exata, omissão detectada, digest adulterado, escopo divergente e perfil incompatível como indeterminado.

### Passo 4.4 — TimestampProvider

- [x] Porta substituível definida na Application.
- [x] Tentativa, validação e âncora temporal são registros append-only distintos.
- [x] Indisponibilidade e resultado desconhecido permanecem explícitos e recuperáveis.
- [x] Provider falso é identificado como sintético e restrito ao desenvolvimento.
- [x] Assinatura, imprint, policy, nonce, autoridade, cadeia e validade são validados.
- [x] Token inválido, indeterminado ou de outro checkpoint nunca cria `TemporalAnchor`.
- [x] Tabelas são `PROTECTED`, com RLS e `FORCE RLS`.
- [x] Migration `20260721_0011` aplicada e `alembic check` sem divergências.
- [x] 11 testes relacionados, Ruff e Mypy aprovados.
- [x] Validação manual do responsável: 11 testes, Alembic, Ruff e Mypy aprovados.
- **Estado:** CONCLUÍDO E APROVADO.
- **Riscos residuais:** o provider falso não implementa RFC 3161, não possui confiança pública e não produz efeito jurídico; TSA real e seu perfil exigem decisão posterior aprovada.

## Como validar o Passo 4.4

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/application/test_timestamping_service.py tests/infrastructure/test_timestamp_persistence_contract.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_application/timestamping.py packages/core_infrastructure/fake_timestamp.py packages/core_infrastructure/persistence/timestamping.py tests/application/test_timestamping_service.py tests/infrastructure/test_timestamp_persistence_contract.py
.venv\Scripts\python.exe -m ruff format --check packages/core_application/timestamping.py packages/core_infrastructure/fake_timestamp.py packages/core_infrastructure/persistence/timestamping.py tests/application/test_timestamping_service.py tests/infrastructure/test_timestamp_persistence_contract.py
.venv\Scripts\python.exe -m mypy packages/core_application/timestamping.py packages/core_infrastructure/fake_timestamp.py packages/core_infrastructure/persistence/timestamping.py tests/application/test_timestamping_service.py tests/infrastructure/test_timestamp_persistence_contract.py
```

Resultado esperado: 11 testes aprovados; banco em `20260721_0011 (head)`; nenhuma operação Alembic pendente; Ruff e Mypy aprovados.

### Passo 4.5 — Correção sem sobrescrita

- [x] `Correction` é um novo `DomainEvent` imutável no agregado original.
- [x] Evento corrigido é referenciado por `causation_id` e pelo payload canônico.
- [x] Justificativa, `ChangeKind`, versão original e novo conteúdo são preservados.
- [x] Correção exige versão posterior e nunca altera o payload original.
- [x] Application coordena construção e append sem conhecer PostgreSQL.
- [x] Event store preserva timeline ordenada e encadeamento de integridade.
- [x] PostgreSQL retorna original e correção como dois registros distintos.
- [x] Idempotência, projeção corrente e concorrência adicional não foram antecipadas.
- [x] 8 testes focados, Ruff e Mypy aprovados.
- [x] Validação manual do responsável: todos os testes aprovados.
- **Estado:** CONCLUÍDO E APROVADO.
- **Riscos residuais:** a resolução da versão corrente, idempotência e concorrência pertencem aos passos seguintes; neste incremento, a timeline preserva e explica a correção sem escolher automaticamente seus efeitos downstream.

## Como validar o Passo 4.5

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m pytest -q tests/core_domain/test_correction.py tests/application/test_correction_service.py tests/integration/test_correction_postgresql.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m ruff check packages/core_domain/corrections.py packages/core_application/corrections.py packages/core_domain/__init__.py packages/core_application/__init__.py tests/core_domain/test_correction.py tests/application/test_correction_service.py tests/integration/test_correction_postgresql.py
.venv\Scripts\python.exe -m ruff format --check packages/core_domain/corrections.py packages/core_application/corrections.py packages/core_domain/__init__.py packages/core_application/__init__.py tests/core_domain/test_correction.py tests/application/test_correction_service.py tests/integration/test_correction_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_domain/corrections.py packages/core_application/corrections.py tests/core_domain/test_correction.py tests/application/test_correction_service.py tests/integration/test_correction_postgresql.py
```

Resultado esperado: 8 testes aprovados; Ruff e Mypy aprovados. O teste PostgreSQL confirma a timeline `registro_criado → registro_corrigido`, a preservação do original e o encadeamento dos hashes.

### Passo 4.6 — Idempotência

- [x] Identidade semântica inclui principal, Organization, Purpose, operação e Digest da intenção.
- [x] Primeira execução adquire o registro e compromete efeito e resultado na mesma transação.
- [x] Retry equivalente recupera exatamente o resultado canônico sem repetir o handler.
- [x] Mesma chave com intenção diferente produz conflito estável em português.
- [x] Operação sem resultado recuperável permanece desconhecida e não é reexecutada automaticamente.
- [x] PostgreSQL é autoritativo; Valkey não participa da garantia.
- [x] Registro é `PROTECTED`, possui RLS e escopo único por identidade semântica.
- [x] Transição no banco permite somente `EM_PROCESSAMENTO → CONCLUIDA` sem mudar identidade.
- [x] Migration `20260722_0012` possui downgrade.
- [x] 9 testes sem banco, Ruff e Mypy aprovados.
- [x] Migration, integração PostgreSQL e `alembic check`: 10 testes aprovados; downgrade/upgrade validado; banco em `20260722_0012 (head)`.
- [x] Validação manual do responsável.
- **Estado:** CONCLUÍDO E APROVADO.
- **Riscos residuais:** retenção operacional ainda será definida por perfil futuro; resultado desconhecido exige reconciliação, não repetição automática; concorrência otimista de agregados pertence ao Passo 4.7.

## Como validar o Passo 4.6

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/application/test_idempotency_service.py tests/infrastructure/test_idempotency_persistence_contract.py tests/integration/test_idempotency_postgresql.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_application/idempotency.py packages/core_infrastructure/persistence/idempotency.py packages/core_application/__init__.py packages/core_infrastructure/persistence/__init__.py packages/core_infrastructure/persistence/migrations/env.py tests/application/test_idempotency_service.py tests/infrastructure/test_idempotency_persistence_contract.py tests/integration/test_idempotency_postgresql.py
.venv\Scripts\python.exe -m ruff format --check packages/core_application/idempotency.py packages/core_infrastructure/persistence/idempotency.py packages/core_application/__init__.py packages/core_infrastructure/persistence/__init__.py packages/core_infrastructure/persistence/migrations/env.py tests/application/test_idempotency_service.py tests/infrastructure/test_idempotency_persistence_contract.py tests/integration/test_idempotency_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_application/idempotency.py packages/core_infrastructure/persistence/idempotency.py tests/application/test_idempotency_service.py tests/infrastructure/test_idempotency_persistence_contract.py tests/integration/test_idempotency_postgresql.py
```

Resultado esperado: 10 testes aprovados; banco em `20260722_0012 (head)`; nenhuma operação Alembic pendente; Ruff e Mypy aprovados. A repetição equivalente executa o efeito uma vez e a intenção divergente produz conflito.

### Passo 4.7 — Concorrência otimista

- [x] `aggregate_version` permanece a versão forte e sequencial do agregado.
- [x] Conflito possui contrato estável na Application e código público em português.
- [x] Infrastructure preserva compatibilidade com `EventAppendConflict`.
- [x] Lock transacional serializa concorrentes do mesmo agregado.
- [x] Constraint única impede versões duplicadas como defesa adicional.
- [x] Duas transações concorrentes partindo da mesma versão aceitam somente uma alteração.
- [x] Alteração obsoleta falha explicitamente sem last-write-wins.
- [x] Timeline final contém somente as versões `[1, 2]`, sem perda silenciosa.
- [x] Nenhuma migration ou API HTTP foi antecipada.
- [x] 8 testes relacionados, Ruff e Mypy aprovados.
- [x] Validação manual do responsável.
- **Estado:** CONCLUÍDO E APROVADO.
- **Riscos residuais:** ETag e `If-Match` serão adicionados somente quando existir endpoint mutável correspondente; retry automático não resolve conflito de negócio e exige nova leitura e reavaliação.

## Como validar o Passo 4.7

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m pytest -q tests/application/test_optimistic_concurrency.py tests/integration/test_optimistic_concurrency_postgresql.py tests/integration/test_domain_events_postgresql.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m ruff check packages/core_application/concurrency.py packages/core_application/__init__.py packages/core_infrastructure/persistence/events.py tests/application/test_optimistic_concurrency.py tests/integration/test_optimistic_concurrency_postgresql.py
.venv\Scripts\python.exe -m ruff format --check packages/core_application/concurrency.py packages/core_application/__init__.py packages/core_infrastructure/persistence/events.py tests/application/test_optimistic_concurrency.py tests/integration/test_optimistic_concurrency_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_application/concurrency.py packages/core_infrastructure/persistence/events.py tests/application/test_optimistic_concurrency.py tests/integration/test_optimistic_concurrency_postgresql.py
```

Resultado esperado: 8 testes aprovados; Ruff e Mypy aprovados. O teste concorrente retorna exatamente uma `ACEITA` e um conflito, mantendo apenas uma versão 2.

### Passo 4.8A — Transactional Outbox

- [x] `OutboxMessage` é contrato técnico de Application e não substitui `DomainEvent`.
- [x] Semântica distingue Domain Event, Integration Event, Command e Job.
- [x] Envelope preserva contrato, versão, Organization, Actor, produtor, correlação e causação.
- [x] Payload é canônico, versionado e classificado; credenciais continuam proibidas.
- [x] Event e OutboxMessage são gravados na mesma transação PostgreSQL.
- [x] Falha na Outbox reverte o Event da mesma operação.
- [x] Mensagem nasce `PENDENTE` e permanece imutável neste incremento.
- [x] Tabela é `PROTECTED`, com RLS e sem políticas de update ou delete.
- [x] Migration `20260722_0013` possui downgrade validado.
- [x] 9 testes relacionados, Ruff, Mypy e `alembic check` aprovados.
- [x] Validação manual do responsável: todos os testes aprovados.
- **Estado:** CONCLUÍDO E APROVADO.
- **Fora deste incremento:** publisher, claim/lease, confirmação RabbitMQ, resultado desconhecido, consumer/worker, Inbox e replay.
- **Riscos residuais:** mensagem pendente ainda não é publicada; estados operacionais de publicação serão registros separados para não alterar o envelope original.

## Como validar o Passo 4.8A

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/application/test_outbox.py tests/infrastructure/test_outbox_persistence_contract.py tests/integration/test_outbox_postgresql.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_application/outbox.py packages/core_application/__init__.py packages/core_infrastructure/persistence/outbox.py packages/core_infrastructure/persistence/__init__.py packages/core_infrastructure/persistence/migrations/env.py tests/application/test_outbox.py tests/infrastructure/test_outbox_persistence_contract.py tests/integration/test_outbox_postgresql.py
.venv\Scripts\python.exe -m ruff format --check packages/core_application/outbox.py packages/core_application/__init__.py packages/core_infrastructure/persistence/outbox.py packages/core_infrastructure/persistence/__init__.py packages/core_infrastructure/persistence/migrations/env.py tests/application/test_outbox.py tests/infrastructure/test_outbox_persistence_contract.py tests/integration/test_outbox_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_application/outbox.py packages/core_infrastructure/persistence/outbox.py tests/application/test_outbox.py tests/infrastructure/test_outbox_persistence_contract.py tests/integration/test_outbox_postgresql.py
```

Resultado esperado: 9 testes aprovados; banco em `20260722_0013 (head)`; Alembic, Ruff e Mypy aprovados. O teste de falha confirma que não permanece Event sem OutboxMessage.

### Passo 4.8B — Publisher da Outbox

- [x] Dependência `pika` adicionada ao manifesto e ao lockfile após aprovação.
- [x] Application define contrato broker-neutral para publisher.
- [x] Publisher registra aceite do broker separadamente de consumo.
- [x] Resultado desconhecido permanece recuperável e republicável com o mesmo `message_id`.
- [x] Estado operacional de publicação fica em tabelas separadas da `OutboxMessage` original.
- [x] Claim de publicação possui lease recuperável.
- [x] Adapter RabbitMQ fica restrito à Infrastructure.
- [x] Validação manual do responsável: aprovado.
- **Estado:** CONCLUÍDO E APROVADO.
- **Fora deste incremento:** consumer/worker, Inbox, DLQ/quarentena funcional, replay operacional e topologia definitiva de filas de negócio.
- **Riscos residuais:** a confirmação positiva prova aceite pelo broker conforme configuração local, não recebimento ou processamento por consumidor; falhas de transporte podem deixar resultado desconhecido e exigir retry/reconciliação.

### Passo 4.8C — Consumer, Inbox no PostgreSQL e Worker Executável (`apps/worker`)

- [x] ADR-0038 criada, refinada com Opção A e aprovada.
- [x] Schema `core_messaging` criado via migration Alembic (`20260722_0015_create_core_messaging_inbox.py`).
- [x] RLS isolada por `Organization` configurada nas tabelas `inbox_messages`, `inbox_delivery_attempts` e `inbox_conflicts`.
- [x] Tabela `untrusted_message_quarantine` criada para quarentena pré-tenant minimizada sem RLS.
- [x] Core Application expandido com `IncomingMessageEnvelope`, digest semântico `titan-json-v1`, portas e enums.
- [x] `TransactionalInboxRepository` implementado no Core Infrastructure com transação única e RLS transacional.
- [x] Transação de controle separada para agendamento de retry em caso de aborto da transação de processamento.
- [x] Adapter `RabbitMQPikaConsumer` implementado com `prefetch_count=1`, ACK pós-commit e graceful shutdown.
- [x] Executável `apps/worker/main.py` implementado com suporte aos sinais `SIGINT`/`SIGTERM`.
- [x] Suíte de testes (197/197), Ruff, Mypy e Alembic check aprovados.
- [x] Validação manual do responsável: aprovado.
- **Estado:** CONCLUÍDO E APROVADO.
- **Fora deste incremento:** topologia final de mensageria com múltiplas filas por vertical, UI/CLI de reconciliação e replay de Dead Letter Queue.
- **Riscos residuais:** instabilidade de rede no broker pode causar cancelamento temporário da subscrição de consumo, sendo tratada pelo ciclo de reconexão do worker.

### Passo 4.9A — Reconciliação operacional da Outbox

- [x] Estruturas `OutboxHealthSummary` (sem payload) e `OutboxReconciliationReport` criadas em `core_application`.
- [x] Porta `OutboxReconciliationRepositoryPort` e caso de uso `OutboxReconciliationService` implementados em `core_application`.
- [x] Repositório `TransactionalOutboxReconciliationRepository` implementado via SQLAlchemy Core em `core_infrastructure`.
- [x] Varredura `release_expired_claims()` atua exclusivamente em `outbox_publication_state` limpando claims expirados (`LEASE_EXPIRADA`) para re-elegibilidade por `claim_next()`.
- [x] Suíte de testes (200/200), Ruff, Mypy e Alembic check aprovados.
- [x] Validação manual do responsável: aprovado.
- **Estado:** CONCLUÍDO E APROVADO.
- **Fora deste incremento:** Inbox, quarentena, replay de consumo e `apps/worker`.
- **Riscos residuais:** nenhuma nova tabela ou coluna foi criada; a liberação atua somente sobre a tabela de estado operacional mantendo a `OutboxMessage` original intacta.

### Passo 4.9B — Inbox e ConsumerReceipt

- [x] Contratos e exceções de consumo `TransientConsumptionError` e `PermanentConsumptionError` em `core_application`.
- [x] Deduplicação determinística com digest semântico `titan-json-v1` UTF-8 NFC.
- [x] Repositório `TransactionalInboxRepository` no PostgreSQL com suporte a `PROCESSED`, `DUPLICATE_RECOVERED` e `CONFLICT_DETECTED` (tabela `core_messaging.inbox_conflicts`).
- [x] Suíte de testes (202/202), Ruff, Mypy e Alembic check aprovados.
- [x] Validação manual do responsável: aprovado.
- **Estado:** CONCLUÍDO E APROVADO.
- **Fora deste incremento:** Replay de consumo autorizado por operador e CLI do worker.
- **Riscos residuais:** mensagens com digest divergente geram registro forense em `inbox_conflicts` sem re-executar a aplicação.

### Passo 4.9C — Replay e quarentena

- [x] Estruturas `QuarantinedMessageRecord`, `ReplayRequest` e `ReplayResult` criadas em `core_application`.
- [x] Porta `InboxQuarantineRepositoryPort` e caso de uso `InboxQuarantineService` implementados em `core_application`.
- [x] Validação estrita de operador (`operator_actor_reference`) e obrigatoriedade de justificativa (`reason`).
- [x] Repositório `TransactionalInboxQuarantineRepository` no PostgreSQL com suporte a consulta paginada de quarentena e replay auditável via `inbox_delivery_attempts`.
- [x] Suíte de testes (205/205), Ruff, Mypy e Alembic check aprovados.
- [x] Validação automática e integridade: aprovado.
- **Estado:** CONCLUÍDO E APROVADO.
- **Fora deste incremento:** Topologia multi-broker de mensagens e consumidores distribuídos fora do Titan Core.
- **Riscos residuais:** nenhuma nova tabela criada; o worker compõe serviços já testados e aprovados.

### Passo 4.9D — Worker Executável

- [x] Configuração centralizada `WorkerSettings` em `apps/worker/config.py`.
- [x] Ponto de entrada executável `apps/worker/main.py` com composição de RabbitMQ Consumer, TransactionalInboxRepository, OutboxReconciliationService e suporte a encerramento gracioso (`SIGINT`/`SIGTERM`).
- [x] Testes unitários de configuração (`tests/unit/test_worker_config.py`).
- [x] Suíte de testes (207/207), Ruff, Mypy e Alembic check aprovados.
- [x] Validação automática e integridade: aprovado.
- **Estado:** CONCLUÍDO E APROVADO.
- **Fora deste incremento:** Métricas de observabilidade Prometheus/Grafana do worker.
- **Riscos residuais:** perda de conexão durante shutdown gracioso é tratada por rejeição/re-enfileiramento RabbitMQ sem perda de mensagens.



## Como validar o Passo 4.9B

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/application/test_inbox.py tests/application/test_inbox_deduplication.py tests/infrastructure/test_inbox_persistence_contract.py tests/integration/test_inbox_postgresql_flow.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_application/inbox.py packages/core_infrastructure/persistence/inbox.py tests/application/test_inbox_deduplication.py tests/integration/test_inbox_postgresql_flow.py
.venv\Scripts\python.exe -m ruff format --check packages/core_application/inbox.py packages/core_infrastructure/persistence/inbox.py tests/application/test_inbox_deduplication.py tests/integration/test_inbox_postgresql_flow.py
.venv\Scripts\python.exe -m mypy packages/core_application/inbox.py packages/core_infrastructure/persistence/inbox.py tests/application/test_inbox_deduplication.py tests/integration/test_inbox_postgresql_flow.py
```

Resultado esperado: testes do incremento aprovados; banco em `20260722_0015 (head)`; Alembic, Ruff e Mypy aprovados sem erros.


## Como validar o Passo 4.9A

```powershell
docker compose up --detach --wait postgres
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/application/test_outbox_reconciliation.py tests/infrastructure/test_outbox_reconciliation_persistence_contract.py tests/integration/test_outbox_reconciliation_postgresql.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_application/outbox.py packages/core_infrastructure/persistence/outbox.py tests/application/test_outbox_reconciliation.py tests/integration/test_outbox_reconciliation_postgresql.py
.venv\Scripts\python.exe -m ruff format --check packages/core_application/outbox.py packages/core_infrastructure/persistence/outbox.py tests/application/test_outbox_reconciliation.py tests/integration/test_outbox_reconciliation_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_application/outbox.py packages/core_infrastructure/persistence/outbox.py tests/application/test_outbox_reconciliation.py tests/integration/test_outbox_reconciliation_postgresql.py
```

Resultado esperado: testes do incremento aprovados; banco em `20260722_0015 (head)`; Alembic, Ruff e Mypy aprovados sem erros.


## Como validar o Passo 4.8C

```powershell
docker compose up --detach --wait postgres rabbitmq
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/application/test_inbox.py tests/infrastructure/test_inbox_persistence_contract.py tests/infrastructure/test_rabbitmq_consumer.py tests/integration/test_inbox_postgresql.py tests/integration/test_worker_e2e.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy
```

Resultado esperado: 197 testes aprovados; banco em `20260722_0015 (head)`; Alembic, Ruff e Mypy aprovados sem erros.


## Como validar o Passo 4.8B

```powershell
docker compose up --detach --wait postgres rabbitmq
$env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q tests/application/test_outbox.py tests/infrastructure/test_outbox_persistence_contract.py tests/infrastructure/test_rabbitmq_publisher.py tests/integration/test_outbox_postgresql.py tests/architecture/test_dependency_boundaries.py
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m ruff check packages/core_application/outbox.py packages/core_application/__init__.py packages/core_infrastructure/persistence/outbox.py packages/core_infrastructure/persistence/__init__.py packages/core_infrastructure/persistence/migrations/env.py packages/core_infrastructure/rabbitmq.py tests/application/test_outbox.py tests/infrastructure/test_outbox_persistence_contract.py tests/infrastructure/test_rabbitmq_publisher.py tests/integration/test_outbox_postgresql.py
.venv\Scripts\python.exe -m ruff format --check packages/core_application/outbox.py packages/core_application/__init__.py packages/core_infrastructure/persistence/outbox.py packages/core_infrastructure/persistence/__init__.py packages/core_infrastructure/persistence/migrations/env.py packages/core_infrastructure/rabbitmq.py tests/application/test_outbox.py tests/infrastructure/test_outbox_persistence_contract.py tests/infrastructure/test_rabbitmq_publisher.py tests/integration/test_outbox_postgresql.py
.venv\Scripts\python.exe -m mypy packages/core_application/outbox.py packages/core_application/__init__.py packages/core_infrastructure/persistence/outbox.py packages/core_infrastructure/persistence/__init__.py packages/core_infrastructure/persistence/migrations/env.py packages/core_infrastructure/rabbitmq.py tests/application/test_outbox.py tests/infrastructure/test_outbox_persistence_contract.py tests/infrastructure/test_rabbitmq_publisher.py tests/integration/test_outbox_postgresql.py
```

Resultado esperado: testes aprovados; banco em `20260722_0014 (head)`; Alembic, Ruff e Mypy aprovados. O teste de integração confirma retry após `RESULTADO_DESCONHECIDO` com o mesmo `message_id`.

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

### Passo 5.1 — Evidência e Fonte de Origem (Evidence e Source)

- [x] Agregado `Evidence`, `Source` e `SourceType` implementados em `packages/core_domain/evidence.py`.
- [x] Função `compute_content_hash` (SHA-256) garantindo cálculo imutável e determinístico.
- [x] Porta `EvidenceRepositoryPort` e serviço `EvidenceService` criados em `packages/core_application/evidence_service.py`.
- [x] Tabela `core_audit.evidences` com RLS por `Organization` e `TransactionalEvidenceRepository` em `packages/core_infrastructure/persistence/evidence.py`.
- [x] Migration Alembic `20260722_0016_create_evidences_table.py` aplicada com sucesso.
- [x] Testes unitários (`test_evidence_domain.py`) e de integração PostgreSQL com RLS (`test_evidence_postgresql.py`) aprovados (212 testes no total).

## Comandos para testar o Passo 5.1

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 212 testes aprovados; banco em `20260722_0016 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 5.2 — Níveis de Confiança (ConfidenceLevel)

- [x] Value Object `ConfidenceLevel` e enumeração `ConfidenceTier` implementados em `packages/core_domain/evidence.py`.
- [x] Invariante de validação de `reason` não vazia e pertença a `ConfidenceTier` garantida no Domínio.
- [x] Agregado `Evidence` atualizado para conter `confidence_level: ConfidenceLevel`.
- [x] `EvidenceService` e `EvidenceRepositoryPort` atualizados em `packages/core_application/evidence_service.py`.
- [x] Tabela `core_audit.evidences` com colunas `confidence_tier` e `confidence_reason` e `TransactionalEvidenceRepository` atualizado em `packages/core_infrastructure/persistence/evidence.py`.
- [x] Migration Alembic `20260722_0017_add_confidence_level_to_evidences.py` aplicada com sucesso.
- [x] Testes unitários (`test_evidence_domain.py`) e de integração PostgreSQL com RLS (`test_evidence_postgresql.py`) atualizados e aprovados (213 testes no total).

## Comandos para testar o Passo 5.2

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 213 testes aprovados; banco em `20260722_0017 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 5.3 — Validade, Verificação e Revogação de Evidências

- [x] Value Objects `ValidityPeriod`, `VerificationRecord`, `VerificationOutcome` e `EvidenceRevocation` criados em `packages/core_domain/evidence.py`.
- [x] Agregado `Evidence` estendido para comportar validade temporal, lista imutável de verificações e registro de revogação.
- [x] Casos de uso `verify_evidence` e `revoke_evidence` implementados no `EvidenceService` e porta `EvidenceRepositoryPort` atualizada com `update` em `packages/core_application/evidence_service.py`.
- [x] Tabelas `core_audit.evidences` (com colunas de validade e revogação) e `core_audit.evidence_verifications` com RLS por `Organization` criadas e `TransactionalEvidenceRepository` atualizado em `packages/core_infrastructure/persistence/evidence.py`.
- [x] Migration Alembic `20260722_0018_add_validity_and_revocation_to_evidences.py` aplicada com sucesso.
- [x] Testes unitários (`test_evidence_domain.py`) e de integração PostgreSQL com RLS (`test_evidence_postgresql.py`) aprovados (215 testes no total).

## Comandos para testar o Passo 5.3

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 215 testes aprovados; banco em `20260722_0018 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 5.4 — Contratos Criptográficos (SigningProvider, KeyProvider e TrustValidator)

- [x] Tipos imutáveis `CryptographicProfile`, `SignatureStatus`, `KeyIdentifier`, `CryptographicSignature` e `ValidationResult` criados em `packages/core_domain/crypto.py`.
- [x] Exportações atualizadas em `packages/core_domain/__init__.py`.
- [x] Portas `KeyProviderPort`, `SigningProviderPort` e `TrustValidatorPort` definidas em `packages/core_application/crypto.py`.
- [x] Adapters in-memory para desenvolvimento e testes (`SoftwareKeyProvider`, `SoftwareSigningProvider`, `SoftwareTrustValidator`) implementados em `packages/core_infrastructure/crypto.py`.
- [x] Testes unitários (`test_crypto_domain.py`) e de infraestrutura criptográfica (`test_crypto_infrastructure.py`) aprovados (217 testes no total).

## Comandos para testar o Passo 5.4

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 217 testes aprovados; banco em `20260722_0018 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 5.5 — Gestão e Rotação de Chaves (KeyRegistry e Criptoperíodo)

- [x] Enumeração `KeyState` (`ACTIVE`, `ROTATED`, `REVOKED`) e entidade `KeyRecord` criados em `packages/core_domain/crypto.py`.
- [x] Exportações atualizadas em `packages/core_domain/__init__.py`.
- [x] Porta `KeyRegistryPort` e serviço `KeyManagementService` implementados em `packages/core_application/crypto.py`.
- [x] Tabela `core_audit.key_registry` com RLS por `Organization` e `TransactionalKeyRegistryRepository` implementados em `packages/core_infrastructure/persistence/crypto.py`.
- [x] Migration Alembic `20260722_0019_create_key_registry_table.py` criada e aplicada com sucesso.
- [x] Testes unitários (`test_crypto_domain.py`) e de integração PostgreSQL com RLS (`test_crypto_postgresql.py`) aprovados (217 testes no total).

## Comandos para testar o Passo 5.5

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 217 testes aprovados; banco em `20260722_0019 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 5.6 — Assinatura de Evidence

- [x] Atributo opcional `signature: CryptographicSignature | None = None` e método `sign_evidence()` criados em `packages/core_domain/evidence.py`.
- [x] Caso de uso `sign_evidence()` orquestrando busca de chave ativa e geração da assinatura implementado em `packages/core_application/evidence_service.py`.
- [x] Colunas de assinatura adicionadas à tabela `core_audit.evidences` com RLS por `Organization` e `TransactionalEvidenceRepository` atualizado em `packages/core_infrastructure/persistence/evidence.py`.
- [x] Migration Alembic `20260722_0020_add_signature_to_evidences.py` criada e aplicada com sucesso.
- [x] Testes unitários (`test_evidence_domain.py`) e de integração PostgreSQL com RLS (`test_evidence_postgresql.py`) aprovados (217 testes no total).

## Comandos para testar o Passo 5.6

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 217 testes aprovados; banco em `20260722_0020 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 5.7 — Documento e anexo

- [x] Entidade imutável `Attachment` criada em `packages/core_domain/evidence.py`.
- [x] Portas `BlobStoragePort` e `AttachmentRepositoryPort`, e serviço `DocumentService` criados em `packages/core_application/document_service.py`.
- [x] Adapter `SoftwareBlobStorage` criado em `packages/core_infrastructure/storage.py`.
- [x] Tabela `core_audit.attachments` com RLS por `Organization` e `TransactionalAttachmentRepository` criados em `packages/core_infrastructure/persistence/evidence.py`.
- [x] Migration Alembic `20260722_0021_create_attachments_table.py` criada e aplicada com sucesso.
- [x] Testes unitários (`test_evidence_domain.py`) e de integração PostgreSQL com RLS (`test_document_postgresql.py`) aprovados (220 testes no total).

## Comandos para testar o Passo 5.7

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 220 testes aprovados; banco em `20260722_0021 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 5.8 — Proveniência (Conclusão do Marco 5)

- [x] Entidades imutáveis `ProvenanceNode`, `ProvenanceEdge` e `ProvenanceTrace` criadas em `packages/core_domain/provenance.py`.
- [x] Portas e serviço `ProvenanceService` criados em `packages/core_application/provenance_service.py` com suporte a rastreio `trace_from_event()`, `trace_from_evidence()` e `trace_from_source()`.
- [x] Repositórios `DomainEventRepository` e `TransactionalEvidenceRepository` atualizados para suporte a consultas de linhagem por `source_id`.
- [x] Testes unitários (`test_provenance_domain.py`) e de integração PostgreSQL com RLS (`test_provenance_postgresql.py`) aprovados (222 testes no total).

## Comandos para testar o Passo 5.8

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 222 testes aprovados; banco em `20260722_0021 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 6.1 — Policy versionada

- [x] Entidade imutável `Policy` e enum `PolicyStatus` criados em `packages/core_domain/policy.py`.
- [x] Porta `PolicyRepositoryPort` e serviço `PolicyService` criados em `packages/core_application/policy_service.py` com ciclo de vida formal (`DRAFT`, `PUBLISHED`, `SUPERSEDED`, `REVOKED`) e busca por vigência ativa.
- [x] Tabela `core_audit.policies` com RLS por `Organization` e `TransactionalPolicyRepository` criados em `packages/core_infrastructure/persistence/policy.py`.
- [x] Migration Alembic `20260722_0022_create_policies_table.py` criada e aplicada com sucesso.
- [x] Testes unitários (`test_policy_domain.py`) e de integração PostgreSQL com RLS (`test_policy_postgresql.py`) aprovados (225 testes no total).

## Comandos para testar o Passo 6.1

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 225 testes aprovados; banco em `20260722_0022 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 6.2 — Rule versionada

- [x] Entidade imutável `Rule` e enum `SeverityLevel` criados em `packages/core_domain/rule.py`.
- [x] Porta `RuleRepositoryPort` e serviço `RuleService` criados em `packages/core_application/rule_service.py` com suporte a severidade, fonte normativa, evidências requeridas, justificativa e ação corretiva.
- [x] Tabela `core_audit.rules` com RLS por `Organization` e `TransactionalRuleRepository` criados em `packages/core_infrastructure/persistence/rule.py`.
- [x] Migration Alembic `20260722_0023_create_rules_table.py` criada e aplicada com sucesso.
- [x] Testes unitários (`test_rule_domain.py`) e de integração PostgreSQL com RLS (`test_rule_postgresql.py`) aprovados (228 testes no total).

## Comandos para testar o Passo 6.2

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 228 testes aprovados; banco em `20260722_0023 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 6.3 — Contrato de fatos da vertical

- [x] Abstrações imutáveis `Fact` e `FactSnapshot` criadas em `packages/core_domain/facts.py` com cálculo determinístico de hash SHA-256 e consulta por tipo.
- [x] Porta `FactProviderPort` e serviço `FactService` criados em `packages/core_application/fact_service.py` isolando o Core de dependências da vertical pecuária ou banco de dados.
- [x] Testes unitários (`test_fact_domain.py`) e de aplicação com provider simulado (`test_fact_service.py`) aprovados (230 testes no total).

## Comandos para testar o Passo 6.3

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 230 testes aprovados; banco em `20260722_0023 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 6.4 — Execução de uma regra pura

- [x] Abstrações imutáveis `RuleResult` e `RuleResultStatus` (`ATENDIDA`, `NAO_ATENDIDA`, `PENDENTE`, `NAO_APLICAVEL`, `INDETERMINADA`) criadas em `packages/core_domain/evaluation.py`, com justificativa obrigatória e `compute_rule_inputs_hash` (SHA-256 determinístico das entradas relevantes).
- [x] Motor puro `RuleEvaluationEngine` criado em `packages/core_application/evaluation_service.py`, decidindo aplicabilidade por vigência e satisfação pelas evidências exigidas e pelas condições declarativas, sem acessar dados da vertical.
- [x] Condição normativa declarativa `RuleCondition` e `ComparisonOperator` criadas em `packages/core_domain/rule.py`: a condição é dado (`fact_type`, `payload_key`, operador, valor esperado), nunca código, tornando `NAO_ATENDIDA` e `INDETERMINADA` alcançáveis sem acoplar o Core à vertical.
- [x] Coluna `conditions` (JSONB) adicionada a `core_audit.rules` pela migration `20260722_0024`, com round-trip verificado em `test_rule_postgresql.py`; o digest das condições entra no hash das entradas via `compute_conditions_digest`.
- [x] Lacuna nunca vira reprovação: fato ausente => `PENDENTE`; chave ausente ou tipo incomparável => `INDETERMINADA`; apenas violação definitiva => `NAO_ATENDIDA`, com precedência sobre lacunas.
- [x] Testes unitários (`test_evaluation_domain.py`, `test_rule_condition_domain.py`) e de aplicação com casos de sucesso, falha, pendência, indeterminação e não aplicável (`test_evaluation_service.py`) aprovados, confirmando reprodutibilidade de resultado e hash (264 testes no total).

## Comandos para testar o Passo 6.4

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 264 testes aprovados; banco em `20260722_0024 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 6.5 — Agregação em Evaluation

- [x] Agregado imutável `Evaluation` e `EvaluationOutcome` criados em `packages/core_domain/evaluation.py`, preservando Organization, Subject, finalidade, Policy e versão, regras e versões, snapshot completo, RuleResults, momento, versão do motor e executor.
- [x] `compute_evaluation_hash` e `aggregate_outcome` criados: o hash descreve o conteúdo avaliado e omite de propósito a identidade das instâncias de RuleResult, tornando a avaliação reproduzível e verificável por `is_reproducible()`.
- [x] `PolicyEvaluationService` criado em `packages/core_application/evaluation_service.py`, executando as regras em ordem estável para que o resultado não dependa da ordem de leitura do repositório.
- [x] Ausência de regra aplicável nunca é reportada como conformidade: sem nada verificado, o resultado é `INDETERMINADO`.
- [x] Apenas políticas publicadas ou substituídas são executáveis; rascunho e revogada são rejeitados.
- [x] Tabela `core_audit.evaluations` com RLS por `Organization` e gravação append-only criada em `packages/core_infrastructure/persistence/evaluation.py`, com migration `20260722_0025`.
- [x] Testes unitários (`test_evaluation_aggregate_domain.py`), de aplicação (`test_policy_evaluation_service.py`) e de integração PostgreSQL com RLS (`test_evaluation_postgresql.py`) aprovados, confirmando que alterar os fatos depois da avaliação não afeta a avaliação histórica (280 testes no total).

## Comandos para testar o Passo 6.5

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 280 testes aprovados; banco em `20260722_0025 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 6.6 — Decision explicável

- [x] `Decision`, `DecisionResult`, `DecisionReason` e `DecisionReasonCode` criados em `packages/core_domain/decision.py`, preservando política/versão, regras/resultados, sujeitos afetados, evidências, motivos e ações corretivas.
- [x] Invariante de explicabilidade garantida em dois níveis: o domínio recusa Decision sem razão e a tabela impõe `CHECK (jsonb_array_length(reasons) > 0)`, de modo que nem escrita direta em SQL produza conclusão muda.
- [x] Código da razão é contrato e mensagem humana é separada: `compute_decision_hash` inclui o código e ignora a mensagem, permitindo tradução sem inverter a conclusão.
- [x] `DecisionService` criado em `packages/core_application/decision_service.py`, derivando a conclusão da Evaluation sem reavaliar nada; descumprimento `BLOCKING`/`CRITICAL` reprova e descumprimento apenas informativo produz `APROVADA_COM_RESTRICOES`.
- [x] Evaluation adulterada (conteúdo que não confere com o hash registrado) é recusada e não fundamenta Decision alguma.
- [x] Evidências citadas na Decision são reunidas de `Fact.source_reference`, ligando a conclusão às evidências que sustentam os fatos.
- [x] `rule_code` adicionado ao `RuleResult` para que a razão identifique a regra de forma legível, sem alterar os hashes já definidos no Passo 6.4.
- [x] Tabela `core_audit.decisions` com RLS por `Organization` e gravação append-only criada em `packages/core_infrastructure/persistence/decision.py`, com migration `20260722_0026`.
- [x] Testes unitários (`test_decision_domain.py`), de aplicação (`test_decision_service.py`) e de integração PostgreSQL com RLS (`test_decision_postgresql.py`) aprovados, confirmando reconstrução da decisão a partir da Evaluation persistida (295 testes no total).

## Comandos para testar o Passo 6.6

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 295 testes aprovados; banco em `20260722_0026 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 7.1 — Relação universal e temporal

- [x] `UniversalRelation` imutável criada em `packages/core_domain/relations.py` com origem, destino, tipo, período, Organization, Event criador, evidências, confiança, quantidade opcional com unidade e metadados versionados.
- [x] `relation_type` é nome canônico livre validado por padrão, não enum: o Core não conhece os vínculos de nenhuma vertical e não precisa mudar quando uma vertical adiciona um vínculo novo.
- [x] Relação recusa origem ou destino pertencente a outra Organization, e `RelationService` bloqueia travessia entre Organizations com `CrossOrganizationTraversalDenied` antes de consultar o repositório.
- [x] Encerrar relação declara fim de vigência sem apagar o vínculo: consultas em instantes anteriores continuam respondendo, preservando a genealogia.
- [x] Quantidade usa `Decimal` (rejeita `float`), nunca negativa e sempre com unidade declarada.
- [x] Tabela `core_audit.relations` com RLS por `Organization`, índices por origem e destino e migration `20260722_0027` criadas em `packages/core_infrastructure/persistence/relations.py`.
- [x] Testes unitários (`test_relations_domain.py`), de aplicação (`test_relation_service.py`) e de integração PostgreSQL com RLS (`test_relations_postgresql.py`) aprovados, com grafo fictício genérico consultado em datas diferentes (309 testes no total).

## Comandos para testar o Passo 7.1

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 309 testes aprovados; banco em `20260722_0027 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 7.2 — Projeções reconstruíveis

- [x] `ReverseReference`, `ReferencingKind`, `ReferenceRole` e `compute_projection_digest` criados em `packages/core_domain/projections.py`.
- [x] `ProjectionRebuildService` criado em `packages/core_application/projection_service.py`, derivando a projeção de `domain_events` e `relations` sem regra de negócio própria.
- [x] Chave primária é o próprio conteúdo derivado, sem identificador sorteado: reconstruir produz linhas idênticas e a comparação entre reconstruções é exata.
- [x] Digest ignora o instante de reconstrução, que descreve a execução e não o conteúdo derivado.
- [x] Entradas ordenadas por chave total antes de gravar: o conteúdo não depende da ordem de leitura do banco.
- [x] `is_consistent_with_sources()` detecta projeção defasada sem gravar nada.
- [x] Tabela `core_audit.reference_projection` com RLS e migration `20260722_0028` criadas em `packages/core_infrastructure/persistence/projections.py`.
- [x] Testes unitários (`test_projections_domain.py`), de aplicação (`test_projection_service.py`) e de integração PostgreSQL (`test_projections_postgresql.py`) aprovados, confirmando que apagar somente a projeção e reconstruí-la devolve conteúdo idêntico com a fonte histórica intacta (323 testes no total).

## Comandos para testar o Passo 7.2

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 323 testes aprovados; banco em `20260722_0028 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 7.3 — NonConformity Core

- [x] `NonConformity` criada em `packages/core_domain/nonconformity.py` com origem, severidade, período afetado, responsável, prazo, ação corretiva, evidência de correção, reavaliação e histórico.
- [x] Ciclo de vida `DETECTADA → CLASSIFICADA → ATRIBUIDA → EM_CORRECAO → PRONTA_PARA_REAVALIACAO → ENCERRADA` com transições validadas; pular etapas é recusado e encerrada é terminal.
- [x] Reavaliação reprovada devolve o caso a `EM_CORRECAO` sem apagar a tentativa anterior.
- [x] Histórico só cresce, reforçado no banco por `CHECK (jsonb_array_length(transitions) > 0)` e por exigência de `closed_at` quando encerrada.
- [x] Submeter à reavaliação exige evidência de correção; encerrar exige a `Evaluation` reavaliadora e recusa avaliação não reproduzível.
- [x] `NonConformityService.open_from_evaluation` abre casos apenas para resultados que exigem tratamento, ignorando regra atendida e não aplicável.
- [x] Tabela `core_audit.nonconformities` com RLS, índices por sujeito e por estado, e migration `20260722_0029`.
- [x] Testes unitários (`test_nonconformity_domain.py`) e de integração PostgreSQL (`test_nonconformity_postgresql.py`) aprovados, percorrendo abrir, corrigir, reavaliar reprovando, corrigir de novo e encerrar (336 testes no total).

## Comandos para testar o Passo 7.3

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 336 testes aprovados; banco em `20260722_0029 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 7.4 — Recall Core

- [x] `RecallRequest`, `RecallResult`, `RecallPath`, `RecallStep` e `RecallGap` criados em `packages/core_domain/recall.py`, com direção retrospectiva, prospectiva e ambas.
- [x] `RecallService` criado em `packages/core_application/recall_service.py` com travessia em largura, ordem determinística e explicação de cada caminho.
- [x] Limites de profundidade, número de nós e detecção de ciclo geram `RecallGap` explícita; qualquer lacuna torna o resultado `INCONCLUSIVO`.
- [x] Janela temporal filtra as relações vigentes no instante consultado, mudando o grafo alcançável.
- [x] Filtro por tipo de relação restringe a travessia sem alterar o grafo.
- [x] Simulação não deixa rastro; incidente exige repositório e é gravado por inteiro para explicação posterior.
- [x] Decisões afetadas são localizadas a partir dos sujeitos alcançados, via `PostgresAffectedDecisionLookup`.
- [x] Subject inicial de outra Organization é recusado, e a travessia só enxerga o grafo da própria Organization.
- [x] Tabela `core_audit.recalls` com RLS, índice por sujeito e migration `20260722_0030`.
- [x] Testes de aplicação (`test_recall_service.py`) e de integração PostgreSQL (`test_recall_postgresql.py`) aprovados sobre grafo fictício genérico (349 testes no total).

## Comandos para testar o Passo 7.4

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 349 testes aprovados; banco em `20260722_0030 (head)`; Alembic, Ruff e Mypy aprovados sem erros.











