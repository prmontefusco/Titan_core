# ADR 0083 — Persistência inicial de VerificationBundle

**Status:** Aceita com reforços
**Data:** 14 de outubro de 2026
**Decisores:** responsável pelo produto e arquitetura do Titan

## Problema

O Titan já constrói `VerificationBundle` autossuficiente conforme a ADR-0010,
mas a emissão formal inicial do Commercial Passport não preserva o pacote para
recuperação posterior. É necessário decidir onde guardar o primeiro perfil
interno sem introduzir infraestrutura prematura.

## Alternativas

1. regenerar o bundle a partir do Dossier;
2. persistir a exportação completa e imutável em PostgreSQL/JSONB;
3. persistir conteúdo em object storage e metadados no PostgreSQL.

## Decisão

Para o perfil `INTERNAL_SYNTHETIC`, persistir os bytes UTF-8 da serialização
canônica completa produzida a partir de `VerificationBundleService.export()` em
tabela Core append-only protegida por RLS, na mesma transação do Dossier e do
registro idempotente. JSONB não é a fonte autoritativa do artefato.

A linha preservará ao menos:

- `bundle_id`;
- `record_owner_organization_id`;
- `dossier_id` owner-scoped;
- `purpose`, `audience`, `created_at`;
- `format_version`, `serialization_version` e `manifest_digest`;
- `content_type`, `payload_bytes`, `serialized_payload_digest` e
  `serialized_size_bytes`.

O primeiro perfil aceitará somente o conteúdo textual já produzido pelo Core e
terá limite explícito de tamanho. Exceder o limite falhará antes da persistência,
sem truncamento ou armazenamento parcial.

Recuperação byte-idêntica será operação autenticada e autorizada distinta da emissão. O
repositório não publicará o pacote e não criará `VerificationCode`.

Cada leitura verificará tamanho, SHA-256 do payload, digest interno do manifesto
e coerência entre bundle, owner, Dossier e purpose. Verificação semântica offline
permanece conceito distinto da recuperação byte-idêntica.

## Justificativa

Regeneração não preserva a identidade: o builder cria novo `bundle_id`, que
altera o manifesto e seu digest. Também acoplaria reprodução histórica à versão
corrente dos interpretadores.

PostgreSQL é a única infraestrutura durável transacional já adotada neste
escopo, permite atomicidade com Dossier/idempotência e evita credenciais,
reconciliação e operação de um object storage ainda sem demanda medida.

Object storage permanece a direção adequada quando houver anexos binários ou
volume que ultrapasse o perfil inicial, mas exigirá ADR/Discovery próprio sobre
localização, criptografia, retenção, consistência e recuperação.

## Consequências

### Positivas

- recuperação byte-idêntica do artefato realmente emitido;
- atomicidade e isolamento reaproveitando infraestrutura existente;
- nenhuma dependência operacional nova;
- verificação offline continua independente do banco após o download.

### Negativas

- duplicação do Dossier dentro do bundle persistido;
- crescimento do PostgreSQL;
- limite conservador necessário;
- migração futura para object storage deverá preservar IDs, digests e bundles
  históricos.

## Restrições

- append-only; atualização silenciosa é proibida;
- unicidade global de `bundle_id` e unicidade explícita por owner;
- owner e FK do Dossier devem ser compostos por Organization;
- FK não usa `ON DELETE CASCADE`;
- role da aplicação não recebe UPDATE/DELETE e trigger defensiva rejeita
  alteração, exclusão e truncamento;
- payload parcial, truncado ou reconstruído não pode substituir o original;
- RLS e permission são obrigatórios;
- geração, recuperação, Publication e compartilhamento permanecem operações
  distintas;
- nenhuma flag é habilitada por esta ADR.

## Reversão

Antes da implementação, rejeitar esta proposta não altera dados. Depois da
implementação, mudança de storage deve copiar e verificar bytes/digests antes de
trocar a leitura. PostgreSQL continuará preservando a âncora imutável com
identidade, owner, Dossier, tamanho, digest, versão e localização; registros
históricos não serão reemitidos nem sobrescritos.
