# Checklist de Implementação — Titan

**Atualizado em:** 24 de julho de 2026  
**Fonte dos passos:** `docs/PLANO_DE_IMPLEMENTACAO_VALIDADO.md`  
**Próximo passo planejado:** validar o Marco 12 e iniciar o frontend

> **Nota de numeração:** a numeração deste checklist havia divergido do `PLANO_DE_IMPLEMENTACAO_VALIDADO.md`, que é a autoridade. Os registros do Marco 9 abaixo seguem a numeração do **PLANO**: 9.1 Medication e MedicationBatch, 9.2 VeterinaryPrescription, 9.3 TreatmentApplication, 9.4 WithdrawalPeriod, 9.5 elegibilidade farmacológica, 9.6 avaliação de lote. A entrega anterior rotulada "9.1 — Agregadores de Medicamentos e Prescrições" cobriu, na prática, o Medication do PLANO-9.1 **e** o VeterinaryPrescription do PLANO-9.2; o MedicationBatch que faltava no PLANO-9.1 foi entregue depois.

> **Nota sobre o 10.1a e o 10.1b:** o PLANO define um único Passo 10.1 (Timeline Livestock). Ele foi dividido em dois na execução, com aprovação do responsável, porque a timeline pressupõe eventos que a vertical ainda não emitia — o **10.1a** faz a vertical emitir, o **10.1b** entrega a consulta cronológica que o PLANO descreve. A divisão é de execução, não de escopo: o 10.1 do PLANO só estará cumprido ao fim do 10.1b.













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
| 0.1–0.4 | Definições de fronteira, linguagem, ADRs e comandos | CONCLUÍDO | Aprovada |
| 1.1–1.6 | Workspace, qualidade, FastAPI, Docker, PostgreSQL e CI | CONCLUÍDO | Aprovada |
| 2.1–2.4 | Primitivas técnicas do Core (ID, tempo, serialização, payload) | CONCLUÍDO | Aprovada |
| 3.1–3.7 | Identidade, autorização, RLS, OIDC e isolamento | CONCLUÍDO | Aprovada |
| 4.1–4.9D | Auditoria, Outbox, Inbox, Checkpoints, Idempotência e Workers | CONCLUÍDO | Aprovada |
| 5.1–5.8 | Evidence, criptografia, assinaturas e Provenance | CONCLUÍDO | Aprovada |
| 6.1–6.6 | Policy, Rule, Evaluation e Decision explicável | CONCLUÍDO | Aprovada |
| 7.1–7.10 | Relações, recall, dossiê, bundle, sync e prova do Core | CONCLUÍDO (incluindo 7.8 e 7.9) | Aprovada |
| 8.0–8.6 | Fundação Titan Livestock | CONCLUÍDO | Aprovada |
| 9.1–9.6 | Medicamentos e elegibilidade | IMPLEMENTADO — 9.1 a 9.6 (numeração do PLANO) | Pendente |
| 10.1–10.6 | Demonstração vertical verificável | 10.1 a 10.4 e 10.6 completos; 10.5 dispensado (opcional no PLANO) | 10.1 a 10.4 aprovadas; 10.6 pendente |


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

### Passo 7.5 — Dossier Core

- [x] `Dossier` e `compute_dossier_hash` criados em `packages/core_domain/dossier.py`, com verificação offline pelo próprio documento.
- [x] Documento autocontido: sujeito, finalidade, política e versão, regras com condições declarativas, snapshot completo dos fatos, resultados por regra, decisão com razões e ações, evidências e não conformidades com histórico.
- [x] Hash calculado sobre a serialização canônica `titan-json-v1` já adotada pelo Core, permitindo recálculo por terceiros sem acesso ao Titan.
- [x] Evaluation ou Decision não reproduzíveis são recusadas; decisão de outra avaliação ou de outra política também.
- [x] Tabela `core_audit.dossiers` com RLS, índice por sujeito e migration `20260722_0031`.
- [x] Testes de aplicação (`test_dossier_service.py`) e de integração PostgreSQL (`test_dossier_postgresql.py`) aprovados, exportando o JSON, recalculando o hash fora do banco e refazendo o raciocínio da decisão apenas com o documento (358 testes no total).

## Comandos para testar o Passo 7.5

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 358 testes aprovados; banco em `20260722_0031 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 7.6 — VerificationBundle

- [x] `BundleManifest`, `BundleComponent`, `SignatureMaterial`, `VerificationBundle`, `BundleVerifier`, `ValidationReport` e `DimensionResult` criados em `packages/core_domain/verification.py`.
- [x] `VerificationBundleService` criado em `packages/core_application/verification_service.py`, com `export()` e `load()` para o pacote viajar como texto e ser reconstruído fora do Titan.
- [x] Verificador puro: sem rede, sem segredo e sem banco; sete dimensões independentes em vez de um booleano único.
- [x] Ausência de material produz `INDETERMINADA`; adulteração produz `INVALIDA` com o ponto exato nomeado em `failure_point`.
- [x] Componente presente mas não declarado reprova o pacote, impedindo mistura silenciosa.
- [x] Âncora de confiança incluída no pacote não é aceita por estar nele; sem âncora externa a assinatura é indeterminada.
- [x] Chave privada, segredo, token, credencial e contexto de organização são recusados na montagem.
- [x] Dossiê que não confere com o próprio hash não pode ser empacotado.
- [x] Testes (`test_verification_bundle.py`) aprovados, cobrindo transporte fora do Titan, adulteração de componente e de manifesto, componente intruso, ausência de âncora e lacuna declarada (370 testes no total).

## Comandos para testar o Passo 7.6

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 370 testes aprovados; banco em `20260722_0031 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 7.7 — API de verificação externa

- [x] ADR-0039 escrita, revisada e **aceita antes do código**, cumprindo o portão da ADR-0010 que exigia contrato antes da implementação.
- [x] Domínio estendido: `NAO_APLICAVEL` e `NAO_EXECUTADA` acrescentados a `VerificationStatus`; dimensão declarativa `REVOGACAO_ATUAL` sempre não executada; `NORMATIVE_DIMENSION_ORDER` e `MANDATORY_DIMENSIONS` criados.
- [x] Regra do agregado corrigida: dimensão obrigatória `INDETERMINADA`, `NAO_EXECUTADA` ou `NAO_APLICAVEL` sem permissão nunca produz agregado válido.
- [x] Algoritmo fora da allowlist produz `ASSINATURA = INDETERMINADA`, não erro de contrato e não `NAO_EXECUTADA`.
- [x] `failures` lista somente dimensões `INVALIDA`; `first_failure` segue a ordem normativa pública.
- [x] `POST /v1/verification/bundles` criado em `apps/api/verification.py`, hermético e sem consulta ao banco.
- [x] `400` para JSON inválido e chave duplicada; `422` para schema e pacote irrepresentável; `413` para corpo acima do limite; `200` inclusive para `INVALIDA`.
- [x] Limites de corpo, componentes, profundidade e âncoras aplicados; `Cache-Control: no-store`; âncora devolvida por fingerprint; `detail` sanitizado.
- [x] Testes (`test_verification_api.py`, `test_verification_bundle.py`) aprovados, cobrindo íntegro, inválido, incompleto, algoritmo não suportado, âncora duplicada, profundidade excessiva e determinismo do relatório (391 testes no total).

**Fora do escopo da aplicação:** rate limiting (`429`), terminação TLS e não captura de corpo por gateway, APM e tracing são responsabilidades de implantação, declaradas na ADR-0039 e não testáveis no nível do aplicativo.

## Comandos para testar o Passo 7.7

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 391 testes aprovados; banco em `20260722_0031 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 7.9 — Synchronization Core

- [x] Passo 7.8 (representação PDF) **deliberadamente adiado**, com decisão registrada: o cenário do Passo 7.10 não inclui PDF, e `PLANO_DE_IMPLEMENTACAO_VALIDADO.md` condiciona PAdES-LT/LTA a perfil jurídico aprovado, que não existe.
- [x] Contratos criados em `packages/core_domain/synchronization.py`: `DeviceClockReading`, `OfflineOperation`, `OperationManifestEntry`, `SynchronizationBatch`, `SynchronizationConflict`, `SynchronizationResult` e `SynchronizationBatchResult`, com os estados públicos em português da ADR-0021.
- [x] Digest da intenção separado do envelope: `compute_intent_digest` ignora OperationId, sequência local, relógio e tentativa, de modo que a mesma intenção recapturada produz o mesmo digest e o retry não duplica.
- [x] Relógio do Device permanece alegação: `TimeConfidenceLevel` não converte relógio local em prova temporal, e `precedes` só responde dentro da mesma continuidade monotônica — fora dela devolve `None` em vez de inventar precedência.
- [x] Manifesto detecta remoção, duplicação, substituição, alteração, Organization e Device divergentes e sequência fora da fronteira; `inspect` devolve todos os defeitos, não apenas o primeiro.
- [x] Ordem física do lote não cria causalidade: `SynchronizationService` processa por dependência declarada, e a dependente enviada fisicamente antes da origem é aceita depois dela.
- [x] Ciclo de dependências vira `CONFLITANTE` explícito, nunca pendência indefinida; dependência ausente, rejeitada ou em conflito permanece `DEPENDENCIA_PENDENTE` com o motivo nomeado.
- [x] IdempotencyKey reutilizada com intenção divergente produz `CONFLITANTE` e **nunca** recupera nem associa o resultado anterior; a mesma intenção sob a mesma chave produz `DUPLICADA` sem repetir o efeito.
- [x] Retomada é por operação, não por lote: a tentativa é do envelope, e o histórico append-only por tentativa preserva as decisões sucessivas em vez de reescrevê-las.
- [x] `RESULTADO_DESCONHECIDO` exige prazo de reconciliação e não é reprocessado no reenvio, porque reprocessar poderia repetir um efeito que talvez já exista; o estado não implica ausência, sucesso ou falha.
- [x] Conflito nunca é resolvido silenciosamente: não há last-write-wins, maior timestamp do Device nem último lote recebido; todo conflito carrega estado observado e alternativas.
- [x] Rejeição, conflito e quarentena preservam a captura: a OfflineOperation é gravada mesmo sem efeito oficial.
- [x] Tabelas `core_audit.offline_operations`, `core_audit.synchronization_results` e `core_audit.synchronization_batches` criadas com RLS e `FORCE ROW LEVEL SECURITY` na migration `20260722_0032`, com downgrade validado.
- [x] Três invariantes repetidas como `CHECK` no banco: `ACEITA` sem efeito, `CONFLITANTE` sem conflito e `RESULTADO_DESCONHECIDO` sem prazo são recusados mesmo por escrita direta em SQL.
- [x] Ausência deliberada de `UNIQUE (organization, idempotency_key)`: a segunda captura com intenção divergente precisa ser preservada para virar conflito explícito, e a constraint a apagaria em vez de explicá-la.
- [x] Releitura devolve `StoredOfflineOperation` com o payload em bytes canônicos, sem reconstruir `CanonicalPayload`, respeitando o contrato do Passo 2.4 que impede construir payload a partir de bytes arbitrários.
- [x] Testes de domínio (`test_synchronization_domain.py`), de aplicação (`test_synchronization_service.py`) e de integração PostgreSQL com RLS (`test_synchronization_postgresql.py`) aprovados, cobrindo a lista de testabilidade da ADR-0021 (438 testes no total).

**Fora do escopo deste passo, deliberadamente:** `OfflineCapabilityProfile`, `OfflineSession`, `OfflineAuthorizationSnapshot`, `DeviceTrustAssessment` e `LocalPreview` não constam da entrega do Passo 7.9 e não foram antecipados. A admissão do Device existe como porta explícita (`DeviceAdmissionPort`) com implementação permissiva, para que o `DeviceTrustAssessment` futuro tenha onde entrar sem alterar o serviço. O estado `VALIDADO_PARCIALMENTE` permanece declarado e não produzido: validação e processamento ocorrem na mesma fronteira transacional.

## Comandos para testar o Passo 7.9

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 438 testes aprovados; banco em `20260722_0032 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

### Passo 7.10 — Prova completa do Core

