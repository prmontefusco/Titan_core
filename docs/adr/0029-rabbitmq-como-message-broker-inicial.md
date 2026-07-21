# ADR 0029 — RabbitMQ como Message Broker inicial

**Status:** Aceita  
**Data:** 21 de julho de 2026  
**Decisores:** fundador e responsável pela arquitetura do Titan

## Contexto

A ADR-0006 define Transactional Outbox no PostgreSQL, entrega pelo menos uma vez, publicação confirmada, consumo com acknowledgement posterior ao commit, idempotência, retry, quarentena, replay e reconciliação. Ela preserva o Message Broker como transporte substituível e não escolhe produto nem executor de workers.

O Passo 1.4D precisa selecionar um broker gratuito e auto-hospedado para o ambiente local. A escolha deve atender às garantias já aceitas sem transformar o broker em fonte autoritativa, mecanismo de autorização, executor ou modelo de domínio.

## Requisitos da escolha

- código aberto e ausência de assinatura comercial obrigatória;
- imagem oficial e operação local reproduzível;
- persistência e confirmação explícita de publicação;
- redelivery e acknowledgement manual;
- backpressure e prefetch controláveis;
- roteamento para eventos, commands e jobs sem misturar suas semânticas;
- suporte a dead-letter ou quarentena operacional;
- autenticação, autorização, TLS e isolamento por ambiente;
- cliente Python mantido, sem levar tipos do produto ao Domain ou Application;
- operação inicial compreensível por equipe pequena;
- caminho conhecido para alta disponibilidade, backup, métricas e atualização.

## Alternativas consideradas

### RabbitMQ

- modelo de exchanges, bindings e queues apropriado a entrega de trabalho e eventos;
- publisher confirms e retornos de mensagens não roteadas;
- acknowledgements manuais, redelivery, prefetch e dead-letter exchanges;
- quorum queues para filas duráveis e replicadas em produção;
- interface de administração e ecossistema Python maduros;
- maior custo operacional que um broker mínimo e necessidade de compreender corretamente routing, confirmação, limites e dead-letter.

### NATS com JetStream

- servidor compacto, alta vazão, persistência, acknowledgements, consumers e replay;
- oferece work queues e deduplicação em janela;
- exige habilitar e operar JetStream; Core NATS isolado é `at-most-once` e não atende ao contrato;
- semânticas de stream, retention policy, subjects e consumer state ampliam a decisão além da fila de trabalho inicial;
- limites de retenção continuam aplicáveis e podem remover mensagem mesmo sob determinadas políticas, exigindo configuração cuidadosa.

### Apache Kafka ou Redpanda

- excelente retenção, replay, particionamento e ecossistema de streaming;
- adequado quando log distribuído e alto volume são necessidades centrais;
- topologia, particionamento, retenção e operação são desproporcionais ao MVP atual;
- o Titan já preserva OutboxMessage autoritativa no PostgreSQL e não necessita tornar o broker um log histórico central.

### PostgreSQL como fila permanente

- reduz a quantidade inicial de produtos;
- contraria a separação já aceita entre estado autoritativo e transporte;
- mistura polling, backpressure, retenção e carga de consumidores com o banco transacional;
- permanece útil para Outbox e recuperação, não como broker permanente.

## Proposta

Adotar **RabbitMQ 4.3** como Message Broker inicial, usando AMQP 0-9-1 no adapter de Infrastructure. A primeira implementação local utiliza RabbitMQ 4.3.3, fixado também pelo digest da imagem oficial.

A versão patch e o digest exatos são fixados no Compose. Atualizações de patch permanecem deliberadas, testadas e registradas. Não são utilizadas tags móveis como `latest`, `4` ou `management` sem versão.

Esta proposta escolhe somente o broker. Não escolhe Celery, Dramatiq ou outro executor de workers, que continua sujeito a decisão própria antes da implementação do consumo.

## Semântica obrigatória

### Publicação

O publisher:

