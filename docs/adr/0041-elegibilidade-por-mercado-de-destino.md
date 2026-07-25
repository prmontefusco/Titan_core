# ADR 0041 — Elegibilidade por mercado de destino

**Status:** Proposta
**Data:** 25 de julho de 2026
**Decisores:** fundador e responsável pela arquitetura do Titan

## Contexto

O Marco 9 entregou elegibilidade farmacológica: uma `Policy`, uma `Rule` bloqueante por carência, e uma `Decision` explicável por animal. A finalidade declarada foi `ELEGIBILIDADE_FARMACOLOGICA`, e o resultado é único — aprovada, rejeitada, aprovada com restrições ou indeterminada.

A discussão sobre embargos ambientais, terras indígenas e áreas de desmatamento expôs que esse modelo responde à pergunta errada. Perguntado se um animal "está conforme", o sistema teria de escolher uma norma entre várias, e a escolha seria arbitrária: a União Europeia, a China e o mercado interno brasileiro não exigem as mesmas coisas.

O responsável formulou o requisito com precisão: **o sistema deve indicar para quais mercados o animal é elegível, e quem decide é o frigorífico ou o exportador.**

**Vocabulário.** Esta ADR fala de **elegibilidade**, e não de conformidade. "Conforme" é absoluto e sugere juízo jurídico; "elegível segundo o conjunto de regras X, na versão Y, no instante Z" é o que o Titan efetivamente apura.

## Problema

Definir:

- de quem é a elegibilidade — do animal, ou de algo maior;
- como o motor de regras existente comporta destinos com normas divergentes;
- que forma tem a resposta quando há vários destinos;
- o que acontece quando falta informação, quando falta norma, e quando a norma mudou desde a última avaliação;
- como normas que mudam por decisão externa entram sem exigir implantação de código;
- onde termina a informação do Titan e começa a decisão comercial de quem o usa.

## A pergunta certa

**Elegibilidade não é propriedade do animal.** É uma relação entre um sujeito e um mercado de destino, avaliada sob uma norma versionada, num instante determinado.

O mesmo boi é elegível para a China e inelegível para a União Europeia, e nenhum dos dois estados é "o" estado dele. Um campo `elegivel` no animal teria de escolher um mercado e calar sobre os outros.

## Decisão

**O mercado de destino é uma dimensão da avaliação, e não um atributo do sujeito.**

Toda avaliação de elegibilidade possui **um sujeito, uma finalidade de mercado e uma `Policy` versionada**. Cada uma produz `Evaluation` e `Decision` próprias, independentes e versionadas em separado.

**O sujeito é aquele a quem o requisito pertence.** No primeiro corte da vertical Livestock o sujeito predominante é o animal, mas requisitos cuja natureza pertença a estabelecimento, lote, propriedade ou operação são avaliados **sobre o sujeito correspondente**.

> **O Titan não atribui a um sujeito uma condição que pertence a outro.**

Esta é a invariante central da ADR, e a razão de ela existir na forma atual. Uma exigência que recai sobre a planta frigorífica não produz decisão sobre o animal: produziria uma afirmação falsa, porque o mesmo animal seria elegível por uma planta habilitada e inelegível por outra sem que nada nele tivesse mudado.

```text
Animal        × EU  → Decision      (o animal e onde ele esteve)
Estabelecimento × CN  → Decision    (a planta, não o animal)
Lote          × mercado X → Decision
Operação      × mercado Y → Decision
```

`Evaluation.subject_id` e `Decision.subject_id` já são referências tipadas no Core — nada impede sujeito que não seja animal, e restringir conceitualmente a animal seria uma limitação inventada pela vertical.

## Composição: o que a matriz do animal pode e não pode dizer

A matriz de um animal exibe o que se sabe **sobre ele**. Quando um mercado depende também de sujeito que ainda não foi escolhido, a célula declara essa dependência em vez de fingir uma resposta:

```text
BOI-4471
  ├── Mercado interno ...... ELEGÍVEL       avaliado 25/07/2026, BR-v3
  ├── União Europeia ....... INELEGÍVEL     avaliado 25/07/2026, EU-v7
  │     a permanência de 03/2025 a 08/2025 ocorreu em propriedade que
  │     intersecta a camada PRODES v2025-06
  ├── China ................ CONDICIONADO   avaliado 25/07/2026, CN-v4
  │     o que depende do animal está satisfeito; resta requisito do
  │     estabelecimento, que depende da planta escolhida
  └── Japão ................ SEM POLÍTICA   nenhuma regra declarada
```