- [x] Cenário fictício e genérico criado em `tests/integration/test_core_proof_postgresql.py`, encadeado contra o PostgreSQL autoritativo: autenticação → Organization → evento → evidência → genealogia → regra → avaliação → decisão → não conformidade → recall → dossiê → sincronização.
- [x] Vocabulário sem vertical alguma: os sujeitos são `lote`, `insumo` e `remessa`. Escrever a prova com termos de gado esconderia justamente o acoplamento que ela existe para descartar.
- [x] Cada elo alimenta o seguinte de verdade: a evidência assinada é a fonte do fato avaliado, a avaliação fundamenta a decisão, a decisão abre a não conformidade, a genealogia sustenta o recall e a operação offline sincronizada produz uma relação real do grafo.
- [x] **Substituir providers falsos sem alterar o Core:** o mesmo `EvidenceService` assina com `SoftwareSigningProvider` e com um segundo provedor de algoritmo diferente, sem uma linha de mudança no Core, e a chave continua sendo a registrada pelo Core.
- [x] **Adulterar cópias para testar integridade:** inverter a conclusão, trocar o fato que sustenta a reprovação e adulterar os bytes do componente do pacote são todos recusados — o dossiê pelo hash canônico e o `VerificationBundle` pelo verificador offline, sem consultar o Titan.
- [x] **Repetir operações:** o reenvio do lote recupera o resultado por `OperationId` sem repetir o efeito oficial, com `RESULTADO_RECUPERADO` no resultado.
- [x] **Isolamento entre duas Organizations:** role temporária `NOBYPASSRLS` percorre as **treze** tabelas do cenário no contexto da outra Organization e não enxerga nenhum registro. Provar uma tabela e presumir as outras seria exatamente a falha que este passo existe para descartar.
- [x] Recall provado nas duas propriedades: travessia limpa é `CONCLUSIVO`; travessia que reencontra o sujeito declara `CICLO_DETECTADO` e rebaixa o resultado inteiro a `INCONCLUSIVO` — lacuna nunca vira silêncio, mesmo quando o reencontro é inofensivo.
- [x] `VerificationBundle` só é declarado `VALIDA` com assinatura, política de verificação e âncora de confiança; sem âncora o veredito é `INDETERMINADA`, nunca válido por omissão.
- [x] O cenário roda em transação revertida ao final: a prova não deixa resíduo no banco.

#### Testes arquiteturais — correção de um teste que não verificava nada

- [x] **Defeito encontrado e corrigido:** `test_core_does_not_import_verticals` varria `packages/core`, diretório que nunca existiu. O teste passava sem examinar um único arquivo desde que foi escrito. Agora percorre os pacotes reais (`core_domain`, `core_application`, `core_infrastructure`, `core_integrity`).
- [x] `require_existing_root` acrescentada: qualquer teste de fronteira cujo alvo não exista passa a falhar alto. Renomear um pacote não pode transformar a verificação em aprovação automática.
- [x] Fronteiras novas cobertas: Core Domain não importa Application (a dependência aponta para dentro); Core Application não conhece framework nem ORM; `shared_kernel` não depende de quem depende dele.
- [x] Sete testes arquiteturais aprovados, sem nenhuma violação escondida pelo teste vazio anterior.

#### Superfície HTTP pública no fechamento do Core

- [x] `tests/api/test_core_public_surface.py` congela a superfície: `/health`, `/technical/authentication` e `POST /v1/verification/bundles`.
- [x] Guarda explícita contra endpoint de domínio antes do **Passo 10.4**, que é onde o plano prevê a "API mínima do fluxo aprovado". Construir a API REST de domínio agora seria pular um marco e inventar requisito.
- [x] Swagger respondendo em `/docs`, atendendo à validação por API/Swagger prevista no plano.
- [x] 449 testes aprovados no total.

**Portão do Marco 7:** contratos, testes arquiteturais e critérios do Core aprovados automaticamente. O Titan Livestock (Marco 8) permanece bloqueado até a validação manual do responsável.

#### Validação manual executada em 23 de julho de 2026

Roteiro executado pelo responsável, com os resultados observados:

- [x] Cinco testes da prova completa, nomeados um por critério do plano.
- [x] Sete testes arquiteturais e 34 testes de API/arquitetura.
- [x] Catálogo do PostgreSQL: **27 tabelas** em `core_audit`, todas com `relrowsecurity = t` e `relforcerowsecurity = t`, sem exceção.
- [x] Swagger inspecionado: apenas os três endpoints previstos, e apenas dois schemas.
- [x] `400` com `application/problem+json`, `reason_code: MALFORMED_JSON`, `cache-control: no-store` e `pragma: no-cache` observados no header real.
- [x] `detail` sanitizado, sem caminho de arquivo nem stack trace.
- [x] `401` com `www-authenticate: Bearer` na rota protegida sem token.
- [x] Portão completo: 449 testes.

**Três não conformidades encontradas pela inspeção manual, que o portão automático não detectava.** Os testes cobriam o *comportamento* do endpoint; ninguém verificava o que o OpenAPI *publica* sobre ele.

1. **Requisito textual da ADR-0039 não cumprido.** A ADR exige que o aviso "Pacotes sensíveis não devem ser enviados a uma instância pública não confiável. Nesses casos, utilize o verificador local" conste **também da documentação pública**. O `openapi.json` não o continha: o endpoint tinha `summary` e `description` nula. O aviso existia apenas na ADR e no guia de integração, e quem integra com a API lê o Swagger.
2. **Schema do corpo não publicado.** `requestBody` ausente do OpenAPI e resposta `200` com schema vazio. O `VerificationRequest` existia em código, mas o handler recebe `Request` cru — para controlar `400` versus `422` e recusar chave duplicada — e o FastAPI não o inferia. A ADR-0010 exigia schemas públicos.
3. **Rota protegida sem a negação declarada.** `/technical/authentication` não declarava o `401`; o Swagger o exibia como "Undocumented".

**Correção aplicada em 23 de julho de 2026**, sem alterar comportamento algum:

- [x] `description` do endpoint de verificação passa a conter o aviso obrigatório da ADR-0039, mais as limitações da resposta.
- [x] `public_contract_schemas()` publica `VerificationRequest` e `TrustAnchorInput` em `components.schemas`, e o `requestBody` os referencia; `app.openapi` foi estendido porque o FastAPI não registra componentes de rotas que leem o corpo cru.
- [x] `401` declarado em `/technical/authentication`.
- [x] Três testes de regressão criados em `TestContratoPublicado`, que verificam o **contrato publicado** e não apenas o comportamento — a lacuna que permitiu as três passarem despercebidas.
- [x] Portão completo reexecutado: **452 testes**, Ruff, Mypy e Alembic aprovados.

**Estado da validação manual:** aguardando a manifestação do responsável sobre as correções.

## Comandos para testar o Passo 7.10

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest tests/integration/test_core_proof_postgresql.py -v
python -m uv run --locked pytest tests/architecture tests/api -v
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 5 testes da prova completa, 7 arquiteturais e 449 no total aprovados; banco em `20260722_0032 (head)`; Alembic, Ruff e Mypy aprovados sem erros.

---

## Passo 8.1 — RuralProperty

**Data de conclusão:** 23 de julho de 2026  
**Estado:** CONCLUÍDO E APROVADO

### O que foi entregue
- **Domínio (`packages/livestock_domain/property.py`):** Entidade imutável `RuralProperty` com contrato e validações (código, nome, município, UF de 2 letras maiúsculas, área em hectares positiva).
- **Aplicação (`packages/livestock_application/property_service.py`):** Porta `RuralPropertyRepositoryPort` e serviço `RuralPropertyService` com cadastro, busca por ID, busca por código e listagem paginada por `OrganizationId`.
- **Infraestrutura (`packages/livestock_infrastructure/persistence/property_repository.py`):** Repositório PostgreSQL `TransactionalRuralPropertyRepository` sobre a tabela `core_audit.rural_properties` com isolamento estrito via RLS (`titan.organization_id`).
- **Migration (`packages/core_infrastructure/persistence/migrations/versions/20260723_0033_create_rural_properties_table.py`):** Migration Alembic 0033 criando `core_audit.rural_properties` com políticas RLS ativadas e forçadas.
- **Suíte de Testes:**
  - `tests/livestock_domain/test_property_domain.py` (5 testes unitários)
  - `tests/livestock_application/test_property_service.py` (2 testes de aplicação)
  - `tests/integration/test_property_postgresql.py` (1 teste de integração RLS em PostgreSQL real)

### Evidências de execução e verificações
```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
```
- **Resultado:** 473 testes aprovados em 10.69s; Alembic em `20260723_0033 (head)`; Ruff e Mypy 100% limpos sem erros.

---

## Passo 8.2 — Animal e Identity

**Data de conclusão:** 23 de julho de 2026  
**Estado:** CONCLUÍDO E APROVADO

### O que foi entregue
- **Domínio (`packages/livestock_domain/animal.py`):** Entidade imutável `Animal` com `animal_id` permanente, `birth_property_id`, sexo (`AnimalSex`), raça, data de nascimento e coleção imutável de identificadores de campo versionados (`AnimalIdentifier`: brincos visuais, SISBOV, chip RFID).
- **Invariantes de Domínio:** Recusa de alteração da identidade permanente `animal_id` (dataclass `frozen=True`), proibição de mais de uma tag `ACTIVE` do mesmo tipo no mesmo animal e manutenção do histórico completo ao desativar brincos.
- **Aplicação (`packages/livestock_application/animal_service.py`):** Porta `AnimalRepositoryPort` e serviço `AnimalService` com `register_animal`, `attach_identifier`, `deactivate_identifier`, `get_animal` e `find_by_identifier` (com recusa de duplicidade de identificador oficial no tenant).
- **Infraestrutura (`packages/livestock_infrastructure/persistence/animal_repository.py`):** Repositório PostgreSQL `TransactionalAnimalRepository` sobre as tabelas `core_audit.animals` e `core_audit.animal_identifiers` com RLS por `OrganizationId`.
- **Migration (`packages/core_infrastructure/persistence/migrations/versions/20260723_0034_create_animals_tables.py`):** Migration Alembic 0034 criando `core_audit.animals` e `core_audit.animal_identifiers` com políticas RLS ativadas e forçadas.
- **Suíte de Testes:**
  - `tests/livestock_domain/test_animal_domain.py` (4 testes unitários)
  - `tests/livestock_application/test_animal_service.py` (2 testes de aplicação)
  - `tests/integration/test_animal_postgresql.py` (1 teste de integração RLS em PostgreSQL real)

### Evidências de execução e verificações
```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check packages tests
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
```
- **Resultado:** 480 testes aprovados em 14.20s; Alembic em `20260723_0035 (head)`; Ruff e Mypy 100% limpos sem erros.

---

## Passo 8.3 — AnimalMovement e PropertyStay

**Data de conclusão:** 23 de julho de 2026  
**Estado:** CONCLUÍDO E APROVADO

### O que foi entregue
- **Domínio (`packages/livestock_domain/movement.py`):**
  - Entidade `AnimalMovement`: **Fato e Evento de Domínio Autoritativo Imutável** com `origin_property_id`, `destination_property_id`, `movement_time`, `animal_ids`, `reason` e `evidence_reference`.
  - Entidade `PropertyStay`: **Projeção Temporal Reconstruível (Read Model / State)** que representa a permanência temporal contínua do animal em determinada fazenda (`start_time`, `end_time`, `status`).
  - Invariantes: recusa de movimentação com origem igual a destino, recusa de data futura, obrigatoriedade de pelo menos 1 animal, fechamento de permanências antigas e abertura de nova estada ativa no destino.
- **Aplicação (`packages/livestock_application/movement_service.py`):**
  - Portas `MovementRepositoryPort` e `PropertyStayRepositoryPort`.
  - Serviço `MovementService` com `register_movement`, `get_active_stay`, `get_stay_timeline` e `rebuild_stays_for_animal` (reconstrução determinística da linha do tempo a partir dos fatos autoritativos).
  - Provedor de Fatos `LivestockFactProvider` atualizado com localização e estada ativa do animal.
- **Infraestrutura (`packages/livestock_infrastructure/persistence/movement_repository.py`):** Repositórios `TransactionalAnimalMovementRepository` e `TransactionalPropertyStayRepository` em PostgreSQL operando sobre `core_audit.animal_movements`, `core_audit.animal_movement_items` e `core_audit.property_stays`.
- **Migration (`packages/core_infrastructure/persistence/migrations/versions/20260723_0036_create_movement_and_stay_tables.py`):** Migration Alembic 0036 criando as tabelas com suporte a RLS por `OrganizationId`.
- **Suíte de Testes:**
  - `tests/livestock_domain/test_movement_domain.py` (3 testes unitários)
  - `tests/livestock_application/test_movement_service.py` (1 teste de aplicação de timeline)
  - `tests/integration/test_movement_postgresql.py` (1 teste de integração RLS em PostgreSQL real)
- **Script de Validação Manual:** `scratch/validar_passo_8_3.py` (executado e aprovado com sucesso).

### Evidências de execução e verificações
```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check packages tests
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run python scratch/validar_passo_8_3.py
```
- **Resultado:** 485 testes aprovados em 11.08s; Alembic em `20260723_0036 (head)`; Ruff e Mypy 100% limpos sem erros; Validação manual executada com sucesso.

---

## Passo 8.4 — LivestockLot e LotMembership

