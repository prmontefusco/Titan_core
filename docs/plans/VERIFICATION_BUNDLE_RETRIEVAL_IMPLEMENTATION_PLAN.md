# Plano técnico — Persistência e recuperação interna de VerificationBundle

**Estado:** COMPLETE — validação manual adiada
**Data:** 2026-10-14

1. Tornar a exportação do Core serializável em bytes canônicos estáveis.
2. Criar migration Core e repositório append-only com validação integral.
3. Persistir o bundle na composição formal do Commercial Passport.
4. Expor recuperação autenticada que devolva os bytes armazenados sem
   reserialização.
5. Cobrir integridade, replay, RLS e imutabilidade.
6. Atualizar roteiro e checklist; executar verificações completas.
