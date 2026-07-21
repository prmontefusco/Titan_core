# ADR 0025 — Valkey para cache e coordenação efêmera
**Status:** Aceita  
**Data:** 21 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan precisará reduzir leituras repetidas, controlar abuso e coordenar trabalho técnico entre instâncias. O PostgreSQL permanece autoritativo; o Message Broker transporta mensagens; Outbox e Inbox preservam confiabilidade. Nenhuma dessas responsabilidades deve migrar silenciosamente para um cache em memória.

O plano aprovado indica Valkey como tecnologia gratuita para cache. Valkey é open source sob licença BSD e oferece expiração, eviction, replicação e persistência opcional. Essas capacidades não transformam uma instância em fonte autoritativa nem fornecem, por si só, consistência forte após failover.

Esta ADR decide finalidade e limites. Configuração física, versão, topologia e operação serão tratadas no passo de infraestrutura.

## Problema

Definir:

- quais usos de Valkey são permitidos e proibidos;
- como chaves preservam Organization, Purpose, versão e classificação;
- como TTL, eviction e invalidação afetam corretude;
- como impedir cache stampede e dados obsoletos;
- quando falhar aberto, fechado ou recorrer ao PostgreSQL;
- limites de leases, locks, fencing e coordenação;
- como separar Valkey de Message Broker, Outbox, Inbox e banco;
- como testar perda completa, failover, atraso e partição.

## Princípios

1. **Descartável por desenho:** apagar todo o Valkey não perde fato, decisão, auditoria ou obrigação.
2. **PostgreSQL autoritativo:** cache nunca confirma estado de domínio sem regra de freshness aplicável.
3. **Ausência não é negação:** cache miss não prova inexistência do objeto.
4. **TTL não é retenção:** expiração técnica não executa disposição nem cumpre LegalHold.
5. **Eviction é esperada:** corretude não depende de uma chave continuar presente.
6. **Lock não cria verdade:** lease expirada ou failover pode permitir concorrência.
7. **Falha é contextual:** comportamento degradado depende do risco da operação.
8. **Isolamento explícito:** chave e acesso não atravessam Organization, ambiente, Purpose ou versão.

## Invariantes adicionais

- cache hit não prova existência, autorização ou validade material atuais;
- entrada restaurada exige nova admissão por versão, contexto e freshness;
- key não contém identificador pessoal, secret ou informação que revele recurso protegido;
- negative caching distingue ausência, negação, inacessibilidade e indeterminação;
- lease não autoriza commit crítico sem validação na fonte autoritativa;
- fencing protege somente quando token obsoleto é rejeitado pelo recurso protegido;
- falha não converte resultado inconclusivo em resposta vazia conclusiva;
- resposta degradada declara capacidades removidas, freshness e limitações;
- persistence e replication do Valkey são otimizações, não reconstrução histórica.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Sem cache distribuído | Menos infraestrutura | Maior carga e rate limiting inconsistente |
| Cache local por processo | Simples | Invalidação e limites divergem entre instâncias |
| PostgreSQL para toda coordenação | Autoridade transacional | Contenção e custo para usos efêmeros intensos |
| Valkey delimitado e reconstruível | Baixa latência e coordenação | Nova dependência e estados obsoletos |
| Valkey como banco ou broker universal | Menos produtos | Mistura durabilidade, entrega e cache |

## Decisão

Adotar Valkey exclusivamente na Infrastructure para estado derivado, efêmero e reconstruível.

Usos iniciais permitidos:

- cache de leitura derivada;
- cache curto de metadata externa validada;
- rate limiting e proteção contra abuso;
- deduplicação técnica curta que não substitua idempotência autoritativa;
- leases e coordenação best-effort com fencing quando exigido;
- supressão temporária de trabalho duplicado;
- sinalização efêmera de invalidação ou refresh.

Usos proibidos:

- fonte de verdade de Domain, Authorization, Membership, grant ou Policy;
- armazenamento exclusivo de Event, Evidence, Decision, Audit ou DataAccessRecord;
- Outbox, Inbox, ConsumerReceipt ou deduplicação necessária ao replay;
- Message Broker durável do Titan;
- scheduler autoritativo, workflow ou fila de jobs definitiva;
- armazenamento de password, token, secret, chave privada ou payload bruto;
- controle exclusivo de saldo, sequência, unicidade ou invariante de negócio;
- prova de retenção, disposição, entrega, leitura ou processamento.

Nenhum conceito Valkey integra o Domain. Portas e envelopes técnicos pertencem a Application e Infrastructure.

## CacheProfile

Contrato técnico versionado que define, por caso de uso:

- namespace e versão;
- origem autoritativa;
- Organization, Purpose e escopo;
- tipo de dado e DataClassification permitidos;
- TTL, jitter e freshness máxima;
- estratégia de invalidação e reconstrução;
- política de eviction esperada;
- comportamento em miss, timeout, indisponibilidade e dado inválido;
- AuthoritativeSourceReference resolvida pelo caso de uso;
- freshness boundary e bounded staleness;
- NegativeCachePolicy e estratégia de degradação;
- serialization version e requisito de criptografia;
- limites de tamanho e cardinalidade;
- métricas e redaction.

Ausência de CacheProfile impede cache. Cliente não escolhe TTL, namespace ou comportamento de falha.

## CacheKey

Identidade técnica opaca e determinística que inclui versão do namespace e todos os contextos capazes de alterar o resultado:

- ambiente;
- Organization ou escopo público explícito;
- principal ou capacidade quando relevante;
- Purpose e operação;
- recurso e versão;
- Policy, DataContract ou perfil aplicável;
- variante, idioma e formato quando alterarem a resposta.

Chave não contém PII, token, secret, email, nome ou Identifier sensível em claro. Digest previsível de dado sensível também não é usado sem análise de correlação.

Ausência de Organization só é permitida para dado realmente público e versionado. Compartilhamento de mesma instância não implica compartilhamento de namespace.

## AuthoritativeSourceReference

Referência interna resolvida pelo caso de uso para PostgreSQL, Source externa ou Artifact autorizado capaz de reconstruir a materialização dentro de finalidade e limitações declaradas.

Fonte aprovada não é necessariamente suficiente para conclusão sensível. A reconstrução ainda avalia Authorization, freshness, cobertura e limitações.

## CacheEntryEnvelope

Envelope técnico com payload ou referência mínima, schema_version, profile_version, source_version, AuthorizationContextVersion, created_at, valid_until, stale_until, source_digest, classificação segura, integrity marker e limitações.

Conteúdo é minimizado. Artifact, Document, payload externo bruto e Evidence sensível permanecem nos armazenamentos aprovados e são referenciados somente quando necessário.

Entrada inválida, incompatível, sem versão ou fora do profile é ignorada e reconstruída; nunca é promovida por tolerância silenciosa.

## NegativeCachePolicy

Contrato interno que declara quais resultados negativos podem ser armazenados, escopo, TTL curto, fonte, cobertura e invalidação.

`NAO_ENCONTRADO`, `NEGADO`, `INACESSIVEL` e `INDETERMINADO` não são intercambiáveis nem compartilham entrada por padrão. Negação não é persistida como inexistência; indeterminação não vira coleção vazia.

## TTL, freshness e invalidação

TTL limita reutilização técnica e não substitui FreshnessProfile, validade jurídica, revogação, retenção ou disposição.

Dados de autorização usam cache curto e revalidável. Mudança de Membership, grant, restrição, Policy, User ou ServiceIdentity deve impedir uso obsoleto por versionamento, invalidation event ou fallback autoritativo. Invalidação pode reduzir janela, mas não é a única garantia de segurança.

AuthorizationContextVersion ou RevocationEpoch integra a key e o envelope quando o profile armazenar decisão derivada de autorização. Mudança material avança a versão e impede novos hits na geração anterior, sem eliminar revalidação quando exigida.

Preferir versioned keys e bounded staleness a deleção perfeita. Mensagem de invalidação perdida não pode manter autorização além do limite aprovado.

TTL recebe jitter controlado para evitar expiração simultânea. Negative caching é curto, explícito e nunca distingue externamente objeto inexistente de invisível.

## Stampede e refresh

Cache miss concorrente pode usar single-flight ou lease curta para limitar reconstruções. Quem não obtém lease pode aguardar com limite, consultar origem ou retornar degradação segura conforme profile.

Lease abandonada expira. Refresh antecipado não estende freshness sem nova leitura autoritativa. Stale-while-revalidate somente é permitido quando profile declarar que dado obsoleto dentro da janela não afeta segurança ou decisão.

## Rate limiting

RateLimitProfile versionado define sujeito técnico, Organization, capacidade, endpoint ou caso de uso, janela, algoritmo lógico, limites, burst, custo, exceções autorizadas e comportamento de falha.

Rate limit reduz abuso e não substitui Authentication, Authorization, quota contratual ou proteção de infraestrutura. Identificador de chave é opaco e não expõe PII.

Operações sensíveis podem falhar de forma fechada quando o limitador estiver indisponível. Operações públicas de baixo risco podem usar limite local conservador ou degradação aprovada. Nunca existe fail-open universal.

Resposta não revela se o limite pertence a User, Organization, recurso invisível ou investigação. Exceções administrativas são temporais, mínimas e auditadas.

## Leases, locks e fencing