**Data de conclusão:** 23 de julho de 2026  
**Estado:** CONCLUÍDO E APROVADO

### O que foi entregue
- **Domínio (`packages/livestock_domain/lot.py`):**
  - Entidade `LivestockLot`: Agregador que representa o grupo/lote com `lot_id`, `organization_id`, `property_id`, `code`, `name`, `lot_type` (`OPERATIONAL`, `SANITARY`, `COMMERCIAL`, `OTHER`) e `status`.
  - Entidade `LotMembership`: Associação temporal contínua entre animal e lote (`membership_id`, `lot_id`, `animal_id`, `valid_from`, `valid_until`, `reason`).
- **Aplicação (`packages/livestock_application/lot_service.py`):**
  - Portas `LivestockLotRepositoryPort` e `LotMembershipRepositoryPort`.
  - Serviço `LotService`: `create_lot()`, `add_animal_to_lot()` (com **Regra de Exclusividade Rígida para Lotes Operacionais/Manejo** e permissão de sobreposição para Lotes Sanitários/Comerciais), `remove_animal_from_lot()` e `get_lot_composition()` (composição temporal histórica).
- **Infraestrutura (`packages/livestock_infrastructure/persistence/lot_repository.py`):** Repositórios PostgreSQL `TransactionalLivestockLotRepository` e `TransactionalLotMembershipRepository` operando sobre `core_audit.livestock_lots` e `core_audit.lot_memberships`.
- **Migration (`packages/core_infrastructure/persistence/migrations/versions/20260723_0037_create_lots_tables.py`):** Migration Alembic 0037 criando as tabelas com RLS ativado e forçado por `OrganizationId`.
- **Suíte de Testes:**
  - `tests/livestock_domain/test_lot_domain.py` (2 testes unitários)
  - `tests/livestock_application/test_lot_service.py` (1 teste unitário da regra de exclusividade)
  - `tests/integration/test_lot_postgresql.py` (1 teste de integração RLS em PostgreSQL real)
- **Script de Validação Manual:** `scratch/validar_passo_8_4.py` (executado e aprovado com sucesso).

### Evidências de execução e verificações
```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check packages tests
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run python scratch/validar_passo_8_4.py
```
- **Resultado:** 489 testes aprovados em 11.62s; Alembic em `20260723_0037 (head)`; Ruff e Mypy 100% limpos sem erros; Validação manual executada com sucesso.

---

## Passo 8.5 — Veterinarian e Registro Profissional

**Data de conclusão:** 23 de julho de 2026  
**Estado:** CONCLUÍDO E APROVADO

### O que foi entregue
- **Domínio (`packages/livestock_domain/veterinarian.py`):**
  - Entidade `Veterinarian`: Representa o profissional veterinário com `veterinarian_id`, `organization_id`, `name`, `cpf` (validação de 11 dígitos), `council_number` (CRMV), `council_state` (UF de 2 letras), `verification_status` (`DECLARADO`, `DOCUMENTADO`, `VERIFICADO_EM_FONTE`, `INDETERMINADO`) e `evidence_reference`.
- **Aplicação (`packages/livestock_application/veterinarian_service.py`):**
  - Porta `VeterinarianRepositoryPort`.
  - Serviço `VeterinarianService`: `register_veterinarian()` (valida CPF e unicidade de CRMV na organização; inicia como `DECLARADO`), `attach_evidence()` (associa prova documental via módulo `Evidence` da ADR-0026 e eleva para `DOCUMENTADO`), `update_verification_status()` (permite promover para `VERIFICADO_EM_FONTE` ou marcar como `INDETERMINADO`).
- **Infraestrutura (`packages/livestock_infrastructure/persistence/veterinarian_repository.py`):** Repositório PostgreSQL `TransactionalVeterinarianRepository` operando sobre a tabela `core_audit.veterinarians` com RLS por `OrganizationId`.
- **Migration (`packages/core_infrastructure/persistence/migrations/versions/20260723_0038_create_veterinarians_table.py`):** Migration Alembic 0038 criando a tabela com RLS ativado e forçado.
- **Suíte de Testes:**
  - `tests/livestock_domain/test_veterinarian_domain.py` (2 testes unitários)
  - `tests/livestock_application/test_veterinarian_service.py` (1 teste unitário do fluxo de estados e unicidade de CRMV)
  - `tests/integration/test_veterinarian_postgresql.py` (1 teste de integração RLS em PostgreSQL real)
- **Script de Validação Manual:** `scratch/validar_passo_8_5.py` (executado e aprovado com sucesso).

### Evidências de execução e verificações
```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check packages tests
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run python scratch/validar_passo_8_5.py
```
- **Resultado:** 493 testes aprovados em 14.46s; Alembic em `20260723_0038 (head)`; Ruff e Mypy 100% limpos sem erros; Validação manual executada com sucesso.

---

## Passo 8.6 — Prova Integrada E2E da Vertical Titan Livestock (Encerramento do Marco 8)

**Data de conclusão:** 23 de julho de 2026  
**Estado:** CONCLUÍDO E APROVADO

### O que foi entregue
- **Teste de Integração E2E (`tests/integration/test_livestock_vertical_e2e.py`):**
  - Prova de integração completa de ponta a ponta em banco de dados PostgreSQL real conectando todas as primitivas da vertical Titan Livestock: `RuralProperty`, `Animal`, `AnimalIdentifier`, `Veterinarian`, `LivestockLot`, `LotMembership`, `AnimalMovement`, `PropertyStay` e `LivestockFactProvider`.
  - Verificação de isolamento tenant RLS entre diferentes `OrganizationId` em role PostgreSQL sem privilégios (`NOBYPASSRLS`).
- **Script de Validação Manual:** `scratch/validar_passo_8_6.py` (demonstração gráfica interativa da linha do tempo da vida do animal executada com sucesso completo).

### Evidências de execução e verificações
```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check packages tests
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run python scratch/validar_passo_8_6.py
```
- **Resultado:** 494 testes aprovados em 14.65s; Alembic em `20260723_0038 (head)`; Ruff e Mypy 100% limpos sem erros; Validação manual executada com sucesso.

> **MARCO 8 — TITAN LIVESTOCK OFICIALMENTE CONCLUÍDO E APROVADO COM 100% DE SUCESSO!**

---

## Passo 9.1 — Agregadores de Medicamentos e Prescrições

**Data de conclusão:** 23 de julho de 2026  
**Estado:** CONCLUÍDO E APROVADO

### O que foi entregue
- **Domínio (`packages/livestock_domain/medication.py` e `prescription.py`):**
  - Entidade `Medication`: Representa a bula do medicamento com `medication_id`, `organization_id`, `trade_name`, `active_ingredient`, `manufacturer`, `withdrawal_period_days` (carência em dias para abate) e `dosage_instruction`.
  - Entidade `Prescription`: Receita médica emitida pelo veterinário com `prescription_id`, `organization_id`, `veterinarian_id`, `medication_id`, `property_id`, `prescribed_date`, `dosage`, `administration_route`, `target_type` (`ANIMAL` ou `LOT`), `target_ids` e `reason`.
- **Aplicação (`packages/livestock_application/medication_service.py`):**
  - Portas `MedicationRepositoryPort` e `PrescriptionRepositoryPort`.
  - Serviço `MedicationService`: `register_medication()` (com recusa de nome comercial duplicado) e `issue_prescription()` (**com validação de que o veterinário possui status `DOCUMENTADO` ou `VERIFICADO_EM_FONTE`**, recusando prescrições de profissionais apenas `DECLARADO`).
- **Infraestrutura (`packages/livestock_infrastructure/persistence/medication_repository.py`):** Repositórios PostgreSQL `TransactionalMedicationRepository` e `TransactionalPrescriptionRepository` operando sobre `core_audit.medications`, `core_audit.prescriptions` e `core_audit.prescription_targets` com RLS por `OrganizationId`.
- **Migration (`packages/core_infrastructure/persistence/migrations/versions/20260723_0039_create_medication_and_prescription_tables.py`):** Migration Alembic 0039 criando as tabelas com RLS ativado e forçado.
- **Suíte de Testes:**
  - `tests/livestock_domain/test_medication_domain.py` (3 testes unitários)
  - `tests/livestock_application/test_medication_service.py` (1 teste unitário das regras de emissão de prescrição por status de veterinário)
  - `tests/integration/test_medication_postgresql.py` (1 teste de integração RLS em PostgreSQL real)
- **Script de Validação Manual:** `scratch/validar_passo_9_1.py` (executado e aprovado com sucesso).

### Evidências de execução e verificações
```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check packages tests
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run python scratch/validar_passo_9_1.py
```
- **Resultado:** 499 testes aprovados em 12.39s; Alembic em `20260723_0039 (head)`; Ruff e Mypy 100% limpos sem erros; Validação manual executada com sucesso.
- **Ressalva:** o `scratch/validar_passo_9_1.py` foi posteriormente removido do versionamento (scripts descartáveis passaram a ser ignorados pelo `.gitignore`). Além disso, este agregado recebeu depois a correção do contrato temporal (ver seção "Correção — contrato temporal da vertical").

## Correção — contrato temporal da vertical (commit `3846478`)

**Estado:** CONCLUÍDO. Revisão de corretude do Livestock já commitado (Marcos 8 e 9.1) que encontrou três problemas sistêmicos que o portão verde não pegava, todos corrigidos:

1. **datetime naive tratado silenciosamente como UTC** — os agregados coagiam `x.replace(tzinfo=UTC)` em vez de rejeitar; um horário local (ex.: UTC-3) virava UTC errado por 3 horas, sem erro. Corrigido: `require_utc` em todo campo datetime dos 7 agregados **rejeita** naive.
2. **`created_at = datetime.now(UTC)` como default de campo** — avaliado uma vez na carga do módulo (instância única de import) em 11 campos. Corrigido para `field(default_factory=lambda: datetime.now(UTC))`.
3. **Domínio lendo o relógio** — a checagem "movimento não pode ser no futuro" saiu do `__post_init__` para o `MovementService`. O domínio ficou determinístico.

**Evidência:** testes novos travando a rejeição de naive (domínio e serviço) e a checagem de futuro no serviço. 503 testes aprovados após a correção.

## Passo 9.1 (complemento) — MedicationBatch (commit `173b3a8`)

**Data de conclusão:** 23 de julho de 2026 · **Estado:** CONCLUÍDO. Preenche o `MedicationBatch` que o PLANO-9.1 previa e a entrega original omitiu.

### O que foi entregue
- **Domínio (`packages/livestock_domain/medication.py`):** `MedicationBatch` imutável — `batch_id`, `organization_id`, `medication_id`, `batch_number`, `expiry_date`, `manufacturing_date` opcional. Recusa validade inválida (`expiry_date <= manufacturing_date`) e número vazio; `require_utc` nas datas.
- **Aplicação (`medication_service.py`):** `MedicationBatchRepositoryPort` e `MedicationBatchService.register_batch` — recusa duplicidade `(org, medicamento, número)` e medicamento inexistente.
- **Infraestrutura + migration:** tabela `core_audit.medication_batches` com RLS+FORCE, FKs para organização e medicamento, `UNIQUE` de duplicidade; migration `20260723_0040`, registrada no `env.py`.
- **Testes:** 4 de domínio (inclui rejeição de naive), 3 de aplicação, 1 de integração com RLS.

## Passo 9.2 — VeterinaryPrescription

**Estado:** CONCLUÍDO. Entregue dentro da seção "Passo 9.1 — Agregadores de Medicamentos e Prescrições" acima (entidade `Prescription`, `issue_prescription()` com validação do status do veterinário, tabelas `prescriptions`/`prescription_targets` com RLS). Registrado aqui separadamente para alinhar à numeração do PLANO.

## Passo 9.3 — TreatmentApplication (commit `d04b7c1`)

**Data de conclusão:** 23 de julho de 2026 · **Estado:** CONCLUÍDO.

### O que foi entregue
- **Domínio (`packages/livestock_domain/treatment.py`):** `TreatmentApplication` imutável (append-only) — animal, lote (`medication_batch_id`), ator, `applied_at`, evidências, `prescription_id` opcional e `corrects_application_id` para a correção. `require_utc` no `applied_at`; recusa autocorreção.
- **Aplicação (`treatment_service.py`):** `TreatmentApplicationService` com **`register` + `correct`** e **nenhum método de edição**. A correção cria um novo registro que aponta para o original, que permanece imutável.
- **Infraestrutura + migration:** tabela `core_audit.treatment_applications` com RLS+FORCE, FKs (inclusive auto-FK de correção), índices por animal e por lote (base do recall); migration `20260723_0041`.
- **Evento:** `TreatmentAppliedEvent` declarado em `events.py`.
- **Testes:** domínio (imutabilidade, naive, entity_types, autocorreção), aplicação (**cenário do plano: edição recusada → correção por novo registro, original preservado**), integração com RLS + rastreabilidade por lote.
- **Validação manual (plano):** "registrar aplicação, tentar edição e confirmar correção por novo evento" — coberto por teste (`test_correction_creates_new_record_preserving_original`).

