# ADR 0007 — Checkpoints de integridade e timestamp independente
**Status:** Aceita  
**Data:** 20 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan preserva Events append-only, serialização canônica, hashes versionados e encadeamento verificável. Esses mecanismos detectam alteração, mas o relógio e o banco do próprio Titan não comprovam de forma independente que determinado digest existia em um instante.

O domínio já admite checkpoints como mecanismo de Integrity. O plano exige verificação independente e uma porta substituível para timestamp antes de escolher TSA, certificadora ou perfil jurídico.

Timestamp não comprova veracidade, autoria ou validade jurídica do conteúdo. Ele vincula um digest a uma afirmação temporal emitida por uma autoridade segundo uma política verificável.

## Problema

Definir:

- o que é ancorado por um checkpoint;
- quais instantes possuem significados distintos;
- fronteira entre checkpoint interno e timestamp externo;
- protocolo e validação do token;
- indisponibilidade, retry e resultado desconhecido;
- isolamento por Organization;
- renovação e preservação de longo prazo;
- verificação independente;
- limites jurídicos e tecnológicos da decisão.

## Princípios

1. **Tempo possui semântica:** instante alegado, registrado, observado e comprovado não são equivalentes.
2. **Digest mínimo:** TSA recebe digest e metadados estritamente necessários, nunca conteúdo de domínio.
3. **Sem retroatividade:** prova temporal começa no instante efetivamente declarado pela TSA.
4. **Negações explícitas:** ausência ou falha de token não é convertida em sucesso.
5. **Evidência preservada:** token inválido, expirado ou substituído não é apagado.
6. **Provider substituível:** Domain não conhece produto, SDK ou certificado de uma TSA concreta.
7. **Verificação independente:** prova não depende de segredo ou acesso ao banco do Titan.
8. **Isolamento:** checkpoint e suas provas respeitam Organization e Visibility.
9. **Evolução incremental:** Merkle, múltiplas TSAs e perfis jurídicos entram somente quando necessários.
10. **Integridade não é verdade:** resultado criptográfico nunca certifica o conteúdo material.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Somente relógio do Titan | Gratuito e simples | Não oferece prova temporal independente |
| TSA self-hosted | Controle operacional | Mesma parte controla dado, relógio e prova; não adquire confiança pública automaticamente |
| Blockchain pública | Âncora amplamente replicada | Custo, privacidade, latência, dependência externa e complexidade desnecessária |
| Armazenamento externo imutável | Detecta alteração posterior | Não necessariamente oferece tempo confiável ou token interoperável |
| TSA independente por protocolo aberto | Prova temporal verificável e provider substituível | Disponibilidade, validação, operação e possível custo externo |
| Múltiplas TSAs simultâneas | Redundância de confiança | Custo e complexidade maiores sem necessidade comprovada no Core inicial |

## Decisão

Adotar **IntegrityCheckpoint imutável** e porta **TimestampProvider** substituível. O perfil interoperável inicial de timestamp é compatível com RFC 3161.

O checkpoint é criado e persistido antes da solicitação externa. TimestampToken bruto somente forma TemporalAnchor depois de validado, sem alterar digest ou conteúdo original.

A TSA concreta, seu nível de confiança, eventual credenciamento e custo serão escolhidos por perfil e jurisdição em decisão separada.

## Modelo técnico

Os termos não são sinônimos:

- **Digest:** resultado criptográfico calculado sobre bytes determinados;
- **IntegrityCheckpoint:** registro imutável que define conjunto coberto, serialização, algoritmo e Digest;
- **TimestampToken:** resposta bruta assinada pela TSA sobre um `messageImprint`;
- **TemporalAnchor:** associação validada entre IntegrityCheckpoint, tentativa e TimestampToken.

Receber TimestampToken não cria TemporalAnchor. A associação somente existe após validação bem-sucedida do `messageImprint` e dos demais requisitos do perfil.

Esses termos são contratos técnicos desta ADR. Não se tornam automaticamente conceitos normativos do Domain sem atualização aprovada do `DOMAIN.md`.

## Semântica dos instantes

O Titan distingue:

- **ocorrido em:** instante alegado ou reconhecido para o fato;
- **registrado em:** instante em que o registro entrou no Titan;
- **observado em:** leitura do relógio do Titan durante uma operação;
- **solicitado em:** instante em que a emissão do timestamp foi solicitada;
- **comprovado em:** instante declarado em TimestampToken validado;
- **validado em:** instante em que o Titan ou verificador executou a validação.

`observado em` não é prova temporal externa. `comprovado em` não substitui `ocorrido em` nem afirma quando o fato real aconteceu.

