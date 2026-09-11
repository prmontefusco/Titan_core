# MULTI_AGENT_ARCHITECTURE_REVIEW — Titan Asset & Sustainment, primeiro slice

**Status:** Revisão concluída. **Data:** 11 de setembro de 2026. **Lane:** Asset.
**Autoria:** constituição §49 pede três vozes (Codex/Claude/Gemini). Este projeto opera com **dono + Claude
apenas** — sem Codex nem Gemini/Antigravity dedicados a esta vertical (decisão do dono, 11/09/2026). Este
documento é a revisão de **um agente de engenharia** cobrindo as três perguntas do §49, não um consenso de
três agentes independentes. Onde isso importa (não há segunda opinião), digo explicitamente.

**Objeto:** `docs/asset/01`…`09`, `11`, `19`, `20` + o ADR e a SPEC do primeiro slice, já **aprovados** pelo
dono. Esta revisão **encontrou e corrigiu** lacunas nesses documentos antes de considerá-los prontos para
A2 — as correções já estão aplicadas (não é uma lista de pendências).

---

## 1. As três perguntas do §49

### "Pode ser implementada incrementalmente sem quebrar o Titan?" (papel Codex)

**Sim**, com evidência já produzida, não só teórica:

- A stack de Shared Integration (`integration/core/parallel-vertical-foundation`, 10 commits) já prova que
  o Core aceita uma segunda vertical sem mudar comportamento: `alembic upgrade heads` produz schema idêntico
  byte‑a‑byte ao `upgrade head` anterior; `tests/architecture` varre `asset` automaticamente via manifesto;
  `packages/core_*` não ganhou nenhum símbolo por causa de Asset.
- A decisão F (cadeia de integridade por agregado) está confirmada por teste de concorrência real — a
  suspeita de acoplamento entre Livestock e Asset no mesmo tenant **não se sustentava**.
- Cada passo A1–A7 do roadmap (`20_EXECUTION_ROADMAP.md` §3) é um PR isolado, sem tocar `core_*`; A3 tem
  critério de aceite objetivo (`pg_dump` idêntico, `alembic check` limpo).
- Risco residual: A‑M1 (ambiente de migrations de Asset) é o único passo de infraestrutura ainda não
  executado — mas o mecanismo (`make_include_object`) já está implementado e testado (S‑M2, 9 casos), só
  falta ligá‑lo a um `env.py` real.

### "Que suposições poderiam fazer esta arquitetura falhar em produção?" (papel Claude — adversarial)

Ver §2 (achados classificados). As suposições mais perigosas que eu revisei e que **não** se confirmaram
más (ou seja, resisti à tentação de aceitar o design como escrito e procurei ativamente onde ele quebraria):

1. *"O `site_scope` pode ser recalculado a cada request via `Decision` do Core"* — **falsa como estava
   escrita**; corrigida em `11_AUTHORIZATION_MODEL.md` §2 (HIGH, ver §2).
2. *"Uma WorkOrder sempre resolve para exatamente uma linha de contrato"* — **não garantida** por nenhum
   invariante anterior; corrigida com I‑SLI‑6 (MEDIUM, ver §2).
3. *"Duas WorkOrders reservando material concorrentemente sempre convergem"* — verdade, mas só por detecção
   de deadlock do Postgres, não por design; documentada ordem determinística de lock (LOW, ver §2).
4. *"A cadeia de integridade acopla verticais no mesmo tenant"* (H1 original) — **falsa**, corrigida em
   `docs/architecture/PHASE0_ADVERSARIAL_REVIEW.md` e propagada aos documentos do slice que ainda citavam a
   versão errada (`08`, `11`, `CORE_REUSE_ASSESSMENT.md`).

### "Um usuário real completa o fluxo ponta a ponta sem navegar a arquitetura interna?" (papel Gemini — integração/workflow)

Percorri os cenários A e B da SPEC (`docs/asset/specs/approved/2026-09-10-titan-asset-primeiro-slice.md`)
como se fosse cada persona de `11_AUTHORIZATION_MODEL.md` §1, perguntando "essa pessoa consegue fazer isso
só com o que está documentado, sem entender `Evaluation`/`Decision`/agregado?":

- **Técnico de oficina**: abre a fila (`GetWorkshopDashboard`) → clica numa WO. **Faltava** a query de
  detalhe de uma WO — só existia a lista. **Corrigido**: `GetWorkOrder(id)` adicionada a `09` §3.
