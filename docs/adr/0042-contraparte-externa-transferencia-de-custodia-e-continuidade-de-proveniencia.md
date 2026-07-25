# ADR 0042 — Contraparte externa, transferência de custódia e continuidade de proveniência

**Status:** Aceita
**Data:** 25 de julho de 2026
**Decisores:** fundador e responsável pela arquitetura do Titan

## Contexto

O Passo 13.1 entregou a saída do rebanho, com `VENDA` e `TRANSFERENCIA_DEFINITIVA` entre os tipos e um campo `destination` de texto livre. O Passo 8.4 já resolvia a movimentação **dentro** de uma organização, fechando uma permanência e abrindo outra.

O que não existe é a outra metade: **não há aquisição.** Quando o animal vai para outra organização — ou para alguém que nem é cliente do Titan — a história para na fronteira. Do outro lado, o comprador cadastra um animal novo, do zero. O mesmo boi vira duas entidades sem vínculo, e nasce órfão no destino.

O mesmo limite já apareceu quatro vezes: doadora de embrião comprada de terceiro (Passo 13.2), fornecedor indireto (nota de rumo NR-6), habilitação de estabelecimento (ADR-0041) e agora a venda.

## O problema, formulado corretamente

Não é "venda de animal". É:

> **Como preservar continuidade de identidade, proveniência e risco quando um ativo atravessa uma fronteira de Organization, sem quebrar o isolamento entre tenants.**

Essa formulação é o que torna a ADR necessária, e é dela que decorrem todas as decisões abaixo.

## Não é conveniência cadastral: é falha de integridade

```text
Organization A                    Organization B
  tratamento em 20/07               aquisição em 20/08
  carência até 30/08                histórico não transferido
  venda em 20/08                    "nenhum tratamento registrado"
                                    elegibilidade: APROVADA
                                    abate em 22/08  ← dentro da carência
```

O Marco 9 existe para impedir exatamente isso, e não enxerga fora da própria organização. Hoje o Titan **não tem como avisar** — e o `destination` como texto livre agrava, porque dá aparência de rastreabilidade a um dado que não é entidade, não tem CNPJ nem CAR, e só responde a busca textual sobre o que alguém digitou à mão.

## Decisão central

> **O Titan não compartilha bancos nem histórico entre Organizations. Ele transfere declarações verificáveis, preserva identidade e proveniência, e permite que o destinatário incorpore fatos recebidos à sua própria visão — sempre identificando quem os afirmou e quais lacunas permanecem.**

## Invariantes

1. **Uma Organization nunca consulta diretamente o histórico privado de outra.**
2. **Transferência entre Organizations ocorre por artefato verificável**, com fatos cuja proveniência é preservada.
3. **O sujeito local de destino pode ter outro `animal_id`**, e deve preservar vínculo verificável com a identidade recebida.
4. **Fato importado nunca se torna fato próprio.**
5. **Ausência de histórico recebido é lacuna explícita**, e não ausência comprovada de eventos.
6. **Venda e abate são fatos distintos.**
7. **Contraparte externa é representação local de terceiro**, e nunca implica acesso ao tenant representado.
8. **Quando ambas as pontas usam Titan, o aceite fortalece a prova, mas não relaxa o isolamento.**
9. **Integridade criptográfica do artefato não estabelece, por si só, identidade ou autoridade do emissor.**
10. **Continuidade entre sujeitos é afirmação sustentada por evidência**, e nunca inferida apenas por identificador coincidente.
11. **Todo artefato transferido declara até quando a sua cobertura histórica alcança.**
12. **Fato importado chega ao motor pela mesma interface do fato local, com proveniência e confiança preservadas e disponíveis à Policy.**

## Dois modos, um mecanismo

O formato de prova é o mesmo nos dois casos; o que muda é se existe uma segunda ponta capaz de confirmar recebimento.

```text
CustodyTransfer
    ├── INTERNAL_TITAN   — destino é Organization do Titan
    └── EXTERNAL         — destino é terceiro qualquer
```

**Modo `INTERNAL_TITAN`.** A origem emite; o destino aceita e registra a aquisição. Existe protocolo com estados e prova das duas pontas.

**Modo `EXTERNAL`.** A origem registra a saída e gera o pacote verificável. Do ponto de vista transacional, termina ali. Se esse terceiro entrar no Titan mais tarde, importa a prova então.

