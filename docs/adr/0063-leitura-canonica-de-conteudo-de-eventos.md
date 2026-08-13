# ADR-0063 - Leitura canônica de conteúdo de eventos por extensões verticais

**Status:** PROPOSTA
**Data:** 13 de agosto de 2026
**Escopo:** Core Application/Infrastructure e extensões verticais; bloqueador do T-05B da ADR-0062
**Relacionadas:** ADR-0003, ADR-0052, ADR-0060, ADR-0062

## Contexto

O Core já preserva cada `DomainEvent` de forma append-only, com schema,
versão e `payload_canonical_bytes`, além de `occurred_at`, `recorded_at`,
Organization, agregado e cadeia de integridade. A persistência consegue ler
esse conteúdo exatamente como foi gravado.

Por projeto, a porta genérica `DomainEventReader` expõe apenas metadados de
ordem e autoria. Ela não entrega bytes do payload, pois o Core não deve
desserializar nem interpretar conteúdo de verticais. Essa fronteira é correta,
mas impede o T-05B: o Livestock precisa ler os eventos próprios
`identifier_attached` e `identifier_deactivated` para reconstruir identidade
temporal, sem consultar a projeção atual `animal_identifiers`.

`recorded_at` é o instante em que o evento foi registrado pelo Core; não é
sinônimo de `known_at`. A nova porta o preserva sem lhe atribuir significado de
conhecimento. Uma vertical só pode usar `recorded_at` como limite de
conhecimento quando sua própria regra temporal demonstrar que isso é válido para
a fonte em questão.

## Decisão proposta

Criar uma porta adicional e genérica de leitura de conteúdo canônico de eventos,
sem substituir nem ampliar semanticamente `DomainEventReader`:

```text
CanonicalDomainEventReader
    list_for_aggregate(reference)
        -> RecordedCanonicalEvent[]
```

`RecordedCanonicalEvent` estenderá os metadados já disponíveis com somente:

- `payload_schema`;
- `payload_version`;
- `payload_canonical_bytes` imutáveis;
- `payload_digest`, SHA-256 calculado sobre os bytes preservados, sem nova
  persistência;
- identificadores e referência de integridade do evento já preservados, quando
  necessários para referenciar a origem sem reinterpretá-la.

O Core entrega conteúdo preservado; não o decodifica, valida contra schema de
vertical, converte em dicionário nem conhece `livestock.*`. A decodificação
canônica e a validação de schema/version pertencem ao adapter de Application da
vertical que optar pela porta.

Um `RecordedCanonicalEvent` selecionado é evidência preservada, não um fato
histórico reconstruído. O fato só existe depois que a vertical aplica as regras
próprias de schema, versão, validade, lifecycle, conflito, supersession,
admissibilidade e cortes temporais. A existência da porta não autoriza uma
vertical a consumir semanticamente schemas que não declarou suportar.

A implementação de Infrastructure reutilizará a tabela append-only
`core_audit.domain_events` e a mesma proteção RLS/Organization da leitura de
eventos existente. Não haverá endpoint que devolva bytes canônicos, migration,
backfill ou mudança no formato do evento. `DomainEventReader` atual continua
adequado para timeline e outros consumidores que não necessitam conteúdo.

A ordem retornada preservará a ordenação semântica do event store:
`aggregate_version` crescente, com `event_id` apenas como desempate defensivo.
Não será usada a ordem incidental de retorno do banco como autoridade temporal.
O payload canônico só pode atravessar a memória do adapter; logs, traces,
métricas, mensagens de erro e endpoints diagnósticos não podem reproduzir seus
bytes ou seu conteúdo decodificado.

O primeiro consumidor será um leitor temporal Livestock de identificadores, em
corte separado após esta ADR: ele aceita apenas schemas/versionamentos próprios
conhecidos, filtra `occurred_at <= reference_time` e
`recorded_at <= knowledge_cutoff`, e inclui no fato resultante o ID e digest
dos eventos selecionados. Erro de bytes, envelope canônico, schema, versão ou
lifecycle deve falhar fechado com limitação; nunca deve cair para a projeção
atual.

## Invariantes

1. O Core nunca importa nem interpreta semântica de vertical por esta porta.
2. A porta é somente leitura e não fornece mecanismo para alterar, reordenar ou
   suprimir eventos.
3. Bytes devolvidos são exatamente os bytes canônicos persistidos; não há JSON
   normalizado ou objeto mutável intermediário no Core.
4. A consulta permanece limitada à Organization e ao agregado autorizados pela
   mesma política RLS do log existente.
5. Uma vertical só interpreta schemas e versões declarados por ela; o
   desconhecido resulta em limitação determinística.
6. Nenhuma API pública expõe payload canônico bruto por esta decisão.
7. O novo contrato não transforma `recorded_at` em `known_at`; ele preserva o
   tempo de registro que cada vertical decide como usar conforme sua ADR.
8. A autorização de consumo semântico de um schema/version pertence à
   Application da vertical e às políticas de acesso aplicáveis; a porta não é
   autorização universal para interpretar eventos de terceiros.
9. Conteúdo canônico bruto ou decodificado não pode ser registrado em logs,
   traces, métricas, mensagens de erro ou endpoints diagnósticos.

## Consequências

- O T-05B pode reutilizar evidência append-only já existente, sem fabricar
  lifecycle a partir de uma projeção mutável.
- Novas verticais podem precisar da mesma porta, mas continuam responsáveis por
  seus próprios schemas e regras temporais.
- O contrato de leitura fica mais sensível que a timeline; testes de RLS e de
  não exposição HTTP são obrigatórios.
- Cada fato reconstruído pode referenciar exatamente seus eventos-fonte pelo
  `event_id`, `payload_digest` e referência de integridade, sem confundir o
  evento com o fato.
- A introdução é aditiva: consumidores atuais e formatos de evento não mudam.

## Alternativas rejeitadas

- **Consultar `core_audit.domain_events` diretamente pelo Livestock Application:**
  viola a inversão Application → Infrastructure e duplica RLS/ordenação.
- **Adicionar decodificação ou condicionais `livestock.*` ao Core:** cria
  dependência vertical e transforma o log universal em motor de domínio.
- **Usar `animal_identifiers` atual como passado:** reintroduz conhecimento
  retroativo e viola ADR-0052/0062.
- **Criar tabela append-only de identificadores imediatamente:** duplica eventos
  já preservados sem antes provar insuficiência da fonte existente.
- **Expor payloads por endpoint HTTP genérico:** amplia superfície de dados
  protegidos sem caso operacional aprovado.

## Portão para aceite e implementação

1. O contrato novo é aditivo, somente leitura e genérico; Core não conhece
   namespaces, schemas ou vocabulário de verticais.
2. A implementação reutiliza RLS da fonte e prova isolamento com duas
   Organizations, inclusive para bytes de payload.
3. A porta não é exposta por API pública.
4. Testes provam round-trip byte a byte, ordem por `aggregate_version`, evento
   inexistente e compatibilidade dos consumidores de `DomainEventReader` atuais.
5. T-05B é implementado somente depois que a porta e seus testes estiverem
   aceitos; ele terá sua própria matriz T0/T1/T2 e falha fechada.
6. O isolamento prova que uma Organization não obtém bytes canônicos de outra,
   mesmo conhecendo `aggregate_id` e `event_id` estrangeiros.
7. O resultado permite rastrear os eventos que sustentam uma reconstrução, sem
   converter evento em Fact automaticamente.
8. Testes confirmam que payload não aparece em logs, traces, métricas ou erros.
9. Teste explícito confirma que o Core não expõe `recorded_at` com o nome ou a
   semântica de `known_at`.