- **Planejador**: vê a frota (`GetFleetView`) → clica num veículo. **Faltava** `GetVehicle(id)` — mesma
  lacuna, outro agregado. **Corrigido**.
- **Gestor de contrato SLI**: a persona diz explicitamente "acompanha SLA/cobertura... de tudo sob aqueles
  contratos" (`11` §1), mas a única query de contrato era por‑veículo. **Corrigido**: `GetContractSLASummary`
  adicionada.
- **Logístico**: `RequestStockTransfer`/`ReserveStock`/`AdjustStock` cobrem o fluxo; nenhuma lacuna
  encontrada.
- **Representante da OM**: `GetFleetView(site)` com `site_scope` restrito cobre "só a própria OM" — nenhuma
  lacuna.
- **Nenhuma lógica de negócio foi encontrada implícita no frontend** — toda decisão (aplicabilidade,
  disponibilidade, entitlement, prioridade) tem endpoint de servidor com breakdown explicável; o frontend
  consome, não decide (constituição §43).
- **Duplicação de capacidade com Livestock**: nenhuma — os domínios (veículo/peça/contrato de sustentação vs.
  animal/lote/mercado) não se sobrepõem.

**Veredito:** com as correções aplicadas, sim — as seis personas completam seus fluxos documentados sem
precisar entender arquitetura interna. Antes das correções, três delas (técnico, planejador, gestor de
contrato) ficariam sem uma tela de detalhe básica.

---

## 2. Achados (classificados, constituição §31)

Todos os achados abaixo já foram **corrigidos nos documentos** (não é uma lista de pendências).

### HIGH

**H‑A1 — `site_scope` como `Decision` recalculada por request era subespecificado, com risco de má
implementação em A4.**
*Cenário:* `11_AUTHORIZATION_MODEL.md` §2 dizia "uma Policy/Rule governada resolve... produz um Decision" sem
dizer quando. Lido literalmente, um implementador poderia invocar o pipeline completo de
`evaluation_service`/`decision_service` **a cada comando/query** — persistindo um `Decision` por leitura.
*Consequência:* performance inviável (escrita de `Decision` em toda leitura) e uso incorreto do conceito
`Decision` (que representa decisão de negócio auditável, não cache de autorização).
*Correção:* `11` §2 agora especifica que o `site_scope` é resolvido **uma vez por sessão/token**, embutido no
`AssetOperationContext`, recalculado só em renovação de sessão ou invalidação por mudança de
membership/grant.
*Teste de regressão a exigir em A4:* medir nº de `Decision`s de escopo persistidas por sessão de usuário
(deve ser ~1, não 1 por request).

### MEDIUM

**M‑A1 — Cobertura de contratos SLI concorrentes sobre o mesmo veículo sem invariante de unicidade.**
Ver `07_INVARIANTS.md` I‑SLI‑6 (novo). Sem ele, `OpenWorkOrder`/`ResolveEntitlement` não tinham base
determinística caso duas `CoverageLine`s de contratos diferentes casassem para o mesmo veículo/instante.

**M‑A2 — Superfície de leitura incompleta para 3 das 6 personas (técnico, planejador, gestor de contrato).**
Ver §1 "papel Gemini" acima. Corrigido com `GetWorkOrder`, `GetVehicle`, `GetContractSLASummary` em
`09_COMMAND_MODEL.md` §3 (+ permissões correspondentes em `11` §3).

**M‑A3 — Transição T7 da máquina de estados (autorização de exceção) sem comando correspondente.**
A ADR do slice descreve T7 ("gestor de contrato autoriza exceção") mas `09_COMMAND_MODEL.md` não tinha
nenhum comando que produzisse essa `Decision` de exceção. Corrigido com `AuthorizeEntitlementException`.

### LOW

**L‑A1 — `AdjustStock` não especificava qual bucket de `StockQuantities` ajusta.** Corrigido: `delta_by_status`
nomeia o(s) bucket(s); cada um ≥ 0 individualmente.

**L‑A2 — Ordem de aquisição de locks não especificada para `ReserveMaterialForWorkOrder` com múltiplas
peças.** Sem uma ordem determinística, duas WOs com demandas sobrepostas em ordens diferentes dependem só da
detecção de deadlock do Postgres (correto, mas gera retry evitável). Corrigido: ordem por `stock_position_id`
crescente, documentada em `09`.

**L‑A3 — `FleetView` citada em `08`/`09` mas nunca formalmente introduzida como read model em `05`/`06`.**
Corrigido: `05_DOMAIN_MODEL.md` §2.6 novo; `06_AGGREGATE_ANALYSIS.md` atualizada.