Escolhido o estabelecimento, a resposta operacional **compõe** as decisões dos sujeitos envolvidos:

```text
BOI-4471  +  Frigorífico 982  +  China  →  ELEGÍVEL
```

**A composição não é uma decisão nova sobre o animal.** Ela referencia as decisões de cada sujeito e declara o resultado combinado — a forma exata dessa composição e o sujeito `Operação` ficam para decomposição própria, mas o modelo já está preparado para recebê-la, e nenhuma decisão emitida agora precisará ser reinterpretada quando ela chegar.

## Como isso cabe no Core sem alterá-lo

`Evaluation` e `Decision` já exigem `purpose` não vazio, e `DecisionResult` já admite `INDETERMINADA`. O mercado entra como **finalidade**, e não como campo novo.

Acrescentar `market` ao Core faria um domínio genérico carregar vocabulário de uma vertical: o Core não sabe o que é exportar carne.

**Mas a vertical não espalha strings pelo código.** Um Value Object da vertical produz a finalidade canônica:

```text
MarketEligibilityPurpose(market="EU", profile="STANDARD")
        ↓ serializa
livestock.market_eligibility.EU.STANDARD
```

O Core continua vendo apenas `purpose: str`. A vertical ganha um lugar único onde a taxonomia é definida, validada e evoluída — sem o qual uma hierarquia acabaria emergindo escondida dentro de strings montadas à mão em pontos diferentes do código.

**Consequência boa:** cada mercado tem `Policy` e `Rule` próprias, versionadas em separado. Quando a União Europeia mudar a norma, sobe a versão da política da União Europeia, e nenhuma decisão dos outros mercados é afetada. Isolamento de mudança normativa sai de graça.

## Mercado hoje, perfil de mercado amanhã

`BR`, `EU` e `CN` são **identificadores canônicos do primeiro corte**, e não pressupõem que jurisdição seja para sempre a granularidade final da finalidade.

É previsível que um mesmo destino comporte exigências distintas por commodity, programa ou protocolo de cliente — orgânico, EUDR, protocolo do comprador. O campo `profile` do Value Object existe desde já por isso, com valor `STANDARD` no primeiro corte.

Se a granularidade evoluir para um `MarketProfile` explícito — jurisdição, commodity, finalidade — a mudança acontece dentro da vertical, no Value Object e nas políticas, sem tocar no Core e sem invalidar decisões emitidas, que continuam apontando para a finalidade textual que as produziu.

## A matriz é derivação, nunca registro

A matriz é **calculada na leitura**. Não existe tabela de matriz, nem campo agregado no animal.

É o mesmo princípio do Passo 9.4 e da ADR-0040: gravar a derivação criaria segunda fonte de verdade, e ela divergiria da primeira no dia em que uma regra mudasse ou uma camada nova fosse publicada — que é justamente o que acontece o tempo todo neste domínio.

## Três dimensões independentes em cada célula

"Decisão vigente" é expressão perigosa, porque esconde três perguntas diferentes:

1. **Qual foi o resultado?** — da `Decision`, imutável.
2. **Quando foi avaliado?** — o instante, que diz a idade da informação.
3. **A norma usada ainda é a atual?** — comparação entre a versão de política que produziu a decisão e a versão publicada hoje.

```text
UNIÃO EUROPEIA
  Resultado ............ ELEGÍVEL
  Avaliado em .......... 01/06/2026
  Política usada ....... EU-v2
  Política vigente ..... EU-v3
  Estado ............... REAVALIAÇÃO NECESSÁRIA
```

Apresentar apenas "ELEGÍVEL, avaliado em 01/06" seria historicamente verdadeiro e operacionalmente enganoso: a norma mudou em 20/07 e ninguém reavaliou.

**`REAVALIACAO_NECESSARIA` é estado da projeção, e nunca um `DecisionResult`.** A decisão histórica não muda — ela continua dizendo o que disse, sob a política que usou. Quem interpreta atualidade é a leitura da matriz, e essa separação é o que preserva a auditabilidade:

```text
Decision histórica  →  imutável, aponta para a política que a produziu
Célula da matriz    →  interpreta resultado, idade e atualidade normativa
```

## Ausente e indeterminado são coisas diferentes

Ambos significam "não é elegível", e por motivos que exigem ações opostas:

