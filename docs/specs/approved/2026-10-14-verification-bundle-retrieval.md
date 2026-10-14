# SPEC aprovada — Persistência e recuperação interna de VerificationBundle

**Estado:** APPROVED
**Data:** 2026-10-14
**Autoridade:** ADR-0083 aceita com reforços

## Objetivo

Preservar e recuperar byte a byte o VerificationBundle realmente emitido pelo
Commercial Passport interno, sem publicação, object storage ou dados reais.

## Requisitos

- persistir bytes canônicos UTF-8, SHA-256, tamanho, content type e versão;
- preservar bundle, owner, Dossier, purpose, audience, instante e manifest digest;
- verificar integridade e coerência antes de toda entrega;
- tabela append-only, RLS, FK owner-scoped sem cascade e unicidade global;
- emissão, Dossier, bundle e idempotência permanecem na mesma transação;
- replay idempotente retorna o mesmo bundle, sem nova linha;
- endpoint interno exige `DOSSIER_LER`, OrganizationContext e responde `no-store`;
- recuperação retorna exatamente os bytes persistidos;
- corrupção ou incoerência nunca é entregue;
- feature gates permanecem desligados por default.

## Fora de escopo

Publication, VerificationCode, URL pública, object storage, assinatura produtiva,
ZIP/ASiC, UI, fazenda, dados reais e homologação.

## Critérios de aceite

1. Emissão persiste uma única linha de bundle na mesma transação.
2. Replay não cria outra linha nem outro identificador.
3. Recuperação autorizada é byte-idêntica ao artefato emitido.
4. Outra Organization não descobre o bundle.
5. Tamanho, SHA-256, manifesto ou metadado divergente falham fechado.
6. UPDATE, DELETE e cascade são impedidos tecnicamente.
7. Testes, Ruff, Mypy e Alembic checks passam.
