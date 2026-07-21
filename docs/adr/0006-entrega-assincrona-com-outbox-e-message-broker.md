# ADR 0006 — Entrega assíncrona com Outbox e Message Broker
**Status:** Aceita  
**Data:** 20 de julho de 2026  
**Decisores:** responsável pelo produto e arquitetura do Titan

## Contexto

O Titan executará tarefas que não devem prolongar a requisição original, como atualização de projeções, processamento de documentos, integrações e trabalhos derivados de Events.

O domínio já define OutboxMessage como registro transacional no PostgreSQL. A arquitetura exige que Event, mudança de estado e OutboxMessage da mesma operação sejam atômicos, que workers reutilizem Application e que isolamento por Organization seja preservado.

Message Broker pode ficar indisponível, entregar novamente, alterar a ordem observada ou confirmar uma publicação enquanto outro componente falha. A arquitetura não pode depender de entrega única, memória do processo ou transação distribuída.

## Problema

Definir:

- fronteira entre PostgreSQL, publisher, Message Broker e worker;
- garantia realista de entrega;
- atomicidade da produção;
- idempotência do consumo;
- retry, falha permanente, quarentena e replay;
- ordenação e concorrência;
- envelope e versionamento;
- isolamento e Authorization por Organization;
- observabilidade, recuperação e retenção;
- limites desta decisão em relação a produto, executor e offline.

## Princípios

1. **Estado definitivo não existe apenas no broker:** PostgreSQL preserva o registro autoritativo necessário à recuperação.
2. **Atomicidade local:** transação de domínio e OutboxMessage são confirmadas juntas.
3. **Entrega pelo menos uma vez:** duplicação é comportamento esperado.
4. **Idempotência obrigatória:** reprocessar não duplica efeito lógico.
5. **Negações e falhas são explícitas:** mensagem problemática não desaparece silenciosamente.
6. **Isolamento integral:** Organization é preservada em publicação, consumo, retry e replay.
7. **Contratos versionados:** produtor não altera significado de mensagem publicada.
8. **Broker substituível:** tipos e APIs do produto não entram no Domain ou Application.
9. **Observabilidade sem exposição:** operação é explicável sem registrar secrets ou conteúdo protegido desnecessário.
10. **Evolução incremental:** filas, tópicos e workers existem somente para consumidores reais.

A substituição do broker é preservada nos contratos do Core e da Application. Infrastructure pode utilizar capacidades específicas do produto escolhido, desde que não alterem a semântica pública das mensagens nem atravessem as fronteiras internas.

## Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Processamento somente síncrono | Simplicidade inicial | Aumenta latência e acopla disponibilidade de trabalhos derivados à requisição |
| Publicação direta no broker | Menos estruturas | Pode perder mensagem entre commit do domínio e publicação, ou publicar antes de rollback |
| PostgreSQL como fila permanente | Menos componentes | Mistura transporte, retenção e carga operacional no banco transacional |
| Outbox PostgreSQL com Message Broker | Atomicidade local, recuperação e desacoplamento | Exige publisher, idempotência, reconciliação e operação adicional |
| Transação distribuída | Aparente atomicidade global | Complexidade, baixo suporte entre tecnologias e acoplamento operacional |

## Decisão

Adotar **Transactional Outbox no PostgreSQL e Message Broker como transporte**, com entrega **pelo menos uma vez**.

Event, mudança de estado e OutboxMessage originados pelo mesmo caso de uso são persistidos na mesma transação PostgreSQL. Um publisher independente lê mensagens pendentes confirmadas e as publica no broker.

Não existe transação distribuída entre PostgreSQL e Message Broker. A arquitetura não promete exactly-once delivery. Consumidores devem produzir efeito lógico idempotente.

O produto de Message Broker e o executor de workers serão decididos separadamente.

## Semântica das mensagens

Nem toda OutboxMessage representa DomainEvent. OutboxMessage é registro técnico transacional derivado de uma operação; não substitui DomainEvent, IntegrationEvent, Command ou Job e não constitui modelo universal do domínio.

