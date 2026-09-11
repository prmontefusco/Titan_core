# ADR-0080 — Segunda vertical (Titan Asset & Sustainment) e reutilização do Titan Core sem fork

**Data:** 10/09/2026
**Status:** PROPOSTA
**Estado operacional no MVP:** FUTURA_APROVADA
**Escopo:** Confirmação da estrutura de repositório para múltiplas verticais;
formalização da regra de isolamento vertical ⊥ vertical; ambiente de migrations
por vertical; convenções de composição (HTTP e worker). **Não** decide o modelo
de domínio de Titan Asset.

**Relacionada a:** ADR-0001 (monólito modular e estrutura do repositório),
ADR-0002/0003 (isolamento por Organization, RLS), ADR-0060 (extensões verticais
de VerificationBundle), ADR-0077 (FKs compostas por Organization na vertical),
ADR-0079 (assinatura de eventos). Documentos de apoio:
`docs/asset/` (seis artefatos de assessment).

---

## Contexto

O Titan vai receber uma segunda vertical, **Titan Asset & Sustainment**
(gestão de ativos, engenharia de peças, inventário, logística, manutenção e
contratos de sustentação/SLI). A vertical existente, Titan Livestock, é a única
até hoje, e alguns pontos do repositório assumem implicitamente "existe exatamente
uma vertical".

Uma auditoria do Core (registrada em
`docs/asset/CORE_REUSE_ASSESSMENT.md`) constatou:

1. O `Titan Core` (`packages/{shared_kernel,core_domain,core_application,core_infrastructure,core_integrity}`)
   **não contém nenhum conceito de Livestock** — zero vocabulário de vertical,
   zero imports de vertical em domain/application/integrity/shared_kernel.
2. Livestock **já reutiliza** o núcleo de confiança inteiro (evidência, fato,
   política, regra, avaliação, decisão, governança de decisão, dossiê, relações,
   normativo) através das superfícies públicas de `core_domain` e
   `core_application`, mais `shared_kernel`.
3. O Core nunca depende de uma vertical, com **uma única exceção documentada**: o
   `env.py` do Alembic importa as tabelas de `livestock_infrastructure` porque
   Core e vertical compartilham uma única história linear de migrations e uma
   única `MetaData` SQLAlchemy.
4. O atrito para a segunda vertical é **local** (ambiente de migrations único;
   `apps/api` plano com routers de vertical nomeados um a um em `main.py`;
   `apps/worker` cujo registry não faz despacho), **não distribuído**.

A hipótese arquitetural sob avaliação era: *monorepo + monólito modular + Core
compartilhado*. A comparação de opções
(`docs/asset/REPOSITORY_STRUCTURE_PROPOSAL.md`) — mesmo repo (A),
Core como pacote versionado (B), Core em repo próprio (C), subtree/submodule (D)
— confirma a hipótese para a fase atual, na qual o Core co-evolui semanalmente
com as verticais e não há consumidor que precise de releases independentes.

---

## Decisão

### 1. Estrutura: monorepo, monólito modular, Core compartilhado (mantém ADR-0001)

Titan Asset & Sustainment é adicionado como pacotes no mesmo monorepo
(`packages/asset_*` e, se o slice justificar, `packages/sustainment_*`),
consumindo a **mesma** implementação de `packages/core_*` por import direto das
superfícies públicas. **É proibido** copiar, forkar ou versionar internamente o
Core por vertical. **É proibido** introduzir conceito de Asset em qualquer pacote
`core_*` ou `shared_kernel`.

Opções C e D são rejeitadas (repetem a rejeição de ADR-0001). Opção B (Core como
pacote versionado, preferencialmente `uv` workspace no mesmo repo) fica
**registrada como evolução futura**, a reabrir quando: houver ≥ 2 verticais em
produção, a cadência de mudança de contrato do Core tiver caído, e existir um
consumidor que comprovadamente não possa atualizar em lockstep.

### 2. Regra de isolamento vertical ⊥ vertical (nova, formal)

Além das regras de ADR-0001, passa a valer e a ser verificada por teste:

