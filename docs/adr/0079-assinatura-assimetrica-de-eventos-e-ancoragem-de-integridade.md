# ADR-0079 — Assinatura assimétrica de eventos e ancoragem de integridade

**Data:** 09/09/2026  
**Status:** ACEITA  
**Escopo:** FINDING-007; não-repúdio da trilha de eventos, assinatura assimétrica e ancoragem externa de integridade.

## Contexto

A auditoria adversarial apontou que `core_audit.domain_events` e `core_audit.domain_event_integrity` preservam eventos append-only com cadeia SHA-256 calculada pelo servidor, mas não assinam cada elo com criptografia assimétrica nem ancoram raízes verificáveis fora do controle operacional do Titan. Um administrador privilegiado do banco poderia, em tese, alterar eventos e recomputar a cadeia interna sem que um verificador externo detectasse a reescrita apenas pelo banco.

A ADR-0007 já decidiu checkpoints imutáveis e `TimestampProvider` substituível compatível com RFC 3161, mas deixou Merkle, múltiplas TSAs, blockchain, chaves e assinatura fora do escopo inicial. A ADR-0008 já definiu a governança de chaves, isolamento de material privado e provider substituível. A ADR-0009 já definiu que assinatura não é verdade, que perfil e finalidade são obrigatórios e que timestamp não substitui assinatura.

## Decisão

O Titan deve evoluir a trilha de eventos em dois cortes compatíveis:

1. **Assinatura assimétrica de elos de integridade:** cada `EventChainEntry` persistido deve possuir uma assinatura técnica assimétrica sobre bytes canônicos protegidos que incluam, no mínimo, domínio de separação, `event_id`, `record_owner_organization_id`, aggregate, `aggregate_version`, `previous_hash`, `current_hash`, algoritmo, perfil de cadeia, versão de serialização e finalidade. O algoritmo inicial aprovado para o MVP é **Ed25519**, usando a dependência `cryptography` já presente no lockfile. HMAC permanece permitido apenas para desenvolvimento/testes existentes que não aleguem não-repúdio público.
2. **Ancoragem externa por checkpoint:** a prova externa não deve ser criada por evento individual no primeiro corte. Ela deve reutilizar `IntegrityCheckpoint` e `TimestampProvider` da ADR-0007, ancorando o digest do conjunto delimitado. Merkle roots, múltiplas TSAs, blockchain ou ledger público exigem decisão posterior quando houver volume, custo e perfil jurídico definidos.

A assinatura inicial representa um selo técnico da plataforma ou da Organization conforme KeyPurpose aprovado no servidor. Ela não representa assinatura pessoal de User, aprovação humana, certificação regulatória ou verdade material do evento.

## Fronteiras

### Application

- escolhe perfil, finalidade e chave ativa no servidor;
- solicita assinatura após calcular os bytes canônicos do elo;
- falha fechado quando a assinatura exigida não puder ser produzida;
- preserva resultado desconhecido sem inventar assinatura.

### Infrastructure

- implementa `Ed25519SigningProvider` e validador correspondente;
- resolve chave por referência opaca e nunca expõe chave privada ao Domain;
- persiste assinatura, `key_id`, algoritmo, perfil, instante e bytes ou digest protegidos suficientes para revalidação;
- mantém compatibilidade de leitura com elos históricos sem assinatura, marcando lacuna explicitamente.

### Domain e Integrity

- continuam independentes de SDK, HSM, KMS, TSA ou banco;
- definem bytes canônicos e domínio de separação de assinatura;
- não recebem chave privada, PIN, secret ou credencial de provider.

## Não Objetivos

Este recorte não implementa:

- TSA, RFC 3161 real, blockchain ou ledger externo produtivo;
- HSM, KMS, Cloud HSM ou serviço remoto de assinatura;
- assinatura pessoal de usuário ou profissional;
- assinatura jurídica qualificada;
- Merkle tree ou prova de inclusão;
- alteração de contrato HTTP;
- mudança retroativa de eventos históricos.

Eventos históricos sem assinatura permanecem verificáveis pela cadeia SHA-256 existente, mas devem ser classificados como lacuna de não-repúdio assimétrico quando a dimensão for avaliada.

## Consequências

- Um atacante que consiga apenas alterar o banco deixa de conseguir recomputar uma cadeia indistinguível sem acesso à chave privada correspondente.
- A garantia ainda depende da custódia da chave e do perfil de confiança; assinatura técnica self-hosted não substitui timestamp independente.
- A ancoragem externa continua concentrada em checkpoints, evitando custo e latência por evento.
- Migração deve tratar linhas históricas sem inventar assinatura retroativa.
- A implementação futura exigirá migration append-only, testes de verificação positiva/negativa, testes PostgreSQL de imutabilidade/RLS e atualização do checklist.

## Critérios do Próximo BUILD

O primeiro incremento de implementação autorizado por esta ADR deve:

- adicionar colunas ou tabela append-only para assinaturas de `domain_event_integrity`;
- assinar novos elos com Ed25519 em caminho produtivo do `DomainEventRepository.append`;
- validar assinatura durante verificação de cadeia quando material público estiver disponível;
- preservar compatibilidade explícita com elos históricos sem assinatura;
- impedir UPDATE/DELETE/TRUNCATE ordinário da assinatura persistida;
- cobrir adulteração de evento, `previous_hash`, `current_hash`, `key_id`, algoritmo e assinatura;
- não adicionar provider externo real, custo recorrente ou contrato público novo.