## Passo 9.4 — WithdrawalPeriod (commit `6600c10`)

**Data de conclusão:** 23 de julho de 2026 · **Estado:** CONCLUÍDO. **Portão do plano cumprido:** regra de negócio `titan-livestock-withdrawal-v1` proposta e **aprovada pelo responsável** antes da implementação.

### O que foi entregue
- **Regra aprovada:** por aplicação `withdrawal_ends_at = applied_at + withdrawal_period_days` (dias corridos, UTC); por animal a carência termina no **maior** prazo entre as aplicações efetivas; elegível quando `instante >= eligible_from`. O cálculo **congela (snapshot)** o prazo usado e a versão da regra.
- **Domínio (`packages/livestock_domain/withdrawal.py`):** `compute_withdrawal_ends`, `WithdrawalContribution` (prazo congelado + verificação de consistência), `AnimalWithdrawalStatus` (agrega, responde elegibilidade), `WITHDRAWAL_RULE_VERSION`.
- **Aplicação (`withdrawal_service.py`):** `WithdrawalCalculator.assess_animal` — resolve lote→medicamento, faz o snapshot do prazo e **descarta aplicações corrigidas** (conta a correção, não o original).
- **Sem migration:** é cálculo, não estado persistido.
- **Testes:** 10, cobrindo os casos de borda que o plano pede — **timezone** (naive rejeitado), **zero dias**, **sem tratamento** (sempre elegível), **múltiplas aplicações** (maior prazo), **correção** (supersessão).
- **Validação manual (plano):** "conferir datas-limite, timezone e casos de borda; confirmar preservação da versão da regra" — coberto por teste.

## Passo 9.5 — Regra de elegibilidade farmacológica (commit `4c7bf7e`)

**Data de conclusão:** 23 de julho de 2026 · **Estado:** CONCLUÍDO.

### O que foi entregue
- **Fato de carência:** `LivestockFactProvider` passa a emitir o fato `livestock.withdrawal` para um animal (`in_withdrawal`, `eligible_from`, `rule_version`, `blocking_batches`), computado pelo cálculo do 9.4.
- **Regra bloqueante + política (`eligibility.py`):** `build_eligibility_rule` (condição `in_withdrawal == False`, severidade **BLOCKING**, ação corretiva) e `build_eligibility_policy` (publicada). `PharmacologicalEligibilityService.evaluate_animal` delega Evaluation/Decision ao Core.
- **Sem domínio/tabela novos:** reusa a maquinária Policy/Rule/Evaluation/Decision do Core.
- **Testes:** animal em carência → **REJEITADA**; fora → **APROVADA**; sem tratamento → **APROVADA**.
- **Validação manual (plano):** "avaliar animal fora e dentro da carência; confirmar motivo, evidência, versão e sujeito afetado" — coberto por teste (motivo em `decision.reasons`; evidência em `blocking_batches` + snapshot; versão `titan-livestock-withdrawal-v1`; sujeito `decision.subject_id`).

## Passo 9.6 — Avaliação de lote e reavaliação (commit `fa26a18`)

**Data de conclusão:** 23 de julho de 2026 · **Estado:** CONCLUÍDO. **Fecha o Marco 9.**

### O que foi entregue
- **Fato de lote:** `LivestockFactProvider` emite `livestock.lot_eligibility` para um `livestock_lot` (`has_animal_in_withdrawal`, `blocking_animals`, `member_count`), avaliando os membros ativos no instante.
- **Regra de lote + serviço:** `build_lot_eligibility_rule` (BLOCKING: qualquer membro em carência reprova) e `PharmacologicalEligibilityService.evaluate_lot`.
- **Testes:** cenário ponta a ponta do plano — **`REJECTED → remoção do animal em carência → APPROVED`**, com ambas as decisões preservadas e **hashes de snapshot distintos**.
- **Dois defeitos reais corrigidos no caminho:**
  1. **Snapshots da vertical sem hash de integridade** — o `LivestockFactProvider` usava o construtor direto de `FactSnapshot` (hash vazio) em vez de `.create()`. Corrigido; agora todo snapshot da vertical é hashável.
  2. **`remove_animal_from_lot` quebrava no mesmo tick de clock** — no Windows o `datetime.now()` tem resolução grosseira; adicionar e remover rápido fazia `valid_until == valid_from` e a membership recusava, flakando o CI. Corrigido garantindo `valid_until` estritamente posterior.
- **Validação manual (plano):** "executar ponta a ponta o cenário `REJECTED → remoção → APPROVED` e comparar snapshots/hashes" — coberto por teste.

## Comandos para testar o Marco 9 completo

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked alembic upgrade head
python -m uv run --locked pytest
python -m uv run --locked ruff check .
python -m uv run --locked ruff format --check .
python -m uv run --locked mypy
python -m uv run --locked alembic check
```

Resultado esperado: 535 testes aprovados; banco em `20260723_0041 (head)`; Alembic, Ruff e Mypy aprovados sem erros.



















## Passo 10.1a — Emissão de eventos da vertical (commit `568a8bb`)

**Data de conclusão:** 24 de julho de 2026 · **Estado:** IMPLEMENTADO (validação manual pendente). **Abre o Marco 10.**

**Por que este passo existe.** O PLANO define o Passo 10.1 como "consulta cronológica reconstruída a partir dos eventos". Ao levantar o terreno descobriu-se que **a vertical não emitia evento nenhum**: as 13 subclasses de `DomainEvent` declaradas em `livestock_domain/events.py` nunca eram construídas — e não poderiam ser, porque o repositório do Core grava apenas `event_type` e os bytes canônicos do payload, de modo que campos de subclasse não teriam coluna e se perderiam na gravação. Uma linha do tempo lida do log encontraria a tabela vazia. O 10.1 foi então dividido, com aprovação do responsável: **10.1a** faz a vertical emitir; **10.1b** monta a timeline.

### O que foi entregue
- **Contrato de eventos (`packages/livestock_domain/events.py`, reescrito):** 14 constantes de `event_type` namespaced em `livestock.` e um construtor de `CanonicalPayload` por evento, no padrão que o próprio Core usa em `core_domain/corrections.py`. O 14º evento é o **`livestock.medication_batch_registered`**, que faltava desde o 9.1. O nome do schema do payload deriva do `event_type`, para os dois nunca divergirem.
- **Gravador (`packages/livestock_application/event_recorder.py`, novo):** `LivestockOperationContext` (organização, `actor_reference`, `source_reference`, `correlation_id`) e `LivestockEventRecorder`, que consulta a versão corrente no log do Core, monta o `DomainEvent` e delega o append. Recusa `event_type` não declarado, para o log não receber tipo improvisado.
- **Os 8 serviços da vertical emitem:** propriedade, animal (cadastro, marcação, desativação), veterinário (cadastro e promoções), medicamento, lote de medicamento, prescrição, movimentação, lote pecuário (criação, entrada, saída) e tratamento (registro e correção). Todo método de escrita troca `organization_id` solto por `context`.
- **Avaliações persistidas no Core:** `PharmacologicalEligibilityService` grava `Evaluation` e `Decision` nas tabelas do Core (avaliação antes da decisão, porque a decisão a referencia). Sem isso o bloqueio e a reavaliação do Marco 9 existiriam só durante a chamada.
- **Guarda de organização nos serviços:** operar entidade de outra Organization agora é recusado antes de gravar, e não depois.

### Decisões que valem para o resto do Marco 10
- **O agregado do evento é a entidade criada ou alterada.** Movimentar dez animais é **um** evento no fluxo do `animal_movement`, não dez; entrada e saída de lote pertencem ao `livestock_lot`. Um fato gravado duas vezes deixa de ser um fato — a timeline reúne os fluxos das entidades relacionadas.
- **A carência (9.4) NÃO virou evento.** É derivação pura de aplicações efetivas mais o prazo do medicamento; gravá-la criaria uma segunda fonte de verdade capaz de divergir do cálculo.
- **A autoria do tratamento vem do contexto.** O parâmetro `actor_id` foi removido de `register_application`/`correct_application`: com ele, o autor do registro e o do evento podiam divergir.
- **Sem ADR.** Não há decisão arquitetural nova — a vertical usar a porta do Core já é o desenho vigente (ADR-0001), e o esquema de versão por agregado e cadeia de hash é imposto pelo Core.

### Dois defeitos reais corrigidos na revisão
1. **A marcação inicial vinha datada antes do próprio cadastro.** O `AnimalService` lia o relógio duas vezes, então o evento `identifier_attached` ficava com `occurred_at` anterior ao `animal_registered`, e uma timeline ordenada por esse campo mostraria o brinco sendo posto antes de o animal existir. O relógio do Windows tem resolução grosseira (~20 instantes distintos em 20 mil leituras) e escondia o defeito em 199 de 200 execuções — em Linux, com microssegundos, inverteria sempre. Corrigido com um instante único para os dois fatos; empatados, a ordem fica por `aggregate_version`, que não depende do relógio.
2. **Reafirmar o status de um veterinário gravava evento vazio.** `update_verification_status` com o status já vigente escrevia `DOCUMENTADO → DOCUMENTADO` num log append-only, permanente e sem informação. Agora só grava quando o status muda de fato.

### Limitações registradas, a tratar no 10.1b ou depois
- **A correção de tratamento liga-se ao original por `corrects_application_id` no payload, não por `causation_id`.** A porta `DomainEventLog` expõe apenas `append` e `list_versions`, então o serviço não tem como descobrir o `event_id` do evento original. Usar `causation_id` de verdade exigiria ampliar a porta do Core.
- **Mudança só de evidência do veterinário não gera evento**, consequência da correção 2: não existe um `evidence_attached` declarado.
- **`attach_evidence` rebaixa veterinário já verificado** — força `DOCUMENTADO` sem olhar o status atual. Comportamento herdado do Marco 8; agora o rebaixamento fica registrado no log. Não alterado por mudar regra de negócio.
- **A gravação da entidade e a do evento não são atômicas por si.** Nos testes de integração as duas caem na mesma transação da conexão; em produção isso depende de a raiz de composição manter a mesma unidade de trabalho, o que deve ser amarrado no Passo 10.4.

### Testes
- **Contrato (`tests/livestock_domain/test_events_contract.py`):** congela os 14 `event_type`, exige o prefixo e o padrão canônico do Core, e verifica que o schema do payload deriva do tipo e que o payload é determinístico.
- **Gravador (`tests/livestock_application/test_event_recorder.py`):** versão por agregado (não global), separação entre instante do fato e instante do registro, recusa de tipo não declarado, correlação compartilhada e recusa de ator de outra Organization.
- **Por serviço:** cada operação gera exatamente os eventos esperados, no fluxo certo; **operação recusada não deixa evento no log**; CPF do veterinário fica fora do payload; correção de tratamento cria fluxo próprio com o vínculo no payload.
- **Integração (`test_livestock_vertical_e2e.py`):** liga o `DomainEventRepository` real e prova, contra o PostgreSQL, os fluxos por agregado na ordem certa, a **cadeia de hash do Core aplicada aos eventos da vertical** (`previous_hash` nulo no primeiro, encadeado nos seguintes) e autoria e correlação atravessando o fluxo inteiro. Os sete testes de RLS por tabela seguem com log em memória, por serem sobre o RLS das tabelas da vertical.

### Portão de verificação
`568 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (335 arquivos) e `alembic check` sem erros. Sem migration: nenhuma tabela nova — os eventos vão para o `core_audit.domain_events` do Core.

**Atenção ao rodar:** `TITAN_DATABASE_URL` é **obrigatória**, não opcional. Sem ela, `tests/integration/conftest.py` pula a suíte de integração inteira e o `alembic check` falha; o resultado parece verde (`N passed, 50 skipped`) sem ter provado nada. **Conferir `skipped == 0`.**

### Validação manual pendente (a cargo do responsável)
Consultar o log de um animal, de um lote e de um tratamento e confirmar ordem, correções, autoria e evidências — a mesma validação que o PLANO pede para o 10.1, verificável em parte já agora e por completo com a timeline do 10.1b.

## Passo 10.1b — Timeline Livestock

**Data de conclusão:** 24 de julho de 2026 · **Estado:** IMPLEMENTADO (validação manual pendente). **Fecha o Passo 10.1 do PLANO**, junto com o 10.1a.