| Estado | Significado | O que fazer |
|---|---|---|
| `AUSENTE` | Não existe `Policy` declarada para este mercado | Declarar a regra |
| `INDETERMINADO` | Existe `Policy`, mas não foi possível concluir | Obter o dado que falta |

Ausência de informação **nunca** produz elegibilidade, e nenhum dos dois estados é omitido da matriz. É o princípio "desconhecido permanece desconhecido" da ADR-0026 aplicado à saída do motor, e é o que separa um sistema de rastreabilidade de um carimbo.

## A carência passa a ser por mercado

O Marco 9 guarda `withdrawal_period_days` como número único em `Medication`. O prazo de um mesmo princípio ativo, porém, varia por país de destino.

Não foi erro: o escopo era o mercado interno, e um número bastava. Mas o motor multi-mercado o torna insuficiente.

**A correção não é transformar o campo em coleção.** Prazo regulatório não é propriedade intrínseca do medicamento — é requisito normativo associado a produto, uso e mercado, com fonte, vigência e versão próprias, e possivelmente condicionado a espécie, via, dose ou finalidade. Tratá-lo como atributo do `Medication` repetiria, em escala menor, o mesmo erro que esta ADR corrige no animal.

A direção é uma entidade própria:

```text
Medication
    └── WithdrawalRequirement
            ├── market
            ├── conditions        (espécie, via, dose, finalidade)
            ├── period
            ├── normative_source
            └── validity          (valid_from, valid_until, version)
```

**Fica registrada como consequência a detalhar**, e não fixada aqui: ela merece o mesmo cuidado de modelagem que o resto, e o desenho definitivo depende de quantas dimensões de condição a norma real exige.

O que esta ADR fixa é a regra de ausência: **prazo não declarado para um mercado produz `INDETERMINADO` para aquele mercado, e nunca reaproveita o prazo de outro.** Afirmar que o prazo brasileiro vale na União Europeia seria inventar norma estrangeira.

A consequência prática é incômoda e aceita: enquanto ninguém declarar os prazos de um mercado, todo animal tratado sairá indeterminado para ele. Isso é a verdade sobre o estado do conhecimento, e o incômodo é o sinal correto — ele empurra para declarar o dado, e não para fingir que ele existe.

## Fatos entram pela porta que já existe

O motor consome fatos do `FactProvider`. A restrição territorial entrará como **mais um fato**, do mesmo modo que a carência entrou no Marco 9. Mas é preciso separar duas afirmações que não têm o mesmo custo:

> **Acrescentar condição normativa sobre um fato já disponível não exige alteração alguma — é regra, e regra é dado.**
>
> **Acrescentar uma categoria nova de fato exige implementar quem o produz** — integração, adapter, processamento geoespacial, `FactProvider`, guarda da versão da camada — **mas não exige alterar o motor de regras.**

A promessa desta ADR é a segunda, e não a primeira. Dizer "zero código" seria falso e cobrável daqui a seis meses.

**O teste do desenho é este:** se acrescentar restrição territorial exigir alterar o **motor**, o motor está errado. Produzir o fato territorial dá trabalho, e esse trabalho está previsto.

## Regra é dado, não código

Normas de mercado mudam por decisão de autoridade estrangeira, em prazo que não é o do desenvolvimento. Exigir implantação de código a cada mudança inviabiliza o produto.

Esta ADR converte a **nota de rumo NR-5** de intenção em requisito: o administrador compõe regras, e o sistema as executa. `RuleCondition` já é declarativo, versionado, viaja inteiro no dossiê e é reexecutável — para regras que caibam nessas primitivas, o problema de execução já está resolvido, e o que falta é a autoria.

Três restrições que a autoria não afrouxa:

1. **Publicar regra exige portão de aprovação.** Regra de negócio é categoria de aprovação obrigatória no plano, e autoria pelo administrador não muda isso.
2. **Regra publicada é imutável.** Alteração cria versão nova; decisões antigas continuam apontando para a versão que as produziu.
3. **Regra nova não reinterpreta decisão histórica.** Ela produz avaliação nova, com instante próprio — e a célula da matriz passa a `REAVALIACAO_NECESSARIA` até que isso aconteça.

A ADR-0036 (Wasm) permanece reservada para o que não couber nas primitivas declarativas, e só com evidência de que não coube.

## Reprodutibilidade da avaliação territorial

Quando a avaliação territorial existir, ela dependerá de camadas externas. O Titan **importa e guarda** o material que usou — geometria, versão declarada, instante da importação e digest — em vez de consultar o estado atual da fonte no momento da reavaliação.

