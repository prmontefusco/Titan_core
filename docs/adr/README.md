# Governança das ADRs do Titan

As ADRs registram decisões arquiteturais, alternativas, consequências e condições conhecidas no instante da decisão.

## Processo atual

As ADRs 0001 a 0031 foram avaliadas e aceitas pelo fundador e decisor único do Titan durante a fase pré-MVP. `Aceita` significa direção vinculante para a implementação vigente; não significa revisão independente, consenso de equipe ou validação em produção.

## Status decisório e estado operacional

O `Status` de uma ADR registra a decisão arquitetural, não a disponibilidade produtiva da capacidade descrita. Para evitar confusão entre visão aprovada e entrega verificável, ADRs que tratam capacidades ainda não implementadas ou parcialmente implementadas devem declarar também um **Estado operacional no MVP**:

- `IMPLEMENTADA` — há código produtivo, testes, verificação e registro no checklist para a capacidade descrita.
- `PARCIALMENTE_IMPLEMENTADA` — há implementação de parte do contrato, com limites explícitos.
- `FUTURA_APROVADA` — a direção arquitetural foi aceita, mas ainda não há capacidade operacional no repositório.
- `DIFERIDA` — a decisão permanece registrada, mas sua execução foi adiada ou substituída por decisão posterior.

Quando houver dúvida, `docs/CHECKLIST_DE_IMPLEMENTACAO.md` é o ledger do que foi efetivamente entregue; ADR aceita sem entrada correspondente no checklist não deve ser apresentada como funcionalidade disponível.

## Reabertura durante o MVP

A primeira implementação de cada tema funciona como teste da decisão. Uma ADR pode ser reaberta sem cerimônia excessiva quando surgir:

- evidência operacional contrária;
- custo ou complexidade desproporcional;
- requisito comercial validado incompatível;
- risco de segurança, auditoria ou conformidade não considerado;
- alternativa comprovadamente mais simples;
- mudança normativa ou tecnológica material.

Reabertura não reescreve o histórico. A ADR recebe novo estado ou é substituída por outra ADR que declara quais decisões foram alteradas e por quê.

## Revisão futura

Quando existir equipe ou operação produtiva, decisões de segurança, criptografia, identidade, isolamento, retenção, evidência jurídica e recuperação devem receber revisão independente proporcional ao risco.