```
asset_*     -> core_*      PERMITIDO
livestock_* -> core_*      PERMITIDO
core_*      -> asset_*      PROIBIDO
core_*      -> livestock_*  PROIBIDO
asset_*     -> livestock_*  PROIBIDO
livestock_* -> asset_*      PROIBIDO
```

Nenhuma vertical lê tabelas, tipos, constantes ou módulos de outra vertical,
mesmo compartilhando banco e schema `core_audit`. Colaboração entre verticais,
se algum dia necessária, ocorre por evento publicado ou contrato público.

A matriz completa e a allowlist de quais módulos de `core_infrastructure` uma
vertical pode importar estão em
`docs/asset/DEPENDENCY_RULES.md` (fonte normativa).

### 3. Ambiente de migrations por vertical

Cada vertical possui o **próprio ambiente Alembic** (diretório de versões próprio
via `version_locations`, com `env.py` que importa as tabelas-alvo de FK do Core).
A `MetaData` SQLAlchemy **permanece única** (a do Core, `organization_metadata`) —
é o que permite ao SQLAlchemy resolver FKs para `core_identity.organizations`
(mesma razão de ADR-0077 e de
`packages/livestock_infrastructure/persistence/metadata.py`).

- Titan Asset nasce com ambiente de migrations próprio desde o primeiro slice.
- A extração do ambiente de migrations de Livestock (hoje sob
  `core_infrastructure/persistence/migrations/`) é **desejável** e segue como
  trabalho separado, comportamentalmente neutro, com teste de diff de
  `pg_dump --schema-only` como critério de aceite. Não é pré-requisito para
  começar Asset.
- A exceção de fronteira `MIGRATIONS_COMPOSITION_ROOT` no teste arquitetural é
  generalizada para "qualquer `env.py` sob `packages/*/persistence/migrations/`".
- Toda migration de vertical carimba `titan.module_owner=titan_<vertical>` no
  comentário da tabela (já é prática em Livestock).

### 4. Convenções de composição

- **HTTP:** `apps/api/<vertical>/` como subpacote (routers + `dependencies.py`,
  espelhando `apps/api/livestock_dependencies.py`). Adapters HTTP do Core em
  `apps/api/core/`. Um registry (`apps/api/_registry.py`) que `main.py` itera,
  em vez de `main.py` nomear cada router de cada vertical.
- **Worker:** `apps/worker` passa a fazer despacho real keyed por
  `message_type`/vertical; cada vertical registra seus handlers.
- Essas mudanças são comportamentalmente neutras (contrato OpenAPI e
  processamento de mensagens de Livestock idênticos) e ocorrem na trilha
  "reorganizar Core", separada da trilha "implementar Asset".

### 5. Superfície pública do Core

`core_domain` e `core_application` declaram `__all__` refletindo o que seus
`__init__.py` já reexportam, e um teste sinaliza alteração dessa superfície para
que mudança de contrato seja consciente. Não se cria um pacote `core_contracts`
agora; ele só surge se uma necessidade concreta aparecer.

---

## Fronteiras

### O que Titan Asset reutiliza do Core (sem conhecer Livestock)

Identidade/Organizations/`OrganizationContext`; autorização por permissão;
eventos append-only + cadeia de integridade + checkpoints; outbox/inbox;
idempotência e concorrência otimista; política/regra/avaliação/decisão
explicável/governança de decisão (incl. **entitlement de SLI** e **elegibilidade
de garantia** como `Evaluation` → `Decision`); documentos; dossiê verificável com
`VerticalSection` (ADR-0060); proveniência e relações (custódia de peça/lote/
shipment); correção/supersessão/impacto; `shared_kernel` (temporal, referências,
identificadores, serialização canônica).

### O que Titan Asset implementa na própria camada (o Core não fornece)

Workflow do ciclo de vida de Work Order; cálculo de disponibilidade de estoque e
política de reserva de material; BOM/efetividade/intercambiabilidade de peças;
contratos de integração com ERP/PLM/WMS; notificações (não há capacidade de
notificação no Core).

### Bounded contexts