**Mesmo quando as duas pontas são Titan, o destino não consulta os dados da origem.** O mecanismo continua sendo transferência de prova mais aceite — abrir uma exceção ao isolamento porque "os dois são clientes" criaria o caminho de vazamento que a arquitetura inteira evita.

## O dossiê já é o veículo

O Marco 10.2 e 10.3 entregaram um dossiê verificável por terceiro, e a ADR-0010 sustenta que ele se verifica **sem acesso ao Titan**. A ADR-0039 fixou o contrato público de verificação.

```text
Organização A                                 Organização B
  │                                              │
  ├── registra a venda                           │
  ├── emite o pacote verificável ───────────────►│
  │     histórico, carência, linhagem,           ├── registra a aquisição
  │     geometria, hash, assinatura              ├── importa como artefato
  │                                              └── o animal nasce COM história,
  └── o animal sai do rebanho ativo                  marcada como recebida
```

Não há acesso entre organizações. Há **transferência de prova**. E funciona igualmente quando o comprador não usa o Titan: ele recebe um documento que se verifica sozinho.

## Fato de negócio e mecanismo de troca são coisas distintas

```text
AnimalExit        — fato de negócio: o animal saiu do rebanho
TransferProtocol  — mecanismo de troca de prova, com estados
```

A venda pode ocorrer legal e operacionalmente **sem** aceite digital do comprador. Amarrar a saída ao aceite faria o registro do fato depender de um protocolo que a realidade não exige, e o operador ficaria impedido de registrar o que já aconteceu.

Estados do protocolo, previstos e não necessariamente implementados de imediato:

```text
CREATED · DELIVERED · ACCEPTED · REJECTED · EXPIRED
```

> **Estes são estados do `TransferProtocol`, e nunca do `AnimalExit`.**

A saída tem instante de ocorrência, não estado de negociação. Uma implementação que colocasse `AnimalExit.status = ACCEPTED` faria o registro de um fato consumado depender do andamento de um protocolo — e o animal que já saiu da fazenda ficaria "pendente" no sistema porque o comprador não clicou.

```text
AnimalExit         occurred_at = 25/07 16:00      ← o fato
TransferProtocol   status = ACCEPTED              ← a negociação da prova
```

## Dois fatos locais, ligados pela prova

Não existe registro compartilhado entre organizações. Cada uma é dona da sua perspectiva, e a ligação é feita pela referência da transferência:

```text
Organization A          Organization B
  AnimalExit              AnimalAcquisition
    transfer_reference ─────► imported_transfer_reference
```

Um único registro "de ambos" exigiria que uma organização escrevesse na outra, ou que existisse um espaço fora das duas — e as duas coisas quebram o isolamento.

## Identidade de continuidade sem identidade global

O `animal_id` **não** vira identificador global entre tenants. Cada organização mantém o seu, e a continuidade é declarada e verificável:

```text
Organization A                    Organization B
  animal_id = A-123                 animal_id = B-998
  SISBOV: BR000123456               SISBOV: BR000123456
                                    continuity_reference:
                                        source_organization
                                        source_subject_reference
                                        identifiers recebidos
                                        artefato que sustenta
```

O Titan passa a poder afirmar: *"este animal foi adquirido como continuidade documental do indivíduo antes identificado como X"* — sem compartilhar chave primária, e sem que B possa alcançar coisa alguma dentro de A.

Transformar `animal_id` em identidade global fura a fronteira de propriedade do registro: passaria a existir um identificador que atravessa tenants, e com ele a tentação de resolvê-lo do outro lado.

### Identificador coincidente é evidência, não prova

> **A continuidade entre sujeitos é uma afirmação sustentada por evidência, e não é inferida automaticamente pela igualdade de identificadores externos.**

Dois animais com o mesmo SISBOV **provavelmente** são o mesmo indivíduo. Mas também podem ser erro de digitação, brinco reaproveitado indevidamente, importação equivocada ou fraude — e um sistema que funde os dois sozinho transforma qualquer um desses casos em histórico falso, com aparência de rastreabilidade impecável.

A continuidade é declarada, com o que a sustenta:

```text
ContinuityAssertion
    source_subject_reference     de quem se afirma continuidade
    received_identifiers[]       os identificadores que vieram
    source_artifact              o pacote que sustenta a afirmação
    asserted_by                  quem afirma
    verification_result          o que a verificação apurou
```

