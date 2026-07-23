# ADR-0033: Provas de Conhecimento Zero (ZKP) em Dossiês de Proveniência

* **Status:** Aceita
* **Data:** 2026-07-22
* **Decisor:** Fundador / Engenheiro Principal
* **Domínio Afetado:** Titan Core (`core_domain`, `core_integrity`, `core_infrastructure`)

---

## 1. Contexto e Problema

Cadeias de suprimentos reguladas exigem auditabilidade e transparência de proveniência em múltiplos níveis de fornecedores (diretos e indiretos). No entanto, fornecedores intermediários recusam-se frequentemente a compartilhar seus identificadores exatos, localizações geográficas ou volumes transacionados por motivos de segredo comercial e concorrência.

Os mecanismos tradicionais de prova (como envio de dados brutos ou hashes simples) criam um dilema insolúvel entre **transparência de compliance** e **privacidade comercial**.

---

## 2. Alternativas Consideradas

1. **Compartilhamento de dados brutos com RLS / Controle de Acesso:** Exige que todas as partes confiem plenamente no operador do sistema e na política de privacidade. Rejeitado por não oferecer garantia criptográfica autônoma contra vazamento de segredos comerciais.
2. **Anonimização / Mascaramento Simples:** Mascarar nomes ou IDs reduz a auditabilidade e impede que terceiros verifiquem se o mascaramento foi manipulado.
3. **Provas de Conhecimento Zero (Zero-Knowledge Proofs - ZKP):** Permitir a geração de circuitos criptográficos (ex: zk-SNARKs / zk-STARKs) que comprovam que uma afirmação sobre o grafo de proveniência satisfaz regras regulatórias sem expor os atributos sensíveis dos nós intermediários.

---

## 3. Decisão

Adotar o suporte a **Provas de Conhecimento Zero (ZKP)** no Titan Core como primitivas de primeira classe no domínio e na integridade (`ZeroKnowledgeProof`, `ZkCircuitReference`, `PrivateProofConstraint`).

O Core fornecerá as abstrações necessárias para ancorar provas ZKP dentro dos `VerificationBundles` e `Dossiers`, permitindo que verticais (como o Titan Livestock) utilizem circuitos específicos para provar conformidade regulatória sobre elos mascarados da proveniência sem expor dados identificáveis ou sigilosos.

---

## 4. Consequências

### Positivas
* Resolve o dilema histórico entre transparência regulatória e segredo comercial.
* Permite auditoria pública/terceirizada sem vazamento de LGPD ou segredos de negócio.
* Torna o Titan Core a plataforma de confiança mais avançada do mercado para cadeias multinível.

### Negativas / Riscos
* Complexidade matemática e computacional adicional para geração de provas (geração de provos em clientes/edge pode exigir otimização).
* Necessidade de governança rigorosa das referências de circuitos ZKP (`ZkCircuitReference`).
