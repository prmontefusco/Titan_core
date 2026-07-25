# ADR 0041 — Elegibilidade por mercado de destino

**Status:** Aceita
**Data:** 25 de julho de 2026
**Decisores:** fundador e responsável pela arquitetura do Titan

## Contexto

O Marco 9 entregou elegibilidade farmacológica: uma `Policy`, uma `Rule` bloqueante por carência, e uma `Decision` explicável por animal. A finalidade declarada foi `ELEGIBILIDADE_FARMACOLOGICA`, e o resultado é único — aprovada, rejeitada, aprovada com restrições ou indeterminada.

A discussão sobre embargos ambientais, terras indígenas e áreas de desmatamento expôs que esse modelo responde à pergunta errada. Perguntado se um animal "está conforme", o sistema teria de escolher uma norma entre várias, e a escolha seria arbitrária: a União Europeia, a China e o mercado interno brasileiro não exigem as mesmas coisas.

O responsável formulou o requisito com precisão: **o sistema deve indicar para quais mercados o animal é elegível, e quem decide é o frigorífico ou o exportador.**

## Problema

Definir:

- se conformidade é propriedade do animal ou relação entre animal e destino;
- como o motor de regras existente comporta destinos com normas divergentes;
- que forma tem a resposta quando há vários destinos;
- o que acontece quando falta informação para um destino específico;
- como normas que mudam por decisão externa entram sem exigir implantação de código;
- onde termina a informação do Titan e começa a decisão comercial de quem o usa.

## A pergunta certa

**Conformidade não é propriedade do animal.** É uma relação entre o animal e um mercado de destino, avaliada sob uma norma versionada, num instante determinado.

O mesmo boi é elegível para a China e inelegível para a União Europeia, e nenhum dos dois estados é "o" estado dele. Um campo `conforme` no animal teria de escolher um mercado e calar sobre os outros.

## Decisão

**O mercado de destino é uma dimensão da avaliação, e não um atributo do sujeito.**

Cada par (animal, mercado) produz a sua própria `Evaluation` e a sua própria `Decision`, independentes e versionadas em separado. A resposta ao usuário é uma **matriz de elegibilidade**: uma linha por destino, cada uma com resultado, motivo, evidência e versão da regra que a produziu.

```text
BOI-4471
  ├── Mercado interno ...... ELEGÍVEL        avaliado em 25/07/2026
  ├── China ................ ELEGÍVEL        avaliado em 25/07/2026
  ├── União Europeia ....... INELEGÍVEL      avaliado em 25/07/2026
  │     eudr-desmatamento v3: a permanência de 03/2025 a 08/2025 ocorreu em
  │     propriedade que intersecta a camada PRODES v2025-06
  └── Estados Unidos ....... INDETERMINADO   avaliado em 25/07/2026
        cobertura insuficiente: sem geometria para a propriedade de origem
```

**O Titan não decide para onde o animal vai.** Ele informa o que cada norma diz e por quê. A escolha comercial é de quem exporta, e permanece fora do sistema — o que é coerente com a ADR-0016 e com a ADR-0026, que já separava a relação calculada do significado de negócio.

## Como isso cabe no Core sem alterá-lo

`Evaluation` e `Decision` já exigem `purpose` não vazio, e `DecisionResult` já admite `INDETERMINADA`. O mercado entra como **finalidade**, e não como campo novo:

```text
ELEGIBILIDADE_MERCADO.BR
ELEGIBILIDADE_MERCADO.EU
ELEGIBILIDADE_MERCADO.CN
```

O vocabulário é **namespaced e canônico**, como os tipos de evento da vertical. Mercado é conceito da vertical — o Core não sabe o que é exportar carne, e acrescentar um campo `market` ao Core faria um domínio genérico carregar vocabulário de uma vertical.

Consequência boa: **cada mercado tem `Policy` e `Rule` próprias, versionadas em separado.** Quando a União Europeia mudar a norma, sobe a versão da política da União Europeia, e nenhuma decisão dos outros mercados é afetada. Isolamento de mudança normativa sai de graça.

## A matriz é derivação, nunca registro

A matriz é **calculada na leitura**, a partir da decisão vigente de cada mercado. Não existe tabela de matriz, nem campo agregado no animal.

É o mesmo princípio do Passo 9.4 e da ADR-0040: gravar a derivação criaria segunda fonte de verdade, e ela divergiria da primeira no dia em que uma regra mudasse ou uma camada nova fosse publicada — que é justamente o que acontece o tempo todo neste domínio.

**Cada célula declara quando foi avaliada.** Uma decisão de três meses atrás não é falsa, mas pode estar obsoleta, e quem lê precisa saber a idade da informação para decidir se manda reavaliar. Omitir o instante transformaria uma resposta datada numa afirmação atemporal.

## `INDETERMINADO` é resultado de primeira classe