A coincidência de identificador **alimenta** a afirmação; não a substitui. Sem isso, o dia em que dois brincos colidirem produz um animal com duas histórias — e ninguém saberá qual delas é dele.

## Contraparte não é Organization

`Counterparty` é a **representação local que uma organização mantém sobre um terceiro** — com nome, tipo, identificadores externos (CNPJ, CAR, SIF, código de estabelecimento, inscrição estadual), confiança e evidências.

**Mesmo que a Fazenda Y também use o Titan**, a `Counterparty Y` registrada por A continua sendo o cadastro que A tem sobre Y, e não Y. Fundir as duas automaticamente faria o cadastro de A passar a depender do que Y edita, e daria a A uma janela para dentro de Y.

Um vínculo verificado entre a contraparte e uma Organization do Titan é possível, e **deve ser tratado como afirmação verificável, e não como referência direta** — uma coisa é "A afirma, com prova, que esta contraparte é a Organization Y"; outra é uma chave estrangeira que o sistema resolve sozinho.

**A contraparte permanece na vertical, e não sobe ao Core.** Logística e florestal provavelmente precisarão do mesmo conceito, e é só quando o segundo caso concreto existir que vale perguntar se há um `Counterparty` genérico — pela mesma cautela da ADR-0041: generalizar sem um segundo caso real produz abstração especulativa.

## Três camadas na importação

```text
ReceivedArtifact   — o pacote como chegou: hash, emissor, assinatura, instante
      ↓
ImportedFact       — os fatos extraídos, cada um apontando para o artefato
      ↓
FactProvider       — entrega ao motor de regras, como qualquer outro fato
```

A extração existe porque **o motor não pode abrir um dossiê a cada avaliação** — mas o vínculo com a fonte é permanente, e um fato importado sem artefato de origem não existe.

> **Fatos importados chegam ao motor pela mesma interface dos fatos locais, preservando proveniência, `FactOrigin` e `ConfidenceLevel`. A regra de domínio não precisa conhecer a implementação da importação, mas pode exigir níveis de origem ou de confiança conforme a Policy aplicável.**

A distinção importa: uma Policy pode legitimamente exigir que, para determinado mercado, tratamento recebido de terceiro só sustente elegibilidade a partir de `DOCUMENTED`. Dizer que a regra "não precisa saber a diferença" apagaria justamente a informação de que ela pode depender.

O que a interface esconde é **como** o fato chegou; o que ela preserva é **de onde** ele veio e **quanto** vale.

## Proveniência e confiança são dimensões diferentes

Esta é a distinção que mais fácil se perde, e a que mais custa perder.

```text
FactOrigin                    ConfidenceLevel
  LOCAL_OBSERVATION             INFORMED
  LOCAL_DECLARATION             DOCUMENTED
  IMPORTED_ASSERTION            VERIFIED_SOURCE
                                HARDENED_SYSTEM
                                CRYPTOGRAPHICALLY_ATTESTED
```

**As duas são independentes.** Um fato recebido de terceiro, com assinatura validada e dossiê íntegro, é `IMPORTED_ASSERTION` **e** `CRYPTOGRAPHICALLY_ATTESTED` ao mesmo tempo — alta confiança criptográfica e origem externa.

Colapsá-las numa só faria o sistema confundir **"não fui eu que afirmei"** com **"não confio"**, e passaria a descontar confiança de prova boa só porque veio de fora. É o oposto do que uma cadeia de custódia precisa.

### O que uma assinatura válida não prova

> **Integridade criptográfica do artefato não estabelece, por si só, identidade ou autoridade do emissor.**

A ADR-0039 já fixou essa semântica para os pacotes de verificação, e **esta ADR a herda inteira**: verificar uma assinatura contra uma âncora não demonstra que a chave pertence legitimamente a quem se alega emissor, nem que ele estava autorizado a emitir aquilo no instante em que emitiu.

Portanto `CRYPTOGRAPHICALLY_ATTESTED` significa exatamente isto:

> **A assinatura criptográfica confere para o material verificado, contra a âncora utilizada.**

E **nunca** *"o Titan confirmou que isto veio oficialmente da Fazenda X"*. Ler o primeiro como o segundo transformaria integridade em autenticidade institucional, que é o engano mais caro possível numa cadeia de custódia — porque um pacote forjado com par de chaves próprio verifica perfeitamente.

A formulação é deliberadamente estreita: não afirma sequer que o material é o mesmo que algum original, porque isso dependeria de saber qual era o original. Afirma apenas o que a operação de fato apurou.

