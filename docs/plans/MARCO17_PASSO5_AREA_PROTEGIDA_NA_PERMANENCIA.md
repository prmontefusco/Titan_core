# Marco 17, Passo 17.5 — Área protegida na permanência

**Data:** 24 de agosto de 2026
**Estado:** Cortes 1 e 2 IMPLEMENTADOS; revisão humana pendente.

Este documento substitui quatro documentos de planejamento escritos mais cedo neste mesmo dia
(`..._DISCOVERY`, `..._REQUIREMENTS`, `..._BUILD_PLAN`, `..._LAUNCH`), removidos por descreverem um
17.5 que não existe. Eles partiam de um inventário que não foi feito e propunham construir do zero,
no Core, capacidades que já existem na vertical Livestock — e tratavam embargo do IBAMA como o
primeiro corte, quando embargo já tem caminho próprio e o CAR não carrega campo de embargo algum.
O registro do erro fica aqui porque a causa dele — planejar antes de inventariar — é a lição, não o
conteúdo descartado.

---

## O que já existia antes deste passo

| Capacidade | Onde | O que responde |
|---|---|---|
| Embargo ambiental (IBAMA) | `environmental_embargo_service.py`, `environmental_embargo_assertion.py` | "Quais restrições o provider declara sobre o polígono vigente?" — com assertion append-only, digest e versão de geometria |
| Sobreposição territorial atual (FUNAI) | `territorial_overlap_service.py` | "Há sobreposição atual conhecida desta camada?" — validado contra provider real em 04/08/2026 |
| Série temporal (PRODES, DETER) | `territorial_timeline_service.py` | "Que série o provider declara para esta propriedade, camada e intervalo?" |
| Captura versionada e seleção histórica | `territorial_capture.py`, `temporal_territorial_capture.py` | Reconstrução histórica sintética com limitações explícitas |
| Camadas do CAR importadas | `geometry_service.py`, `geometry.py` | `AREA_IMOVEL`, `APPS`, `RESERVA_LEGAL`, `USO_RESTRITO`, … versionadas por `(propriedade, camada)` |

Todas essas leituras são **por propriedade**. Nenhuma delas liga o **animal** ao território.

## O que faltava, e é este passo

O próprio Passo 17.2 registrou a lacuna ao concluir:

> `RESERVA_LEGAL`, `APPS` e `USO_RESTRITO` são áreas onde a legislação restringe atividade, **e vêm
> do próprio CAR do imóvel** — sem depender de camada de embargo alguma. Cruzar `PropertyStay` com
> elas já responde "este animal permaneceu em área de reserva legal?". Não é embargo do IBAMA e não
> substitui.

`ProtectedAreaStayService` faz exatamente esse cruzamento, e nada além dele.

## O limite que o resultado carrega

**A permanência liga o animal ao imóvel, não a um ponto dentro dele.** As camadas do CAR são
polígonos internos ao perímetro. Portanto o resultado positivo diz que o imóvel **declara** área
protegida — nunca que o animal esteve dentro dela. O Titan não rastreia posição intra-imóvel, e
afirmar o contrário seria inventar localização.

Por isso a pergunta do 17.2 foi respondida numa forma mais estreita do que ela foi escrita: não
"este animal permaneceu em área de reserva legal", e sim "este animal permaneceu em imóvel que
declara reserva legal". A limitação viaja no resultado como
`LIVESTOCK_POSICAO_DO_ANIMAL_DENTRO_DO_IMOVEL_DESCONHECIDA`, e não como comentário no código.

## Semântica

| Situação | Status |
|---|---|
| Alguma permanência em imóvel com `APPS`/`RESERVA_LEGAL`/`USO_RESTRITO` vigente | `COM_AREA_PROTEGIDA_DECLARADA` |
| Todos os imóveis observados, nenhum declara área protegida | `SEM_AREA_PROTEGIDA_DECLARADA` |
| Animal sem permanência, ou imóvel sem CAR importado | `INDETERMINADA` |

**Positivo vence lacuna; lacuna vence negativo.** Uma camada declarada é afirmação da fonte e não
deixa de valer porque outro imóvel da linha do tempo está sem CAR. Já o negativo exige que todos os
imóveis tenham sido observados: sem isso, "não há área protegida" seria conclusão tirada de material
que ninguém olhou.

### Lacunas explícitas

- `PERMANENCIA_AUSENTE` — não há imóvel sobre o qual perguntar.
- `GEOMETRIA_AUSENTE` — o CAR daquele imóvel não foi importado. **Ausência de dado não é ausência de
  área protegida.**