Ausência de informação **nunca** produz elegibilidade. Um mercado para o qual falta geometria, falta prazo declarado ou falta camada disponível responde `INDETERMINADO`, com o motivo, e aparece na matriz — não é omitido.

Isso é o princípio "desconhecido permanece desconhecido" da ADR-0026 aplicado à saída do motor. É também o que separa um sistema de rastreabilidade de um carimbo: quem não sabe, diz que não sabe.

**Um mercado ausente da matriz significa que ninguém declarou regra para ele**, e isso é diferente de `INDETERMINADO`. A resposta distingue os dois.

## A carência passa a ser por mercado

O Marco 9 guarda `withdrawal_period_days` como número único em `Medication`. O prazo de um mesmo princípio ativo, porém, varia por país de destino.

Não foi erro: o escopo era o mercado interno, e um número bastava. Mas o motor multi-mercado o torna insuficiente, e a correção é aditiva — o prazo vira uma coleção por mercado, e o valor atual passa a ser o do mercado interno.

**Ausência de prazo declarado para um mercado produz `INDETERMINADO` para aquele mercado, e não reaproveita o prazo de outro.** Afirmar que o prazo brasileiro vale na União Europeia seria inventar norma estrangeira.

A consequência prática é incômoda e aceita: enquanto ninguém declarar os prazos de um mercado, todo animal tratado sairá indeterminado para ele. Isso é a verdade sobre o estado do conhecimento, e o incômodo é o sinal correto — ele empurra para declarar o dado, e não para fingir que ele existe.

## Fatos entram pela porta que já existe

O motor consome fatos do `FactProvider`. A restrição territorial entrará como **mais um fato**, do mesmo modo que a carência entrou no Marco 9.

```text
hoje       carência por mercado          → matriz funcionando
depois     + fato territorial            → mesma matriz, regra nova, zero código
```

Esse é o teste do desenho: **se acrescentar restrição territorial exigir alterar o motor, o motor está errado.** A ordem de implementação existe para submeter o modelo a esse teste com dado real, antes que ele dependa de camadas externas amadurecerem.

## Regra é dado, não código

Normas de mercado mudam por decisão de autoridade estrangeira, em prazo que não é o do desenvolvimento. Exigir implantação de código a cada mudança inviabiliza o produto.

Esta ADR converte a **nota de rumo NR-5** de intenção em requisito: o administrador compõe regras, e o sistema as executa. `RuleCondition` já é declarativo, versionado, viaja inteiro no dossiê e é reexecutável — para regras que caibam nessas primitivas, o problema de execução já está resolvido, e o que falta é a autoria.

Três restrições que a autoria não afrouxa:

1. **Publicar regra exige portão de aprovação.** Regra de negócio é categoria de aprovação obrigatória no plano, e autoria pelo administrador não muda isso.
2. **Regra publicada é imutável.** Alteração cria versão nova; decisões antigas continuam apontando para a versão que as produziu.
3. **Regra nova não reinterpreta decisão histórica.** Ela produz avaliação nova, com instante próprio.

A ADR-0036 (Wasm) permanece reservada para o que não couber nas primitivas declarativas, e só com evidência de que não coube.

## Reprodutibilidade da avaliação territorial

Quando a avaliação territorial existir, ela dependerá de camadas externas. O Titan **importa e guarda** o material que usou — geometria, versão declarada, instante da importação e digest — em vez de consultar o estado atual da fonte no momento da reavaliação.

Isso torna a reprodutibilidade responsabilidade do Titan, e não do provedor, e vale mesmo quando a fonte só expõe o estado corrente.

**Reimportação nunca substitui.** Geometria ou camada reimportada é versão nova; avaliações anteriores continuam apontando para a versão que usaram. É a ADR-0026 ao pé da letra, e sem isso a auditoria de 2027 leria a decisão de 2025 contra um polígono que não existia na época.

## Os três mercados do primeiro corte

Escolhidos por serem **estruturalmente diferentes**, e não por volume:

| Mercado | O que a regra observa |
|---|---|
| Interno (BR) | o animal, sem restrição territorial |
| União Europeia (EU) | o animal **e onde ele esteve** |
| China (CN) | o **estabelecimento**, e não o animal |

Se o modelo comporta os três, comporta quase tudo o que vier. Desenhar apenas com os dois primeiros produziria um motor que só sabe falar sobre o animal, e o primeiro requisito de habilitação de planta quebraria o desenho.

**Os requisitos concretos de cada mercado não são fixados por esta ADR.** Eles são regra, e regra é dado — declarada pelo responsável, sob portão de aprovação, e confirmada contra a norma vigente antes de valer. O que esta ADR fixa é a forma, nunca o conteúdo normativo.

## Fora de escopo

