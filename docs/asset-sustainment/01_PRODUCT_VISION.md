# 01 — PRODUCT VISION — Titan Asset & Sustainment

**Status:** Discovery. Sujeito a `PROCEED`/`DEFER`/`REJECT` (Development OS, `AGENTS.md`).
**Data:** 10 de setembro de 2026
**Lane:** Asset (`vertical/asset/*`). Nenhum código.
**Autoridade acima deste documento:** `VISION.md`, `DOMAIN.md`, `ARCHITECTURE.md`, ADRs aceitas, e a
constituição multi‑agente (arquivo de entrada do projeto). Em conflito, aquilo vence.

---

## 1. O que Titan Asset & Sustainment é

Uma **camada de verdade operacional** para o ciclo de vida de um ativo técnico complexo (um veículo
militar/industrial e suas configurações) — da engenharia e produção à operação, manutenção, consumo de
peças, reposição e realimentação de confiabilidade — sob **contratos de sustentação (SLI)** que impõem
obrigações mensuráveis ao fornecedor.

Não é um CMMS/EAM/ERP genérico nem um clone de produto existente. O que a diferencia:

- **Estado explicável, não opaco.** "Disponível = 3" nunca aparece sozinho: aparece com a derivação
  (em mãos, reservado para produção, reservado para SLI, reservado para venda, em quarentena). "Prioridade =
  92" aparece com os fatores que a compõem. (constituição §1, §22)
- **Aplicabilidade com evidência, não booleano.** "Peça X serve no veículo Y" só existe como
  `Applicability` datada e versionada (modelo/variante/configuração/faixa de série/data/retrofit).
  (constituição §7, §42)
- **Tempo correto.** O sistema responde "qual era a configuração deste veículo em 2026‑03‑01?" e "quais
  regras contratuais valiam quando este reparo aconteceu?". Correção não apaga histórico. (constituição §25,
  §24)
- **Contrato SLI como bounded context de primeira classe** que influencia comportamento operacional
  (SLA, cobertura, entitlement de peça/serviço), versionado, nunca reavaliado com a definição de hoje.
  (constituição §17)

## 2. Para quem

| Persona | Pergunta que Titan responde |
|---|---|
| Técnico de oficina | "O que faço agora, com que peça, e o que está me bloqueando?" |
| Planejador de oficina | "Que ordem de serviço tem prioridade, e por quê?" |
| Logístico | "Onde a peça existe, quanto está realmente disponível, e posso reservar?" |
| Gestor de contrato SLI | "As obrigações de disponibilidade e SLA para esta OM estão sendo cumpridas?" |
| Engenharia | "Que componente falha de forma recorrente, em que configuração?" |
| Representante da OM / cliente | "Meus veículos estão disponíveis? Qual o status dos reparos?" |

Titan é **orientado a situação**, não a módulo (constituição §20, §43): o usuário entra por "o que exige
atenção", não por "qual menu abрir".

## 3. Marco de referência (constituição §47)

Um veículo sob contrato SLI desenvolve uma necessidade de manutenção. Titan responde, com evidência para
cada resposta:

1. Qual veículo? 2. Qual configuração? 3. Qual OM/site? 4. Qual contrato? 5. Qual versão do contrato?
6. Que ação de manutenção é necessária? 7. Qual peça? 8. A peça é aplicável? 9. Onde essa peça existe?
10. Quanto está realmente disponível? 11. Pode ser reservada? 12. O que bloqueia a execução?
13. Qual o SLA? 14. O que a oficina deve fazer a seguir? 15. Por que essa tarefa é prioritária?
16. Que evidência sustenta cada resposta?

Se a arquitetura não responde isso de forma limpa, **não está pronta** — e o primeiro slice existe para
provar que responde.

## 4. Não‑objetivos desta fase

- Não é planejamento de manufatura (BOM explosion, kitting, line supply) — só interfaces e bounded contexts.
  (constituição §13)
- Não é procurement completo — a demanda de material do Work Order **para** na fronteira "falta detectada".
  (constituição §14)
- Não é o catálogo 3D interativo nem AR — a arquitetura deve **permitir** essa evolução sem reescrita, via
  adapters; não a implementa. (constituição §9, §10)
- Não é analytics de confiabilidade (MTBF/MTTR) — só garante que o histórico é capturado para alimentá‑la
  depois. (constituição §19)
- Não é IA — nenhuma pontuação de prioridade oculta; prioridade é determinística e explicável.
  (constituição §22, §23)

## 5. Princípio de escopo

MVP = escopo limitado com **fronteiras corretas**, não arquitetura fraca (constituição §46). Um workflow
ponta a ponta completo vale mais que vinte CRUDs desconexos. O primeiro slice cobre:

```
Vehicle + Part + Configuration + Stock Location + Inventory + SLI Contract
+ Work Order + Material Reservation + Workshop Dashboard
```

## 6. Critério de sucesso da visão

- Toda resposta importante é rastreável aos fatos que a produziram (constituição §50).
- Nenhuma fronteira arquitetural do Titan é violada; `packages/core_*` não ganha conceito de Asset.
- A revisão adversarial (Claude) não tem BLOQUEADOR aberto; a revisão de integração (Gemini) não tem defeito
  crítico de workflow.