O contrato classifica explicitamente cada mensagem:

- **DomainEvent:** descreve algo ocorrido dentro do domínio;
- **IntegrationEvent:** contrato público versionado, derivado de acontecimento interno para outros módulos ou sistemas;
- **Command:** solicitação direcionada para que um consumidor lógico tente executar uma ação;
- **Job:** trabalho técnico ou operacional sem significado de acontecimento de domínio.

Eventos não ordenam implicitamente que um consumidor execute ação. Commands e Jobs não são apresentados como fatos já ocorridos. A classificação determina consumidores esperados, autorização, replay, ordenação e compatibilidade.

IntegrationEvent, Command e Job são semânticas de Application ou Infrastructure nesta ADR. Sua eventual promoção a conceitos normativos do Domain exige atualização aprovada do `DOMAIN.md`.

## Fronteira de responsabilidades

### PostgreSQL e Outbox

- preservam OutboxMessage autoritativa e seu ciclo operacional;
- permitem detectar mensagens pendentes após falha ou reinício;
- registram tentativas e resultados necessários à reconciliação;
- não dependem de confirmação do broker para concluir a transação de domínio;
- não utilizam tabela protegida como fila sem classificação, índices e retenção aprovados.

### Publisher

- busca OutboxMessages pertencentes a transações PostgreSQL confirmadas e ainda não aceitas pelo broker;
- impede que múltiplas instâncias reivindiquem simultaneamente o mesmo trabalho por mecanismo transacional seguro;
- garante que claim ou lease não bloqueie permanentemente mensagem após falha do publisher, por expiração ou recuperação equivalente;
- publica envelope versionado no destino configurado;
- registra a mensagem como aceita pelo broker somente após confirmação positiva de publicação conforme a garantia configurada;
- não interpreta aceitação pelo broker como consumo, processamento ou efeito de negócio concluído;
- preserva tentativa, aceitação pelo broker, resultado desconhecido e necessidade de reconciliação como situações operacionais distintas;
- mantém resultado desconhecido elegível para nova tentativa com o mesmo `message_id`;
- não executa regra de negócio;
- não altera payload já persistido.

Falha de comunicação durante publicação pode produzir resultado desconhecido: o broker pode ter persistido a mensagem sem que a confirmação tenha chegado ao publisher. Resultado desconhecido não equivale a publicação ausente nem confirmada e explica por que redelivery e duplicação são inevitáveis.

A marcação operacional não remove OutboxMessage nem altera seu conteúdo original. Códigos físicos dos estados serão definidos com o schema da implementação.

### Message Broker

- transporta mensagens entre publisher e consumidores;
- oferece confirmação, redelivery e isolamento operacional compatíveis com esta ADR;
- não é fonte autoritativa de Event, Decision, Evidence ou OutboxMessage;
- não concede Authorization e não autentica Actor perante o domínio;
- pode conter cópias transitórias, nunca o único registro necessário à recuperação.

### Worker e consumidor

- recebe e valida o envelope antes de interpretar o payload;
- resolve handler por tipo e versão explicitamente suportados;
- executa caso de uso de Application, sem duplicar regra no app worker;
- inicia transação local para efeito, idempotência e mensagens derivadas;
- confirma consumo somente depois do commit local bem-sucedido;
- não confirma mensagem cuja persistência tenha resultado desconhecido;
- classifica falha como transitória, permanente ou inválida sem ocultá-la.

## Envelope de mensagem

Toda mensagem transportada preserva, quando aplicável:

- `message_id` global e estável;
- tipo e versão do contrato;
- RecordOwnerOrganization ou Organization responsável pela mensagem;
- referência ao Actor original;
- referência à identidade ou ao processo produtor;
- instante de ocorrência e de registro;
- identificadores de correlação e causação;
- IdempotencyKey ou chave de deduplicação;
- payload versionado ou referência opaca autorizável;
- classificação de sensibilidade necessária ao transporte.

Access Token, Refresh Token, ID Token, senha, secret, chave privada e OrganizationContext materializado são proibidos no envelope.