- Decisão comercial de destino, que é de quem exporta.
- Conclusão jurídica de conformidade; o Titan informa relação avaliada, e não infração.
- Habilitação de estabelecimento como avaliação própria — o sujeito ali é a planta, e a combinação com a elegibilidade do animal exige decomposição própria.
- Representação de contraparte externa, necessária para fornecedor indireto, que fica para ADR própria.
- Ingestão e manutenção das camadas ambientais, que são de sistema separado.

## Alternativas descartadas

**Campo de conformidade no animal.** Teria de eleger um mercado e calar sobre os demais, e apodreceria no primeiro embargo novo.

**Uma decisão única com lista de mercados aprovados dentro.** Impediria versionar a norma de cada mercado em separado: mudança na União Europeia invalidaria a decisão sobre a China, que não mudou.

**Campo `market` no Core.** Faria um domínio genérico carregar vocabulário de uma vertical, e o Core não sabe o que é exportar carne.

**Matriz gravada como projeção materializada.** Segunda fonte de verdade, que diverge na primeira mudança de regra ou publicação de camada.

**Omitir mercados sem informação suficiente.** Ausência silenciosa é lida como aprovação por quem consulta.

**Reaproveitar o prazo de carência de um mercado em outro.** Inventa norma estrangeira.

## Consequências

### Positivas

- A pergunta que o cliente faz — "para onde posso mandar este boi?" — passa a ser respondida diretamente.
- Mudança normativa de um mercado não contamina os demais.
- O motor do Marco 9 é reusado inteiro; o multi-mercado é vocabulário e leitura, não motor novo.
- Restrição territorial entra depois como fato, sem alterar o motor.
- A autoria de regras ganha justificativa comercial concreta, e deixa de ser melhoria abstrata.

### Negativas

- O número de avaliações por animal multiplica pelo número de mercados, com custo de armazenamento e de reavaliação em massa.
- Enquanto os prazos por mercado não forem declarados, a matriz exibirá muitos indeterminados.
- A autoria de regras cria superfície nova de risco: regra malformada publicada por engano.
- Reavaliação disparada por camada externa é assíncrona e precisa de execução em lote.

## Riscos e controles

| Risco | Controle |
|---|---|
| Indeterminado ser lido como elegível | Terceiro estado visível na matriz, com motivo, e nunca omitido |
| Decisão obsoleta ser lida como atual | Instante de avaliação declarado em cada célula |
| Regra malformada publicada | Portão de aprovação e imutabilidade da versão publicada |
| Mudança normativa reinterpretar histórico | Regra nova produz avaliação nova; decisão antiga aponta para a versão que a produziu |
| Camada externa mudar depois da decisão | Material importado e versionado no Titan; reimportação não substitui |
| Matriz virar tabela | Derivação calculada na leitura, sem projeção materializada |
| Prazo de um mercado vazar para outro | Ausência produz indeterminado, nunca reaproveitamento |
| Titan emitir conclusão jurídica | Linguagem delimitada; resultado descreve relação avaliada sob norma e versão |
| Custo de reavaliação em massa | Execução em lote, orçamento medido antes de ampliar mercados |

## Testes mínimos

- o mesmo animal produz resultados diferentes em mercados diferentes, no mesmo instante;
- mudar a versão da regra de um mercado não altera a decisão vigente dos demais;
- mercado sem prazo de carência declarado responde indeterminado, e não elegível;
- mercado sem regra declarada não aparece como indeterminado, e sim como ausente;
- a matriz declara o instante de avaliação de cada célula;
- decisão histórica continua apontando para a versão de política que a produziu;
- acrescentar um fato novo ao `FactProvider` não exige alteração no motor;
- a matriz não é lida de tabela própria;
- reimportar geometria cria versão nova e preserva a avaliação anterior;
- resultado não afirma conformidade jurídica nem autoriza operação comercial.

## Critérios de aceitação

A ADR pode ser aceita quando:

- mercado for finalidade, e não campo do Core;
- cada par animal-mercado tiver avaliação e decisão próprias e versionadas;
- a matriz for derivação declarada, com instante por célula;
- indeterminado for resultado visível e nunca conversível em elegível;
- ausência de regra for distinguível de ausência de informação;
- carência por mercado não reaproveitar prazo alheio;
- restrição territorial puder entrar como fato sem alterar o motor;
- autoria de regras preservar portão de aprovação, imutabilidade e não retroatividade;
- a decisão comercial permanecer fora do Titan.

## Relacionadas

ADR-0011 (fontes normativas, vigência e reavaliação temporal); ADR-0016 (decisões explicáveis e revisão humana); ADR-0026 (evidência geoespacial, cobertura e limitações); ADR-0036 (execução determinística de políticas, reservada); ADR-0040 (evento reprodutivo, pelo princípio de que derivação não vira fato gravado). Nota de rumo NR-5, que esta ADR converte em requisito.