Vincular o emissor a uma contraparte ou a uma Organization é afirmação separada, sustentada por evidência própria, e sujeita à mesma escala de confiança.

## Fato importado nunca vira fato próprio

```text
Organization A registra          Organization B recebe
  Treatment T1                     Treatment T1
  asserted_by = A / Vet X          asserted_by  = A / Vet X   ← não muda
                                   received_by  = B
                                   source_artifact = Dossiê 123
```

E quando B emitir o seu próprio dossiê, o tratamento continua declarando quem o afirmou originalmente. **Na terceira revenda a cadeia continua intacta** — é o que permite responder "quem disse isso, e com base em quê" muitos elos adiante.

Reescrever a autoria na importação destruiria a única coisa que a cadeia de custódia tem para oferecer.

## Pacote íntegro pode estar desatualizado

Este é o falso positivo mais perigoso da transferência, porque **todas as verificações passam**:

```text
10:00  A emite o pacote                    integridade: válida
11:00  o animal recebe tratamento em A     assinatura:  válida
14:00  o animal é carregado                cobertura:   até 10:00
16:00  a venda se efetiva
17:00  B importa o pacote das 10:00        → o tratamento das 11:00 não veio
```

Integridade e assinatura dizem que **o material não foi adulterado desde que foi emitido**. Não dizem nada sobre o que aconteceu **depois** de emitido. Um pacote perfeito pode estar três dias atrasado, e o tratamento que ficou de fora é justamente o que colocaria o animal em carência.

Por isso todo artefato declara três instantes distintos, que costumam ser confundidos:

```text
bundle_issued_at            quando o pacote foi emitido
coverage_until              até quando a história nele alcança
transfer_effective_at       quando a custódia de fato mudou
```

E a regra decorre sozinha:

```text
coverage_until < transfer_effective_at   →   existe lacuna, e ela é nomeada
```

## Lacuna declarada, nunca histórico vazio

```text
history_before_acquisition = UNKNOWN      ≠      history = []
```

Se o vendedor não entregou dossiê, o animal entra com a história começando ali, e isso fica **declarado**. Lista vazia afirmaria que nada aconteceu antes; a verdade é que não se sabe.

> **Ausência de fatos anteriores não significa ausência de eventos anteriores.**

É o mesmo princípio do `INDETERMINADO` da ADR-0041 e do "desconhecido permanece desconhecido" da ADR-0026, aplicado à cadeia.

### Cobertura tem duas pontas, e um enum simples não a descreve

```text
        passado                                         presente
──────────┬─────────────────────────────────────────────────┬──────►
      nascimento                                       transferência
```

Conhecer tudo desde o nascimento e **faltar o último dia** é situação real, e a mais perigosa — porque parece completa. Um rótulo único como `COMPLETE_FROM_BIRTH` não consegue dizê-lo.

Esta ADR **não congela** a forma da cobertura, e fixa o que ela precisa ser capaz de representar:

```text
known_from        desde quando a história é conhecida
known_until       até quando ela alcança
gaps[]            os intervalos ausentes no meio
coverage_claim    o que se afirma sobre o conjunto
```

O que permite dizer o que importa:

```text
known_from   = 2024-03-10
known_until  = 2026-07-24 18:00
transfer_at  = 2026-07-25 09:00
                              → lacuna de 15 horas, declarada
```

A entidade concreta fica fora de escopo; a semântica, não.

## Lacuna não é inelegibilidade

> **A existência de lacuna não determina sozinha a inelegibilidade. As Policies consumidoras decidem se a cobertura disponível é suficiente para a finalidade avaliada, e ausência de cobertura exigida não pode ser interpretada como ausência do fato.**

É aqui que esta ADR e a ADR-0041 se encaixam:

```text
Mercado A   exige histórico farmacológico dos últimos 90 dias
Animal      histórico verificável dos últimos 180 dias
                                          → cobertura suficiente

Mercado B   exige cadeia desde o nascimento
Animal      histórico verificável dos últimos 180 dias
                                          → INDETERMINADO
```

O mesmo animal, com a mesma cobertura, responde diferente conforme o destino — que é exatamente o que a ADR-0041 estabeleceu. A lacuna é insumo da avaliação, e não veredito.

## Venda não é abate

Pertencem à mesma família — transferência de custódia — e têm consequências diferentes no ciclo de vida:

