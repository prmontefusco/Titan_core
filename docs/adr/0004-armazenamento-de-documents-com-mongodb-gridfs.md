# ADR 0004 — Armazenamento de Documents com MongoDB GridFS

**Status:** Aceita  
**Data:** 20 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

Evidence e Dossier podem referenciar PDFs, imagens, vídeos, certificados e outros Artifacts. O conteúdo binário pode ser grande, enquanto identidade, ownership, autorização, hashes, versões e relações exigem consistência com o domínio transacional.

PostgreSQL foi definido como banco transacional e source of truth. MongoDB foi escolhido como armazenamento de conteúdo documental. É necessário limitar claramente sua responsabilidade e tratar a ausência de transação distribuída entre PostgreSQL e GridFS.

GridFS divide arquivos em chunks e os recompõe no download. A documentação oficial informa que GridFS não suporta transações multidocumento. Portanto, disponibilidade de Document não pode depender de commit atômico entre os dois bancos.

## Problema

Definir:

- divisão de responsabilidade entre PostgreSQL e MongoDB;
- fluxo seguro e idempotente de upload;
- integridade e hash;
- imutabilidade e versionamento;
- autorização e isolamento por Organization;
- arquivos incompletos, órfãos ou adulterados;
- download e auditoria;
- backup e restauração coordenados;
- limites do MongoDB no Titan.

## Princípios

1. **Uma fonte de verdade:** PostgreSQL determina se um Document existe e está disponível.
2. **Binário sem domínio:** GridFS armazena bytes e metadados técnicos mínimos, não regras ou estado de negócio.
3. **Imutabilidade:** conteúdo disponível não é renomeado, substituído ou alterado.
4. **Nova versão, novo Document:** correção nunca sobrescreve conteúdo anterior.
5. **Integridade calculada pelo Titan:** hash do cliente ou do storage não é aceito sem verificação.
6. **Negação por padrão:** cliente nunca acessa GridFS diretamente.
7. **Disponibilidade explícita:** upload concluído fisicamente não torna o Document disponível automaticamente.
8. **Recuperação verificável:** backup e restore preservam referências, bytes e hashes.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Binário em coluna PostgreSQL | Transação única | Aumenta banco transacional, backup e I/O de dados operacionais |
| Filesystem compartilhado | Simplicidade local | Escala, consistência, backup e operação distribuída frágeis |
| Object storage compatível com S3 | API e operação próprias para objetos | Contraria a tecnologia escolhida e exige nova decisão operacional |
| MongoDB GridFS | Streaming, chunks, driver oficial e metadados técnicos | Sem transação multidocumento no GridFS e sem RLS equivalente ao PostgreSQL |

## Decisão

Utilizar **MongoDB GridFS exclusivamente para conteúdo binário de Documents**, mantendo no PostgreSQL todo estado autoritativo.

### PostgreSQL mantém

- Identity e versão do Document;
- RecordOwnerOrganization;
- Actor, Issuer e Source;
- nome original tratado como metadado não confiável;
- tipo declarado e tipo verificado, quando disponível;
- tamanho esperado e confirmado;
- SHA-256 calculado pelo Titan;
- validade, Signature e VerificationStatus;
- estado do processo de upload;
- referência opaca ao objeto GridFS;
- EvidenceReferences e demais relações;
- histórico, Corrections e Revocations;
- autorização e auditoria.

### GridFS mantém

- bytes divididos em chunks;
- identificador opaco de armazenamento;
- tamanho e dados técnicos necessários ao driver;
- cópia não autoritativa de upload ID, Organization, hash e versão técnica para diagnóstico e recuperação.

Metadado do GridFS nunca substitui registro do PostgreSQL.

## Limites do MongoDB

MongoDB não armazena:

- Organization, User, Membership, Role ou Permission como entidades do domínio;
- Claim, Fact ou Event autoritativos;
- Evidence ou Document autoritativos;
- UniversalRelation ou Genealogy;
- Policy, Rule, Evaluation ou Decision;
- NonConformity, RecallResult ou Dossier autoritativos;
- OutboxMessage ou estado definitivo de processo.

Nenhum módulo consulta MongoDB para decidir autorização, conformidade ou elegibilidade.

## Identidade e referência

Document ID do domínio e GridFS file ID são identidades diferentes.

