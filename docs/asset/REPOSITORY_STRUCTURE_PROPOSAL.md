# REPOSITORY_STRUCTURE_PROPOSAL — Opções de estrutura e recomendação

**Versão:** 1.0
**Status:** Proposta para revisão (Fases 4 e 5)
**Data:** 10 de setembro de 2026

---

## 1. Contexto para a decisão

- **Titan está em evolução ativa.** Média recente de commits mostra Core e
  Livestock evoluindo juntos, inclusive contratos (`git log`: mudanças de
  governança de regras, assinatura de eventos, imutabilidade relacional nas
  últimas semanas).
- **ADR-0001 já decidiu** monólito modular em monorepo e **já rejeitou**
  explicitamente microserviços e "repositórios separados para Core e cada
  vertical", por dificultarem mudança coordenada de contratos, testes ponta a
  ponta e desenvolvimento greenfield.
- **O Core já é reutilizado com sucesso** por Livestock via contratos públicos
  (`CORE_REUSE_ASSESSMENT.md` §1.4).
- O atrito real para uma segunda vertical é **local** (migrations, composição),
  não **distribuído**.

A pergunta desta fase não é "qual arquitetura é mais sofisticada", é "o que
minimiza risco de divergência e custo operacional mantendo as garantias
arquiteturais atuais enquanto Titan ainda muda rápido".

---

## 2. Opções avaliadas

### OPÇÃO A — Mesmo repositório / monólito modular / Core compartilhado *(estado atual, generalizado)*

Verticais como `packages/<vertical>_{domain,application,infrastructure}` no mesmo
monorepo, consumindo o mesmo `packages/core_*` por import direto. Ajustes: cada
vertical com ambiente de migrations próprio; composição HTTP/worker por vertical.

| Critério | Avaliação |
|---|---|
| Complexidade | **Baixa.** Nenhuma infra nova. Só convenções + testes de fronteira. |
| Evolução | **Ótima.** Mudança de contrato Core+verticais no mesmo commit, com CI cobrindo tudo. |
| Testes | **Ótima.** Suite única; testes de integração ponta a ponta triviais; `alembic check` num único comando. |
| Versionamento | Implícito (um repo, um SHA). Sem semver de Core — que hoje é vantagem, não falta. |
| CI/CD | **Simples.** Um pipeline. Build/lint/mypy/pytest já configurados. |
| Segurança | Igual ao atual. RLS por Organization, sem superfície de rede nova. |
| Risco de divergência | **Mínimo.** Uma implementação do Core, fisicamente impossível forkar sem PR visível. |
| Desenvolvimento local | **Melhor possível.** `uv sync`, `pytest`. Sem publicar/linkar pacotes. |
| Autonomia das verticais | **Lógica**, garantida por teste de fronteira. Física não — aceitável nesta fase. |
| Custo operacional | **Mínimo.** Um deploy (API + worker), um banco. |

### OPÇÃO B — Titan Core como pacote versionado separado (ainda no mesmo repo, como *workspace member* `uv`, com semver)

`packages/core_*` vira um distribuível (`titan-core`) com versão semântica;
verticais declaram `titan-core >= x.y`. Pode ser workspace `uv` (mesmo repo) ou
publicação em índice privado.

| Critério | Avaliação |
|---|---|
| Complexidade | **Média.** Precisa de versionamento disciplinado, changelog de contrato, matriz de compatibilidade. |
| Evolução | **Atritada agora.** Toda mudança de contrato vira "bump + upgrade nas verticais", mesmo dentro do mesmo repo. Freia o ritmo atual. |
| Testes | Boa se workspace (`uv` resolve local); ruim se publicado (precisa de pré-release para testar integração). |
| Versionamento | Explícito. Útil **quando** houver consumidores que não podem atualizar em lockstep — não é o caso hoje. |
| CI/CD | Mais estágios: build+publish do Core, depois verticais. |
| Segurança | Igual, se workspace. |
| Risco de divergência | Baixo se workspace; **sobe** se publicado (verticais podem ficar em versões diferentes do Core). |
| Desenvolvimento local | Bom com workspace `uv`; pior com índice (editable installs, tokens). |
| Autonomia das verticais | Alta — cada vertical escolhe quando adotar nova versão do Core. |
| Custo operacional | Médio. |

**Veredito:** É a **evolução natural da Opção A** quando (e só quando) uma
segunda vertical estiver em produção e a cadência de mudança de contrato tiver
caído. Adotar agora paga custo de governança sem colher o benefício.

### OPÇÃO C — Titan Core em repositório independente

`titan-core` em outro repo Git, publicado; `titan-livestock` e `titan-asset` em
repos próprios (ou um repo de verticais).