```text
transfer_type      = SALE | DONATION | CONSIGNMENT | ...
counterparty_type  = FARM | SLAUGHTERHOUSE | ...
```

**Venda para outra fazenda:** o animal sai da custódia de A, entra na de B, e **continua vivo**.

**Venda para frigorífico:** o animal sai da custódia da fazenda e entra na do frigorífico. O abate é **evento posterior**, e entre um e outro existem transporte, recebimento, inspeção e espera. Tratar a venda para frigorífico como sinônimo de abate registraria como consumado um fato que ainda não ocorreu — e apagaria a janela em que o animal está vivo sob custódia de terceiro.

Por isso `VENDA` e `ABATE` permanecem eventos distintos, como já são no Passo 13.1.

## Fora de escopo

**A genealogia de produtos.** Quando o abate ocorre, o animal não "vira" produto: há transformação com vários resultados.

```text
Animal
  └─ produz ─┬─ Carcaça
             ├─ Miúdos
             └─ ...
                  ↓
          Lote de produção  →  Produto
```

Isso é DAG, e não árvore — é a nota de rumo NR-2, que aponta para o GS1 EPCIS. **Esta ADR não resolve, e não fecha a porta:** `UniversalRelation` já sustenta a forma, e a transferência de custódia aqui definida é o elo anterior a ela.

Também fora: a implementação do protocolo de aceite; o desenho do `HistoryCoverage` como entidade; e a reconciliação automática entre contraparte e Organization.

## Alternativas descartadas

**Permitir que o destino consulte o histórico da origem.** Caminho de vazamento entre tenants, ainda que ambos sejam clientes. O `UniversalRelation` já o recusa.

**`animal_id` global entre organizações.** Fura a fronteira de propriedade do registro e cria identificador resolvível do outro lado.

**Registro único de transferência, compartilhado pelas duas.** Exigiria que uma organização escrevesse na outra, ou um espaço fora das duas.

**Fundir `Counterparty` com `Organization` quando o terceiro também for Titan.** Faria o cadastro de A depender do que Y edita, e daria a A uma janela para dentro de Y.

**Reescrever a autoria do fato na importação.** Destrói a cadeia de custódia na primeira revenda.

**Colapsar origem e confiança num campo só.** Confunde "não fui eu que afirmei" com "não confio", e desconta prova boa por vir de fora.

**Histórico vazio para animal sem dossiê recebido.** Afirma que nada aconteceu, quando o que há é desconhecimento.

**Inferir continuidade por identificador coincidente.** Transforma erro de digitação, brinco reaproveitado e fraude em histórico falso com aparência impecável.

**Tratar integridade criptográfica como autenticidade do emissor.** Um pacote forjado com par de chaves próprio verifica perfeitamente.

**Cobertura como rótulo único.** Não distingue "conheço desde o nascimento" de "conheço desde o nascimento, menos o último dia" — e a segunda é a mais perigosa, porque parece completa.

**Lacuna como inelegibilidade automática.** Quem decide se a cobertura basta é a Policy do mercado avaliado, e não a ausência em si.

**Amarrar a saída ao aceite do comprador.** Impediria registrar um fato que já ocorreu no mundo.

**Venda para frigorífico como abate.** Registra como consumado o que ainda não ocorreu.

## Consequências

### Positivas

- Fecha a falha de integridade que permitia abater animal em carência adquirido sem histórico.
- O fornecedor indireto passa a ser representável, que é o que a ADR-0026 declara como go-to-market.
- O mecanismo funciona com terceiros que não usam o Titan, sem exigir adoção do outro lado.
- Resolve, com um só desenho, os quatro casos em que o limite apareceu.
- A distinção entre origem e confiança permite reconhecer prova externa forte sem descontá-la.

### Negativas

- Duas metades do mesmo movimento em organizações diferentes, com reconciliação que pode nunca acontecer.
- Fato importado é superfície nova de erro: dossiê adulterado, artefato de emissor não confiável, importação parcial.
- O volume de fatos importados cresce com a cadeia, e a terceira revenda carrega a proveniência das anteriores.
- Contraparte cadastrada por cada organização produz duplicidade inevitável entre tenants, e isso é aceito.

## Riscos e controles

