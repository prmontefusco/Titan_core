# BuyerPolicy Fase 2 Discovery

**Data:** 2026-08-19  
**Status:** DISCOVERY — sem autorização para PLAN/BUILD  
**Escopo:** Investigar necessidade real de compartilhamento bilateral de Policies contratuais entre Comprador e Fornecedor

---

## 1. Contexto Atual

**Fase 1 (ADR-0064, ACEITA):**
- Comprador cria Policy homogeneamente INTERNAL_POLICY (critério privado, isolado)
- Avalia próprias Policies sobre próprios animais (mesma Organization)
- Resultado marcado `INTERNAL_ONLY` — nunca exportado, nunca visível fora

**Modelo Livestock hoje (ADR-0044, ACEITA):**
- Elegibilidade regulatória por mercado (LAW, REGULATION, CERTIFICATION)
- Fluxo unidirecional: fornecedor publica, comprador avalia via importação de VerificationBundle/Dossier
- Sem Policies contratuais, sem compartilhamento de resultado comprador → fornecedor

**Arquitetura de compartilhamento reservada (ADR-0018, proposta, não codificada):**
- `Sharing`, `AuthorizationGrant`, `AccessPurpose`, `FieldScope` existem como conceitos
- Nenhuma implementação de cross-tenant visibility hoje
- RLS por `organization_id` é o único isolamento ativo

---

## 2. Caso Real Mínimo Proposto

**Atores:**
- **Fornecedor (Farm):** Organização que produz e oferece animais
- **Comprador (Slaughterhouse/Buyer):** Organização que seleciona animais para compra

**Transação:**
1. Comprador publica Policy com critérios contratuais (origem: `CONTRACT`)
   - Ex: "Lote deve ter 15+ dias de repouso pós-transporte, peso 450–550kg, sem medicação em últimos 7 dias"
   - Compartilha esta Policy com Fornecedor via `AuthorizationGrant`

2. Fornecedor avalia seus próprios animais contra esta Policy
   - Vê resultado: "ELEGÍVEL" ou "NAO_ELEGÍVEL" + motivo
   - Vê evidências faltando (ex: "peso não registrado") para corrigir

3. Comprador, ao importar VerificationBundle do Fornecedor, vê:
   - Resultado da auto-avaliação do Fornecedor contra própria Policy
   - Evidência de que Fornecedor conhece critério e declarou conformidade

4. Encerramento: Comprador revoga `AuthorizationGrant`
   - Fornecedor perde acesso à Policy e não consegue reavaliar

**Benefício esperado:** Reduz fricção (Fornecedor sabe de antemão qual é o critério), aumenta conformidade (auto-avaliação), cria evidência auditável (Fornecedor explicitamente confirmou conformidade).

---

## 3. Respostas às 8 Perguntas

### 3.1 Quem são as duas Organizations envolvidas no primeiro caso real?

**Resposta:** Comprador (slaughterhouse/trading company) e Fornecedor (farm/property owner).

**Variação a considerar:** Múltiplos fornecedores sob um comprador (1:N model).

**Decisão necessária:** Fase 2 cobre apenas 1:1 bilateral ou 1:N broadcasting? *Recomendação: começar 1:1, extensível a 1:N*.

---

### 3.2 Qual dado do fornecedor o comprador precisa ver para aplicar critério contratual?

**Resposta:** Fatos sobre o sujeito (Animal/Lot) que sustentam a elegibilidade:
- Peso (livestock.weight)
- Histórico de tratamento (livestock.treatment_history)
- Período de confinamento/repouso (livestock.transport_status, withdrawal)
- Medicação última (livestock.medication_classification)
- Sanidade (livestock.health_status)

**Adicional:** Comprador pode querer **evidência de que Fornecedor conhece o critério e afirma conformidade**, não apenas resultado de avaliação.

**Decisão necessária:** Fase 2 compartilha apenas Policy + resultado de auto-avaliação, ou também compartilha dados brutos (VerificationBundle)? *Recomendação: apenas Policy + resultado + lista de facts faltando; dados brutos já existem em VerificationBundle separado*.

---

### 3.3 O fornecedor vê apenas o resultado, as razões, as regras, ou também evidências?

**Opções:**
1. **Apenas resultado:** "ELEGÍVEL" / "NAO_ELEGÍVEL" (mínimo)
2. **Resultado + razões:** +"Peso fora de faixa" / "Medicação recente"
3. **Resultado + razões + regras:** +mostra cada condição (weight 450–550kg, etc.)
4. **Tudo + evidências:** +lista fatos coletados vs. faltando

**Trade-offs:**
- Opção 1: mínimo risco de revelação indevida, mas Fornecedor não consegue corrigir
- Opção 3/4: máxima transparência e capacidade de ação, risco de Fornecedor reverter-engineerizar critério