Isso torna a reprodutibilidade responsabilidade do Titan, e não do provedor, e vale mesmo quando a fonte só expõe o estado corrente.

**Reimportação nunca substitui.** Geometria ou camada reimportada é versão nova; avaliações anteriores continuam apontando para a versão que usaram. É a ADR-0026 ao pé da letra, e sem isso a auditoria de 2027 leria a decisão de 2025 contra um polígono que não existia na época.

## Os três mercados do primeiro corte

Escolhidos por serem **estruturalmente diferentes**, e não por volume:

| Mercado | Sujeito do requisito |
|---|---|
| Interno (BR) | o animal |
| União Europeia (EU) | o animal **e onde ele esteve** |
| China (CN) | o **estabelecimento**, e não o animal |

O terceiro é o que obriga o modelo a admitir sujeitos distintos — e foi ao tentar encaixá-lo em `animal × mercado` que a fragilidade desta ADR apareceu.

**Os requisitos concretos de cada mercado não são fixados por esta ADR.** Eles são regra, e regra é dado — declarada pelo responsável, sob portão de aprovação, e confirmada contra a norma vigente antes de valer. O que esta ADR fixa é a forma, nunca o conteúdo normativo.

## Fora de escopo

- Decisão comercial de destino, que é de quem exporta.
- Conclusão jurídica de conformidade; o Titan informa relação avaliada, e não infração.
- A **forma da composição operacional** — sujeito `Operação`, e como as decisões de vários sujeitos se combinam numa resposta única. O modelo a admite; o desenho exige decomposição própria.
- Representação de contraparte externa, necessária para fornecedor indireto.
- Ingestão e manutenção das camadas ambientais, que são de sistema separado.
- O desenho definitivo de `WithdrawalRequirement`.

## Alternativas descartadas

**Fixar `animal × mercado` como unidade universal da elegibilidade.** Foi a primeira formulação desta ADR, e é contraditória: a China, usada como caso de prova, tem requisito que pertence ao estabelecimento. Produziria decisão sobre o animal a partir de característica de outro sujeito — afirmação falsa, porque o resultado mudaria conforme a planta escolhida sem que nada no animal tivesse mudado.

**Campo de elegibilidade no animal.** Teria de eleger um mercado e calar sobre os demais, e apodreceria no primeiro embargo novo.

**Uma decisão única com lista de mercados aprovados dentro.** Impediria versionar a norma de cada mercado em separado: mudança na União Europeia invalidaria a decisão sobre a China, que não mudou.

**Campo `market` no Core.** Faria um domínio genérico carregar vocabulário de uma vertical.

**Finalidade montada como string solta na vertical.** Produziria taxonomia escondida e divergente entre pontos do código.

**`REAVALIACAO_NECESSARIA` como `DecisionResult`.** Faria a decisão histórica mudar de resultado por causa de um fato externo a ela, quebrando a imutabilidade que sustenta a auditoria.

**Matriz gravada como projeção materializada.** Segunda fonte de verdade, que diverge na primeira mudança de regra ou publicação de camada.

**Omitir mercados sem informação suficiente.** Ausência silenciosa é lida como aprovação por quem consulta.

**Reaproveitar o prazo de carência de um mercado em outro.** Inventa norma estrangeira.

## Consequências

### Positivas

- A pergunta que o cliente faz — "para onde posso mandar este boi?" — passa a ser respondida diretamente.
- Requisitos de estabelecimento, lote e operação têm lugar no modelo desde já, sem decisão emitida hoje precisar ser reinterpretada depois.
- Mudança normativa de um mercado não contamina os demais.
- O motor do Marco 9 é reusado inteiro; o multi-mercado é vocabulário e leitura, não motor novo.
- A matriz distingue resultado, idade e atualidade normativa — três perguntas que "vigente" confundia numa só.
- A autoria de regras ganha justificativa comercial concreta.

### Negativas

- O número de avaliações multiplica por sujeito e por mercado, com custo de armazenamento e de reavaliação em massa.
- Enquanto os prazos por mercado não forem declarados, a matriz exibirá muitos indeterminados.
- `CONDICIONADO` exige que a leitura saiba quais requisitos pertencem a que sujeito — informação que hoje vive só na política.
- A autoria de regras cria superfície nova de risco: regra malformada publicada por engano.
- Reavaliação disparada por camada externa ou por política nova é assíncrona e precisa de execução em lote.

### A abstração excede a pecuária