- publica somente OutboxMessages de transações PostgreSQL confirmadas;
- utiliza mensagens persistentes e publisher confirms;
- utiliza publicação obrigatoriamente roteável, com detecção de retorno quando não existir destino;
- registra `BROKER_ACCEPTED` ou estado equivalente somente após confirmação positiva;
- preserva resultado desconhecido como elegível para nova tentativa com o mesmo `message_id`;
- não interpreta confirmação como consumo ou efeito de negócio.

### Consumo

O consumidor:

- utiliza acknowledgement manual;
- confirma somente após commit local do efeito e da deduplicação;
- limita prefetch e concorrência conforme o consumidor;
- rejeita ou posterga mensagem segundo classificação explícita da falha;
- não depende da memória do broker para idempotência durável;
- não confia em OrganizationContext, Roles ou Permissions transportadas.

### Quarentena e dead-letter

Dead-letter exchange e queue são mecanismos operacionais, não registro autoritativo de falha. O PostgreSQL preserva os estados, tentativas, motivos e referências necessários à auditoria e ao replay autorizado.

Falha permanente reconhecida pode encaminhar cópia para quarentena. Exceção desconhecida não é automaticamente permanente. Remover, expirar ou mover uma mensagem no broker não apaga a OutboxMessage nem o histórico de consumo.

Em produção, quando dead-letter com garantia pelo menos uma vez for exigido, a topologia deverá usar capacidades compatíveis de quorum queues e configuração que não silencie perda por overflow. Essa configuração será validada em passo próprio, não presumida por esta ADR.

## Topologia incremental

Nenhuma exchange ou queue vazia será criada sem produtor e consumidor reais.

O Passo 1.4D adicionará somente:

- um nó RabbitMQ local persistente;
- AMQP e interface de administração limitados a loopback;
- usuário e vhost locais substituíveis por configuração externa;
- health check e volume nomeado;
- versão e digest fixos;
- teste de publicação confirmada, consumo manual, redelivery e persistência técnica.

Exchanges, queues, routing keys, retry, dead-letter, publisher Titan e workers concretos serão criados nos passos funcionais correspondentes.

## Segurança

- credenciais padrão do Compose são exclusivamente locais;
- usuário `guest` não integra o contrato e não será utilizado pela aplicação;
- produção exige usuário, vhost e permissions mínimos por identidade de serviço;
- AMQP, administração, métricas e clustering não ficam publicamente expostos;
- produção exige TLS e secrets externos ao repositório e à imagem;
- management UI local não constitui autorização para expô-la em produção;
- payloads, headers, dead-letter e logs seguem classificação, retenção e minimização;
- broker não recebe Access Token, Refresh Token, ID Token, senha, chave privada ou documento binário.

## Persistência e disponibilidade

O volume local comprova reinício e recuperação básica, não alta disponibilidade.

Produção deverá decidir e testar:

- cluster com número ímpar de membros quando quorum queues forem utilizadas;
- storage, capacidade, limites, alarmes de memória e disco;
- política de overflow que rejeite publicação em vez de descartar silenciosamente quando a semântica exigir;
- backup de definições e recuperação de configuração;
- recuperação ou reconstrução segura das mensagens a partir da Outbox autoritativa;
- atualização compatível da série e do Erlang/OTP incorporado;
- RPO, RTO, métricas, alertas e procedimento de desastre.

O broker pode ser reconstruído a partir da configuração aprovada e da Outbox dentro das limitações registradas. Ele não substitui backup ou retenção do PostgreSQL.

## Fronteiras arquiteturais

Domain e Application podem conhecer Message, DomainEvent, IntegrationEvent, Command, Job, OutboxMessage e contratos internos aprovados. Não conhecem:

- RabbitMQ;
- AMQP;
- exchange, binding, queue ou delivery tag;
- channel, connection ou publisher confirm do produto;
- dead-letter exchange nativa;
- biblioteca cliente concreta.

Infrastructure traduz contratos internos para RabbitMQ. Capacidades específicas podem ser usadas sem alterar a semântica pública ou atravessar a fronteira do Core.

