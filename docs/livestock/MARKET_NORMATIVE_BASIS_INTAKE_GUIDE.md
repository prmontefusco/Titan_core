# Guia de Intake — Do Resultado da Pesquisa Gemini a uma `NormativeBasis` Real

**Data:** 2026-09-14
**Propósito:** explicar o que fazer (e o que não fazer) com o resultado de
`docs/livestock/MARKET_NORMATIVE_BASIS_RESEARCH_PROMPT.md`, para que a pesquisa de IA vire base normativa
confiável no Titan sem violar as garantias que o produto existe para dar.

---

## Por que este passo intermediário existe

O Titan nunca afirma automaticamente que algo é verdadeiro (`DOMAIN.md`, princípio 2.1). Uma `NormativeBasis`
não é texto livre: ela exige instrumento normativo identificado, versão imutável, autoridade que aprovou,
evidência de competência dessa autoridade, jurisdição, vigência e Digest — e "aprovação privada não é
apresentada como entendimento oficial sem Evidence específica" (`DOMAIN.md`, seção `NormativeBasis`). A
ADR-0061 (13/08/2026) criou de propósito um portão fail-closed que impede `Evaluation`/`Decision` de mercado
sem essa fotografia normativa real — e é explícita: "o primeiro adapter pode servir somente o caso fictício
aprovado... nunca inferências a partir de Rule."

Um resultado de pesquisa de IA — mesmo com grounding/busca ativado — é uma **Claim**, não um **Fact** nem uma
**NormativeBasis**. `DOMAIN.md` é direto sobre isso na seção de Decisões explicáveis: *"Modelo estatístico ou
IA pode produzir Claim, extração ou recomendação... Não recebe autoridade decisória por capacidade técnica."*
Este guia é o caminho entre os dois.

## O que o resultado do Gemini é

- Uma Claim de pesquisa, com fontes citadas (ou explicitamente marcadas como não verificadas).
- Ponto de partida para revisão humana, não uma conclusão pronta.
- Sujeito a erro, desatualização e alucinação residual mesmo com as instruções anti-invenção do prompt.

## O que o resultado do Gemini NÃO é

- Não é uma `NormativeBasis` aprovada.
- Não autoriza nenhuma mudança de código, nenhuma `Policy`/`Rule` nova, nenhuma migration.
- Não deve ser colado diretamente em nenhum campo do sistema como se fosse fonte oficial.
- Não tira nenhum mercado do estado `INDETERMINADO` por si só.

## Passos para transformar o resultado em algo utilizável

1. **Revisão humana com competência declarada.** Alguém com capacidade real de interpretar regulação
   sanitária/comercial internacional (jurídico, compliance regulatório, ou consultoria especializada em
   comércio exterior pecuário) precisa revisar cada item da seção 6 do prompt (tabela de instrumentos) e
   confirmar, contra a fonte primária, que a citação está correta. Itens marcados "NÃO VERIFICADO" pelo
   Gemini exigem essa verificação manual antes de qualquer uso — nunca promovê-los a verificado por
   conveniência.
2. **Registrar a fonte, não só a conclusão.** Para cada instrumento confirmado, preservar URL, data de
   acesso e, se possível, uma cópia/hash do documento original (`Evidence`/`Document` do Core já oferecem
   isso — `packages/core_domain/evidence.py`, `packages/core_domain/decision.py` para o contrato de
   `NormativeBasis`/`NormativeInstrumentVersion`).
3. **Decidir escopo antes de implementar.** A revisão pode concluir que a exigência real é mais estreita ou
   mais ampla do que a Policy fictícia atual (`SANITARY_TEST_A_v1`, `MARKET_TEST_A`) presume. Esse é o
   momento de decidir o desenho real da `Policy`/`Rule` por mercado — não antes.
4. **Seguir o fluxo canônico do projeto.** Uma vez com fonte validada, isto vira DISCOVERY → DECISION → SPEC
   → PLAN → BUILD como qualquer outra frente (`DEVELOPMENT.md`), incluindo ADR própria se a decisão for
   arquitetural. O adapter técnico já existe como padrão (`InternalTestNormativeBasisSnapshotProvider` /
   `PersistedInternalTestNormativeBasisSnapshotProvider`, `core_audit.internal_test_normative_bases`) — o
   trabalho de BUILD é replicar esse padrão para material real, não inventar um novo mecanismo.
5. **Indonésia especificamente.** Antes de qualquer BUILD, decidir separadamente se Indonésia entra na
   matriz de mercados (`market_eligibility.py` hoje só tem China/EUA/UE) — isso é uma decisão de produto,
   independente de a pesquisa regulatória existir ou não.

## Sinal de alerta

Se, em algum momento deste processo, a pressão for "já temos a pesquisa da IA, vamos só usar direto" —
pare. É exatamente o atalho que a ADR-0061 foi escrita para impedir, e o motivo é concreto: uma Decision de
elegibilidade de mercado baseada em fundamento não verificado pode liberar ou barrar um embarque real com
base em algo que ninguém confirmou ser verdade.