Distributed lease representa posse temporária best-effort, não exclusão absoluta.

Toda lease preserva resource key opaca, holder, LeaseId, fencing token monotônico dentro da autoridade definida, issued_at, expires_at e finalidade.

Operação cujo atraso possa violar invariante exige validação do fencing token no recurso autoritativo ou transação PostgreSQL equivalente. Processo pausado não pode gravar depois que lease expirou apenas porque ainda acredita ser owner.

Lock sem fencing é permitido somente para otimização idempotente cujo processamento duplicado seja seguro. Unicidade, transferência, publicação, disposição, assinatura, sequence e efeitos de negócio usam constraints ou transações autoritativas.

`lock adquirido` não significa autoridade para commit. A fonte protegida registra ou valida resource, token, emissão, expiração, owner técnico, versão e resultado da validação quando o efeito for crítico.

Renovação é limitada e observável. Resultado desconhecido de aquisição ou release não prova posse ou liberação.

## Deduplicação e idempotência

Valkey pode suprimir repetição técnica dentro de janela curta, mas não substitui IdempotencyKey, Inbox, ConsumerReceipt, constraint ou registro transacional exigido pelo caso de uso.

Perda da chave pode repetir computação, nunca efeito de negócio não idempotente. Replay permitido por período superior à TTL usa deduplicação durável no PostgreSQL.

## Indisponibilidade e degradação

Cada CacheProfile classifica comportamento:

- `RECORRER_A_FONTE_AUTORITATIVA`: consultar PostgreSQL ou fonte aprovada;
- `NEGAR_COM_SEGURANCA`: impedir operação sensível;
- `DEGRADAR_COM_LIMITES`: oferecer capacidade reduzida e explícita;
- `IGNORAR_OTIMIZACAO`: executar sem cache.

Esses valores formam `CacheFailureBehavior`. O resultado posterior é `CacheResolutionResult`: `RESOLVIDO`, `RESOLVIDO_COM_DEGRADACAO`, `NEGADO_COM_SEGURANCA` ou `INDETERMINADO`. Recorrer à fonte pode terminar em qualquer resultado compatível com a observação.

`DegradedCapability` registra capacidades disponíveis e removidas, freshness, fonte, prazo, ReasonCodes e limitações. Presentation diferencia visualmente degradação de funcionamento normal; não permite Decision oficial, exportação, mudança de grant ou efeito irreversível quando o profile os remover.

Circuit breaker, timeout e bulkhead evitam esgotar recursos. Recuperação do Valkey não torna entradas antigas confiáveis; warm-up reconstrói a partir das fontes autoritativas.

Circuit breaker aberto registra decisão local de suspender chamadas, não indisponibilidade comprovada da Source. Timeout não prova que operação externa deixou de executar.

Warm-up é nova materialização e reaplica CacheProfile, Organization, Purpose, classificação, DataContract, Authorization, schema, freshness e versão da key. Entrada incompatível é descartada, não migrada silenciosamente.

## Persistência e replicação

O Titan não depende de RDB, AOF ou replicação do Valkey para durabilidade de negócio. Persistência pode acelerar warm-up ou suportar necessidade operacional aprovada, mas perda total continua recuperável.

Replicação assíncrona e failover podem perder writes reconhecidos conforme configuração; por isso contador, lock ou cache não sustentam conclusão definitiva.

Backup de Valkey não integra backup obrigatório de domínio por padrão. Se habilitado, recebe DataClassification, DataLocationProfile, RetentionAssignment, criptografia e testes próprios.

Restore submete cada entrada a processo de admissão; não recoloca diretamente autorizações revogadas, versões antigas, namespaces aposentados, entradas expiradas ou dados além da retenção operacional.

## Segurança

Valkey fica em rede privada, sem exposição pública, com autenticação, TLS quando aplicável, ACL de menor privilégio, comandos administrativos restritos e credenciais por ambiente e aplicação.

Application runtime não executa administração, flush global, mudança de configuração ou acesso a namespace alheio. Observabilidade coleta métricas e metadados seguros, não valores.

Namespace na key não substitui ACL, credenciais separadas, validação de contexto, segregação de ambientes ou Authorization. Conhecer o padrão da key não concede leitura.

Limites de memória, tamanho, cardinalidade e clientes impedem abuso. Eviction policy é compatível com uso exclusivamente descartável. Falha de serialização ou conteúdo inesperado não executa código.

Serialização usa tipos permitidos e schema versionado, sem desserialização genérica executável. Conteúdo incompatível produz miss seguro e compressão possui limite de expansão.

## Separação de responsabilidades

