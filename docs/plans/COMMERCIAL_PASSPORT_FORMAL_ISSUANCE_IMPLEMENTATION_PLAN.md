# Plano técnico — Emissão formal do Commercial Passport interno

**SPEC:** `docs/specs/approved/2026-10-14-commercial-passport-formal-issuance.md`  
**Estado:** COMPLETE — validação manual adiada  
**Data:** 2026-10-14

## Incremento único

Compor o port de emissão formal já existente para uma oportunidade interna
sintética configurada, sem alterar domínio, schema ou contrato do Dossier.

## Passos

1. Implementar no adapter Livestock a resolução determinística da tríade
   Decision/Evaluation/Policy e a emissão na transação ativa.
2. Compor a dependência HTTP somente sob gate específico, perfil interno e
   configuração válida.
3. Tornar `Idempotency-Key` obrigatório e envolver a emissão com o serviço Core
   de idempotência na mesma transação.
4. Mapear ausência/ambiguidade/divergência e conflitos idempotentes para resposta
   uniforme `409`, sempre `no-store`.
5. Cobrir seleção exata, falhas fechadas, replay/conflito e RLS com testes.
6. Atualizar `apps/validacao` e o checklist de implementação.
7. Executar suíte completa, Ruff, Mypy e os dois Alembic checks; revisar diff e
   registrar riscos residuais.

## Restrições

- nenhuma flag é habilitada;
- nenhuma migration é criada;
- nenhuma escolha por ordenação temporal substitui unicidade exata;
- nenhuma alteração fora da emissão formal do Commercial Passport.