### O que foi entregue
- **`packages/livestock_application/timeline_service.py` (novo):** `LivestockTimelineService` com três consultas — `animal_timeline`, `lot_timeline` e `treatment_timeline`, exatamente os três sujeitos que a validação manual do PLANO pede.
- **Porta de leitura no Core (`core_application/event_log.py`):** `DomainEventReader` e `RecordedEvent`. A porta existente só sabia escrever (`append`) e contar versões; ler um fluxo exigia a Infrastructure, que a Application não pode conhecer. `RecordedEvent` descreve o registro **por estrutura**, em propriedades somente-leitura, e o `DomainEventRepository` o satisfaz sem que nada precise mudar nele — a mesma solução que `ProvenanceService` já usava, aqui tipada em vez de `Any`.
- **Consulta histórica de vínculos (`lot_repository.py` + porta):** `list_memberships_for_animal`. O método existente filtra `valid_until IS NULL` e serve à regra de exclusividade; uma linha do tempo montada com ele mostraria só o lote atual e perderia todos os anteriores.
- **Corte bitemporal (`TimelineCutoff`):** dois eixos independentes, porque o Titan separa quando o fato ocorreu de quando foi registrado e as perguntas são diferentes — `occurred_until` responde "o que aconteceu até tal data"; `known_until` responde "o que o Titan sabia em tal data", que é a pergunta de auditoria. Um tratamento lançado com atraso não aparece numa reconstrução do que se sabia antes de ele ser lançado. Instante naive é recusado.

### Decisões
- **A ordem é uma chave total, não só `occurred_at`.** A chave é `(occurred_at, tipo do agregado, id do agregado, origem, sequência, id da origem)`. Ordenar apenas por instante deixaria empates resolvidos pela ordem em que o banco devolveu as linhas — duas leituras da mesma história seriam parecidas, não idênticas. Mesmo princípio do Passo 7.2.
- **Os repositórios da vertical dizem QUAIS fluxos pertencem ao sujeito; quem diz O QUE aconteceu é o evento.** Nenhum campo de estado atual entra na linha do tempo.
- **A correção não reordena nada: ela marca.** O registro corrigido permanece na sua posição cronológica com `superseded_by` apontando para quem o corrigiu. Reordenar para "correção sempre depois" mentiria sobre quando o fato ocorreu; omitir o corrigido apagaria o passado. O vínculo é lido do campo tipado da aplicação, não do payload — o payload diria o mesmo, mas exigiria desserializar bytes canônicos.
- **`Evaluation` e `Decision` entram como entradas próprias.** Não são eventos de domínio, mas são registros imutáveis do Core, e sem eles o bloqueio por carência e a reavaliação — o coração do Marco 9 — não apareceriam na história. A fronteira está nomeada no cabeçalho do módulo para não virar precedente frouxo.

### Testes
- **Unitários (`tests/livestock_application/test_timeline_service.py`, 12):** reunião dos fluxos que tocaram o animal e exclusão do que não é história dele; **ordem idêntica entre duas leituras**; cadastro nunca depois do que o seguiu; entrada de lote preservada após a remoção que a encerrou; correção marca o original sem removê-lo; cadeia de correção e lote de medicamento na história do tratamento; os dois eixos de corte; recusa de instante naive; isolamento por Organization.
- **Integração (`test_livestock_vertical_e2e.py`):** a mesma timeline montada sobre o `DomainEventRepository` real, contra o PostgreSQL — reunião dos fluxos, ordem reproduzível, corte devolvendo um prefixo exato da leitura completa, e outra Organization enxergando história vazia.

### Portão de verificação
`580 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (337 arquivos) e `alembic check` sem erros. Sem migration: a consulta é leitura.

### Limitação herdada, agora sem efeito prático
O vínculo de correção viaja em `corrects_application_id` no payload e não em `causation_id`, porque a porta do log não permite descobrir o `event_id` do evento original. A timeline contorna lendo o campo tipado do registro, então **a limitação não afeta a leitura**; ampliar a porta do Core continua sendo opção, não necessidade.

### Validação manual pendente (a cargo do responsável)
Consultar animal, lote e tratamento e confirmar ordem, correções, autoria e evidências — a validação que o PLANO define para o Passo 10.1.

## Passo 10.2 — Dossiê JSON da decisão farmacológica

**Data de conclusão:** 24 de julho de 2026 · **Estado:** IMPLEMENTADO (validação manual pendente).

**Divisão adotada, com aprovação do responsável:** o 10.2 foi dividido porque as evidências da vertical eram texto livre, e um dossiê que citasse `evidence:foto-1` cumpriria a forma da entrega sem cumprir o fundo — a validação manual do PLANO exige entender a decisão, com suas evidências, sem acesso ao banco.

### 10.2a — Evidência tipada na vertical (commit `60f3572`) · CONCLUÍDO

- **Domínio:** `TreatmentApplication.evidence_references` passou de `tuple[str, ...]` para `tuple[UniversalReference, ...]` apontando para `Evidence` do Core, na convenção que `Decision` e `NonConformity` já usavam. Recusa texto livre, referência que não seja `evidence` e evidência de outra Organization.
- **Campo novo `evidence_notes`:** as strings antigas nunca foram evidência — eram anotação de operador. Separar as duas impede que anotação seja apresentada como prova, e preserva informação operacional útil.
- **Serviço:** porta `EvidenceLookupPort`. Citar evidência inexistente é recusado (dossiê que aponta para o nada é prova vazia), e o serviço recusa aceitar referência sem ter como conferi-la, em vez de confiar no chamador.
- **Segurança:** evidência de outra Organization é recusada com a **mesma** mensagem de "não encontrada". Mensagem distinta viraria oráculo — bastaria tentar identificadores para descobrir o que outra organização possui. Mesmo princípio do `OrganizationContextDenied`.
- **Migration `20260724_0042`, sem perda:** havia 28 linhas com valores. A subida copia para `evidence_notes` antes de esvaziar; a descida devolve antes de remover a coluna. Ambos os sentidos foram executados e conferidos.

### 10.2b — Template do dossiê · CONCLUÍDO

**Fundação:**

- **O fato de carência mostra a conta, não só o resultado.** O payload de `livestock.withdrawal` passou a carregar `contributions`, com aplicação, lote, instante da aplicação, prazo congelado e fim calculado de cada contribuição. Duas consequências: quem tem o fato refaz o cálculo, e o dossiê consegue percorrer fato → aplicação → evidência, cadeia que o 10.2a tornou possível.
- **Seção de vertical no documento do Core** (`VerticalSection`, documento versão 3). Sob a chave única `vertical`, com `namespace`, `section_version` própria e `content`. O Core valida **apenas o envelope** — namespace canônico, versão inteira positiva, conteúdo não vazio — e não interpreta o conteúdo, porque conhecer vertical lhe é proibido. Ausência é declarada (`null`), não omitida. Há teste de que nenhum campo da vertical vaza para o nível do Core e de que a versão da seção é independente da versão do documento.

**Template (`livestock_application/dossier_template.py`):** `LivestockDossierTemplate` monta a seção `livestock` com quatro blocos.

- **`subject`** — identidade que um fiscal usa: brinco e SISBOV, lidos do fato `livestock.animal` **dentro do snapshot**, não do cadastro atual. O snapshot está congelado no instante da avaliação; o cadastro não. O campo `identity_source` declara essa origem.
- **`withdrawal`** — a conta da carência, com o prazo congelado de cada contribuição.
- **`evidence_chain`** — contribuição → aplicação → evidências, com hash de conteúdo e proveniência copiados. As anotações de operador viajam em campo separado, identificadas como tal: informação útil que não é prova.
- **`timeline`** — a linha do tempo completa do animal (decisão do responsável: inteira por padrão), cortada em `known_until` = instante da decisão.

**Por que o bloco `evidences` do Core fica vazio neste dossiê.** Aquele bloco é alimentado por `Fact.source_reference`, que é **singular** — serve ao fato que veio de um documento. A carência não vem de um documento: vem de um cálculo sobre N aplicações, cada uma com suas evidências. Declarar uma fonte única seria escolher arbitrariamente uma delas. `source_reference` fica nulo, que é a resposta honesta, e a cadeia completa viaja na seção da vertical. Para não haver dois formatos de evidência no mesmo documento, a serialização do conteúdo foi extraída para `evidence_content`, função pública do Core que a vertical reusa.

**Testes (10):** o dossiê é serializado, reconstruído e **verifica-se sem o Titan**; o animal é identificável pelo brinco; a decisão mostra a aritmética; a cadeia alcança a evidência com hash de 64 caracteres; anotação não se passa por prova; a timeline chega inteira até a decisão; **nada registrado depois da decisão entra na prova** — e um tratamento lançado depois aparece no dossiê novo sem invalidar o antigo, que continua conferindo.

### Correção no Core que este passo exigiu (commit `0a00128`, mesclado pelo PR #6)

O `DossierService` declarava copiar conteúdo e nunca apenas referenciar, mas o bloco `evidences` emitia só `{entity_type, id, contract_version}`. Cada entrada passou a poder carregar hash SHA-256, fonte, nível de confiança, validade, verificações e **revogação** — apresentar evidência revogada como válida transformaria o dossiê em prova falsa. Mudança aditiva, com teste de que dossiê da versão 1 continua verificando e não recebe campo novo retroativamente.

## Passo 10.3 — Dossiê PDF

**Data de conclusão:** 24 de julho de 2026 · **Estado:** IMPLEMENTADO (validação manual pendente).

### O que foi entregue

- **Porta `VerticalPdfTemplate` e `PdfSection` (`core_application/dossier_pdf_template.py`):** o PLANO exige template **fornecido pela vertical**, e o Core não pode conhecer vertical alguma. A porta troca **dados** — título, colunas e linhas de texto — e não objetos de renderização. A vertical não importa biblioteca de PDF; quem desenha é a Infrastructure do Core.
- **`SoftwareDossierPdfAdapter` recebe os templates de quem compõe a aplicação** e casa o namespace da seção com o do template. **Seção sem template não é descartada em silêncio:** o PDF declara que ela existe, não foi apresentada, e manda consultar o JSON.
- **`LivestockPdfTemplate` (`livestock_infrastructure/dossier_pdf_template.py`):** identificação do animal com brinco e SISBOV primeiro; carência com a aritmética visível (aplicação, prazo aplicado, fim calculado); uma seção de evidências por aplicação, com hash SHA-256 do conteúdo e **revogação em destaque**; e a linha do tempo.
- **Bloco "Como verificar este documento"** no PDF: procedimento em quatro passos para recalcular o hash canônico, com a regra de precedência escrita — havendo divergência entre JSON e PDF, **o JSON prevalece**.

### Decisões

- **Fidelidade antes de brevidade.** A linha do tempo é impressa inteira. Um PDF que resumisse o histórico deixaria de ser representação fiel do snapshot e passaria a ser uma opinião sobre ele. Para animal com histórico longo isso gera muitas páginas; reduzir é decisão de produto, e custa a palavra "fiel" que o PLANO usa.
- **Anotação de operador aparece marcada `NÃO É PROVA`.** No JSON a separação é estrutural; no papel precisava ser visível, senão alguém lê a anotação como evidência.

### Testes (8)

Todo valor impresso vem do JSON; a aritmética da carência é legível na folha; a anotação sai marcada como não sendo prova; **a linha do tempo é impressa inteira, sem resumo**; o PDF é produzido e carrega o material de verificação; seção sem template é declarada e não descartada; documento sem seção de vertical não imprime nada a mais; e linha que não cabe nas colunas é recusada, porque tabela desalinhada no papel vira dado trocado de coluna.

### Portão de verificação

`618 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (344 arquivos) e `alembic check` sem erros.

### Validação manual pendente

Comparar JSON e PDF campo a campo, verificar legibilidade e recalcular a integridade usando o procedimento impresso.

## Passo 10.4 — API mínima do fluxo aprovado

**Data de conclusão:** 24 de julho de 2026 · **Estado:** CONCLUÍDO. 10.4a e 10.4b implementados e **validados manualmente**. **Fecha o Passo 10.4.**

**Divisão adotada, com aprovação do responsável.** O 10.4 exige autenticação, autorização, teste positivo e negativo, tratamento de erro e validação com dois papéis e duas Organizations. A fundação não é detalhe de implementação: é pré-condição de todo endpoint. Separá-la isola um risco arquitetural transversal da simples exposição dos casos de uso — e se a raiz de composição estiver errada, todo endpoint construído sobre ela teria de ser refeito.

**Portão declarado:** nenhum outro endpoint da vertical é implementado enquanto a prova ponta a ponta do 10.4a não estiver aprovada.

### Decisões congeladas para o 10.4b

**Sete endpoints**, não seis — a contagem anterior tratava medicamento e lote como um só:

```
POST /v1/livestock/animals
POST /v1/livestock/medications
POST /v1/livestock/medication-batches
POST /v1/livestock/treatments
POST /v1/livestock/animals/{id}/eligibility
GET  /v1/livestock/animals/{id}/timeline
GET  /v1/livestock/dossiers/{id}
```

