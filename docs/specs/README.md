# Lifecycle de SPEC

Uma SPEC é a unidade de trabalho que transforma uma decisão de produto em um
incremento implementável e verificável. Ela não é backlog, nem autorização implícita
para construir.

## Fluxo

`IDEA → DISCOVERY → DECISION → SPEC → PLAN → BUILD → VERIFY → ACCEPT`

- **IDEA:** observação, pergunta ou hipótese ainda sem requisito.
- **DISCOVERY:** investigação proporcional do problema, usuário, evidência,
  alternativas, capacidades existentes, riscos, custos e perguntas abertas.
- **DECISION:** `REJECT`, `DEFER` ou `PROCEED`. Só `PROCEED` abre uma SPEC.
- **SPEC:** intenção, comportamento, limites e critérios de aceite aprováveis.
- **PLAN:** desenho técnico limitado à SPEC e arquivos/fronteiras afetados.
- **BUILD:** implementação dentro dos limites aprovados.
- **VERIFY:** testes, validação manual quando aplicável, revisão e riscos residuais.
- **ACCEPT:** aceite humano da entrega e atualização do ledger quando houver etapa
  observável concluída.

Uma ideia não é uma feature. Uma hipótese não é um requisito. Uma SPEC aprovada não
significa prioridade imediata. Código é consequência de uma decisão de produto.

## Estados e localização

Uma SPEC vive em exatamente um destes locais:

- `docs/specs/proposed/`: em elaboração ou aguardando decisão;
- `docs/specs/approved/`: autorizada, mas ainda não entregue;
- `docs/specs/implemented/`: entregue e aceita;
- `docs/specs/rejected/`: decisão de não seguir.

Os diretórios surgem na primeira SPEC que receberem; não criar estrutura vazia.
Nome sugerido: `YYYY-MM-DD-slug-da-capacidade.md`.

## Proporcionalidade

Usar `docs/specs/_template.md`.

- **SMALL:** mudança local e baixo risco; registrar somente se a decisão não couber
  de modo claro no pedido aprovado e plano curto.
- **STANDARD:** nova capacidade, comportamento relevante, entidade, API, migration
  compatível, integração ou UX relevante.
- **CRITICAL:** segurança, tenancy, auditoria, integridade, criptografia, retenção,
  migration destrutiva/incompatível, arquitetura ou contrato público relevante.

## Relação com o checklist

`docs/CHECKLIST_DE_IMPLEMENTACAO.md` é o ledger de execução: registra o que foi
efetivamente implementado, validado e aceito. A SPEC registra o contexto e a decisão
anterior ao código. Não repetir no checklist o conteúdo da SPEC, nem usar uma SPEC
como histórico paralelo de entrega.

## Discordância técnica

O agente deve interromper e apresentar evidência antes de seguir uma proposta que
contradiga documentos de autoridade, duplique capacidade existente, crie
overengineering, viole invariantes, aumente risco de segurança ou tenha alternativa
materialmente mais simples. Para decisões relevantes, apresentar CONTEXTO, EVIDÊNCIA
NO REPOSITÓRIO, OPÇÕES, TRADE-OFFS, RECOMENDAÇÃO e DECISÃO NECESSÁRIA.