- Document ID é público somente conforme Authorization;
- GridFS file ID é detalhe opaco de Infrastructure;
- API nunca aceita GridFS file ID como prova de acesso;
- download localiza conteúdo pela referência persistida no PostgreSQL;
- busca por `filename` é proibida como identidade, pois nomes não são únicos;
- buckets e nomes físicos não fazem parte do contrato público.

## Fluxo de upload

O upload é uma operação coordenada, idempotente e recuperável:

1. Application valida OrganizationContext, Permission, finalidade, limites e metadados.
2. PostgreSQL cria registro de upload iniciado com ID e IdempotencyKey.
3. Infrastructure transmite o conteúdo para GridFS usando ID opaco.
4. Titan calcula SHA-256 e tamanho durante o streaming.
5. Conteúdo é verificado contra tamanho e hash esperados, quando fornecidos.
6. Verificações de formato e segurança exigidas são executadas antes da disponibilidade.
7. PostgreSQL registra referência, hash confirmado e conclusão em transação.
8. Event e OutboxMessage correspondentes são gravados atomicamente no PostgreSQL.
9. Somente estado disponível permite download ou uso como Evidence.

GridFS não participa da transação PostgreSQL. A coordenação utiliza estado persistido e recuperação, não uma transação distribuída fictícia.

## Estados operacionais do upload

Estados iniciais em português:

`INICIADO`, `RECEBENDO`, `RECEBIDO`, `EM_VERIFICACAO`, `DISPONIVEL`, `FALHOU` e `EM_QUARENTENA`.

Esses estados representam processo técnico. Document de domínio só é reconhecido como utilizável após `DISPONIVEL`.

Transições são explícitas, auditáveis e idempotentes. Falha nunca é convertida silenciosamente em disponibilidade.

## Upload incompleto e órfãos

Conteúdo GridFS sem Document disponível é staging, não Document de domínio.

Processo de reconciliação deve localizar:

- upload iniciado sem conteúdo;
- conteúdo completo sem confirmação PostgreSQL;
- chunks incompletos;
- referência PostgreSQL sem conteúdo;
- hash ou tamanho divergente;
- objetos sem upload conhecido.

Staging abandonado pode ser removido por política aprovada, usando papel técnico separado e auditoria. Conteúdo já disponível não é removido por esse processo.

Quarentena preserva objeto suspeito sem permitir download normal ou uso em Decision.

## Integridade

SHA-256 é calculado pelo Titan sobre os bytes originais. Hash fornecido pelo cliente serve apenas para comparação.

O hash confirmado é armazenado no PostgreSQL e pode ser duplicado em metadado técnico do GridFS. Divergência sempre considera PostgreSQL autoritativo e conteúdo indisponível até investigação.

MD5 legado do GridFS não é prova de integridade do Titan. A documentação do MongoDB o trata como depreciado; o Titan implementa digest próprio.

Verificação ocorre:

- ao concluir upload;
- após restore;
- por amostragem ou rotina periódica aprovada;
- quando houver suspeita de adulteração;
- antes de operação de alta criticidade, quando Policy exigir.

## Imutabilidade e versões

Depois de disponível:

- bytes não são alterados;
- rename do GridFS não é operação de domínio;
- substituição é proibida;
- nova versão recebe novo Document ID, GridFS file ID e hash;
- relação entre versões fica no PostgreSQL;
- Correction ou Revocation não remove a versão original;
- APIs normais não expõem delete físico.

Retenção, expurgo legal e descarte criptográfico exigem ADR e política próprias.

## Organization e Authorization

MongoDB não oferece a mesma RLS decidida para PostgreSQL. Portanto:

- cliente nunca conecta diretamente ao MongoDB;
- Application autoriza usando registro PostgreSQL e OrganizationContext;
- adapter recebe referência opaca somente depois da Authorization;
- credencial de runtime possui menor privilégio e acesso apenas aos buckets necessários;
- metadado técnico inclui Organization para reconciliação, não para autorizar;
- download, exportação e verificação são auditados conforme criticidade;
- erro não revela existência de objeto de outra Organization;
- worker reconstrói contexto antes de acessar conteúdo.

Bucket compartilhado não implica Visibility entre Organizations. Estratégia física de buckets será definida na implementação com base em operação comprovada, sem virar contrato público.

## Validação de conteúdo

Antes de disponibilidade, o fluxo deve aplicar limites aprovados para:

- tamanho;
- formatos permitidos;
- nome e metadados não confiáveis;
- tipo declarado versus conteúdo identificado;
- conteúdo malicioso, quando houver mecanismo de detecção aprovado;
- arquivos compactados e risco de expansão;
- timeouts e consumo de recursos.