Os contexts candidatos (Asset Management, Product Configuration, Parts
Engineering, Inventory, Logistics, Maintenance, SLI/Sustainment Contracts)
**não** viram pacotes independentes de imediato. O corte inicial proposto é de
**dois módulos** — `asset_*` (Vehicle, Part, Configuration, Inventory,
Reservation) e `sustainment_*` (SLI Contract, Entitlement, Work Order, demanda de
material) — com divisão adicional apenas quando um invariante transacional exigir.
Detalhe em `docs/asset/ASSET_VERTICAL_BOOTSTRAP_PLAN.md`.

---

## Alternativas consideradas

| Alternativa | Motivo da rejeição (nesta fase) |
|---|---|
| **B — Core como pacote versionado** (workspace `uv` ou índice privado) | Introduz versionamento, changelog de contrato e matriz de compatibilidade enquanto o Core ainda muda toda semana. Benefício (releases independentes) ainda não é necessário. Registrada como evolução futura. |
| **C — Core em repositório independente** | Já rejeitada em ADR-0001. Mudança de contrato vira PR-multi-repo + release; testes ponta a ponta exigem orquestração; risco alto de divergência de versão entre verticais. |
| **D — git subtree/submodule** | Pior dos dois mundos: atrito de multi-repo sem fronteira limpa de pacote; versionamento por SHA opaco; CI frágil. |
| **Manter ambiente de migrations único** e importar `asset_infrastructure` no `env.py` do Core | Amplia a exceção de fronteira para N verticais; acopla o ciclo de release de Core + todas as verticais; impede versionar/reverter uma vertical isolada. |
| **Copiar `core_*` para `asset/core/`** | Explicitamente proibido pelo objetivo: cria fork interno, duplica garantias, diverge. |

---

## Consequências

### Positivas

- Custo incremental próximo de zero; nenhuma infraestrutura nova.
- Garantias arquiteturais atuais (Core ⊥ vertical, camadas, isolamento por
  Organization) preservadas e agora verificadas para N verticais.
- Uma única implementação do Core; forkar exige um PR visível que os testes
  reprovam.
- Asset nasce no modelo correto de migrations por vertical.
- Core e verticais continuam podendo evoluir no mesmo commit quando um contrato
  aprovado exigir.

### Negativas

- Autonomia da vertical permanece **lógica**, não física: uma mudança incorreta
  no Core pode, em tese, afetar duas verticais no mesmo deploy. Mitigação: teste
  de estabilidade da superfície pública + suíte de integração.
- `main.py` e `alembic.ini` ganham um registry e múltiplos `version_locations`
  (complexidade pequena, paga uma vez).
- Assimetria temporária: Asset com migrations próprias enquanto Livestock ainda
  vive sob o Core, até a extração de Livestock ser feita.

### Riscos e controles

| Risco | Controle |
|---|---|
| Extração de migrations altera o schema | Teste de diff `pg_dump --schema-only` antes/depois; fazer para Livestock em PR isolado |
| Teste de fronteira generalizado vira aprovação vazia para vertical inexistente | Guarda que falha se nenhuma vertical foi verificada (mesma filosofia de `require_existing_root`) |
| Refactor de `apps/api` altera contrato | Snapshot de `/openapi.json` idêntico antes/depois |
| `sustainment_*` e `asset_*` acoplarem demais | ADR do slice decide se são um módulo vertical (dois pacotes que se referenciam) ou duas verticais irmãs isoladas |
| Tentação de extrair "abstração de ERP" comum às duas verticais | ADR-0001 §"extração deve responder a necessidade concreta" — não antes de haver uso nas duas |

---

## O que esta ADR não decide

- O modelo de domínio de Titan Asset (entidades, agregados, invariantes) — vai
  para a ADR do primeiro slice.
- Se `sustainment_*` é um pacote da mesma vertical de `asset_*` ou uma vertical
  irmã — decisão do slice, a partir dos invariantes.
- O momento de adotar a Opção B (Core versionado).
- Estratégia de frontend multi-vertical (`apps/web`).
- Formato dos contratos de integração externa de Asset (ERP/PLM/WMS/logística).
- Quando extrair o ambiente de migrations de Livestock.

---

## Critérios de aceitação

Esta ADR pode ser aceita quando:

- os seis documentos de `docs/asset/` estiverem revisados;
- a regra vertical ⊥ vertical estiver acordada como vinculante;
- a direção "ambiente de migrations por vertical, `MetaData` única" estiver
  aceita;