Todos os instantes possuem timezone ou representação UTC inequívoca, precisão conhecida e fonte identificável.

## IntegrityCheckpoint

IntegrityCheckpoint não é hash isolado. É registro técnico imutável que define e ancora um estado verificável da cadeia ou conjunto delimitado.

Preserva, quando aplicável:

- identificador estável;
- RecordOwnerOrganization;
- tipo, identificador e critérios do escopo;
- delimitadores, primeira e última sequência cobertas;
- quantidade de registros;
- hash inicial, hash final ou raiz verificável;
- algoritmo de hash e versão;
- versão da CanonicalSerialization;
- digest enviado para timestamp;
- instante observado;
- Actor ou processo produtor;
- correlação e causação;
- estado de timestamp;
- referências imutáveis às tentativas e tokens;
- política ou perfil de confiança exigido.

O Digest do checkpoint é calculado sobre bytes produzidos por versão específica da CanonicalSerialization e inclui escopo, delimitadores, contagem, raiz ou cabeça da cadeia, algoritmos e versões. Alterar metadado protegido invalida o Digest.

Ordem de campos ou registros, timezone, normalização Unicode, representação decimal e tratamento de campos ausentes pertencem à versão da serialização. Recalcular objeto semanticamente equivalente com serialização diferente não verifica o checkpoint original. Regras e implementações históricas permanecem testáveis e disponíveis durante toda a retenção.

Checkpoint não reescreve Events, não corrige cadeia inválida e não transforma Projection em fonte de verdade.

## Escopo e estrutura inicial

O primeiro mecanismo ancora cabeça ou conjunto verificável de uma cadeia aprovada. A prova permite recalcular o Digest a partir dos registros e detectar ponto de divergência.

O checkpoint determina exatamente os registros cobertos por IDs ordenados, sequências, contagem, último hash, critérios e leitura transacional consistente aplicáveis. Intervalo de datas isolado é insuficiente, pois registros podem chegar tardiamente ou fora de ordem.

Checkpoint protegido pertence a uma única RecordOwnerOrganization. Agregação entre Organizations é proibida inicialmente para evitar vazamento de existência, volume ou correlação.

Árvore de Merkle não integra o mecanismo inicial. Sua adoção exige volume real, formato canônico de folhas, regra de ordenação, prova de inclusão, proteção contra duplicação e nova aprovação.

## TimestampProvider

Application utiliza porta interna que recebe:

- digest;
- algoritmo;
- perfil ou política requerida;
- nonce, quando aplicável;
- correlação técnica.

O adapter de Infrastructure realiza comunicação, autenticação técnica e tratamento do protocolo. Domain não conhece URL, credencial, RFC 3161, TSA, certificado, CMS ou formato do token.

O provider retorna bytes imutáveis do token, metadados mínimos de transporte e resultado técnico. O Titan preserva os bytes originais para validação independente.

Provider falso ou self-hosted é permitido em desenvolvimento e testes, identificado como não confiável para prova jurídica ou independente.

TSA operada pela mesma entidade do Titan pode testar integração e protocolo, mas não oferece por si só independência institucional, mesmo com RFC 3161 e criptografia corretos. Confiança depende também de governança, política e reconhecimento da autoridade.

## Solicitação e idempotência

Retries preservam o mesmo IntegrityCheckpoint e `messageImprint`. Cada tentativa possui identidade, instante e correlação próprios e pode usar novo nonce ou provider previamente compatível, sem alterar o conjunto coberto.

Tokens distintos para o mesmo Digest podem coexistir, formar TemporalAnchors próprios depois de validados e permanecer correlacionados. IdempotencyKey protege a operação Titan; protocolo externo pode emitir mais de um token legítimo.

Falha de comunicação pode produzir resultado desconhecido: a TSA pode ter emitido token sem que a resposta tenha chegado ao Titan. Não se presume recebimento nem ausência de emissão. A tentativa permanece reconciliável e nova solicitação preserva checkpoint, Digest, correlação e histórico.

Quando a solicitação incluir nonce, somente token com o mesmo nonce válido pode ser associado à tentativa. A obrigatoriedade depende do perfil técnico, mas nonce presente nunca é ignorado.

## Validação do TimestampToken

TimestampToken recebido permanece não confiável antes da validação criptográfica completa. Recebimento, parsing ou persistência dos bytes não constituem prova temporal válida.

A validação confirma, no mínimo e conforme perfil:

- formato e finalidade esperados;
- correspondência entre `messageImprint`, digest e algoritmo;
- assinatura criptográfica do token;
- algoritmo em allowlist;
- certificado apropriado para timestamp;
- cadeia até trust anchor permitido;
- política ou OID esperada;
- período de validade relevante;
- correspondência do nonce, sempre que enviado;
- estado histórico da cadeia e da revogação no instante relevante;
- instante declarado e precisão permitida;
- integridade do material associado.