**Decisão necessária:** Qual AccessPurpose value habilita Fornecedor a ver cada nível? *Recomendação: `EXECUCAO_CONTRATUAL` habilita opção 3 (resultado + razões + regras, não dados brutos)*.

---

### 3.4 Qual é a finalidade exata do compartilhamento?

**Propósito principal:** Comprador quer que Fornecedor auto-avalie conformidade antes de ofertar; reduz assimetria de informação e fricção operacional.

**Propósito secundário:** Criar evidência auditável de que Fornecedor conhecia critério e afirmou estar dentro.

**Fora de escopo (Fase 2):** Forçar Fornecedor a aceitar/rejeitar a Policy; Comprador alterar Policy dinamicamente; negociação iterativa.

**Decisão necessária:** Compartilhamento é read-only ou precisa capturar "Fornecedor confirmou estar dentro"? *Recomendação: read-only por enquanto; captura de "acknowledgment" é Fase 3*.

---

### 3.5 Qual evento encerra ou revoga o acesso?

**Opções:**
1. **Comprador revoga:** Expiração automática ou revogação explícita de `AuthorizationGrant`
2. **Fim da transação:** Depois que um Lot é efetivamente comprado/rejeitado
3. **Período fixo:** Grant válido por 30 dias, depois expira
4. **Cláusula contratual:** Grant vinculado a contrato; encerra quando contrato é rescindido

**Decisão necessária:** Qual é o modelo inicial? *Recomendação: Comprador revoga explicitamente, sem vencimento automático (mais simples; expirações automáticas é Fase 3)*.

**Adicional:** Quando grant é revogado, Evaluation histórica permanece válida (imutabilidade, ADR-0013), mas Fornecedor não consegue avaliar de novo.

---

### 3.6 O primeiro corte precisa apenas de `Evaluation` bilateral ou também de `DecisionProposal`/`Decision`?

**Definições:**
- **Evaluation:** Aplicação de Rule a Fact, resultado + razões (já existe, Fase 1 usa)
- **DecisionProposal:** Fornecedor propõe "Vou oferecer este Lot com estas garantias baseado nesta Evaluation" (não existe)
- **Decision:** Comprador aceita ou rejeita a proposta (não existe)

**Decisão necessária:** Fase 2 precisa de DecisionProposal/Decision ou só Evaluation bilateral? *Recomendação: DEFER DecisionProposal/Decision para Fase 3; Fase 2 foca em compartilhamento de Evaluation apenas*.

---

### 3.7 A BuyerPolicy contratual fica separada da matriz regulatória ou precisa aparecer lado a lado?

**Opções:**
1. **Separadas:** BuyerPolicy Contratual é trilha independente; Comprador vê resultado contratual E resultado regulatório em dois lugares distintos
2. **Lado a lado:** Matriz de elegibilidade mostra regulatório + contratual em grid único
3. **Composto:** Resultado composto (ELEGÍVEL só se regulatório=SIM E contratual=SIM)

**Trade-offs:**
- Opção 1: Claro, sem risco de confundir origem; mais cliques
- Opção 2: Integrado, menos cliques; risco de misturar semântica
- Opção 3: Simples para decisão final; opaco para auditoria

**Decisão necessária:** Qual visual Comprador espera? *Recomendação: Opção 1 (separadas) para Fase 2; composição é product decision após validação de uso*.

---

### 3.8 Há exigência real de persistir `recognition_boundary`, ou o valor ainda pode continuar derivado?

**Contexto:** Fase 1 deixou `recognition_boundary=INTERNAL_ONLY` como derivado (não persistido).

**Pergunta:** Se Fornecedor vê resultado de BuyerPolicy contratual, precisa-se persistir que o resultado é "INTERNAL_ONLY" (não para matriz regulatória)?

**Decisão necessária:** Sim ou não? *Recomendação: NÃO. Continue derivado em Fase 2. Fornecedor nunca entra na matriz regulatória, então não há confusão. Persistir é Fase 3 quando composição entrar em escopo*.

---

## 4. Opções de Design (Trade-offs)

### Opção A: Mínimo viável — Policy contratual unidirecional

**Escopo:**
- Comprador publica Policy com origem CONTRACT
- Compartilha via `AuthorizationGrant` (new)
- Fornecedor avalia, vê resultado + razões (opção 3 acima)
- Revogação explícita; sem vencimento
- Evaluation histórica permanece válida

**Vantagens:**
- Cabe em Fase 2 sem explodir escopo
- Reutiliza `PolicyEvaluationService`, `PolicyOrigin`, `RuleIdentity` já existentes
- Não toca `Decision`, `DecisionProposal`, composição com matriz
- `recognition_boundary` continua derivado