## Consequências

### Positivas

- correspondência direta com confirmação, redelivery e acknowledgement da ADR-0006;
- topologia adequada a trabalho assíncrono e roteamento de eventos;
- administração local visível e ecossistema maduro;
- caminho conhecido de fila única local para quorum queues em produção;
- independência preservada por adapter de Infrastructure.

### Negativas

- novo componente stateful para operar, atualizar, observar e recuperar;
- configuração incorreta pode perder mensagens não roteadas ou em dead-letter;
- alta disponibilidade exige cluster e capacidade adicionais;
- management UI e credenciais ampliam superfície operacional;
- série comunitária possui janela de suporte que exige atualizações frequentes.

## Riscos e controles

| Risco | Controle |
|---|---|
| Mensagem publicada sem rota | publicação obrigatoriamente roteável e tratamento de retorno |
| Confirmação confundida com processamento | estados separados e confirmação somente como aceitação do broker |
| Ack antes do commit | acknowledgement manual posterior à transação local |
| Redelivery duplica efeito | Inbox/invariante idempotente no PostgreSQL |
| Dead-letter perde mensagem | configuração validada e PostgreSQL autoritativo para falha/replay |
| Fila cresce sem limite | backpressure, prefetch, limites, alarmes e política de overflow explícita |
| Nó local interpretado como HA | produção exige decisão e teste de cluster/quorum |
| UI administrativa exposta | loopback local e rede privada em produção |
| Lock-in no protocolo ou cliente | adapter de Infrastructure e contratos internos genéricos |
| Broker vira repositório histórico | retenção limitada e Outbox/Audit autoritativos no PostgreSQL |

## Critérios de aceitação

A proposta poderá tornar-se aceita quando estiver confirmado que:

- RabbitMQ atende às garantias normativas da ADR-0006;
- publisher confirms, retorno de não roteada e acknowledgement manual são obrigatórios;
- PostgreSQL permanece autoritativo para Outbox, idempotência, quarentena lógica e replay;
- RabbitMQ não atravessa Domain ou Application;
- executor de workers permanece decisão separada;
- topologia local não é apresentada como topologia de produção;
- segurança, persistência, atualização e reversibilidade estão delimitadas;
- versão patch e digest estão fixados no Compose;
- NATS JetStream, Kafka/Redpanda e PostgreSQL-fila foram avaliados de forma suficiente para o MVP.

## Plano de reversão

Antes da implementação, a proposta pode ser rejeitada ou substituída sem migration de dados.

Depois da adoção, a troca preserva OutboxMessage, envelopes versionados, `message_id`, IdempotencyKey, ConsumerReceipt/Inbox, estados de quarentena e correlação. O novo adapter republica somente mensagens elegíveis a partir do PostgreSQL. Metadados nativos do RabbitMQ não integram o contrato migrável.

## Referências

- [RabbitMQ — release information](https://www.rabbitmq.com/release-information), consultada em 21 de julho de 2026.
- [RabbitMQ — publishers e publisher confirms](https://www.rabbitmq.com/docs/4.3/publishers), consultada em 21 de julho de 2026.
- [RabbitMQ — consumer acknowledgements e publisher confirms](https://www.rabbitmq.com/docs/4.3/confirms), consultada em 21 de julho de 2026.
- [RabbitMQ — quorum queues](https://www.rabbitmq.com/docs/4.3/quorum-queues), consultada em 21 de julho de 2026.
- [RabbitMQ — dead-letter exchanges](https://www.rabbitmq.com/docs/4.3/dlx), consultada em 21 de julho de 2026.
- [RabbitMQ — Docker Official Image](https://hub.docker.com/_/rabbitmq), consultada em 21 de julho de 2026.
- [NATS — JetStream](https://docs.nats.io/nats-concepts/jetstream), consultada em 21 de julho de 2026.
- [NATS — JetStream consumers](https://docs.nats.io/nats-concepts/jetstream/consumers), consultada em 21 de julho de 2026.