| Critério | Avaliação |
|---|---|
| Complexidade | **Alta.** Publicação, versionamento, credenciais, sincronização de PRs entre repos. |
| Evolução | **Ruim para a fase atual.** Mudança de contrato = PR no Core → release → PR em cada vertical. Já rejeitado em ADR-0001. |
| Testes | Integração ponta a ponta exige orquestração multi-repo (checkout coordenado, versões casadas). |
| Versionamento | Obrigatório e cerimonioso. |
| CI/CD | Múltiplos pipelines + gatilhos cross-repo. |
| Segurança | Superfície de supply chain nova (índice de pacotes, tokens). |
| Risco de divergência | **Alto.** Verticais em versões diferentes do Core é o estado natural; regressão só aparece na integração. |
| Desenvolvimento local | Pior. Clonar N repos, linkar Core editável para iterar. |
| Autonomia das verticais | Máxima — provavelmente **mais** do que se quer nesta fase. |
| Custo operacional | Alto. |

**Veredito:** Rejeitada. Só faz sentido com organizações/times separados por
vertical e Core estável — cenário futuro, não atual.

### OPÇÃO D — Git subtree / submodule

Core como submódulo (ou subtree) referenciado pelos repos das verticais.

| Critério | Avaliação |
|---|---|
| Complexidade | **Alta e escorregadia.** Submodule: estado destacado, `--recursive` esquecido, ponteiros de commit. Subtree: merges/splits manuais. |
| Evolução | Ruim. Mudança de contrato exige commit no Core + atualização de ponteiro em cada consumidor. |
| Testes | Frágeis: CI precisa resolver submódulos na versão certa. |
| Versionamento | Por SHA, opaco. Pior que semver e pior que monorepo. |
| CI/CD | Pontos de falha extras. |
| Segurança | Neutra. |
| Risco de divergência | Alto — cada consumidor aponta para um SHA diferente do Core. |
| Desenvolvimento local | **Pior de todos.** Pega o atrito do multi-repo sem o benefício de fronteira limpa de pacote. |
| Autonomia | Ilusória (parece isolado, opera acoplado). |
| Custo operacional | Alto. |

**Veredito:** Rejeitada. É o pior dos dois mundos; nenhuma vantagem sobre B ou C.

---

## 3. Comparação sintética

| Critério (peso na fase atual) | A | B | C | D |
|---|:--:|:--:|:--:|:--:|
| Ritmo de evolução de contrato (alto) | ✅✅ | ⚠️ | ❌ | ❌ |
| Simplicidade de testes ponta a ponta (alto) | ✅✅ | ✅ | ❌ | ❌ |
| Risco de divergência do Core (alto) | ✅✅ | ✅ | ❌ | ❌ |
| Custo operacional (alto) | ✅✅ | ⚠️ | ❌ | ❌ |
| Desenvolvimento local (médio) | ✅✅ | ✅ | ⚠️ | ❌ |
| Autonomia física da vertical (baixo agora) | ⚠️ | ✅ | ✅✅ | ⚠️ |
| Versionamento explícito (baixo agora) | ❌ | ✅✅ | ✅✅ | ⚠️ |

Na fase atual (Titan mutável, um time, Core co-evoluindo com as verticais), os
critérios de peso alto apontam todos para **A**.

---

## 4. Recomendação (Fase 5)

### Confirmada: **MONOREPO + MODULAR MONOLITH + SHARED CORE** (Opção A, generalizada)

A hipótese inicial resiste ao repositório real. Evidências:

1. **ADR-0001 já decidiu isso** e rejeitou C e microserviços com a mesma
   fundamentação que continua válida.
2. **O Core já está limpo** de conceitos de vertical (`CORE_REUSE_ASSESSMENT.md`
   §2) — a fundação genuinamente reutilizável já existe.
3. **A reutilização já funciona** — Livestock consome o núcleo de confiança
   inteiro via contratos públicos.
4. **O atrito é local e barato de remover**: ambiente de migrations por vertical,
   composição HTTP/worker por vertical, e um teste de fronteira generalizado.
   Nenhum desses exige distribuição.
5. **Distribuir agora** (B publicado / C / D) adicionaria versionamento,
   supply chain e orquestração multi-repo enquanto o benefício (autonomia
   física, releases independentes) ainda não é necessário.

### Estrutura-alvo

