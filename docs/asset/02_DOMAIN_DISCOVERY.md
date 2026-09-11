# 02 — DOMAIN DISCOVERY — Titan Asset & Sustainment (primeiro slice)

**Status:** Discovery. **Data:** 10/09/2026. **Lane:** Asset. Nenhum código.
**Escopo:** o corte do primeiro slice (`01_PRODUCT_VISION.md` §5). Subdomínios fora do slice são
**nomeados** para fixar fronteira, não modelados.

Método (constituição §33, §38): partir dos **fatos, transições, obrigações, evidência e consequências**, não
de telas. Para cada área: o que o negócio precisa afirmar, que pergunta o sistema deve responder, e **onde um
invariante transacional deixa de valer** (é isso que corta bounded context — `ASSET_VERTICAL_BOOTSTRAP_PLAN.md`
§2, não o nome do subdomínio).

---

## 1. Cenários‑fonte (constituição §41)

| ID | Cenário | O que estressa |
|---|---|---|
| **A** | Manutenção corretiva com estoque local | fluxo feliz ponta a ponta; reserva na mesma transação da demanda |
| **B** | Manutenção corretiva **sem** estoque local | `WAITING_MATERIAL`, transferência, `IN_TRANSIT`, recebimento, reserva pós‑chegada |
| **C** | Produção × SLI × Venda disputam a mesma peça | disponibilidade **não** é quantidade física; política de reserva/alocação; decisão explicável e auditável |
| **D** | Supersessão de peça | instalações históricas preservadas; planejamento usa a substituta aplicável |
| **E** | Contrato expira durante Work Order aberto | condições contratuais de cada evento preservadas (temporal) |
| **F** | Catálogo 3D de manutenção | frontend **não** possui lógica de aplicabilidade |

O slice implementa **A** e **B** ponta a ponta; **C**, **D**, **E** entram como invariantes exercidos por
teste, não como fluxo completo; **F** só como fronteira arquitetural.

---

## 2. Áreas de descoberta

### 2.1 Ativo / Veículo

**Fatos a afirmar:** este veículo existe, com número de série/chassi/frota; pertence a uma Organization
operadora; está alocado a uma OM/site; tem uma **configuração‑base vigente**; tem leituras de horímetro/
hodômetro; tem um **estado técnico de ciclo de vida**; tem cobertura contratual.

**Perguntas:** qual a configuração do veículo EB‑XXXXX **hoje** e **em 2026‑03‑01**? Ele está disponível,
degradado, em manutenção, indisponível? A que OM pertence? Sob qual contrato?

**Fronteira de consistência:** `Vehicle` + referência à `ConfigurationBaseline` vigente. Um `Vehicle` tem
**exatamente uma** baseline efetiva no instante T; a transição de estado é monotônica e auditável. Meter
readings são append‑only e não retrocedem sem evento de correção explícito.

**Não modela agora:** hierarquia System→Subsystem→Assembly→Component em profundidade (constituição §6) —
só o suficiente para uma falha apontar para uma posição. Retrofit/campanha: nomeado, fora do slice.

### 2.2 Peça (Part Master)

**Fatos a afirmar:** esta peça é um objeto técnico (part number, descrição, fabricante, PN do fabricante,
NSN quando aplicável); tem **revisões** com cadeia de supersessão; tem **aplicabilidade** a
modelos/configurações/faixas de série; tem estado de ciclo de vida (ativa, superseção, obsoleta,
alternativa). A existência da Peça **não implica estoque** (constituição §8).

**Perguntas:** esta peça é aplicável a este veículo nesta configuração? Qual a revisão vigente? Qual a
substituta quando superseção? Quais alternativas/intercambiáveis?

**Fronteira de consistência:** `Part` + suas revisões + cadeia de supersessão (acíclica) + grupo de
intercambiabilidade (simétrico). `Applicability` é uma **asserção datada com evidência**, nunca um booleano
(constituição §42). Definição técnica e estado logístico são conceitos **separados**.

**Não modela agora:** Engineering BOM vs Manufacturing BOM vs Service BOM como estruturas distintas
(constituição §7) — o slice usa só "aplicabilidade de peça a configuração"; as três BOMs são nomeadas e
diferidas. Mídia técnica / 3D: fronteira apenas.

### 2.3 Configuração

**Fatos a afirmar:** esta baseline de configuração vale para este modelo/variante, com faixa de
efetividade; ela evolui por revisão com supersessão; distingue as‑designed / as‑built / as‑delivered /
as‑maintained.

**Perguntas:** que baseline se aplica a este veículo? Que revisão de desenho valia quando a peça foi
instalada (constituição §25)?

**Fronteira de consistência:** junto de `Vehicle` no slice (mesma transação de "definir baseline"). Faixas
de efetividade **não se sobrepõem** para a mesma posição; a cadeia de revisão é **acíclica**.

**Não modela agora:** effectivity multi‑dimensional completa (lote de produção × data × retrofit ×
equipamento opcional) — o slice cobre modelo + faixa de série + data.

### 2.4 Inventário

**Fatos a afirmar:** existe quantidade desta peça **nesta localização**, **com este propósito**
(produção / serviço‑SLI / OM remota / comercial), **neste status** (em mãos, reservado, alocado, em
trânsito, quarentena, inspeção, dano), **deste dono** (empresa / cliente / consignação), por lote/série
quando exigido. Estoque é uma **rede contextual**, não `Peça → quantidade` (constituição §11).