**Desvantagens:**
- Não captura "Fornecedor confirmou estar dentro" (só vê resultado)
- Sem vencimento automático de grant (manual operacional)
- Sem integração visual com matriz regulatória (duas trilhas)

**Risco:** Comprador não consegue negociar critério dinamicamente (não é caso real se exigido).

---

### Opção B: Compartilhamento bidireccional com acknowledgment

**Escopo:** Opção A + 
- Fornecedor pode "reconhecer" Policy (confirm="Estou dentro" ou escalate="Não consigo atender")
- Comprador vê histórico de acknowledgments
- Novo estado na Evaluation: `FORNECEDOR_CONFIRMADO`, `FORNECEDOR_NCONFORME`, `AGUARDANDO_RESPOSTA`

**Vantagens:**
- Captura evidência clara de que Fornecedor conhece critério
- Comprador tem feedback se Fornecedor consegue conformidade
- Auditoria mais completa

**Desvantagens:**
- Adiciona nova entidade (`EvaluationAcknowledgment` ou campo em `Evaluation`)
- Maior coordenação: grant precisa estar "ativa" para aceitar acknowledgment
- API mais complexa

**Risco:** Escopo cresce; Fase 2 vira mais que "compartilhamento", vira "negociação".

---

### Opção C: Integração imediata com matriz regulatória

**Escopo:** Opção A + 
- Market Eligibility Matrix estende para mostrar contratual lado a lado
- Policy contratual aparece como linha na matriz
- Composição: animal é elegível se regulatório=SIM E contratual=SIM

**Vantagens:**
- UI integrado; Comprador vê tudo em um lugar
- Decisão binária simples

**Desvantagens:**
- Mistura duas trilhas não relacionadas (regulatória vs. contratual)
- Toca ADR-0044, possivelmente requer revisão
- Risco de Fornecedor confundir resultado contratual com regulatório

**Risco:** Escopo explode; bloqueia se houver questão de compliance regulatória.

---

## 5. Riscos e Mitigações

| Risco | Fase 2? | Mitigação |
|---|---|---|
| Fornecedor vê mais do que deve (reversa critério) | A, B, C | AccessPurpose controla visibilidade; auditoria de acesso |
| Grant expirado mas Evaluation aparece válida em histórico | A, B, C | Evaluation é imutável; grant revogado não afeta histórico |
| Comprador não consegue negociar dinamicamente com Fornecedor | A | Fase 3: feedback loop ou versioning de Policy |
| `recognition_boundary` fica ambíguo quando trilhas se misturam | C | Fase 3: persistir boundary; Fase 2 mantém derivado |
| Comprador compartilha mesma Policy com múltiplos Fornecedores sem saber (broadcast acidental) | A, B, C | Controle de grant por (Comprador, Fornecedor, Policy) tuple; auditoria |

---

## 6. Decisão Recomendada

**RECOMENDAÇÃO: PROCEED com Opção A (Compartilhamento unidirecional mínimo).**

**Justificativa:**
1. **Caso real existe:** Buyer-supplier asymmetry é problema conhecido em Livestock; auto-avaliação reduz fricção
2. **Escopo contido:** Reutiliza componentes Fase 1; nova entidade só é `AuthorizationGrant` (já reservada em ADR-0018)
3. **Risco mitigado:** AccessPurpose + FieldScope definem limites; RLS permanece por Organization
4. **Extensível:** Opções B e C viram iterações futuras sem quebrar Fase 2

**Próximo passo se PROCEED:**
1. Abrir ADR-0065 (BuyerPolicy Fase 2: Compartilhamento Contratual)
2. Detalhar `AuthorizationGrant` e `AccessPurpose` para implementação
3. Definir schema e API (Sharing + GET Policy com grant validado)
4. Estimar PLAN e complexidade

**Se DEFER:**
- Aguardar feedback de validação com clientes real
- Reavaliação em Q4 2026 quando Marco 18+ consolidar uso de Fase 1

**Se REJECT:**
- Signalize que buyer-supplier interaction é fora de escopo Titan
- Recomende integração externa (buyer publica contrato, Fornecedor importa offline)

---

## Apêndice: Questões em Aberto (Fase 3+)

1. **Decision/Proposal:** Fornecedor propõe combinar Lot após avaliação?
2. **Dinâmica:** Comprador altera critério; como Fornecedor sabe?
3. **Feedback:** Comprador comunica resultado (comprou/rejeitou) de volta a Fornecedor?
4. **Composição:** Resultado contratual + regulatório = elegibilidade composta?
5. **Mercados:** Fornecedor tem política diferente por país/comprador?
6. **Revogação:** Quando grant revoga, Fornecedor recebe notificação?
7. **Versionamento:** Se Comprador atualiza Policy, grant aplica nova versão ou a original?
8. **Escalação:** Fornecedor consegue questionar motivo de rejeição e pedir revisão?