Trust anchor, política e algoritmos são configurados explicitamente. Valores do token não direcionam livremente o verificador para URLs, certificados ou trust anchors.

Expiração atual do certificado não invalida automaticamente token histórico. Revogação anterior ou posterior, ausência de material histórico, cadeia atualmente não confiável e política de longo prazo são avaliadas separadamente e explicadas conforme o perfil.

Resultado agregado é:

- `VALIDO`, quando todas as condições do perfil forem satisfeitas;
- `INVALIDO`, quando houver falha criptográfica ou violação determinística;
- `INDETERMINADO`, quando faltar material ou não for possível concluir.

O resultado registra escopo efetivamente analisado, perfil, instante, verificações, warnings e códigos de razão verificáveis, como divergência do Digest ou `messageImprint`, assinatura inválida, nonce divergente, política não permitida, material de confiança ausente, revogação indisponível, serialização indisponível ou conjunto incompleto.

`INDETERMINADO` não é falha genérica nem pode ser convertido em `VALIDO` por configuração permissiva. Um único booleano é insuficiente.

## Estados operacionais

O ciclo operacional contém, conceitualmente:

- checkpoint criado;
- solicitação enviada;
- resultado de comunicação desconhecido;
- token recebido e ainda não validado;
- validação concluída como válida, inválida ou indeterminada;
- nova tentativa pendente ou falha operacional.

Estado operacional da tentativa, resultado de validação do token e existência de TemporalAnchor são distintos. Códigos finais em português e transições serão consolidados no `DOMAIN.md` ou contrato de Application antes da implementação.

## Indisponibilidade e fallback

Indisponibilidade da TSA não desfaz checkpoint nem bloqueia operações cujo perfil exija apenas integridade interna.

Quando Policy exigir prova temporal externa, publicação, emissão ou conclusão correspondente permanece pendente até token válido.

Retry preserva checkpoint e `messageImprint`, não necessariamente os bytes da requisição. Provider secundário somente substitui o principal quando estiver previamente aprovado para o perfil exigido, incluindo política, cadeia, algoritmos, precisão, jurisdição, qualificação e assurance. Compatibilidade RFC 3161 não implica equivalência jurídica ou regulatória.

Relógio do Titan, timestamp do banco, log, broker, arquivo ou operador nunca substitui TSA. Não existe carimbo retroativo nem modo de emergência que marque token ausente como válido.

## Renovação e preservação

Token e material de validação são preservados mesmo após expiração, revogação, obsolescência de algoritmo ou nova ancoragem.

Nova ancoragem não substitui ou altera TimestampToken ou TemporalAnchor anterior. Cria prova correlacionada sobre checkpoint original, token anterior ou novo Digest de preservação, conforme mecanismo aprovado. A cadeia histórica permanece disponível e o instante original não muda.

Antes de algoritmo, certificado ou material de revogação perder utilidade, processo aprovado pode acrescentar prova de preservação. Política de longo prazo será definida com VerificationBundle e assinatura.

Backup e restauração preservam checkpoints, tokens, tentativas, certificados, políticas, correlações e material necessário à validação.

## Verificação independente

Verificador independente recebe:

- conteúdo ou registros cobertos;
- regras e versão de serialização;
- algoritmos;
- checkpoint;
- TimestampToken;
- cadeia de certificados;
- trust anchors e política aplicável;
- material de revogação necessário.

Ele recalcula hashes, valida escopo e intervalo, confere o token e produz resultado explicado sem consultar segredo ou estado mutável do Titan.

A auditoria distingue RecordOwnerOrganization do checkpoint, Actor ou processo solicitante, ServiceIdentity que executou a integração e provider e identidade certificada da TSA. Organization responsável não precisa ser a identidade técnica utilizada perante a TSA.

Ausência de material resulta em `INDETERMINADO`, não em aceitação por conveniência.

## Privacidade e segurança

Somente digest e metadados mínimos são enviados à TSA. Organization, Actor, Subject, conteúdo, filename e dado pessoal não são enviados salvo exigência formal do protocolo e aprovação de privacidade.

Credenciais de acesso ao provider ficam em Infrastructure e secret storage. Não entram no Domain, checkpoint, token auditado ou logs.

Respostas possuem limite de tamanho, parsing seguro e timeouts. Endpoints e trust anchors são previamente configurados; dados externos não provocam acesso arbitrário à rede.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Alteração detectável; prova temporal independente opcional; provider substituível; validação offline; preservação por Organization |
| Negativas | Novo fluxo assíncrono; dependência operacional externa; material de validação adicional; custo possível; renovação de longo prazo |