Binários e documentos não são transportados no payload. A mensagem utiliza referência opaca; o consumidor obtém conteúdo pelo caso de uso autorizado e verifica identidade, versão e hash quando exigido.

Metadados internos do broker não integram o contrato público do evento.

Quando o processamento depender do estado conhecido na produção, o payload contém snapshot mínimo imutável ou referência a versão imutável. Referência ao estado mutável atual somente é permitida quando o contrato exigir deliberadamente reavaliação no momento do consumo.

## Participantes e auditoria

A auditoria distingue:

- Actor que originou a operação;
- mecanismo ou processo que produziu a mensagem;
- ServiceIdentity que executou o consumo;
- Actor administrativo que iniciou eventual replay.

Esses participantes podem coincidir, mas não são equivalentes. Publisher não se torna Actor do acontecimento apenas por transportar a mensagem, e worker não substitui o Actor originador.

## Isolamento e autorização

OutboxMessage protegida possui RecordOwnerOrganization e segue RLS conforme a ADR 0003.

O app worker autentica-se como ServiceIdentity com concessões mínimas. A identidade técnica do worker não substitui o Actor original nem concede acesso universal.

A mensagem carrega referências auditáveis, não Roles, Permissions ou Authorization confiáveis. Antes de executar operação protegida, Application reconstrói e valida OrganizationContext apropriado.

Operações assíncronas distinguem:

- **efeito técnico já autorizado pela transação original:** preserva autorização, Actor, finalidade e decisão que causaram a mensagem;
- **nova decisão de negócio no momento do consumo:** reavalia estado, vínculos, Permissions, Grants e Policies aplicáveis.

Essa classificação pertence ao contrato do caso de uso. Replay não amplia autorização, não troca Organization e não transforma ServiceIdentity em owner do registro.

## Idempotência do consumo

Cada consumidor persiste um registro de processamento por `message_id` e identidade lógica do consumidor, ou utiliza invariante equivalente no mesmo limite transacional do efeito.

Deduplicação por `message_id` protege contra redelivery da mesma mensagem. Quando mensagens distintas puderem representar a mesma intenção lógica, o contrato também utiliza IdempotencyKey ou invariante natural apropriada. `message_id` e IdempotencyKey não são necessariamente equivalentes.

Regras:

- primeira entrega pode produzir o efeito;
- entrega repetida retorna o mesmo efeito lógico sem duplicá-lo;
- mesma IdempotencyKey com conteúdo diferente gera conflito;
- marcação de concluído e efeito local são atômicos;
- cache não é registro suficiente de deduplicação;
- expiração do registro considera retenção e maior janela possível de redelivery ou replay;
- handlers não dependem apenas de consulta anterior seguida de escrita não atômica.

Mensagem não permanece elegível para replay depois que o registro necessário à deduplicação for descartado, salvo procedimento que trate explicitamente a possibilidade de novo efeito e exija autorização correspondente.

Uma estrutura técnica de recebimento pode ser chamada de Inbox no adapter, mas não cria conceito de domínio sem aprovação no `DOMAIN.md`.

## Retry e falhas

Falha transitória utiliza retry com atraso progressivo, limite configurado e variação para evitar repetição sincronizada.

Falhas permanentes ou mensagens inválidas não são repetidas indefinidamente. Depois do limite, a mensagem é encaminhada para destino de quarentena ou dead-letter e recebe estado operacional correspondente.

Exemplos de falha permanente incluem contrato não suportado, envelope inválido, referência impossível e violação determinística de invariante. Timeout, indisponibilidade temporária e contenção podem ser transitórios.

A classificação não pode transformar erro desconhecido em sucesso. Exceção inesperada do consumidor não é automaticamente defeito permanente da mensagem. Falha permanente exige motivo reconhecível e determinístico; erro não classificado segue política segura de retry e quarentena e permanece observável.

## Replay

Replay é operação administrativa explícita, autenticada, autorizada e auditada.