- `CAPTURA_POSTERIOR_A_PERMANENCIA` — `captured_at` é a data de atualização do cadastro, não a da
  importação (Passo 17.2), e o CAR é retificável. Camada atualizada depois de o animal sair descreve
  o imóvel de hoje; usá-la como se descrevesse o período da permanência afirmaria sobre um passado
  que ela não viu.

## Fronteiras preservadas

Estes cortes **não** fazem: conclusão jurídica de irregularidade, elegibilidade de mercado, Rule
publicada, `Evaluation`, `Decision`, `Dossier`, endpoint HTTP, persistência, migration, interseção
geométrica intra-imóvel, contaminação de lote, nem qualquer alteração em embargo, FUNAI, PRODES ou
DETER.

O fato existe, mas **nenhuma regra o consome ainda** — logo ele não muda elegibilidade alguma. Qual
mercado deve exigi-lo, e com que efeito comercial, é decisão normativa explícita, exatamente como
ficou registrado para `rule-sobreposicao-funai` na validação FUNAI de 04/08/2026.

Se há gado em área protegida e se isso é irregular é **avaliação com regra versionada** — nunca
inferência deste serviço. É o que o próprio domínio já dizia em `PropertyGeometry.e_area_protegida`.

## Corte 2 — o fato governável

`livestock.territorial.protected_area_stay` entra no `FactProvider` no mesmo padrão de
`livestock.territorial.funai`: serviço opcional, e sem ele o fato simplesmente não existe. **Ausência
do serviço nunca vira fato negativo** — um fato dizendo "não há área protegida" quando ninguém
perguntou seria pior que fato nenhum.

Diferente dos três fatos territoriais anteriores, este é **por animal**, não por propriedade: o
serviço já percorre a linha de permanências inteira, e o imóvel atual é só o último ponto dela.

**A chave que uma Rule consome é `has_declared_protected_area`**, e ela só é `true` quando alguma
camada foi de fato declarada. Em `INDETERMINADA` ela é `false` **e** `gaps` não está vazio: uma regra
que ler apenas a chave booleana leria lacuna como ausência de área protegida. Por isso `status`,
`gaps` e `limitations` viajam no mesmo payload — a conclusão não existe sem eles.

### Fora da leitura temporal, de propósito

O fato entra em `get_snapshot`, nunca em `get_snapshot_with_temporal_context`. `PropertyStay` é
projeção mutável, e o caminho temporal já declara que ela nunca é usada porque não sustenta
reprodução histórica. Incluí-lo ali faria uma avaliação retrospectiva afirmar sobre o passado com
material que só descreve o presente. Há teste fixando isso.

## Evidência

`packages/livestock_application/protected_area_stay_service.py`,
`packages/livestock_application/fact_provider.py`;
`tests/livestock_application/test_protected_area_stay_service.py` (13 casos),
`tests/livestock_application/test_fact_provider_protected_area.py` (7 casos).

**Portão verificado:** 20 testes dos dois cortes passando; suíte completa `1423 passed`, com as 12
falhas pré-existentes do BuyerPolicy Fase 2 inalteradas (confirmado com o corte removido);
`ruff check`, `ruff format --check`, `mypy` e `alembic check` limpos nos arquivos tocados. Nenhuma
migration — os cortes são derivação pura sobre `PropertyStay` e `PropertyGeometry` existentes.

### As 12 falhas pré-existentes

São do BuyerPolicy Fase 2, anteriores a este passo e não tocadas por ele. A raiz da primeira é
arquitetural e vale registrar porque é o mesmo erro que este passo evitou:
`packages/core_application/policy_sharing_service.py` importa
`packages.core_infrastructure.persistence.authorization_grant`, violando
`test_core_application_does_not_import_apps_or_infrastructure`. As outras onze são de API/integração
do mesmo conjunto. Corrigi-las é trabalho próprio do NEXT-10/NEXT-11.

## Próximos cortes possíveis

Nenhum deles está autorizado por este registro.

1. **Template de Rule e decisão de mercado.** Publicar uma regra que cite
   `livestock.territorial.protected_area_stay` e decidir qual `MarketProfile` a consome. É o portão
   para qualquer efeito comercial — e é decisão normativa, não técnica.
2. **Leitura HTTP.** Endpoint por animal, no padrão de
   `GET /v1/livestock/properties/{id}/territorial-overlaps/funai`.
3. **Interseção intra-imóvel.** Só faz sentido se existir posição do animal dentro do imóvel. Hoje
   não existe, e sem ela não há o que calcular.
4. **Reprodução histórica.** Exige camada com vigência, não só `captured_at` — o mesmo modelo
   próprio que a ADR-0026 previu para camadas territoriais. É o que tiraria o fato da restrição de
   só existir na leitura corrente.