## Riscos e controles

| Risco | Controle |
|---|---|
| Relógio local tratado como TSA | Semântica distinta e resultado pendente |
| Conteúdo enviado ao provider | Somente digest e metadados mínimos |
| Token de outro digest | Validação obrigatória do `messageImprint` |
| TSA indisponível | Checkpoint preservado, tentativa própria e provider previamente aprovado para o perfil |
| Timestamp retroativo | Instante do token preservado e ausência nunca convertida em sucesso |
| Trust anchor escolhido pelo token | Configuração explícita e allowlist |
| Vazamento entre Organizations | Checkpoint por RecordOwnerOrganization |
| Self-hosted apresentado como qualificado | Perfil de desenvolvimento explícito |
| Prova antiga ficar inverificável | Preservação de material e renovação correlacionada |
| Conjunto omitido apesar de digest válido | Delimitadores, contagem, critérios e leitura consistente |
| Token recebido tratado como prova | Estado não validado e TemporalAnchor somente após validação |
| Serialização histórica indisponível | Versões preservadas e testáveis durante a retenção |
| Timestamp confundido com verdade | Resultado declara somente existência do digest |

## Verificação automatizada

Testes devem cobrir:

- cálculo determinístico do checkpoint;
- conjunto coberto completo, omissão e inclusão indevida;
- alteração de registro, intervalo, algoritmo ou versão;
- isolamento entre duas Organizations;
- token válido para o digest correto;
- token de outro digest;
- assinatura, cadeia, política, algoritmo, nonce e validade incorretos;
- material insuficiente com resultado `INDETERMINADO`;
- token recebido mantido não confiável antes da validação;
- indisponibilidade e retries distintos com o mesmo checkpoint e Digest;
- resultado de comunicação desconhecido;
- múltiplos tokens válidos correlacionados;
- nonce enviado ausente ou divergente na resposta;
- provider secundário incompatível com o perfil;
- certificado expirado atualmente e revogação antes ou depois da emissão;
- versão de serialização histórica indisponível;
- ausência de conteúdo de domínio na solicitação;
- provider falso identificado como não confiável;
- preservação depois de nova ancoragem;
- distinção entre Organization, Actor, ServiceIdentity e TSA;
- backup, restauração e verificação independente.

## Critérios de aceitação

A ADR pode ser aceita quando:

- instante observado e comprovado forem distintos;
- Digest, checkpoint, token e TemporalAnchor forem distintos;
- checkpoint identificar exatamente conjunto coberto e ser recalculável;
- TSA receber somente digest mínimo;
- validação do token for normativa e explicável;
- indisponibilidade não fabricar prova temporal;
- operação que exija timestamp aguardar token válido;
- token recebido permanecer não validado até conclusão criptográfica;
- retries preservarem checkpoint e Digest com tentativas distintas;
- múltiplos tokens válidos puderem permanecer correlacionados;
- provider secundário exigir o mesmo perfil previamente aprovado;
- serialização histórica permanecer disponível durante a retenção;
- renovação nunca sobrescrever prova anterior;
- auditoria distinguir Organization, solicitante, executor e TSA;
- resultado possuir estado, códigos de razão e escopo analisado;
- resultado admitir válido, inválido e indeterminado;
- isolamento por Organization for mantido;
- provider concreto permanecer substituível;
- self-hosted não for apresentado como confiança independente;
- timestamp não implicar autoria, verdade ou validade jurídica;
- Merkle, blockchain, chaves e assinatura permanecerem fora do escopo inicial.

## O que esta ADR não decide

Esta ADR não escolhe:

- TSA, ACT, certificadora ou fornecedor concreto;
- credenciamento ICP-Brasil, eIDAS ou efeito jurídico;
- chave de assinatura do Titan ou seu armazenamento;
- assinatura de Evidence ou Dossier;
- frequência e tamanho final de checkpoints;
- árvore de Merkle;
- blockchain;
- valores finais de timeout, retry, retenção e precisão;
- formato completo do VerificationBundle.

## Referências normativas
RFC 3161 — Internet X.509 Public Key Infrastructure Time-Stamp Protocol; RFC 5816 — atualizações ao RFC 3161; e DOC-ICP-11/DOC-ICP-11.01 — Rede de Carimbo do Tempo na ICP-Brasil, quando o perfil brasileiro for aplicável.

## Plano de reversão

Antes da implementação, esta proposta pode ser substituída por nova ADR. Depois da adoção, troca de provider preserva checkpoints, digests, tokens, tentativas, perfis e resultados históricos. Evidência emitida por provider anterior não é reescrita.