**Perguntas:** onde a peça existe? Quanto está **realmente disponível** para este propósito? Posso reservar?
Por que a disponível é menor que a física?

**Fronteira de consistência:** `StockPosition` por `(peça, localização, propósito, status)` + `Reservation`.
Invariante central: `disponível(peça, localização, propósito) ≥ 0` e nenhuma reserva referencia quantidade
inexistente. Reserva de estoque protegido por contrato **não** pode ser tomada por outro propósito
(cenário C) — a política de alocação decide, e a decisão é **explicável e auditável**.

**Não modela agora:** rede logística completa (central→regional→oficina→OM) com replenishment/reorder point/
safety stock/cycle counting (constituição §12) — o slice tem 2..3 localizações e uma transferência simples
(cenário B). Recomendação preditiva de estoque: nomeada, fora.

### 2.5 Contrato SLI / Sustentação

**Fatos a afirmar:** este contrato cobre estes modelos/veículos/OMs por um período; define serviços
cobertos, peças cobertas/excluídas, regras de mão de obra e deslocamento, **SLA de resposta e de reparo**,
metas de disponibilidade, limites de serviço, regras financeiras; tem **emendas e versões**.

**Perguntas:** para este veículo → OM → contrato ativo → **versão do contrato** → cobertura → SLA aplicável
→ obrigação operacional. Que condições valiam quando **este** reparo aconteceu (cenário E)?

**Fronteira de consistência:** `SLIContract` + suas `ContractVersion`. Regras contratuais são **versionadas**;
uma Work Order resolve para **exatamente uma** linha de contrato ativa no instante do serviço; o
`Entitlement` não excede a cobertura contratada. Work Orders históricas **nunca** são avaliadas com a
definição de hoje.

**Não modela agora:** penalidades/créditos financeiros, relatórios contratuais, cálculo de disponibilidade
agregada da frota coberta — nomeados, fora. O slice resolve **cobertura + SLA + entitlement de peça**.

### 2.6 Manutenção / Work Order

**Fatos a afirmar:** existe uma solicitação/necessidade; ela vira uma **Work Order** com tarefas; a WO tem
demanda de material, mão de obra, ferramentas; a WO passa por estados com transições autorizadas; a WO
registra falha, diagnóstico, causa, resolução, disposição do componente removido; a WO é validada e o
veículo retorna ao serviço; história e métricas atualizam.

**Perguntas:** o que a oficina faz a seguir e por quê (prioridade explicável)? O que bloqueia esta WO?
Qual o SLA restante?

**Fronteira de consistência:** `WorkOrder` + tasks + demanda de material é **um** agregado transacional
(constituição §15) — mas **não** um "God Aggregate": a reserva de estoque, quando local e síncrona, entra
na mesma transação; se cross‑warehouse/assíncrona, vira fluxo próprio com evento (cenário B). Invariantes:
a WO não fecha com tarefa obrigatória aberta; material reservado ≤ material demandado; toda transição emite
evento + registro de auditoria + motivo quando exigido.

**Não modela agora:** máquina de estados final (será derivada — constituição §16), preventiva/inspeção/
campanha/retrofit, agendamento de recursos, `MaintenancePlan`. `FailureRecord` entra **leve** (o suficiente
para "que ação é necessária" e para alimentar confiabilidade depois).

### 2.7 OM / Site (Customer Site)

**Fatos a afirmar:** esta OM é uma entidade organizacional/site (não texto livre — constituição §18); tem
veículos, estoque local, oficina, contatos, cobertura contratual; pertence a uma Organization (cliente ou
operadora).

**Pergunta em aberto (decisão G / H2):** OM/Site é (a) uma partição **dentro** da Organization operadora,
(b) uma Organization própria com concessão de cobertura cross‑Organization, ou (c) um escopo de primeira
classe no Core? Ver `11_AUTHORIZATION_MODEL.md`. **Nenhum conceito `OM`/`Vehicle`/`Workshop` entra no
Core** (constituição §18).

---

## 3. Loop de ciclo de vida que o slice precisa fechar (constituição §19)

```
FALHA → WORK ORDER → DIAGNÓSTICO → CAUSA → REPARO → PEÇAS/MÃO DE OBRA
     → RETORNO AO SERVIÇO → DADO DE CONFIABILIDADE (capturado, não analisado no slice)
```

## 4. Saídas desta descoberta

- Vocabulário → `03_UBIQUITOUS_LANGUAGE.md`
- Fronteiras de contexto → `04_BOUNDED_CONTEXT_MAP.md`
- Entidades/agregados → `05_DOMAIN_MODEL.md`, `06_AGGREGATE_ANALYSIS.md`
- Invariantes → `07_INVARIANTS.md`
- Eventos/comandos → `08_DOMAIN_EVENTS.md`, `09_COMMAND_MODEL.md`
- Autorização e a decisão G → `11_AUTHORIZATION_MODEL.md`
- Riscos e sequência → `19_RISK_REGISTER.md`, `20_EXECUTION_ROADMAP.md`

**Recomendação de discovery:** `PROCEED` para o corte do slice. As condições — decisão B (`sustainment` =
mesma vertical), decisão F (teste de concorrência da cadeia de integridade) e decisão G (escopo OM/Site) —
foram todas **aceitas em 10–11/09/2026** (`docs/architecture/DECISIONS_REQUIRED_PHASE0.md`).
