# DISCOVERY — Entrega recuperável de VerificationBundle

**Estado:** PROCEED — ADR-0083 aceita com reforços
**Data:** 2026-10-14
**Origem:** continuidade da emissão formal interna do Commercial Passport

## Contexto

A emissão formal do Commercial Passport persiste o Dossier e constrói um
`VerificationBundle`, mas hoje retorna somente `bundle_id` e
`manifest_digest`. O bundle não possui repositório e seus componentes deixam de
estar disponíveis após a resposta.

O objetivo deste Discovery é escolher como preservar e recuperar exatamente o
artefato emitido, sem habilitar publicação externa ou homologação.

## Evidência no repositório

- `VerificationBundleService.build_from_dossier()` cria
  `TypedId.new("verification_bundle")` em toda execução;
- `bundle_id` integra o conteúdo protegido do manifesto e, portanto, altera o
  `manifest_digest`;
- `LivestockVerificationBundleInterpreter` também participa dos escopos e
  lacunas, que podem evoluir entre versões;
- `Dossier` já é append-only e persistido como JSONB no PostgreSQL;
- não existe repositório/tabela de VerificationBundle nem infraestrutura de
  object storage no projeto;
- ADR-0010 exige bundle imutável, autossuficiente e historicamente verificável;
- geração e download são operações distintas e autorizadas.

## Conclusão da prova de regeneração

Regenerar somente a partir do Dossier **não reproduz o bundle emitido**. Mesmo
com o mesmo Dossier, audience e instante, o serviço cria nova identidade; sem
preservar também versão exata do interpretador, perfis e demais parâmetros, uma
evolução de código pode mudar o manifesto.

Persistir apenas metadados e reconstruir sob demanda violaria a identidade
imutável do artefato ou exigiria transformar o builder em um protocolo histórico
versionado, complexidade sem uso atual.

## Opções

### A — Regeneração a partir do Dossier

**Vantagem:** não duplica bytes.  
**Desvantagem:** não preserva `bundle_id`, manifesto nem comportamento histórico
do interpretador.  
**Decisão recomendada:** rejeitar neste corte.

### B — Exportação completa imutável em PostgreSQL/JSONB

Persistir a forma retornada por `VerificationBundleService.export()` junto a
metadados owner-scoped: bundle, Organization, Dossier, purpose, audience,
created_at, formato e manifest digest.

**Vantagens:** menor mudança operacional, mesma transação do Dossier, RLS e
backup já existentes, replay exato, nenhuma dependência nova.  
**Desvantagens:** duplica o Dossier dentro do payload e não é adequada para
bundles grandes com muitos anexos.

### C — Conteúdo em object storage e metadados no PostgreSQL

**Vantagens:** melhor escala para arquivos grandes e download por streaming.  
**Desvantagens:** introduz fornecedor/serviço, credenciais, criptografia,
localização, retenção, reconciliação transacional e recuperação de desastre sem
necessidade medida no MVP.

## Recomendação

Adotar **Opção B** para o perfil interno sintético inicial, com limite explícito
de tamanho e sem anexos binários. Persistir a exportação completa exatamente no
momento da emissão, na mesma transação do Dossier e da idempotência.

Se um perfil futuro ultrapassar o limite ou incluir binários, abrir novo
Discovery para object storage; não fazer migração antecipada agora.

## Corte proposto após aprovação

1. tabela Core append-only `verification_bundles`, com RLS e FK owner-scoped para
   Dossier;
2. repositório transacional que salva e carrega a exportação completa;
3. persistência incorporada ao serviço formal antes do commit da emissão;
4. endpoint interno autenticado de recuperação por `bundle_id`, com permission,
   OrganizationContext e `no-store`;
5. limite de tamanho aplicado antes da persistência;
6. teste PostgreSQL de emissão, replay idempotente, recuperação, verificação
   offline, isolamento entre Organizations e rollback;
7. feature gate permanece desligado por default.

## Fora de escopo

- Publication pública, VerificationCode ou URL anônima;
- object storage, ZIP/ASiC, compressão ou criptografia de container;
- assinatura produtiva, certificado ou KMS;
- UI de download;
- dados reais, fazenda ou homologação;
- múltiplas versões físicas do mesmo bundle.

## Decisão

Opção B aprovada com preservação dos bytes canônicos em `bytea`, digest próprio,
tamanho, content type, versão de serialização, integridade em toda leitura e
imutabilidade defensiva no banco. JSONB não é a fonte do artefato emitido.