Deve registrar mensagem, motivo, solicitante, Organization, destino, instante e resultado. O conteúdo original não é alterado; correção de contrato ou dado produz nova mensagem correlacionada quando necessário.

Replay passa pelos mesmos controles de validação, idempotência, isolamento e autorização do consumo ordinário. Recolocar mensagem não significa apagar o registro da falha anterior.

Replay executa o handler atualmente suportado para a versão do contrato. Quando reprodução exata do comportamento histórico for necessária, o contrato preserva versão do produtor, versão do motor ou referência à lógica aplicável. Replay operacional não equivale automaticamente à reprodução histórica.

## Ordenação e concorrência

Não há garantia de ordenação global.

Ordenação por agregado, Subject ou chave de partição só é exigida quando uma invariante documentada depender dela. O contrato declara a chave e o consumidor também utiliza versão esperada ou concorrência otimista.

Partições diferentes podem avançar independentemente. Mensagem fora de ordem não é descartada silenciosamente: é processada com semântica compatível, adiada por dependência ou classificada como conflito.

## Publicação, desligamento e recuperação

Publisher e worker suportam desligamento gracioso: param de reivindicar novos itens, concluem ou liberam trabalho em andamento e preservam redelivery seguro.

Após reinício:

- OutboxMessage pendente volta a ser elegível;
- publicação com resultado desconhecido pode ocorrer novamente;
- consumo não confirmado volta a ser entregue;
- idempotência impede efeito lógico duplicado;
- reconciliação detecta divergência entre outbox e broker.

Backpressure deve limitar concorrência, prefetch e taxa sem descartar mensagens. Sobrecarga de consumidor não autoriza crescimento ilimitado de processos ou conexões.

## Retenção e privacidade

Retenção de Outbox, registros de consumo e quarentena deve cobrir auditoria, recuperação e janela de replay aprovadas.

Payload contém apenas o mínimo necessário. Dados sensíveis seguem classificação, criptografia de transporte, controle de acesso e política de retenção. Logs utilizam identificadores e motivos seguros, não payload integral por padrão.

Exclusão permitida de cópia operacional não apaga Events ou registros históricos cuja retenção seja obrigatória.

## Compatibilidade e evolução de mensagens

Tipo e versão fazem parte da identidade do contrato. Depois de publicada, uma versão não muda de significado.

Alteração compatível pode adicionar campo opcional com semântica e ausência definidas. Alteração incompatível exige nova versão.

Consumidores devem:

- rejeitar versões não suportadas;
- ignorar somente extensões cuja compatibilidade esteja prevista;
- não presumir valor ausente sem regra do contrato;
- validar estrutura antes de executar o caso de uso.

Remoção de suporte a uma versão exige comprovar que não existem OutboxMessages, mensagens no broker, registros em quarentena ou replays elegíveis dependentes dela.

## Observabilidade

Devem existir métricas e correlação para:

- quantidade e idade da Outbox pendente;
- latência entre commit, publicação e consumo;
- taxa de publicação, confirmação e redelivery;
- tentativas por tipo e consumidor;
- mensagens em quarentena;
- falhas de contrato, autorização e isolamento;
- divergências encontradas pela reconciliação.

Alertas consideram atraso e tendência, não apenas indisponibilidade do processo. Correlation ID permite navegar da operação original aos trabalhos derivados sem expor conteúdo protegido.

## Consequências

| Tipo | Consequências |
|---|---|
| Positivas | Estado e mensagem atômicos; recuperação após falha; broker substituível; consumidores escaláveis; rastreabilidade operacional |
| Negativas | Duplicação esperada; maior complexidade operacional; tabelas e retenção adicionais; reconciliação e idempotência obrigatórias |

## Riscos e controles