### OBSERVAÇÃO

**O‑A1 — Referências obsoletas à cadeia de integridade "por Organization" (H1 original) sobreviviam em
`08_DOMAIN_EVENTS.md`, `11_AUTHORIZATION_MODEL.md` e `CORE_REUSE_ASSESSMENT.md`** mesmo depois da decisão F
ter sido corrigida em `docs/architecture/`. Lição: quando uma finding upstream é corrigida, `grep` os
documentos que a citam antes de considerar a correção completa — não bastava corrigir só onde o erro
apareceu primeiro. Todas as três referências corrigidas nesta revisão.

**O‑A2 — `RecordFailure` (comando WO‑scoped) vs. o campo `failure` de `OpenWorkOrder` têm sobreposição de
propósito não totalmente clara na documentação** (registro inicial vs. registros adicionais/recorrentes).
Não é um defeito estrutural — ambos são coerentes com o domínio — só falta uma frase explícita em A1/A4
distinguindo os dois. Não corrigido agora (granularidade de implementação, não de arquitetura); marcado para
A4.

---

## 3. Acordos (o que a revisão confirma como correto)

- O corte de dois módulos numa vertical (B1) é a fronteira certa para os invariantes do slice — a operação
  "reservar material" genuinamente precisa de transação única no cenário A.
- A máquina de estados da WO (T1–T17) é derivada dos invariantes reais, não copiada de outro produto, e cada
  transição tem evento + auditoria.
- Entitlement e prioridade como `Evaluation → Decision` governados (não `if`) é a escolha certa e está
  consistentemente aplicada em todos os documentos revisados.
- A separação Core⊥vertical e vertical⊥vertical está preservada em todo o slice — nenhum documento propõe
  tocar `packages/core_*`.
- G1 (escopo de site na vertical, RLS por Organization no Core) é proporcional ao que se sabe hoje; G2/G3
  ficam corretamente adiadas.

## 4. Riscos não resolvidos (não bloqueiam A2, mas precisam de dono/atenção em A3–A4)

- **A‑M1 real** (ligar `make_include_object` a um `env.py` de Asset) ainda não foi executado — é código, fica
  para quando A2/A3 começarem.
- **Performance do predicado `site_scope`** em queries com muitos sites (`WHERE site_id IN (...)` com lista
  grande) não foi medida — atenção em A4/A7 se um cliente tiver centenas de sites.
- **G2 vs G1** depende da estrutura real do primeiro cliente — não decidível sem esse dado; A1 já registrou
  a opção.
- Sem uma segunda pessoa/agente revisando este documento, o risco de um ponto cego meu não é mitigado por
  segunda opinião — só pela sua avaliação quando tiver tempo (conforme o modelo de trabalho combinado).

## 5. Bloqueios arquiteturais

**Nenhum.** B1 (BLOQUEADOR da Fase 0, migrations) está resolvido pela stack de Shared Integration. Nenhum
achado desta revisão do slice chegou a nível BLOQUEADOR — os HIGH/MEDIUM encontrados foram lacunas de
documentação/especificação, já corrigidas, não falhas de arquitetura que exigissem redesenho.

## 6. Slice proposto (confirmado, sem mudança)

Vehicle + Part + Configuration + StockLocation + Inventory + SLI Contract + Work Order + Material
Reservation + Workshop Dashboard + Fleet View, cenários A e B ponta a ponta, C/D/E por teste — conforme
`docs/asset/adr/draft-20260910-primeiro-slice-titan-asset-sustainment.md` e a SPEC aprovada.

## 7. Critérios de aceite propostos para A2 em diante

Os já registrados em `20_EXECUTION_ROADMAP.md` §3 (por passo A1–A7) permanecem válidos. Adiciono dois, fruto
desta revisão:

- **A4** deve incluir o teste de "nº de `Decision`s de escopo por sessão ≈ 1" (H‑A1).
- **A2/A3** devem incluir teste de I‑SLI‑6 (cobertura de contrato ambígua recusada, não escolhida
  silenciosamente).

---

## 8. Fechamento

Discovery revisada. Sem BLOQUEADOR. HIGH/MEDIUM encontrados e corrigidos nos próprios documentos de
discovery (não ficam como dívida). Este documento satisfaz o critério "Discovery revisada... sem BLOQUEADOR
aberto; `MULTI_AGENT_ARCHITECTURE_REVIEW.md` produzido" da ADR do slice — ver atualização do checklist de
critérios de aceitação naquele documento.