**`VeterinaryPrescription` NÃO integra a API mínima do Marco 10.** A capacidade de domínio existe e continua existindo, mas `prescription_id` é opcional em `TreatmentApplication` e **nenhuma regra do cenário aprovado depende de prescrição** — a regra bloqueante do 9.5 consulta o fato `livestock.withdrawal`. Expor `POST /prescriptions` agora seria endpoint que grava algo que nenhuma regra consulta, violando o critério de "estritamente necessários". A exposição depende da definição futura dos casos em que a prescrição será obrigatória, conforme a NR-4 — e então nascerão juntos regra de domínio, validação, fato, permissão, endpoint e testes.

**O dossiê é consequência da decisão, não criação manual.** `POST /animals/{id}/eligibility` executa fatos → avaliação → decisão → dossiê e devolve os identificadores. Não existe `POST /dossiers`: o operador não deveria ficar criando prova à mão.

**Permissões e papéis:**

| Papel | Permissões |
|---|---|
| `OPERADOR_PECUARIO` | `LIVESTOCK_ANIMAL.CRIAR`, `LIVESTOCK_MEDICATION.CRIAR`, `LIVESTOCK_TREATMENT.REGISTRAR`, `LIVESTOCK_ELIGIBILITY.EXECUTAR` |
| `AUDITOR` | `LIVESTOCK_TIMELINE.LER`, `DOSSIER.LER` |

`LIVESTOCK_ELIGIBILITY.EXECUTAR` é **uma** permissão de caso de uso, e não `AVALIAR` mais `EMITIR`. Internamente `Evaluation` e `Decision` são conceitos distintos; externamente, "executar elegibilidade" é uma capacidade de negócio única. Granularidade de permissão deve acompanhar necessidade real de separação de autoridade, não a quantidade de classes internas envolvidas — e hoje não há dois atores para as duas etapas.

O auditor não recebe **nenhuma** permissão de escrita. É o que torna o teste negativo inequívoco.

### 10.4a — Fundação HTTP da vertical · CONCLUÍDO

**Data:** 24 de julho de 2026. **Estado: CONCLUÍDO — validação manual aprovada.**

- **Raiz de composição (`apps/api/livestock_dependencies.py`):** conexão e **uma transação por requisição** — registro e evento nascem juntos ou não nascem; contexto organizacional resolvido a partir do cabeçalho `X-Titan-Organization-Id`; **RLS armado dentro da transação** com `set_config(..., true)`, para o isolamento acompanhar a unidade de trabalho e não sobrar para a próxima conexão do pool.
- **`require_permission(código)`, nunca papel.** A cadeia é `User → Membership → Role → Permission → Endpoint`. Uma rota que perguntasse "é OPERADOR_PECUARIO?" congelaria a organização de papéis dentro do código HTTP; perguntando pela permissão, papéis novos entram sem tocar em rota alguma.
- **Problem Details (`apps/api/problem.py`)** com `reason_code` estável, e a distinção mantida explícita: **401** — não sei quem você é; **403** — sei quem você é, e você não pode. Erro não previsto vira **500 sanitizado**, sem vazar nada do que aconteceu por dentro.
- **Endpoint-prova `POST /v1/livestock/animals`**, escolhido por ser simples o bastante para provar o encanamento sem envolver motor de regras, avaliação, decisão ou dossiê.
- **Superfície pública atualizada conscientemente.** As rotas de domínio do **Core** seguem fechadas: a API do Marco 10 é da vertical, e expor `/v1/decisions` ou `/v1/evidences` seria decisão à parte.

### Defesa em profundidade encontrada e corrigida no Core

O teste de isolamento falhou primeiro com **201 em vez de 403**: o operador da Org A criou animal na Org B.

A causa era o ambiente — o usuário `titan` do PostgreSQL é superusuário e **ignora RLS**. Mas isso expôs uma fragilidade real: `OrganizationContextService` consultava vínculos **confiando inteiramente no RLS** para filtrar por Organization, sem conferir se o vínculo devolvido pertencia à organização pedida. Uma conexão com role privilegiado — superusuário, engano de configuração, migração malfeita — derrubaria o isolamento **em silêncio**.

A ADR-0003 se chama "RLS **e defesa em profundidade**", e a segunda camada não existia. Foi acrescentada a conferência explícita `membership.organization_id == requested_organization_id`, com teste que usa um leitor deliberadamente permissivo para simular a ausência de RLS.

Além disso, as requisições da API no teste de integração passaram a rodar sob role `NOBYPASSRLS` criado por teste: sem isso, a prova de isolamento não valeria nada.

### Validação manual do 10.4a — APROVADA em 24 de julho de 2026

Os sete cenários foram operados pelo Swagger, com dois papéis e duas Organizations, contra o Keycloak e o PostgreSQL locais. Todos responderam o esperado.

**Ela encontrou cinco defeitos que os testes automatizados não pegaram.** Vale registrar quais, porque explicam por que o portão de validação manual existe:

1. **`reason_code` genérico no 401.** O handler devolvia `ERRO_HTTP`, e não havia como o cliente distinguir credencial ausente de qualquer outra falha HTTP. Corrigido com códigos por status conhecido (401, 403, 405, 409). O teste anterior afirmava apenas `status_code == 401` e passava com o corpo errado — passou a verificar código, mensagem, `www-authenticate` e content-type.
2. **Segurança ausente no OpenAPI.** A autenticação era ligada por `dependency_overrides`, e override **não entra no esquema**: o endpoint não declarava segurança, e o Swagger não anexava o token do botão Authorize. Fiação de produção por override é erro de desenho — a autenticação foi extraída para `apps/api/authentication.py`, de onde o `main` e a raiz de composição da vertical dependem da mesma dependência declarada.
3. **Configuração ausente reportada como credencial inválida.** Sem `TITAN_OIDC_ISSUER` e `TITAN_OIDC_AUDIENCE`, a API respondia 401 "Access Token ausente ou inválido" — mentira que manda o integrador caçar o defeito no lado errado. Agora responde 500 `AUTENTICACAO_NAO_CONFIGURADA`.
4. **Consulta de vínculos sem filtro por Organization.** `list_valid_for_user` filtrava por usuário, status e validade, e dependia **inteiramente do RLS** para o resto. Com a API rodando como superusuário — que ignora RLS — a consulta devolvia os vínculos de todas as Organizations, e a regra "exatamente um vínculo" negava acesso legítimo. A Organization passou a ser parâmetro obrigatório e filtro explícito na cláusula `WHERE`.
5. **Ruído no roteiro impresso** pela ferramenta de semeadura, e falha de codificação no console do Windows (cp1252 recusa `→`), que fazia a semeadura funcionar e o resultado se perder.

Os itens 3 e 4 são **defesa em profundidade** (ADR-0003), e somam-se à conferência acrescentada ao `OrganizationContextService` durante a implementação. Nenhuma das três foi pega pelos testes automatizados, porque todos rodam sob RLS efetivo; foi a validação com superusuário que as expôs.

### Ferramenta de semeadura (`apps/seed/`)

Escrita para destravar esta validação, e reusável em toda validação seguinte — é o começo do Passo 10.6, antecipado. Cria os usuários no Keycloak pela API de administração, monta as duas Organizations, os dois papéis com suas permissões, os vínculos e uma propriedade, e imprime o roteiro com os sete cenários e o corpo JSON pronto.

Usa apenas a biblioteca padrão: acrescentar dependência HTTP de produção por causa de uma ferramenta de desenvolvimento seria caro pelo motivo errado. É idempotente onde precisa ser — reusa usuário do Keycloak e vínculo externo, porque o par (emissor, subject) é único. Exige `TITAN_SEED_CONFIRM=1`, porque cria usuários com senha conhecida e isso só é aceitável em ambiente descartável.

### Dívida registrada

**A API não valida a própria configuração ao subir.** Ela inicia sem as variáveis de OIDC e só falha na primeira requisição autenticada. O certo é falhar no arranque, com mensagem clara. Some-se aos dois itens já anotados — rollback explícito da transação e 500 sanitizado — que têm código e não têm teste.

### Testes da prova ponta a ponta (8)

Criação autorizada `201`; sem token `401`; sem a permissão exigida `403` com `PERMISSAO_AUSENTE`; organização sem vínculo `403` com `CONTEXTO_ORGANIZACIONAL_NEGADO`, negação indistinguível; cabeçalho de organização ausente `400`; entrada inválida `422` em `problem+json` com os campos; conflito de domínio `409`; e o animal criado nasce com o evento no log do Core, provando que a transação cobre entidade e prova.

### Portão de verificação

`627 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (349 arquivos) e `alembic check` sem erros.

### Dívida registrada

Dois itens têm o código escrito e **não têm teste**: o **rollback explícito da transação** — a fixture já desfaz tudo, o que mascararia a prova — e o **500 sanitizado para erro inesperado**. Devem ser cobertos antes de o 10.4 fechar.

### Portão liberado

A prova ponta a ponta da fundação foi aprovada, e o 10.4b está liberado para começar.

### 10.4b — API mínima do fluxo · CONCLUÍDO

**Data:** 24 de julho de 2026. **Estado: CONCLUÍDO — validação manual aprovada.**

As sete rotas congeladas foram expostas, mais uma oitava que a decisão de escopo não previa e o domínio exige (ver abaixo). Todas sobre a fundação já aprovada no 10.4a.

| Rota | Permissão |
|---|---|
| `POST /v1/livestock/animals` | `LIVESTOCK_ANIMAL.CRIAR` |
| `POST /v1/livestock/medications` | `LIVESTOCK_MEDICATION.CRIAR` |
| `POST /v1/livestock/medication-batches` | `LIVESTOCK_MEDICATION.CRIAR` |
| `POST /v1/livestock/treatments` | `LIVESTOCK_TREATMENT.REGISTRAR` |
| `POST /v1/livestock/treatments/{id}/corrections` | `LIVESTOCK_TREATMENT.REGISTRAR` |
| `POST /v1/livestock/animals/{id}/eligibility` | `LIVESTOCK_ELIGIBILITY.EXECUTAR` |
| `GET /v1/livestock/animals/{id}/timeline` | `LIVESTOCK_TIMELINE.LER` |
| `GET /v1/livestock/dossiers/{id}` | `DOSSIER.LER` |

**A rota de correção não estava na lista congelada, e precisa estar.** Sem ela, a API ofereceria registro de tratamento sem oferecer correção — e corrigir por novo registro é o cenário que o Marco 9 existe para demonstrar. Não é rota nova de escopo: é a segunda metade de uma capacidade que já estava aprovada. **Não há PUT, PATCH nem DELETE em rota alguma da vertical**, e um teste de contrato falha se algum aparecer: append-only não é convenção, é ausência de rota que sobrescreva.

**A elegibilidade é POST, e não GET.** Ela não consulta: produz `Evaluation`, `Decision` e `Dossier` — registros permanentes. Um GET que grava prova quebra a expectativa de quem integra, e qualquer intermediário que repita a chamada produziria registros duplicados.

**O dossiê é consequência da decisão.** Não existe `POST /dossiers`: a execução da elegibilidade o materializa e devolve o identificador. O operador não cria prova à mão.

### Defeito estrutural encontrado: política não persistida

A avaliação falhava contra o PostgreSQL com violação de chave estrangeira: `evaluations` referencia `policies`, e **a política de elegibilidade era construída em memória a cada execução, sem nunca ser gravada**. Os testes unitários não pegavam porque repositórios falsos não impõem integridade.

O defeito era mais fundo que a chave estrangeira. Política construída em memória não tem existência própria: não pode ser consultada, comparada com a de ontem, nem citada por um dossiê emitido no ano passado. **Uma decisão só é reproduzível se a norma sob a qual foi tomada estiver registrada** — que é a tese do produto.

Foi criado `EligibilityPolicyProvider`, que grava política e regras na primeira execução e as reusa nas seguintes, procurando por código e versão. É o passo mínimo na direção da nota de rumo **NR-5**: quando a autoria passar ao administrador, o que muda é quem escreve a política; a leitura pela versão vigente já está aqui.

### Testes ponta a ponta (10, em `test_livestock_api_flow.py`)

O fluxo inteiro por HTTP — animal, medicamento, lote, tratamento, elegibilidade, dossiê — com dois papéis e duas Organizations. Cobre: bloqueio dentro da carência e aprovação fora dela; **o dossiê devolvido pela API verifica-se pelo próprio hash**, sem o Titan; a linha do tempo mostra cadastro, tratamento e decisão; a correção cria registro novo e o corrigido continua visível, marcado; auditor não escreve (403); **operador não lê dossiê** (403 — a separação vale nos dois sentidos); outra Organization não alcança o dossiê; lote inexistente devolve 404; tratamento no futuro devolve 409.

Dois testes de contrato foram acrescentados ao congelamento da superfície: nenhuma rota da vertical permite edição destrutiva, e toda rota declara autenticação e as negações 401 e 403 no OpenAPI.

### Defeito no próprio teste, encontrado e corrigido

O cliente de teste definia o override de autenticação na construção, e o override é **global à aplicação**. Num teste que usasse operador e auditor, o último sobrescrevia o outro, e os dois papéis agiam como um só — falha silenciosa que faria o teste provar o contrário do que afirma. O cliente passou a reafirmar o principal a cada requisição.

### Portão de verificação

`640 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (359 arquivos) e `alembic check` sem erros.