- as convenções de composição (`apps/api/<vertical>/`, registry, despacho no
  worker) estiverem aceitas;
- estiver claro que o primeiro passo de execução é **apenas** generalizar o teste
  de fronteira arquitetural, sem mover código de produção.

## Plano de reversão

Enquanto nenhum código for movido, reverter é atualizar esta ADR para
`DESCARTADA`. Depois de iniciada a execução, cada passo é um PR independente e
revertível (ver `docs/asset/CORE_EXTRACTION_RISKS.md` §4); o passo de
migrations é o único com cuidado extra e deve ser feito isolado.

---

## Reconciliação (10/09/2026) — desenvolvimento paralelo e revisão adversarial

Esta ADR permanece `PROPOSTA`. A revisão adversarial (`docs/architecture/PHASE0_ADVERSARIAL_REVIEW.md`) e a
restrição de desenvolvimento paralelo (Livestock ativo sob o Codex) exigem os ajustes abaixo **antes** de esta
ADR poder ser aceita. A governança de paralelismo está no rascunho de ADR
`docs/adr/draft-20260910-governanca-de-desenvolvimento-paralelo-de-verticais.md`, que **complementa** esta.

### Substituições

- **§3 (ambiente de migrations por vertical) é substituído** pela estratégia **Opção D → C** de
  `docs/architecture/MIGRATION_CONCURRENCY_STRATEGY.md`: cadeia de Livestock intocada agora; Asset com
  `env.py`/`versions/` próprios, *branch label* `asset`, filtro `include_object` por `titan.module_owner` +
  allowlist de FK do Core, `depends_on` para a revisão do Core que cria `core_identity.organizations`;
  `alembic upgrade head` → `alembic upgrade heads` repo‑wide em PR de Shared Integration próprio. A extração
  do ambiente de Livestock é `BLOCKED_WHILE_LIVESTOCK_ACTIVE` (janela de integração coordenada com o Codex).
- **§4 (convenções de composição):** mover `apps/api/livestock_*.py` para `apps/api/livestock/` é
  `REQUIRES_INTEGRATION_WINDOW`. O `apps/api/_registry.py` e `apps/api/asset/` são aditivos e podem nascer
  antes; a migração física dos módulos de Livestock ocorre em janela coordenada.

### Impacto de Segurança (não constava; §30)

Isolamento reforçado, não enfraquecido: a regra vertical ⊥ vertical passa a ser verificada por CI (import,
acesso a persistência, ownership de migration, namespace de evento). RLS por Organization (ADR‑0002/0003)
permanece a fronteira de isolamento de dados. Verticais não editam `core_*`/`shared_kernel` em branch de
feature; mudança de primitiva de identidade/RLS/`organization_context`/integridade é Shared Integration com
regressão obrigatória dos cenários de isolamento de Livestock sob role restrita. Escopo OM/Site (H2) fica
diferido para a discovery — proibido introduzir escopo sub‑Organization sem `CORE_CHANGE_REQUEST`.

### Impacto de Auditoria (não constava; §30)

A cadeia de integridade (`event_integrity_table`) é escopada por `record_owner_organization_id`
(`events.py:247‑256`). Com duas verticais no mesmo tenant, os `append` interleavam numa cadeia e serializam.
Classificado como **garantia global do Core**, não acoplamento vertical↔vertical (decisão F de
`docs/architecture/DECISIONS_REQUIRED_PHASE0.md`); exige teste de concorrência antes do 1º slice de Asset.
Qualquer alteração da semântica de integridade é Shared Integration com ADR própria. O ledger
(`docs/CHECKLIST_DE_IMPLEMENTACAO.md`) permanece append‑only por lane.

### Critérios de aceitação — adendo

Além dos cinco itens já listados: (6) os 8 documentos de `docs/architecture/` revisados; (7) invariante
`PARALLEL_VERTICAL_SAFETY` acordado como vinculante; (8) decisões A e C de `DECISIONS_REQUIRED_PHASE0.md`
aceitas; (9) estratégia de migrations D → C aceita como oficial. Fica explícito que a aceitação desta ADR
cobre **estrutura de repositório e paralelismo**, não a discovery de domínio de Asset (§48/§49 da constituição
seguem pendentes — H3).