"Sob quais regras, para quais destinos e com quais restrições este ativo pode ser utilizado" não é pergunta exclusiva de gado. O **padrão** — sujeito, finalidade de mercado, política versionada, matriz derivada com atualidade declarada — é genérico.

Isso **não** autoriza movê-lo para o Core agora: o vocabulário de mercado continua sendo da vertical, e generalizar sem um segundo caso real produziria abstração especulativa. Fica registrado como direção, para quando existir a segunda vertical.

## Riscos e controles

| Risco | Controle |
|---|---|
| Condição de um sujeito ser atribuída a outro | Invariante explícita; requisito avaliado sobre o sujeito a que pertence |
| `CONDICIONADO` ser lido como elegível | Estado próprio, com a dependência nomeada na célula |
| Indeterminado ser lido como elegível | Terceiro estado visível, com motivo, nunca omitido |
| Ausência de política confundida com falta de dado | `AUSENTE` e `INDETERMINADO` são estados distintos |
| Decisão obsoleta lida como atual | Instante e política usada declarados; comparação com a política vigente |
| Atualidade normativa mudar decisão histórica | `REAVALIACAO_NECESSARIA` é estado da projeção, não da decisão |
| Taxonomia de finalidade divergir no código | Value Object único na vertical |
| Granularidade de mercado engessar | `profile` desde o primeiro corte; evolução dentro da vertical |
| Regra malformada publicada | Portão de aprovação e imutabilidade da versão publicada |
| Camada externa mudar depois da decisão | Material importado e versionado no Titan; reimportação não substitui |
| Matriz virar tabela | Derivação calculada na leitura |
| Prazo de um mercado vazar para outro | Ausência produz indeterminado, nunca reaproveitamento |
| Titan emitir conclusão jurídica | Linguagem delimitada; resultado descreve relação avaliada sob norma e versão |
| Custo de reavaliação em massa | Execução em lote, orçamento medido antes de ampliar mercados |

## Testes mínimos

- o mesmo animal produz resultados diferentes em mercados diferentes, no mesmo instante;
- requisito de estabelecimento produz decisão cujo sujeito é o estabelecimento, e não o animal;
- a matriz do animal declara `CONDICIONADO` quando o mercado depende de sujeito ainda não escolhido;
- mudar a versão da regra de um mercado não altera a decisão vigente dos demais;
- política nova publicada leva a célula a `REAVALIACAO_NECESSARIA` sem alterar a `Decision` histórica;
- a célula declara resultado, instante, política usada e política vigente;
- mercado sem política declarada responde `AUSENTE`; mercado com política e sem dado responde `INDETERMINADO`;
- mercado sem prazo de carência declarado responde indeterminado, e não elegível;
- decisão histórica continua apontando para a versão de política que a produziu;
- acrescentar condição sobre fato já disponível não altera nenhum código do motor;
- a matriz não é lida de tabela própria;
- reimportar geometria cria versão nova e preserva a avaliação anterior;
- a finalidade textual é produzida pelo Value Object, e não montada manualmente;
- resultado não afirma conformidade jurídica nem autoriza operação comercial.

## Critérios de aceitação

A ADR pode ser aceita quando:

- elegibilidade for avaliação de **um sujeito** para uma finalidade de mercado, sem fixar o animal como sujeito universal;
- nenhuma condição de um sujeito for atribuída a outro;
- mercado for finalidade, e não campo do Core, produzida por Value Object da vertical;
- a granularidade da finalidade puder evoluir sem tocar no Core;
- a matriz for derivação declarada, com resultado, instante, política usada e atualidade normativa;
- `REAVALIACAO_NECESSARIA` for estado da projeção, nunca `DecisionResult`;
- `AUSENTE` e `INDETERMINADO` forem distinguíveis;
- carência por mercado não reaproveitar prazo alheio;
- a distinção entre "condição nova sobre fato existente" e "categoria nova de fato" estiver explícita;
- autoria de regras preservar portão de aprovação, imutabilidade e não retroatividade;
- a decisão comercial permanecer fora do Titan.

## Relacionadas

ADR-0011 (fontes normativas, vigência e reavaliação temporal); ADR-0016 (decisões explicáveis e revisão humana); ADR-0026 (evidência geoespacial, cobertura e limitações); ADR-0036 (execução determinística de políticas, reservada); ADR-0040 (evento reprodutivo, pelo princípio de que derivação não vira fato gravado). Nota de rumo NR-5, que esta ADR converte em requisito.
