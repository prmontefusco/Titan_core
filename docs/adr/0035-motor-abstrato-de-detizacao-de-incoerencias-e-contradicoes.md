# ADR-0035: Motor Abstrato de Detecção de Incoerências e Contradições

* **Status:** Aceita
* **Data:** 2026-07-22
* **Decisor:** Fundador / Engenheiro Principal
* **Domínio Afetado:** Titan Core (`core_domain`, `core_integrity`, `core_application`)

---

## 1. Contexto e Problema

Integridade criptográfica (hash chains e assinaturas) garante apenas que um dado não foi modificado após sua inserção no sistema. Ela não impede a inserção inicial de dados plausíveis, porém falsos (fraude na origem, esquentamento/lavagem de ativos ou relatórios com incoerências físicas/matemáticas).

Para manter o princípio de que o Titan não emite conclusões falsas, o Core necessita de um mecanismo para detectar e sinalizar incoerências no grafo de proveniência antes de aprovar avaliações.

---

## 2. Alternativas Consideradas

1. **Validação rígida hardcoded por vertical no Core:** Inserir regras específicas (ex: suporte de pasto por hectare, tempo de gestação bovina) diretamente no Core. Rejeitado por violar a proibição de vazamento de conceitos de vertical no Titan Core.
2. **Deleção/Rejeição automática de registros incoerentes:** Excluir ou recusar dados incoerentes. Rejeitado porque a história de inserções não pode ser apagada.
3. **Motor Abstrato de Contradições e Limites Físicos/Relacionais (`ContradictionAssessment`):** O Core provê abstrações de regras de restrição (`InconsistencyRule`, `DomainConstraint`, `PhysicalBoundAssertion`) que analisam taxas de variação, limites agregados e intersecções de conjuntos disjuntos.

---

## 3. Decisão

Implementar no Titan Core um **Motor Abstrato de Detecção de Incoerências** sustentado pelas entidades `ContradictionAssessment`, `InconsistencyRule`, `DomainConstraint` e `PhysicalBoundAssertion`.

O Core valida se as afirmações e transformações no grafo respeitam as regras e limites parametrizados pela vertical (ex: capacidade agregada máxima, deltas de tempo mínimos/máximos, violação de exclusão mútua). Quando uma contradição é detectada, o Titan não apaga o histórico, mas marca o resultado da avaliação como **`INDETERMINADA`** com o código de razão `CONTRADICAO_DETECTADA`.

---

## 4. Consequências

### Positivas
* Impede que o sistema emita atestados "verdes" para dados criptograficamente válidos, porém fisicamente impossíveis.
* Mantém a separação estrita: o Core provê a matemática de verificação de restrições; as verticais registram os parâmetros do seu domínio (ex: pecuária, logística, saúde).

### Negativas / Riscos
* Custo computacional de validação do grafo aumenta com o número de restrições ativas.