| Necessidade | Autoridade |
|---|---|
| Estado de domínio, autorização e auditoria | PostgreSQL |
| Bytes de Artifact ou Document | GridFS |
| Entrega assíncrona | Message Broker |
| Publicação transacional | Outbox no PostgreSQL |
| Consumo idempotente durável | Inbox/ConsumerReceipt no PostgreSQL |
| Cache e coordenação efêmera | Valkey |

Valkey não é usado como broker do Celery nesta decisão. Produto de Message Broker e executor permanecem decisões próprias.

## Observabilidade

Métricas incluem hit/miss, idade no hit, latência, timeout, fallback, negação segura, degradação, eviction, expiração, memória, cardinalidade por profile, hot keys, stampede, reconstrução, versões e contextos rejeitados, chaves órfãs, invalidações recebidas e aplicadas, lease expirada, fencing rejeitado e tempo de recuperação.

Logs não contêm chave sensível ou value. Métricas não usam labels com User, objeto ou Organization. CorrelationId seguro relaciona fallback e reconstrução. Alerta de disponibilidade não é incidente confirmado automaticamente.

## Testabilidade

Testes futuros devem cobrir:

- perda total do Valkey sem perda autoritativa;
- cache miss apresentado como objeto inexistente;
- negative cache ocultando objeto criado posteriormente;
- negação armazenada como inexistência ou indeterminação como lista vazia;
- key contendo email, CPF, token ou Identifier sensível;
- Organization, Purpose ou versão ausente na key;
- ambiente de homologação lido em produção;
- schema ou formato diferente reutilizando a mesma key;
- dado público e protegido compartilhando namespace;
- Membership ou grant revogado ainda autorizado pelo cache;
- invalidação perdida ultrapassando bounded staleness;
- TTL tratado como retenção ou disposição;
- eviction quebrando caso de uso;
- stampede após expiração simultânea;
- stale-while-revalidate usado em decisão sensível;
- stale entry servida além da janela de degradação;
- indisponibilidade com comportamento diferente do profile;
- rate limit vazando identidade ou recurso invisível;
- lease expirada permitindo writer antigo;
- lock sem fencing protegendo invariante;
- fencing token não validado no PostgreSQL ou recurso autoritativo;
- owner sem autoridade renovando lease;
- failover duplicando efeito não idempotente;
- deduplicação expirada antes da janela de replay;
- token, secret, PII ou payload bruto no cache ou log;
- restore do Valkey promovendo entrada obsoleta;
- circuit breaker apresentado como Source comprovadamente indisponível;
- timeout apresentado como efeito externo não executado;
- rate limit de uma Organization afetando outra;
- warm-up causando stampede sobre fonte autoritativa;
- representação ampla respondendo FieldScope reduzido;
- payload comprimido causando expansão descontrolada;
- Valkey usado como broker, Outbox, Inbox ou Audit.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Menor latência; proteção contra abuso; coordenação reconstruível; tecnologia gratuita |
| Negativas | Nova dependência; invalidação; estados obsoletos; operação e observabilidade adicionais |

## Critérios de aceitação

A ADR pode ser aceita quando:

- Valkey permanecer efêmero e reconstruível;
- PostgreSQL continuar autoritativo;
- usos permitidos e proibidos forem explícitos;
- CacheProfile definir contexto e comportamento de falha;
- keys isolarem ambiente, Organization, Purpose e versão;
- TTL, freshness, retenção e disposição permanecerem distintos;
- invalidação não for garantia única de Authorization;
- leases críticas utilizarem fencing ou autoridade transacional;
- deduplicação efêmera não substituir Inbox ou idempotência durável;
- indisponibilidade possuir comportamento por risco;
- dados sensíveis, tokens e secrets não forem armazenados;
- Valkey, Message Broker, Outbox e PostgreSQL permanecerem distintos;
- versão, topologia e persistence mode ficarem para implementação.

## Referências

- Valkey, visão geral e licença: <https://valkey.io/>.
- Valkey, persistência: <https://valkey.io/topics/persistence/>.
- Valkey, replicação e limites de consistência: <https://valkey.io/topics/replication/>.
- Valkey, eviction: <https://valkey.io/topics/lru-cache/>.

Referências consultadas em 21 de julho de 2026.

## O que esta ADR não decide

Esta ADR não escolhe versão, client library, topologia standalone, Sentinel ou Cluster, persistence mode, memory policy, tamanho, número de réplicas, cloud ou configuração física. Também não seleciona Message Broker, Celery backend ou schema de chave definitivo.

## Plano de reversão

Valkey pode ser removido com perda apenas de estado efêmero. A Application deve continuar correta por fallback, degradação aprovada ou negação segura.

Troca de tecnologia preserva portas, CacheProfiles e semântica de falha. Nenhum Event, Decision, Audit, grant, mensagem durável ou Evidence depende de exportar o dataset Valkey.
