# BuyerPolicy Fase 3 — Discovery & Requisitos

**Data:** 19 de agosto de 2026  
**Sessão:** Discovery (Pré-Planning)  
**Commit base:** 6732580 (Fase 2 concluída)

---

## Contexto Histórico

- **Fase 1 (ADR-0064, NEXT-09):** Autoavaliação privada — comprador avalia sua própria Policy INTERNAL_POLICY isoladamente
- **Fase 2 (ADR-0065, NEXT-10):** Compartilhamento mínimo — comprador compartilha Policy CONTRACT com fornecedor; fornecedor autoavalia seus dados contra Policy recebida; resultado permanece isolado (não toca matriz)
- **Fase 3 (proposto):** Expandir para capturing de intenção, negociação, composição regulatória

---

## Requisitos Indicados (ADR-0065 §23 / Risco Table)

### 1. Decision & Proposal (Feedback do Fornecedor)

**Problema:** Fase 2 produz avaliação, mas:
- Comprador não sabe se fornecedor viu o critério
- Fornecedor não consegue escalar não-conformidade
- Sem trilha de reconhecimento explícito

**Caso de uso:**
```
1. Comprador compartilha Policy com fornecedor (grant ativo)
2. Fornecedor avalia e recebe resultado "NAOCONFORM"
3. Fornecedor quer contestar/explicar → criar Decision/Proposal
4. Comprador revisa proposta do fornecedor → aprova/rejeita/reenvia
5. Audit trail completo: o que cada parte viu/rejeitou/quando
```

**Escopo em Dúvida:**
- Quem cria a Decision — fornecedor unilateralmente ou comprador em nome dele?
- A avaliação é modificável ou imutável após criação?
- Acknowledgment é obrigatório ou opcional?

---

### 2. Composição com Matriz Regulatória (ADR-0044)

**Problema:** Hoje Policy contratual é completamente separada:
```
Elegibilidade regulatória (matriz, rules governadas) ← não toca
             ||
             ↓
BuyerPolicy compartilhada ← isolada
```

**Caso de uso:**
```
Fornecedor avalia contra Policy contratual (Fase 2) → CONFORM
Comprador vê que fornecedor passou no contrato
Mas precisa também CONFIRMAR que passou na matriz regulatória antes de contratação
```

**Semântica em Dúvida:**
- A avaliação compartilhada aparece lado-a-lado com matriz em tela?
- Policy contratual bloqueia elegibilidade ou é informativa?
- Qual vence quando há conflito?

---

### 3. Rate-Limiting e Auditoria de Acesso (Risco Table)

**Problema:** Risco baixo, mas apontado — "Fornecedor consegue derivar dataset do comprador por força bruta"

**Escopo:**
- Quantas avaliações por segundo um grant permite?
- Rate-limit por grant, por Organization, global?
- Auditoria registra cada tentativa?

---

### 4. Avaliação com Sujeitos de Outra Organization

**Problema:** Fase 2 `POST /shared-policies/{policy_id}/evaluate` reutiliza `LivestockFactProvider`, que só acessa facts da Organization própria

**Caso de uso:**
```
Fase 2: Fornecedor avalia sua própria Property/Animal contra Policy contratual ✓
Fase 3: Comprador consegue rodar uma avaliação compartilhada em nome do fornecedor?
        OU fornecedor consegue compartilhar seus animals/properties também?
```

**Alternativas:**
- A. Apenas fornecedor avalia seus próprios sujeitos (expand FieldScope apenas)
- B. Comprador pode rodar avaliação do fornecedor via endpoint diferente (comprador-inicia)
- C. Fornecedor compartilha também seus dados + Policy, comprador vê resultado final

---

## Questões Críticas para Product/Arquitetura

1. **Decision ownership:** Quem pode criar Decision sobre avaliação compartilhada — só fornecedor, só comprador, ambos?
2. **Auditoria de negação:** Se fornecedor cria Proposal contestando resultado, como comprador rejeita? Fica DENIED na Evaluation? Nova Evaluation criada?
3. **Composição UI:** Compartilhada aparece em tela de elegibilidade regulatória? Em abas? Em dashboard separado?
4. **Renovação:** Ao expirar grant, avaliações históricas ficam "órfãs"? Como fornecedor acessa histórico após expiração?
5. **Backpressure:** Se comprador não renova grant, fornecedor perde acesso a critério? Precisa arquivo/snapshot?

---

## Dependências Externas

- **ADR-0050 (Execução determinística):** Já em vigor; Fase 3 reutiliza
- **ADR-0044 (Matriz regulatória):** Já em vigor; precisa de integração explícita se composição entra
- **ADR-0052 (Temporalidade):** Já em vigor; Evaluation é imutável
- **ADR-0055 (Assinatura):** Já em vigor; Proposal pode exigir assinatura do comprador (Fase 4?)

---

## Próximos Passos (Decision Gate)

**Opção A: Proceder com Planning Completo (Recomendado)**
- Agendar alinhamento com product/compliance
- Responder as 5 questões críticas
- Redação de ADR-0066 (BuyerPolicy Fase 3)
- SPEC com scenarios/cenários/fluxos
- Estimativa de BUILD

**Opção B: Punt para Fase 3 Menor**
- Fazer apenas rate-limiting + auditoria (técnico, baixo risco)
- Defer Decision/Proposal/Composição (estratégico, exige alignment)

**Opção C: Encerrar BuyerPolicy por Agora**
- Validar Fase 2 em ambiente real
- Coletar feedback de uso real antes de expandir
- Retomar quando houver demanda explícita