### Validação manual — APROVADA em 24 de julho de 2026

O fluxo completo foi operado pelo Swagger, com os dois papéis e as duas Organizations semeadas: cadastro, medicamento, lote, tratamento, elegibilidade bloqueando, correção por novo registro, leitura do dossiê e da linha do tempo pelo auditor, e as nove negações. Todos os cenários responderam o esperado.

**Dois defeitos de usabilidade encontrados, ambos na ferramenta de validação e não no produto:**

1. **Token expirando no meio do roteiro.** O padrão do Keycloak é de cinco minutos, e o roteiro não cabe nisso — o 401 resultante parece defeito da API quando é a credencial vencendo. A semeadura passou a ampliar a validade para 3600s no realm local, via API de administração, e o `titan-realm.json` já nasce assim. Está escrito no código por que isso só vale em ambiente local: ampliar validade de token em ambiente real amplia a janela em que uma credencial vazada continua servindo.
2. **Placeholders de data no roteiro** (`<hoje menos 10 dias>`) sendo enviados literalmente, com 422 correto em resposta. Todas as datas passaram a ser calculadas no instante da semeadura e impressas prontas para colar. A lição ficou registrada: placeholder em roteiro é convite a ser enviado literalmente.

A API se comportou corretamente nos dois episódios — o 422 apontou o campo exato e o motivo, que é o mínimo para corrigir sem adivinhação.

### Ferramenta de validação (`apps/seed/`)

O roteiro impresso pela semeadura cobre, com identificadores e datas reais: preparação do ambiente, o fluxo completo em cinco passos, a correção que não apaga, a leitura pelo auditor com o corte bitemporal, e as nove negações com seus `reason_code`. Fecha com o que o conjunto demonstra — que serve tanto para conferir quanto para apresentar.

## Passo 10.6 — Cenário demonstrativo reproduzível

**Data de conclusão:** 24 de julho de 2026 · **Estado:** IMPLEMENTADO (validação manual pendente). **Fecha o Marco 10**, já que o 10.5 é opcional pelo PLANO e a validação por Swagger se mostrou suficiente.

### O que foi entregue

`python -m apps.demo` executa, num comando, exatamente a sequência que o PLANO exige — **cadastro → tratamento → bloqueio → correção → reavaliação → dossiê** — e grava os artefatos em disco.

**A narrativa escolhida é a que prova a tese do produto.** Um operador lança a data errada de uma aplicação; o animal é **barrado** pela regra de carência; o erro é corrigido por novo registro; a reavaliação **libera**. As duas decisões existem, as duas aplicações continuam legíveis, e o registro errado permanece marcado. O Titan não apenas bloqueia: ele **redecide sobre fatos corrigidos sem apagar o que decidiu antes**.

Um cenário que apenas bloqueasse mostraria metade do produto — qualquer sistema recusa. O que é raro é recusar, aceitar correção e refazer a conta preservando as duas versões.

**Artefatos:** o dossiê em JSON e em PDF, gravados em `artefatos-demonstracao/` (ignorado pelo git — é saída, não fonte). O JSON é a prova: quem o recebe recalcula o SHA-256 dos bytes canônicos e compara com `dossier_hash`, sem o Titan no ar.

**Transação única:** ou o cenário inteiro existe, ou nada dele existe. Cenário pela metade confunde quem o inspeciona.

**Dados fictícios**, como o PLANO exige — nenhuma pessoa, propriedade ou animal real, e um teste verifica que nem `@` nem CPF aparecem no dossiê produzido.

### Testes (6)

Um roteiro de demonstração que ninguém executa apodrece em silêncio: a API muda, o cenário quebra, e só se descobre na hora de mostrar a alguém. Por isso a demonstração inteira roda no portão, com rollback ao final.

Cobrem: bloqueio seguido de aprovação sobre fatos corrigidos, com decisões distintas; o registro corrigido permanecendo legível e marcado; a sequência do PLANO percorrida inteira, na ordem; **o dossiê gravado em disco reconstruído e verificado sem o Titan**; o relatório narrando o essencial; e a ausência de dado pessoal.

### Portão de verificação

`646 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (362 arquivos) e `alembic check` sem erros.

### Validação manual pendente

Recriar o ambiente do zero — `docker compose down -v`, `docker compose up -d`, `alembic upgrade head` — e executar `python -m apps.demo`, conferindo os sete passos e inspecionando o JSON e o PDF gravados.

## Marco 12 — API de leitura e entidades faltantes

**Data:** 25 de julho de 2026 · **Estado:** IMPLEMENTADO (validação manual pendente).

**Fora do PLANO_DE_IMPLEMENTACAO_VALIDADO**, que se encerrou no Marco 10. Autorizado diretamente pelo responsável ao constatar que a API do Marco 10 não sustenta um frontend.

### Por que existe

A API do Marco 10 tinha oito rotas: seis criavam, duas liam por identificador. **Não havia listagem alguma** — quem cadastrasse um animal e perdesse o UUID não o alcançava mais. Metade do domínio (propriedade, lote pecuário, veterinário, movimentação) tinha serviço e persistência completos e nenhuma rota. E não havia CORS, o que bloqueia qualquer navegador em outra origem antes da requisição sair.

Nada disso era falha do Marco 10: o PLANO definiu "endpoints **estritamente necessários** para operar o cenário". A API existia para provar a tese, não para sustentar produto.

### O que foi entregue

**36 rotas** ao todo, contra 11 antes.

- **CORS** por `TITAN_CORS_ORIGINS`, sem curinga por padrão. `*` com credenciais é recusado pelo próprio navegador, e liberar tudo num serviço que carrega prova auditável não é conveniência.
- **Listagem e detalhe** de animal, propriedade, medicamento, lote de medicamento, tratamento, lote pecuário, veterinário e movimentação. Filtros onde fazem sentido: lotes por medicamento, tratamentos e movimentações por animal.
- **Composição temporal do lote** (`/lots/{id}/members?at_time=`): sem instante devolve a vigente; com ele, a que valia então. Um lote não é o que ele é hoje.
- **Escrita** de propriedade, lote, inclusão e encerramento de permanência, veterinário, atualização de verificação e movimentação.
- **`GET /dossiers?subject_id=`**, que exige o sujeito: devolver toda a prova da organização de uma vez não é pergunta que alguém faça, e é varredura cara sobre a tabela mais sensível.

### Decisões

**Paginação sem contagem total.** Contar exige varrer a tabela a cada página, e o custo cresce com o acervo — justamente onde a paginação deveria aliviar. `has_more` responde a única pergunta da interface, obtido pedindo um registro a mais e descartando-o. O teto de 200 é rígido: pedir acima é **recusado**, não reduzido em silêncio, para o cliente não acreditar que recebeu tudo.

**Permissão de leitura por área**, não uma só para tudo: `LIVESTOCK_ANIMAL.LER`, `LIVESTOCK_MEDICATION.LER`, e assim por diante. Papel de consulta restrita — um comprador que só vê o dossiê, um técnico que só vê tratamentos — deixa de exigir código novo para existir. Os conjuntos `LEITURA` e `ESCRITA` compõem os papéis, e `LIVESTOCK_PERMISSIONS` deriva deles.

**O operador passou a ler o que opera.** Cadastrar sem poder consultar o que se cadastrou não é papel utilizável. O dossiê ficou de fora: a prova é do auditor.

**`organization_id` nunca vem do cliente** — vem do contexto resolvido, e o RLS confirma no banco. Aceitá-lo por parâmetro daria ao chamador a chance de pedir dados de outra organização.

**Encerrar permanência é POST, não DELETE.** Fecha a vigência e acrescenta um fato; o vínculo anterior permanece. Um DELETE prometeria apagar o que o domínio preserva.

**O CPF do veterinário não sai da API.** É usado para impedir duplicidade no cadastro e não aparece em consulta alguma — há teste.

### Defeito encontrado no caminho

A ferramenta de semeadura mantinha uma **lista paralela** de permissões e ficou para trás em silêncio quando as de leitura nasceram. Passou a derivar de `LIVESTOCK_PERMISSIONS`, que é a fonte única.

### Testes (13, em `test_livestock_api_leitura.py`)

O animal cadastrado aparece na listagem; a página indica continuidade sem contar tudo, e páginas não se sobrepõem; pedir acima do teto é recusado; detalhe por identificador; recurso de outra organização responde como inexistente; identificador malformado é erro do cliente; ciclo completo de uma entidade que não tinha rota; o lote recebe e encerra permanência **sem apagar o vínculo**, com consulta temporal; movimentação é um fato só ainda que mova vários; o CPF não vaza; o auditor lê e não escreve; e os dossiês de um sujeito são encontráveis sem saber o UUID.

### Portão de verificação

`667 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (368 arquivos) e `alembic check` sem erros.

### Validação manual pendente

Percorrer as rotas de leitura pelo Swagger e conferir a paginação. Depois disso, a API sustenta um frontend.

## Marco 13 — Ciclo de vida do animal

**Fora do PLANO_DE_IMPLEMENTACAO_VALIDADO.** Descrito em `docs/PLANO_DE_CONCLUSAO_DO_DOMINIO.md`, autorizado pelo responsável ao optar por concluir o domínio antes de partir para o frontend.

### Passo 13.1 — Saída do rebanho

**Data:** 25 de julho de 2026 · **Estado:** IMPLEMENTADO (validação manual pendente).

#### Por que existe

Até aqui **o animal não tinha fim**. Todo animal cadastrado permanecia implicitamente vivo e presente, para sempre. As consequências não eram cosméticas: um recall varreria animais mortos há anos, a carência seria calculada para bois que já saíram, e toda listagem, tela e relatório nasceriam enviesados por incluir o rebanho inteiro desde a fundação da organização.

#### O que foi entregue

- `AnimalExit` em `livestock_domain/exit.py`, com `ExitType` (`MORTE`, `ABATE`, `VENDA`, `TRANSFERENCIA_DEFINITIVA`), instante, motivo, destino e evidências opcionais.
- `AnimalExitService` e `guard_animal_active` em `livestock_application/exit_service.py`.
- Tabela `core_audit.animal_exits` (migration `20260725_0043`) com RLS `FORCE` e `UNIQUE (animal_id)`.
- `POST /v1/livestock/animals/{id}/exit`, com permissão própria `LIVESTOCK_ANIMAL.REGISTRAR_SAIDA`.
- Listagem de animais passou a devolver o **rebanho ativo** por padrão, com `incluir_saidos=true` para o levantamento histórico. O detalhe sempre traz o objeto `saida`.

#### Decisões

**O estado é derivado, nunca campo mutável.** Não existe coluna `ativo` em `animals`: quem responde se o animal saiu é a existência da linha em `animal_exits`. Estado guardado em campo diverge do histórico assim que alguém o edita; estado derivado não tem como divergir.

**A saída fecha o futuro, não o passado** (decisão D-2 do plano de conclusão, tomada por delegação). `admite_fato_em` aceita `occurred_at <= saida.occurred_at`. Lançar hoje um tratamento aplicado na semana passada, antes do abate, é **regularização de registro** — o caso mais comum no campo — e recusá-lo apagaria o que de fato aconteceu, que é justamente o que um registro append-only não faz. Já um fato posterior à saída não pôde ocorrer: o animal não estava mais lá. O critério é sempre o instante em que o fato **ocorreu**, nunca o do registro.

**A guarda entrou pela porta de animal, e não por uma porta nova.** `guard_animal_active` lê a saída por `AnimalRepositoryPort.get_exit`, que todo serviço já recebe. Uma porta separada exigiria alterar a fiação de cada serviço, e quem esquecesse de fazê-lo teria a guarda desligada em silêncio. Hoje ela está ligada em tratamento, movimentação e lote.

**Terminalidade garantida no banco, e não só no serviço.** `UNIQUE (animal_id)` recusa a segunda saída mesmo que a conferência da aplicação falhe. Invariante que só a aplicação garante é invariante que se perde na primeira execução concorrente.

**Permissão própria para declarar a saída.** Quem cadastra não é necessariamente quem atesta morte, abate ou venda — um ato irreversível que encerra a história do animal. `LIVESTOCK_ANIMAL.REGISTRAR_SAIDA` deixa essa separação possível sem código novo.

