# ADR 0082 — Correções específicas por vertical com rastreabilidade comum

**Status:** Aceita
**Data:** 8 de outubro de 2026
**Decisores:** fundador e responsável pela arquitetura do Titan
**Estado operacional no MVP:** PARCIALMENTE_IMPLEMENTADA — aplicada inicialmente à retirada de Applicability no Asset; outras verticais adotam o padrão somente quando surgir um caso concreto.

## Contexto

O Core possui `CorrectionService` e o evento genérico `registro_corrigido`. O Asset também possui operações cujo significado já é uma correção de domínio, como `CorrectMeterReading` e `WithdrawPartApplicability`. Emitir simultaneamente o evento genérico e o evento específico duplicaria a mesma decisão, disputaria a próxima versão do agregado e obrigaria consumidores a reconciliar duas representações da mesma mudança.

Ao mesmo tempo, permitir uma operação genérica capaz de alterar qualquer agregado contornaria permissões, invariantes e vocabulário das verticais.

## Decisão

Quando a correção possui significado reconhecido pela vertical, ela é executada por comando, autorização, regra e evento específicos da vertical. O evento específico é o evento de correção canônico e referencia o evento original por `causation_id`.

O Core continua responsável pelo mecanismo transversal já existente: log append-only, autoria, Organization, instante, correlação, causalidade, integridade e ordenação. Ele não decide como o estado de uma vertical é corrigido.

`CorrectionService` e `registro_corrigido` permanecem disponíveis para correções de registros ou eventos que não possuam uma operação de domínio específica. Eles não são uma porta para modificar livremente agregados de verticais.

Não será criado agora um Value Object compartilhado de correção. A estrutura comum só será extraída quando um segundo caso concreto demonstrar campos e comportamento realmente idênticos.

## Aplicação em Applicability

`WithdrawPartApplicability`:

- exige `expected_version` e motivo;
- preserva a asserção e seu evento original;
- altera o estado corrente para `WITHDRAWN`, sem `DELETE`;
- emite somente `asset.applicability.withdrawn`;
- usa como `causation_id` o `event_id` de `asset.applicability.asserted` do mesmo agregado;
- registra no payload o motivo, sem uma segunda referência ambígua a Correction.

## Alternativas descartadas

### Emitir `registro_corrigido` e o evento específico

Descartada por duplicar semântica, exigir duas versões para uma única operação e ampliar a coordenação transacional sem benefício de negócio.

### Emitir somente `registro_corrigido`

Descartada porque apaga o vocabulário da vertical e obriga consumidores a interpretar conteúdo genérico para descobrir que uma Applicability foi retirada.

### Criar um comando global de correção

Descartada porque contornaria invariantes e permissões específicas e formaria uma API administrativa capaz de alterar qualquer agregado.

## Consequências

Correções de domínio permanecem compreensíveis e autorizáveis dentro de cada vertical. Consumidores transversais podem navegar do evento corretivo ao original por causalidade. O histórico original permanece imutável.

Como consequência negativa, cada vertical precisa definir explicitamente seus comandos corretivos. Essa duplicação de vocabulário é intencional: as regras corrigidas não são iguais apenas porque compartilham infraestrutura de auditoria.

## Critérios de aceitação

- a retirada de Applicability não apaga nem sobrescreve a asserção original;
- `asset.applicability.withdrawn.causation_id` referencia `asset.applicability.asserted`;
- há exatamente um evento corretivo para a retirada;
- conflito de versão e retirada repetida são recusados;
- não existe permissão ou endpoint genérico para corrigir agregados de verticais.