| Risco | Controle |
|---|---|
| Destino acessar dados da origem | Transferência por artefato; nenhuma consulta cross-tenant |
| Fato importado virar fato próprio | `asserted_by` preservado; `received_by` e artefato obrigatórios |
| Origem externa ser lida como baixa confiança | `FactOrigin` e `ConfidenceLevel` independentes |
| Histórico ausente virar histórico vazio | Cobertura declarada; ausência é lacuna nomeada |
| Contraparte confundida com Organization | Entidade local, vínculo apenas como afirmação verificável |
| `animal_id` virar identificador global | Continuidade por referência declarada e identificadores externos |
| Dossiê adulterado ser importado | Verificação do pacote antes da extração; artefato guarda hash e emissor |
| Venda a frigorífico contada como abate | Eventos distintos, com custódia entre eles |
| Saída bloqueada por falta de aceite | Fato de negócio separado do protocolo de troca |
| Pacote íntegro porém desatualizado | `coverage_until` comparado a `transfer_effective_at`; lacuna nomeada |
| Assinatura válida lida como emissor confirmado | Semântica herdada da ADR-0039; vínculo do emissor é afirmação à parte |
| Dois animais fundidos por identificador igual | Continuidade exige afirmação com evidência |
| Lacuna virar reprovação automática | A Policy do mercado decide se a cobertura basta |

## Testes mínimos

- animal vendido em carência chega ao destino com a carência conhecida, e a elegibilidade o recusa;
- fato importado preserva `asserted_by` da origem depois de duas revendas;
- fato importado com assinatura válida é `IMPORTED_ASSERTION` e alta confiança ao mesmo tempo;
- aquisição sem dossiê declara cobertura desconhecida, e não histórico vazio;
- o destino não alcança nenhum registro da origem por nenhuma rota;
- contraparte que representa uma Organization do Titan não dá acesso a ela;
- venda para frigorífico não produz abate;
- saída é registrável sem aceite do comprador;
- artefato com hash que não confere não produz fato importado algum;
- identidade de continuidade é verificável sem compartilhar `animal_id`;
- **pacote íntegro e corretamente assinado, cuja cobertura termina antes do instante efetivo da transferência, produz lacuna explícita** — e nunca cobertura completa;
- **igualdade de identificador externo, sem afirmação de continuidade sustentada por evidência, não vincula dois animais como o mesmo sujeito histórico**;
- assinatura válida não é apresentada como confirmação de que o emissor é quem alega ser;
- Policy que exige confiança mínima para fato importado recusa o que não a atinge, sem recusar o que a atinge por ser importado.

## Critérios de aceitação

A ADR pode ser aceita quando as doze invariantes estiverem refletidas no desenho; o mecanismo funcionar com destino fora do Titan; origem e confiança permanecerem dimensões independentes e disponíveis às Policies; integridade criptográfica não for apresentada como autoridade do emissor; continuidade exigir evidência além de identificador coincidente; a cobertura declarar até quando alcança; lacuna for insumo da avaliação e não veredito; e venda e abate continuarem eventos distintos.

## O padrão que está emergindo

Vale registrar o que as ADRs 0041 e 0042 estão construindo em conjunto, sem que nenhuma das duas o tenha proposto isoladamente:

```text
              MUNDO REAL
                  │
               Subject
                  │
        ┌─────────┴─────────┐
   fatos locais        fatos externos
        │                   │
        │            ReceivedArtifact
        │                   │
        │             ImportedFacts
        └─────────┬─────────┘
                  ▼
             Provenance
                  ▼
             Confidence
                  ▼
               Policy
                  ▼
             Evaluation
                  ▼
              Decision
```

**O Titan não precisa possuir toda a realidade.** Precisa saber quem afirmou, o que afirmou, sobre qual sujeito, em qual instante, com base em qual evidência, com qual cobertura e com qual confiança.

É por isso que a transferência de custódia cabe sem exceção ao isolamento: o que atravessa a fronteira não é acesso, é afirmação — e afirmação já é cidadã de primeira classe neste modelo.

## Relacionadas

ADR-0003 (isolamento por Organization e RLS); ADR-0010 (verificação externa e pacote autossuficiente); ADR-0016 (decisões explicáveis); ADR-0026 (cobertura da cadeia de estabelecimentos); ADR-0039 (contrato público de verificação); ADR-0040 (origem da identidade do animal); ADR-0041 (elegibilidade por mercado, que depende da cadeia para o fornecedor indireto). Notas de rumo NR-2 (GS1 EPCIS, genealogia de produtos) e NR-6.