#### Testes

`test_exit_service.py` (7): registro grava o fato no fluxo do animal; sair é terminal; saída no futuro é recusada; animal de outra organização não é alcançado; a guarda recusa fato posterior, aceita fato anterior e o instante exato da saída, e é silenciosa para quem está no rebanho. `test_treatment_service.py` (2): tratamento posterior à saída é recusado **sem deixar rastro no log**, e tratamento anterior continua aceito. `test_livestock_api_saida.py` (5): o animal que saiu deixa o rebanho ativo mas continua alcançável pelo detalhe; o levantamento histórico o traz com a saída preenchida; a segunda saída responde 409; o auditor recebe 403; animal inexistente responde 404.

#### Portão de verificação

`681 testes aprovados, 0 pulados`; `ruff check`, `ruff format --check`, `mypy` (374 arquivos) e `alembic check` sem erros.

#### Validação manual pendente

Registrar uma saída pelo Swagger, conferir que o animal some da listagem padrão e reaparece com `incluir_saidos=true`, e tentar lançar um tratamento com data posterior à saída.

#### Armadilha de ambiente descoberta aqui

A senha do PostgreSQL local **não** é `titan`: o `compose.yaml` usa `TITAN_POSTGRES_PASSWORD`, com padrão `titan_local_dev_password`. Com a senha errada o `psycopg` não falha rápido — tenta `::1`, espera o timeout de conexão, e a suíte parece travada em vez de erro de configuração. A URL correta é:

```
postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan
```

**As duas Organizations do roteiro não se substituem, e confundi-las custou duas rodadas de diagnóstico às cegas.** `TITAN_OPERATOR_ORGANIZATION_ID` recebe a **operadora** — onde a identidade do usuário vive, e onde ele justamente *não* opera. O cabeçalho `X-Titan-Organization-Id` recebe a **Organization A**, que é onde há vínculo e onde estão a propriedade e o rebanho. O seed imprime as duas com rótulos distintos.

**Dívida do Marco 10.4 confirmada em campo: a API não valida a própria configuração ao subir.** `TITAN_OPERATOR_ORGANIZATION_ID` com valor que não é UUID não impede o `uvicorn` de anunciar "Application startup complete" — a falha só aparece na primeira requisição autenticada, como **500 `ERRO_INTERNO` sanitizado**, cuja causa real (`ValueError: O identificador de Organization não é um UUID válido`) existe apenas no log do servidor. Para quem valida pelo Swagger, o sintoma é indistinguível de erro de dados. O correto é conferir as quatro variáveis no startup e recusar-se a subir nomeando a que está errada.

## Notas de rumo — decisões de direção fora da numeração do PLANO

**Registradas em 24 de julho de 2026.** Não são passos do plano e não têm portão de verificação. São conclusões de análise que orientam passos futuros e que se perderiam se ficassem apenas em conversa. Nenhuma delas está implementada.

### NR-1 — Âncora temporal por documento de terceiro

**Problema.** O `occurred_at` de um evento capturado offline é **tempo alegado** pelo relógio do dispositivo. Quem controla o aparelho controla a alegação. Isso é grave especificamente na carência: ela é calculada como `applied_at + dias`, então antedatar uma aplicação encurta a carência efetiva e libera o animal antes da hora — resíduo na carne, exatamente o dano que o Marco 9 existe para impedir. A ADR-0021, princípio 4, já veda tratar relógio de dispositivo como prova temporal, e o PLANO lista o risco na sua tabela ("relógio local apresentado como prova temporal").

**Direção.** Todo evento offline já possui um **intervalo provável ancorado no servidor**, sem precisar confiar no dispositivo:

- limite superior: o instante em que o lote sincronizou;
- limite inferior: `DeviceClockReading.last_server_contact_at`, campo que já existe no domínio, reforçado por `monotonic_elapsed_ms` e `monotonic_continuity_id` — relógio civil que salta sem o cronômetro monotônico acompanhar é inconsistência aritmética, não opinião.

Documentos de terceiro estreitam o intervalo e acrescentam corroboração independente. A **nota fiscal do medicamento** dá limite inferior forte (não se aplica o que ainda não se comprou) e permite conferência cruzada do número do lote contra o `batch_number` já registrado. A **nota do serviço veterinário** corrobora presença profissional na data. Ambas são documentos de terceiro com autorização carimbada pela SEFAZ e chave verificável fora do Titan.

**Limite honesto:** nota prova aquisição, não aplicação. Eleva confiança sem produzir certeza — por isso o destino natural é `ConfidenceLevel` (Passo 5.2), e não um booleano. Enquanto a chave não for validada na fonte, o estado é `EvaluationOutcome.VALIDACAO_EXTERNA_PENDENTE`, hoje declarado no Core e **sem nenhum produtor** — este seria o primeiro.

**Consequência para a regra de elegibilidade:** o registro entra sempre (registro existente vale mais que registro ausente), mas um animal cuja carência repousa em hora não verificável não deve ser liberado com o mesmo peso de outro registrado online.

**Aplicação prevista para além de medicamento:** vacinação, serviços veterinários e demais manejos com nota.

**Pendência de decisão:** quem introduz cada informação — veterinário, produtor ou ambos. Ver NR-4.

### NR-2 — Alinhar ao GS1 EPCIS quando houver abate e produtos

**Contexto.** Abate e produtos não estão nos Marcos 8 a 10; o Marco 11 cita regras adicionais de recall. Quando entrarem, a cadeia deixa de ser linear: o abate é **fan-out** (um animal vira dezenas de cortes) e o processamento é **fan-in** (carne moída e linguiça misturam muitos animais num lote). A estrutura correta é **DAG, não árvore** — árvore pressupõe um pai, e isso quebra no primeiro produto misto. A genealogia animal também é fan-in.

**Direção.** O problema já está resolvido e padronizado internacionalmente. O **GS1 EPCIS** define `TransformationEvent` exatamente para esse caso, com listas de entrada e de saída; é o único tipo de evento que quebra a cadeia de lote e cria lote novo, e é irreversível. A regulação norte-americana (FSMA 204) usa o vocabulário de CTE e KDE.

**Recomendação:** quando o escopo chegar, o trabalho é **mapear o modelo do Titan para o EPCIS**, não desenhar um grafo próprio. Um sistema de auditoria que não troca dados com o sistema do frigorífico e do comprador vira ilha, e ilha não serve como prova para terceiros.

**Forma esperada:** o produto é entidade nova, com fluxo de eventos próprio, mais relação de origem apontando para a carcaça e daí para o animal. A linha do tempo do produto é o fluxo dele mais a travessia da origem — mesma forma que a timeline do animal já tem. `LivestockTimelineService` generaliza; não precisa ser reescrito. **Cópia da história para dentro do produto é o caminho errado:** cria N cópias do mesmo fato, e uma correção na origem passa a exigir propagação para N lugares.

**Fundação já existente:** `RecallService` faz travessia de grafo; as relações do Passo 7.1 são universais e temporais; o `reference_projection` do 7.2 indexa quem aponta para cada entidade. Rastreabilidade para trás (*tracking*) e para frente (*tracing*) são as duas direções da mesma travessia.

**Problema em aberto:** o que a linha do tempo de um lote de carne moída com dezenas de origens deve mostrar. Históricos completos de todas as origens é ilegível; provavelmente o certo é o fluxo próprio do produto mais os pontos de decisão de cada origem. Decisão para quando houver produto.

### NR-3 — O diferencial é a proveniência da decisão, não o grafo

O grafo de rastreabilidade é mesa posta: padronizado, com implementações maduras e concorrência estabelecida. O Titan não deve competir ali, e sim adotar o padrão.

O que é raro, e não está nos padrões de rastreabilidade, é **provar por que uma decisão foi tomada e permitir refazê-la**: política versionada, regra versionada, snapshot de fatos hasheável, avaliação explicável e dossiê reproduzível por terceiro sem acesso ao banco. EPCIS diz para onde as coisas foram; não diz por que algo foi liberado ou barrado.

**Consequência prática:** ao priorizar, passos que reforçam reprodutibilidade da decisão (dossiê, verificação externa, confiança temporal) valem mais que passos que ampliam cobertura de rastreio.

### NR-4 — Quem registra o fato: pendência de decisão

**Questão levantada em 24/07/2026 e ainda em aberto:** quem introduz cada informação — o veterinário, o produtor, ou ambos.

**Observação que estreita a questão:** o modelo de dupla participação **já existe** no fluxo farmacológico. A prescrição exige veterinário com status `DOCUMENTADO` ou `VERIFICADO_EM_FONTE` — é a autoridade dele; a aplicação registra o ator que executou — é o ato do produtor. São dois papéis, dois registros, duas autorias, já modelados.

Portanto a pergunta em aberto não é "quem registra", e sim **em que casos a prescrição deixa de ser opcional na aplicação** — hoje `prescription_id` é opcional em `TreatmentApplication`. Torná-la obrigatória para certas classes de produto é decisão de regra de negócio, com portão de aprovação, e afeta diretamente o peso probatório do registro.

Relacionado: `DecisionAuthorityProfile` e o fluxo de aprovações da ADR-0016 permanecem como pendência deliberada do Core.

### NR-5 — Autoria de regras pelo administrador da vertical

**Levantado em 24/07/2026. Precisa de solução, não apenas de registro.**

**O problema.** Regras dependem de lei, e lei muda. Hoje a única regra de negócio da vertical — a de carência — é construída em Python, por `build_eligibility_rule` em `livestock_application/eligibility.py`. Nenhum administrador a edita. Publicar uma norma nova exige alterar código, revisar, testar e implantar, o que é lento demais para acompanhar mudança regulatória e concentra em desenvolvedores uma decisão que é do domínio.

**A dificuldade real, que precisa ser enunciada antes de qualquer solução.** Regra escrita em tempo de execução por um humano precisa continuar **determinística e reproduzível**. Se o administrador puder escrever expressão livre, perde-se a garantia de que a mesma decisão refeita daqui a cinco anos produz o mesmo resultado — que é a tese inteira do produto. Uma regra editável e não reproduzível seria pior do que não ter regra editável.

**Segunda exigência, temporal.** Quando a lei muda, decisões antigas **não** podem ser reavaliadas pela regra nova: foram tomadas sob a norma vigente à época, e o dossiê precisa continuar reproduzível sob aquela versão. `Policy` e `Rule` já são versionadas, com `valid_from`, `valid_to`, `status` e `normative_source`, e o dossiê já copia as condições declarativas de cada regra — a fundação existe. O que falta é o comportamento ficar explícito quando a autoria sair das mãos do desenvolvedor.

**Há um caminho barato que já está estruturalmente pronto, e vale explorá-lo antes do caro.** `RuleCondition` **já é dado declarativo**, não código: `fact_type`, `payload_key`, `operator`, `expected_value`, `description`. Uma regra composta por essas primitivas é determinística por construção, já é versionada, já viaja inteira dentro do dossiê e já é reexecutável. Ou seja, **para regras que caibam nessas primitivas, o problema de execução está resolvido** — o que falta é apenas a *autoria*: interface, validação e fluxo de aprovação para o administrador compor condições, sem tocar em código.

Vale medir quanto da regulação real cabe nessas primitivas antes de construir qualquer coisa maior. A suspeita é que a maior parte caiba: "carência cumprida", "vacinação registrada no prazo", "veterinário habilitado" são todas comparações sobre fatos.

**O caminho caro, para o que não couber.** A **ADR-0036 já está aceita** e decide justamente isso: compilar regras normativas para bytecode Wasm imutável e versionado, executado em sandbox determinístico, recuperando na reavaliação o bytecode exato vigente na data do evento. Ela nomeia `WasmNormativePolicyEvaluator`, `PolicyExecutionSandbox` e `NormativeExecutionReceipt`. Está aceita e **não implementada**.

**Encaminhamento proposto:**

1. Levantar quais regras reais da pecuária são necessárias e classificar cada uma como "cabe nas primitivas declarativas" ou "não cabe".
2. Se a maioria couber, construir a autoria declarativa primeiro — é incomparavelmente mais barata que o sandbox e resolve o problema prático.
3. Reservar a implementação da ADR-0036 para o que sobrar, com evidência de que sobrou.
4. Em qualquer dos caminhos, exigir portão de aprovação para publicar regra: o plano já trata regra de negócio como categoria de aprovação obrigatória, e autoria por administrador não afrouxa isso.

Decidido em 24/07/2026: `VeterinaryPrescription` **não** integra a API mínima do Marco 10 — ver Passo 10.4. A pendência é de **regra de negócio**, não de API.

Relacionado: [ADR-0011] fontes normativas, vigência e reavaliação temporal; [ADR-0016] decisões explicáveis e revisão humana; NR-4, sobre quem registra cada fato.