```text
apps/
  api/
    core/                 adapters HTTP do Core (authentication, problem, pagination,
                          verification, policy_governance, configuration, main)
    livestock/            routers + dependencies da vertical (movidos de livestock_*.py)
    asset/                routers + dependencies da vertical Asset  [criado no 1º slice]
    _registry.py          lista de routers que main.py itera
  worker/
    main.py
    dispatch.py           registry real keyed por message_type/vertical
    livestock_handlers.py
    asset_handlers.py     [criado quando houver mensagem de Asset]

packages/
  shared_kernel/          (inalterado, contido)
  core_domain/            + __all__ e teste de superfície pública
  core_application/       + __all__ e teste de superfície pública
  core_infrastructure/
    persistence/
      migrations/         SÓ migrations do Core  (livestock migrations saem daqui)
  core_integrity/
  livestock_domain/
  livestock_application/
  livestock_infrastructure/
    persistence/
      metadata.py         = MetaData do Core (mantido)
      migrations/          ambiente Alembic PRÓPRIO da vertical  [Passo 2]
  asset_domain/           [criado no 1º slice, incremental]
  asset_application/
  asset_infrastructure/
    persistence/
      metadata.py         = MetaData do Core (mesmo padrão)
      migrations/          ambiente Alembic próprio desde o dia 1

docs/
  adr/0080-...            ADR desta decisão
  asset-sustainment/      estes seis documentos
```

### Migrations — modelo-alvo

- **Uma `MetaData`** (a do Core) continua sendo o registro único de tabelas, para
  o SQLAlchemy resolver FKs para `core_identity.organizations`.
- **Múltiplos `version_locations`** no `alembic.ini` (ou um `env.py` por
  vertical que importa as tabelas do Core como alvo de FK + as próprias).
- Cada diretório de versões tem sua própria cabeça (`head`); Alembic suporta
  múltiplas cabeças com `depends_on` para ordenar o que precisa de ordem
  (tabela de vertical depende da migration que cria `organizations`).
- Cada migration de vertical carimba `titan.module_owner=titan_<vertical>` (já é
  prática em Livestock).
- `alembic upgrade head` (todas as cabeças) num ambiente de dev/CI continua
  produzindo o schema completo; o diff de schema antes/depois da extração é o
  critério de aceite (`CORE_EXTRACTION_RISKS.md`).

### Onde a Opção B entra depois

Reabrir a discussão de "Core como pacote versionado" **quando todos** os
seguintes forem verdade:

- há ≥ 2 verticais em produção;
- a cadência de mudança de contrato do Core caiu (semanas → meses);
- surge um consumidor que comprovadamente **não pode** atualizar em lockstep.

Nesse momento, o passo natural é `uv` workspace com `titan-core` versionado
(ainda no mesmo repo), não repositório separado. Registrar como item aberto na
ADR-0080.

---

## 5. Consequências

**Positivas:** custo incremental próximo de zero; garantias arquiteturais atuais
preservadas e agora verificadas para N verticais; Asset nasce no modelo correto
de migrations; nada a reverter em infra.

**Negativas:** autonomia da vertical continua lógica, não física — uma mudança
errada no Core ainda pode, em tese, quebrar duas verticais no mesmo deploy (o
teste de superfície pública e a suite de integração são a mitigação).

**Neutras:** o `main.py` e o `alembic.ini` deixam de crescer por vertical, ao
custo de introduzir um registry e múltiplos `version_locations` (complexidade
pequena, paga uma vez).

---

## 6. Reconciliação com `PARALLEL_VERTICAL_SAFETY` (10/09/2026)

A recomendação (Opção A generalizada — monorepo / monólito modular / Core compartilhado) **permanece**.
Correções na "estrutura‑alvo" da §4 sob desenvolvimento paralelo:

- **"Múltiplos `version_locations` → `upgrade head` resolve todas as cabeças" está errado.** Com múltiplas
  cabeças, `alembic upgrade head` (singular) aborta; é `alembic upgrade heads`. A troca é repo‑wide (CI,
  `CLAUDE.md`, `AGENTS.md`, `DEVELOPMENT.md`, `apps/validacao/*`, checklist) e vira PR de Shared Integration
  próprio. Ver `docs/architecture/MIGRATION_CONCURRENCY_STRATEGY.md` S‑M1.
- **`MetaData` única + `env.py` por vertical** só funciona com filtro `include_object`/`include_name` por
  `titan.module_owner` (o `env.py` atual filtra por schema). Sem isso, `alembic check` de uma vertical propõe
  `DROP` das tabelas das outras.
- **Estrutura‑alvo de `apps/api/`.** `apps/api/livestock/` (mover os módulos de Livestock) é
  `REQUIRES_INTEGRATION_WINDOW` enquanto o Codex estiver ativo. `apps/api/asset/` e `apps/api/_registry.py`
  são aditivos e podem nascer já; a migração de `livestock_*.py` para o subpacote fica para janela
  coordenada.
- **Fonte da verdade.** Introduzir `docs/architecture/verticals.toml` (manifesto de composição, sem domínio,
  não importado pelo Core) para que testes e portões sejam genéricos sobre a lista de verticais.
- Governança completa em `docs/architecture/PARALLEL_VERTICAL_DEVELOPMENT_PROTOCOL.md` e no rascunho de ADR
  `docs/adr/draft-20260910-governanca-de-desenvolvimento-paralelo-de-verticais.md`.
