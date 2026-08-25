# ADR-0067 — Área protegida do CAR na permanência do animal

**Data:** 24 de agosto de 2026 · **Estado:** PROPOSTA (aguarda revisão humana)

**Contexto:** Marco 17, Passo 17.5. Depende dos Passos 17.1 (geometria versionada, ADR-0026) e 17.2
(importação do CAR por camada).

---

## Contexto

O Passo 17.2 terminou com as camadas `RESERVA_LEGAL`, `APPS` e `USO_RESTRITO` importadas e
versionadas por `(propriedade, camada)`, e registrou explicitamente que cruzá-las com `PropertyStay`
já responderia uma pergunta de conformidade territorial real — sem depender de nenhuma camada de
embargo.

Essa pergunta continuava sem resposta. Tudo o que existia era **por propriedade**: embargo ambiental
do IBAMA (`environmental_embargo_service`), sobreposição atual da FUNAI
(`territorial_overlap_service`), séries do PRODES e DETER (`territorial_timeline_service`). Nenhuma
delas liga o **animal** ao território.

## Decisão

Criar `ProtectedAreaStayService` na Application da vertical Livestock, respondendo exclusivamente:
**nos imóveis onde este animal permaneceu, o CAR declara área protegida?**

### 1. O resultado é sobre o imóvel, não sobre o animal dentro do imóvel

A permanência liga o animal ao imóvel; as camadas do CAR são polígonos internos ao perímetro. O
Titan não rastreia posição intra-imóvel.

Portanto o resultado positivo afirma que o **imóvel declara** área protegida durante a permanência —
nunca que o animal esteve dentro dela. A limitação
`LIVESTOCK_POSICAO_DO_ANIMAL_DENTRO_DO_IMOVEL_DESCONHECIDA` viaja em todo assessment, inclusive nos
negativos.

**Alternativa recusada:** afirmar sobreposição animal↔polígono. Exigiria posição do animal dentro do
imóvel, que não existe; produzir a afirmação sem ela seria inventar localização.

### 2. Ausência de CAR importado é lacuna, não negativa

Imóvel sem geometria importada devolve `GEOMETRIA_AUSENTE` e leva o resultado a `INDETERMINADA`.

**Positivo vence lacuna; lacuna vence negativo.** Uma camada declarada é afirmação da fonte e não
deixa de valer porque outro imóvel da linha do tempo está sem CAR. O negativo, ao contrário, exige
que todos os imóveis tenham sido observados — sem isso, "não há área protegida" seria conclusão
tirada de material que ninguém olhou.

**Alternativa recusada:** tratar ausência como `SEM_AREA_PROTEGIDA`. Converteria falta de dado em
prova de conformidade, que é o erro que a ADR-0042 e o tratamento de cobertura sanitária já
recusaram em outra frente.

### 3. Camada capturada depois da permanência é lacuna declarada

`captured_at` é a data de atualização do cadastro no SICAR, não a da importação (descoberta de campo
do Passo 17.2), e o CAR é retificável. Camada atualizada depois de o animal sair descreve o imóvel de
hoje. Ela continua entrando no resultado — é o melhor material disponível — mas acompanhada de
`CAPTURA_POSTERIOR_A_PERMANENCIA`, para que quem lê saiba que a afirmação não cobre o período.

**Alternativa recusada:** descartar a camada. Perderia o único material existente e produziria
`INDETERMINADA` onde há informação parcial legítima.

### 4. Só `APPS`, `RESERVA_LEGAL` e `USO_RESTRITO` contam

A distinção já existia no domínio, em `PropertyGeometry.e_area_protegida`. `HIDROGRAFIA`,
`AREA_CONSOLIDADA`, `VEGETACAO_NATIVA` e as demais são camadas do imóvel sem restrição legal de
atividade associada. Este passo reusa a propriedade existente em vez de redefinir o critério.

### 5. O fato carrega a lacuna junto da conclusão

O assessment é exposto como `livestock.territorial.protected_area_stay`, por animal — os três fatos
territoriais anteriores são por propriedade, e este não precisa ser, porque o serviço já percorre a
linha de permanências.

`has_declared_protected_area` é a chave que uma Rule consumiria, e ela é `false` tanto em
`SEM_AREA_PROTEGIDA_DECLARADA` quanto em `INDETERMINADA`. O que as separa é `gaps` não estar vazio.
Uma regra que ler só a chave booleana leria lacuna como ausência — por isso `status`, `gaps` e
`limitations` viajam no mesmo payload, e não em fato separado.

O fato entra apenas em `get_snapshot`, nunca na leitura temporal: `PropertyStay` é projeção mutável,
e o caminho temporal já a recusa por não sustentar reprodução histórica.

**Alternativa recusada:** emitir o fato mesmo sem o serviço configurado. Produziria um negativo
silencioso — "não há área protegida" onde ninguém perguntou.

### 6. Nenhuma conclusão jurídica, e nenhuma persistência

O serviço não decide irregularidade nem elegibilidade de mercado, não emite `Fact`, `Evaluation`,
`Decision` ou `Dossier`, e não cria tabela, migration ou endpoint. Se há gado em área protegida e se
isso é irregular é avaliação com regra versionada — exatamente o que o domínio já declarava.

O assessment é derivado a cada leitura, não tem identificador, ciclo de vida, aprovação ou revogação.
Persisti-lo seria duplicar `PropertyStay` e `PropertyGeometry` sem ciclo de vida demonstrado — o
mesmo critério que encerrou o NEXT-03 sem entidade nova.

## Consequências

**Positivas.** A primeira leitura de conformidade territorial que fala do animal, não do imóvel.
Reusa geometria versionada e permanência existentes, sem schema novo. As lacunas são nomeadas, então
"não sei" nunca se apresenta como "está tudo bem".

**Limitações preservadas.** Sem posição intra-imóvel, o resultado não prova presença em área
protegida. Sem vigência por camada, não há reprodução histórica — só `captured_at` e a lacuna que ele
gera, e por isso o fato fica fora da leitura temporal. **Nenhuma regra consome o fato ainda**, logo
ele não muda elegibilidade alguma.

**Portão seguinte.** Publicar um template de Rule que cite o fato e decidir qual `MarketProfile` o
consome, com qual efeito comercial. É decisão normativa explícita — o mesmo portão que ficou aberto
para `rule-sobreposicao-funai` — e não está autorizado por esta ADR.

## Relação com outras decisões

- **ADR-0026** — geometria versionada, `SpatialAssessment` e a separação entre camada do imóvel e
  camada territorial independente de propriedade. Esta ADR fica inteiramente do lado "camada do
  imóvel"; embargo, FUNAI, PRODES e MapBiomas continuam exigindo o modelo próprio que a 0026 previu.
- **ADR-0042** — proveniência preservada e lacuna explícita em vez de histórico vazio. A decisão 2
  aplica o mesmo princípio ao território.
- **ADR-0050** — a conclusão normativa pertence a regra versionada, não a este serviço.