Conteúdo ativo não é executado ou renderizado em contexto privilegiado. Download usa headers seguros e nome sanitizado.

## Confiabilidade do MongoDB

Produção deve usar configuração compatível com durabilidade requerida, autenticação, TLS e write concern explicitamente aprovado. `w: "majority"` será avaliado como padrão de produção; sua garantia depende da topologia e journaling configurados.

Ambiente local pode usar topologia simplificada, mas não pode ser confundido com garantia de produção.

Versões de MongoDB e driver são fixadas e verificadas por compatibilidade antes da fundação.

## Backup e restauração coordenados

PostgreSQL e MongoDB são restaurados como conjunto lógico verificável.

Procedimento deve:

1. preservar identificadores e referências;
2. registrar pontos ou janelas de backup;
3. restaurar metadados e bytes;
4. reconciliar Documents disponíveis e objetos GridFS;
5. verificar tamanho e hashes;
6. identificar referências ausentes e órfãos;
7. manter conteúdo divergente indisponível;
8. produzir relatório auditável.

Backup não é considerado válido sem teste periódico de restauração.

## Observabilidade

Métricas devem incluir uploads iniciados, duração, bytes, falhas, quarentena, órfãos, divergência de hash, downloads e erros de reconciliação.

Logs não registram conteúdo binário, credenciais, tokens ou metadados pessoais desnecessários.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Banco transacional sem grandes binários; Document auditável no PostgreSQL; streaming por driver oficial; falhas recuperáveis; histórico versionado |
| Negativas | Sem transação atômica entre bancos; backup coordenado; autorização obrigatoriamente pela Application; maior operação; staging e órfãos reconciliados |

### Riscos e controles

| Risco | Controle |
|---|---|
| Conteúdo salvo sem registro | Estado de upload e reconciliação |
| Registro aponta para conteúdo ausente | Verificação antes de disponibilidade e após restore |
| Arquivo adulterado | SHA-256 calculado e reverificado |
| Acesso cross-Organization | Authorization no PostgreSQL e GridFS não exposto |
| Sobrescrita de versão | Novo Document e novo file ID |
| Upload malicioso | Limites, identificação, quarentena e download seguro |
| Backup inconsistente | Restauração coordenada e relatório de reconciliação |
| MongoDB virar banco de domínio | Adapter limitado e testes arquiteturais |

## Verificação automatizada

Testes devem comprovar:

- mesmo upload com IdempotencyKey não duplica Document;
- falha em cada etapa pode ser retomada ou encerrada;
- apenas `DISPONIVEL` pode ser baixado ou referenciado;
- hash e tamanho divergentes bloqueiam disponibilidade;
- outra Organization não acessa conteúdo;
- nova versão preserva a anterior;
- adapter não oferece rename, overwrite ou delete normal;
- reconciliação encontra ausência, órfão e divergência;
- restore preserva referências e hashes;
- módulos de domínio não importam driver MongoDB.

## Licenciamento e custo

A implantação será auto-hospedada e não dependerá de assinatura obrigatória. A versão Community e sua licença devem ser revisadas na ADR geral de licenças antes do uso em produção.

“Sem assinatura” não significa ausência de custo de servidor, backup, armazenamento, observabilidade e operação.

## O que esta ADR não decide

Permanecem para decisões próprias: versão de MongoDB e driver, topologia e alta disponibilidade, limites por formato, estratégia física de buckets, ferramenta de detecção de conteúdo malicioso, criptografia em nível de aplicação, retenção, expurgo e Visibility interorganizacional.

## Critérios de aceitação

A ADR pode ser aceita quando:

- PostgreSQL permanecer source of truth;
- GridFS armazenar apenas bytes e metadados técnicos;
- ausência de transação distribuída estiver tratada por estado e reconciliação;
- SHA-256 for calculado pelo Titan;
- apenas conteúdo verificado ficar disponível;
- nova versão criar novo Document;
- cliente nunca acessar MongoDB diretamente;
- autorização ocorrer antes do acesso ao adapter;
- backup e restore forem coordenados e verificáveis;
- MongoDB não armazenar entidades do domínio;
- decisões ainda pendentes permanecerem fora do escopo.

## Plano de reversão

Antes de armazenar Documents, a decisão pode ser substituída por nova ADR. Depois disso, mudança de storage exige migration incremental que preserve Document IDs, versões, hashes, referências, autorizações, auditoria e capacidade de verificar conteúdo antigo.