| Risco | Controle |
|---|---|
| Commit sem publicação | Outbox autoritativa e publisher recuperável |
| Publicação duplicada | `message_id` estável e consumidor idempotente |
| Claim abandonado | Expiração ou recuperação segura da reivindicação |
| Aceitação confundida com consumo | Estados e métricas operacionais distintos |
| Commit do consumidor sem ack | Redelivery tratado pela mesma idempotência |
| Ack antes do commit | Proibido pelo contrato do consumidor |
| Poison message | Limite de retry, classificação e quarentena |
| Vazamento entre Organizations | Organization no envelope, contexto reconstruído, RLS e testes negativos |
| Replay indevido | Permission administrativa, justificativa e auditoria |
| Mensagem incompatível | Tipo e versão explícitos; falha permanente observável |
| Replay sob lógica nova | Versões preservadas e distinção entre replay e reprodução histórica |
| Broker como fonte de verdade | PostgreSQL e registros de domínio permanecem autoritativos |
| Sobrecarga | Backpressure, concorrência limitada e métricas de atraso |

## Verificação automatizada

Testes devem cobrir:

- atomicidade entre estado, Event e OutboxMessage;
- falha depois do commit e antes da publicação;
- publicação duplicada;
- resultado de publicação desconhecido com o mesmo `message_id`;
- recuperação de claim ou lease abandonado;
- falha depois do commit do consumidor e antes do ack;
- redelivery sem efeito lógico duplicado;
- mensagens diferentes com a mesma IdempotencyKey;
- IdempotencyKey reutilizada com conteúdo diferente;
- duas instâncias de publisher concorrentes;
- retry transitório e limite de tentativas;
- mensagem inválida ou versão não suportada em quarentena;
- replay autorizado e não autorizado;
- mensagem fora de ordem e concorrência otimista;
- snapshot imutável e consulta deliberada de estado atual;
- compatibilidade entre versões e remoção de versão ainda referenciada;
- auditoria distinta de Actor originador, produtor, executor e operador de replay;
- ausência de tokens, secrets e binários no envelope;
- tentativa de consumo em outra Organization;
- worker sem Grant ou Permission necessária;
- desligamento e retomada;
- indisponibilidade temporária do broker;
- reconciliação de mensagens pendentes ou resultado desconhecido.

## Critérios de aceitação

A ADR pode ser aceita quando:

- PostgreSQL permanecer autoritativo para OutboxMessage;
- transação de domínio não depender do broker;
- entrega for assumida como pelo menos uma vez;
- consumidor idempotente for obrigatório;
- ack ocorrer somente após commit;
- retry, falha permanente, quarentena e replay estiverem distintos;
- Organization e contexto auditável forem preservados;
- worker reconstruir Authorization sem confiar em Permissions da mensagem;
- envelope for versionado e não transportar credenciais ou binários;
- mensagem for classificada como DomainEvent, IntegrationEvent, Command ou Job;
- `message_id`, IdempotencyKey e invariante natural mantiverem semânticas distintas;
- aceitação pelo broker não for confundida com processamento concluído;
- resultado desconhecido e claim abandonado permanecerem recuperáveis;
- referência a estado mutável existir somente quando exigida pelo contrato;
- retenção da deduplicação for compatível com redelivery e replay;
- remoção de versão considerar Outbox, broker, quarentena e replay;
- replay operacional não for tratado como reprodução histórica exata;
- auditoria distinguir originador, produtor, executor e operador de replay;
- ordenação global não for prometida;
- produto e executor permanecerem substituíveis;
- falhas e atraso forem observáveis e reconciliáveis.

## O que esta ADR não decide

Esta ADR não escolhe:

- produto de Message Broker;
- Celery ou outro executor de workers;
- topologia, protocolo, nomes de filas, tópicos ou partições;
- valores finais de retry, timeout, prefetch e retenção;
- schema físico da Outbox ou do registro de consumo;
- processamento agendado;
- protocolo completo de Synchronization e OfflineOperation;
- eventos concretos de domínio ou integrações específicas.

Essas decisões serão tomadas apenas quando houver consumidor real e critérios operacionais verificáveis.

## Plano de reversão

Antes da implementação, esta proposta pode ser substituída por nova ADR. Depois da adoção, mudança de broker ou executor preserva contratos versionados, OutboxMessage, IdempotencyKey, registros de consumo, estados de quarentena e correlação histórica.
