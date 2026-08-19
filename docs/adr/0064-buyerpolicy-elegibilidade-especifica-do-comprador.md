# ADR-0064 - BuyerPolicy: elegibilidade especifica do comprador (Fase 1 interna)

**Data:** 2026-08-19<br>
**Status:** ACEITA<br>
**Aceita em:** 2026-08-19<br>
**Base normativa:** `DOMAIN.md` v1.21, ADRs aceitas ate ADR-0063<br>
**Escopo:** Titan Core e Titan Livestock<br>
**Relacionadas:** ADR-0018, ADR-0038, ADR-0043, ADR-0044, ADR-0048, ADR-0049, ADR-0050, ADR-0053<br>
**Origem:** `docs/specs/proposed/2026-08-15-buyer-specific-eligibility-policies-discovery.md`

---

## 1. Contexto

Alem de exigencias regulatorias de mercado, frigorificos e outros compradores possuem
criterios comerciais, contratuais ou internos proprios para aceitar um fornecedor,
lote ou animal. A Discovery de 2026-08-15 investigou o problema e recomendou nao
criar uma segunda engine de regras: a exigencia do comprador deve ser uma `Policy`
existente, de propriedade da Organization compradora, com `Rule`s governadas pela
ADR-0043 e origem classificavel como `CONTRACT` ou `INTERNAL_POLICY`.

O Core ja oferece os blocos necessarios. `Policy` (`packages/core_domain/policy.py`)
e isolada por `organization_id` proprietaria, sem hardcode de qual Organization pode
criar uma. `RuleIdentity` (`packages/core_domain/rule_governance.py`, ADR-0043) ja
distingue `RuleSourceType.CONTRACT` e `RuleSourceType.INTERNAL_POLICY` de `LAW`,
`REGULATION`, `CERTIFICATION` e `TITAN_TEMPLATE`. `rule_governance_service.py` ja
recebe `organization_id` como parametro em toda operacao — criar identidade, publicar
versao, adotar, substituir — sem privilegiar a Organization operadora. A API
`/v1/rule-governance` ja expõe essas capacidades sob `RULE_GOVERNANCE_CRIAR`,
`RULE_GOVERNANCE_PUBLICAR`, `RULE_GOVERNANCE_ADOTAR` e `RULE_GOVERNANCE_LER`.

Em outras palavras: o mecanismo generico de governanca de regras (ADR-0043) ja foi
desenhado para suportar uma Organization usuaria autorando sua propria regra. O que
falta nao e uma nova entidade, e sim decisoes de fronteira que a ADR-0049 §10
deixou explicitamente em aberto ("a forma persistida, cardinalidade e regras dessa
classificacao exigem definicao posterior") e que a ADR-0044 nao cobre, porque
`MarketEligibilityPurpose` e um enum fechado de destinos de mercado
(`exportacao-uniao-europeia`, `exportacao-china`, `exportacao-estados-unidos`), nao
um espaco de finalidades por comprador.

Esta ADR resolve essas fronteiras para o primeiro incremento seguro identificado pela
Discovery: uma Policy privada, `INTERNAL_POLICY`, avaliada apenas sobre dados ja
visiveis a propria Organization compradora.

---

## 2. Problema

Definir, sem criar segunda fonte de regras nem enfraquecer isolamento por
Organization:

1. Qual e o nome canonico da capacidade, usado em documentacao, API e testes.
2. Se a Fase 1 cobre `INTERNAL_POLICY`, `CONTRACT`, ou ambas.
3. Qual limite de reconhecimento o resultado carrega (`INTERNAL_ONLY`,
   `BILATERAL_CONTRACTUAL` ou outro).
4. Quem pode ver resultado, razoes, Rules e Evidence de uma Policy do comprador.
5. Onde vive a classificacao de origem (`Policy`, `Rule`, `RuleAdoption` ou
   combinacao) e como ela evita mistura com Policy regulatoria.
6. Quais capabilities server-side sao necessarias para criar, publicar, revogar,
   avaliar e ler o resultado.
7. Como a Organization compradora demonstra autoridade para publicar criterio
   interno, sem antecipar `DecisionAuthorityProfile` antes de existir `Decision`.
8. Qual `AccessPurpose` e `FieldScope` sao necessarios quando houver avaliacao de
   dados de terceiro — e por que a Fase 1 nao precisa deles.
9. Como o sistema responde quando a Policy privada e aplicavel mas o dado
   necessario e invisivel.
10. Como revogacao de Policy, de Sharing ou de relacao comercial afeta avaliacoes
    novas e leituras historicas.
11. Se o primeiro resultado e `Evaluation`, `DecisionProposal`, `Decision` ou
    resultado comparativo.
12. Como impedir que o resultado de uma Policy do comprador seja lido, agregado ou
    apresentado como conclusao regulatoria.

---

## 3. Decisao

Adotar **BuyerPolicy** como o nome canonico da capacidade descrita nesta ADR.

`BuyerPolicy` **nao e uma nova entidade persistida do Core**. E o vocabulario para
um padrao de uso de conceitos ja existentes: uma `Policy` (ADR-0038) cuja
`organization_id` pertence a uma Organization que atua como compradora, cujas
`Rule`s sao publicadas sob `RuleIdentity`s (ADR-0043) com `source_type` homogeneo
igual a `INTERNAL_POLICY`, adotada pela propria Organization compradora e avaliada
pelo `RuleEvaluationEngine`/`PolicyEvaluationService` (ADR-0038/ADR-0050) ja
existentes, produzindo `Evaluation` separada, sem `Decision`.

```text
Organization compradora
    -> cria RuleIdentity(source_type=INTERNAL_POLICY, organization_id=compradora)
    -> publica RuleVersion sob template controlado (fact_type/condicao ja Livestock)
    -> cria Policy(organization_id=compradora) e adota a RuleVersion (RuleAdoption)
    -> avalia sujeito ja visivel a propria Organization
    -> produz Evaluation isolada, com boundary INTERNAL_ONLY explicito
    -> apresentacao lado a lado com a matriz regulatoria (ADR-0044), nunca fundida
```

Nenhuma classe nova, tabela nova, `Permission` nova ou motor novo e criada por esta
ADR. A Fase 1 e, deliberadamente, uma decisao de **fronteira e composicao**, nao de
implementacao de mecanismo novo.

**Precisao de vocabulario — "Organization compradora" nao e um tipo tecnico.**
Nenhum mecanismo do Titan hoje distingue uma Organization compradora de qualquer
outra: `RULE_GOVERNANCE_CRIAR`/`PUBLICAR`/`ADOTAR`/`LER` sao concedidas por
`Role`/`Permission` dentro do `OrganizationContext` de cada Organization
(ADR-0031), sem nocao de tipo, segmento ou papel comercial de Organization. Nao
existe `OrganizationType`/`EntityType` "comprador" em `packages/core_domain`; o
`EntityTypeRequest` citado em `DEVELOPMENT.md` qualifica vinculo de Membership,
nao a Organization como um todo. Portanto, mecanicamente, **qualquer** Organization
que ja possua essas permissions em seu proprio contexto pode aplicar o padrao
BuyerPolicy sobre seus proprios dados — nao apenas uma Organization que o produto
rotule como "compradora". Esta ADR usa "Organization compradora" como atalho de
linguagem, porque e o papel de negocio que motivou a Discovery, mas essa expressao
nao implica gate tecnico. Se o produto quiser restringir formalmente quem pode
publicar BuyerPolicy — por exemplo, um `OrganizationType` proprio — isso e decisao
de produto separada e nao resolvida aqui (secao 23).

---

## 4. Escopo e nao objetivos

Esta ADR define o contrato de fronteira do primeiro incremento seguro
(`INTERNAL_POLICY`, `INTERNAL_ONLY`, sem atravessar Organizations).

Esta ADR nao:

- cria `BuyerPolicy`, `BuyerRule` ou `BuyerMarket` como classes ou tabelas novas;
- autoriza `RuleSourceType.CONTRACT` para uso bilateral nesta fase (permanece
  reservado para a Fase 2, ADR futura de compartilhamento);
- cria relacionamento novo entre Organizations, `Sharing`, `AuthorizationGrant` ou
  `AccessPurpose` novo — isso pertence a uma Fase 2 com ADR propria;
- cria `DecisionAuthorityProfile` especializado — a Fase 1 nao emite `Decision`;
- cria composicao agregada entre Policy regulatoria e Policy do comprador;
- altera `MarketEligibilityPurpose`, `MarketProfile` ou a matriz da ADR-0044;
- altera `DOMAIN.md` diretamente; onde uma alteracao formal for necessaria, esta
  ADR aponta o texto candidato como criterio de liberacao (secao 12);
- autoriza qualquer implementacao de codigo — permanece decisao de arquitetura, a
  ser seguida por SPEC CRITICAL propria.

---

## 5. Decisao 1 — Natureza da exigencia (Decisao 1 da Discovery)

A Fase 1 cobre **exclusivamente `RuleSourceType.INTERNAL_POLICY`**.

`RuleSourceType.CONTRACT` continua existindo no enum (ADR-0043) mas **nao e usado
por BuyerPolicy nesta fase**, porque um criterio contratual bilateral pressupoe uma
relacao comprador–fornecedor com escopo, vigencia, visibilidade e revogacao
proprias (ADR-0018), que esta ADR explicitamente nao cria. Autorizar `CONTRACT` sem
essa relacao permitiria a uma Organization declarar unilateralmente uma "clausula
contratual" sem contraparte nem `Sharing` — o que contradiz a propria semantica do
tipo.

Restringir a `INTERNAL_POLICY` tambem simplifica a Decisao 2 (limite de
reconhecimento): torna-o deterministico em vez de exigir novo campo persistido.

---

## 6. Decisao 2 — Limite de reconhecimento

O limite de reconhecimento de uma `Evaluation` de BuyerPolicy e **`INTERNAL_ONLY`**,
**derivado**, nao persistido como campo novo: enquanto a Fase 1 restringir Rules a
`source_type=INTERNAL_POLICY`, o boundary e sempre `INTERNAL_ONLY` por construcao.

`INTERNAL_ONLY` autoriza a interpretacao "atende ao criterio interno daquele
comprador, naquela versao, finalidade e instante" e proibe a interpretacao
"conformidade legal, aceite de outro comprador ou certificacao". Toda superficie de
apresentacao (API, UI futura, Dossier) que exibir uma `Evaluation` de BuyerPolicy
deve carregar esse boundary de forma explicita e nao apenas implicita pelo
`source_type` da Rule.

`BILATERAL_CONTRACTUAL` e `PUBLISHED_COMMERCIAL_PROFILE` permanecem valores
conceituais adiados para as Fases 2 e 3 da Discovery e nao sao decididos aqui.

---

## 7. Decisao 3 — Quem enxerga resultado, razoes, Rules e Evidence

**Somente a Organization compradora.** Isso e consequencia direta, e nao adicao,
do isolamento ja vigente: `Policy.organization_id`, `RuleIdentity.organization_id`
e a persistencia de `Evaluation` ja seguem RLS por Organization proprietaria
(ADR-0002/ADR-0003). Como a Fase 1 nao cria `Sharing` nem `AuthorizationGrant` para
esse conteudo, nenhuma outra Organization tem caminho de leitura — nem por relacao,
nem por identificador, nem por busca.

Isso responde tambem, por construcao, a Decisao 9 da Discovery ("modelo de relacao
comprador–fornecedor"): a Fase 1 nao atravessa tenant.

---

## 8. Decisao 4 — Onde vive a classificacao de origem

A classificacao de origem continua em **`RuleIdentity.source_type`** (ADR-0043),
que ja e o campo autoritativo. Esta ADR nao move nem duplica esse campo em `Policy`
ou em `RuleAdoption`.

O que esta ADR adiciona e um **invariante de composicao a nivel de Policy**, ausente
da ADR-0049 e da ADR-0043: uma `Policy` reconhecida como BuyerPolicy so pode compor
`RuleVersion`s cujas `RuleIdentity`s declarem `source_type` homogeneo
(`INTERNAL_POLICY`, nesta fase). Uma `Policy` que misture `RuleIdentity`s de
`LAW`/`REGULATION`/`CERTIFICATION`/`TITAN_TEMPLATE` com `INTERNAL_POLICY` **nao e**
uma BuyerPolicy e nao recebe o boundary `INTERNAL_ONLY`; ela deve ser tratada como
caso indeterminado de classificacao e rejeitada na publicacao/adocao, nunca
apresentada com origem ambigua.

Essa homogeneidade e o mecanismo que evita a "mistura semantica" identificada como
risco pela propria Discovery (secao 9): sem ela, seria possivel uma Policy parecer
parcialmente oficial por conter uma Rule de origem regulatoria ao lado de uma Rule
privada.

---

## 9. Decisao 5 — Capabilities server-side

**Nenhuma capability nova e necessaria para a Fase 1.** Qualquer Organization
proprietaria de uma BuyerPolicy reutiliza, sobre seu proprio `OrganizationContext`
— sem gate tecnico especifico de "comprador" (ver nota de vocabulario na secao 3):

- `RULE_GOVERNANCE_CRIAR` para criar `RuleIdentity` e rascunhar `RuleVersion`;
- `RULE_GOVERNANCE_PUBLICAR` para publicar a `RuleVersion` e a `Policy`;
- `RULE_GOVERNANCE_ADOTAR` para registrar `RuleAdoption`;
- `RULE_GOVERNANCE_LER` para consultar timeline, versoes e adocoes;
- a capability de execucao de `Evaluation` ja existente para `PolicyEvaluationService`
  (a SPEC da Fase 1 deve confirmar o nome exato dessa capability no codigo atual e
  cobri-la em teste; esta ADR nao introduz uma nova).

Isso responde a Decisao 6 da Discovery ("quem pode criar, revisar e publicar"): a
Fase 1 reaproveita a governanca existente de Policy/Rule sem reforcar segregacao
adicional, porque o efeito de uma BuyerPolicy em Fase 1 e estritamente interno a
propria Organization compradora — nao ha terceiro afetado nem `Decision` emitida
que justifique excecao ao padrao ja usado por qualquer outra Organization hoje.
Segregacao mais forte (autor != publicador, aprovacao dupla) fica registrada como
questao adiada para quando a BuyerPolicy puder afetar terceiro (Fase 2 ou `CONTRACT`).

---

## 10. Decisao 6 — Autoridade para publicar criterio interno

A autoridade e demonstrada por **`Membership` + `Role` + `Permission`** dentro do
`OrganizationContext` da propria Organization compradora — o mesmo mecanismo que
qualquer Organization ja usa para publicar suas proprias Rules hoje (ADR-0031,
ADR-0043). Isso **nao** exige resolver `DecisionAuthorityProfile` (ADR-0053), porque
`DecisionAuthorityProfile` e pre-condicao de emissao de `Decision`, e a Fase 1 nao
emite `Decision` (Decisao 11 abaixo). Antecipar um perfil de autoridade decisoria
para um caso que so produz `Evaluation` seria overengineering — seria criar
abstracao para necessidade que ainda nao existe, o que `DEVELOPMENT.md` proibe.

---

## 11. Decisao 7 — AccessPurpose e FieldScope

**Fora de escopo na Fase 1.** Como nenhum dado de terceiro e avaliado (Decisao 3),
nao ha travessia de Organization a autorizar, logo nao ha `AccessPurpose` novo nem
`FieldScope` novo a definir agora. Essas dimensoes tornam-se obrigatorias somente
na Fase 2 (avaliacao bilateral), sob a governanca ja definida pela ADR-0018 —
`AccessPurpose`, `GrantScope`, `SharingRequest`, `GrantAssessment` e
`AuthorizationGrant` — sem necessidade de conceito novo. Esta ADR nao antecipa
esses valores porque nao ha consumidor real ainda (mesmo principio da ADR-0049
§21.4 para rejeitar `MarketProfile` generico prematuro).

---

## 12. Decisao 8 — Policy privada aplicavel mas dado invisivel

**Estruturalmente, esse caso nao ocorre na Fase 1**, porque o escopo restringe a
avaliacao a sujeitos e Facts ja autorizadamente visiveis para a propria Organization
compradora (nenhuma leitura de terceiro existe). Ausencia de Fact especifico dentro
do proprio dominio da Organization segue o contrato generico ja definido pela
ADR-0050: `RuleResult.PENDENTE` ou `RuleResult.INDETERMINADA`, conforme o contrato
declarado pela propria `RuleVersion` — nunca resultado negativo silencioso.

O caso "Policy privada aplicavel mas dado do fornecedor invisivel" so existe a
partir da Fase 2 e deve ser resolvido junto da ADR de compartilhamento: a resposta
correta la sera analoga a `EvidenceAdmissibilityAssessment`/`Authorization` —
declarar reducao ou indeterminacao, nunca revelar existencia do dado invisivel.
Esta ADR registra a pergunta como adiada, nao como resolvida.

---

## 13. Decisao 9 — Efeito de revogacao

A Fase 1 nao introduz semantica de revogacao nova. Reaproveita, sem alteracao, os
invariantes ja aceitos:

- revogar/substituir uma `RuleVersion` ou uma `Policy` e prospectivo (ADR-0043,
  `DOMAIN.md` §10) — bloqueia novo uso, preserva `Evaluation`s historicas;
- uma nova `Evaluation` apos revogacao **nao encontra** Policy aplicavel e deve
  reportar ausencia explicita (analogo a `POLITICA_APLICAVEL_AUSENTE`, ADR-0049
  §14), nunca reutilizar silenciosamente a ultima versao publicada;
- `RuleImpactAssessment` (ADR-0043) continua o mecanismo para localizar
  `Evaluation`s potencialmente afetadas por mudanca de `RuleVersion`, sem
  reescreve-las.

"Revogacao de Sharing" e "revogacao de relacao comercial" nao se aplicam nesta fase
porque nenhum dos dois existe ainda; ficam para a ADR de Fase 2, que devera seguir
o padrao ja definido pela ADR-0018 (revogacao prospectiva, sem apagar uso ou copia
historica).

---

## 14. Decisao 10 — Forma do resultado

O resultado da Fase 1 e **exclusivamente `Evaluation`** (ADR-0038/ADR-0048),
executada por `PolicyEvaluationService`/`RuleEvaluationEngine` sobre a `Policy` do
comprador, isolada de qualquer `Evaluation` da matriz regulatoria (ADR-0044).

Nao ha `DecisionProposal` nem `Decision` nesta fase: nao existe `Decision` comercial
"aprovado pelo comprador" a emitir, porque nenhuma autoridade decisoria (ADR-0053)
foi definida e nenhuma necessidade concreta de efeito oficial foi demonstrada.
`Decision` de BuyerPolicy fica registrada como questao adiada, condicionada a caso
de uso real e a `DecisionAuthorityProfile` proprio.

Nao ha resultado agregado: cada `Policy` (regulatoria ou do comprador) continua
produzindo sua propria `Evaluation`, conforme ADR-0049 §13.

---

## 15. Decisao 11 — Composicao com Policy regulatoria

Reafirma-se, para BuyerPolicy, o que a ADR-0049 §13/§15 ja decidiu para Policies
regulatorias, contratuais e internas em geral, com um invariante adicional de
apresentacao:

1. `BuyerPolicy` **nunca** e inserida em `MarketEligibilityPurpose`,
   `MarketProfile` ou na matriz da ADR-0044. Sao trilhas de leitura e finalidade
   distintas: a matriz responde "esse sujeito pode ser exportado para X"; a
   `Evaluation` de BuyerPolicy responde apenas "esse sujeito atende ao criterio
   interno daquele comprador".
2. Toda apresentacao de `Evaluation` de BuyerPolicy carrega, de forma explicita e
   nao inferivel por omissao: origem (`INTERNAL_POLICY`), boundary
   (`INTERNAL_ONLY`), Organization proprietaria da Policy e Organization ativa no
   pedido.
3. Nenhuma frase de produto ou API pode declarar "elegivel" sozinho sem qualificar
   a camada (regulatoria vs. comprador); a UI/Dossier futuros devem seguir o
   padrao lado a lado ja recomendado pela Discovery (secao 6, Fase 3) e pela
   ADR-0049 §15.
4. Conclusao agregada entre camadas continua proibida sem `Policy` agregadora
   publicada e versionada, ou ADR formal futura.

---

## 16. Alternativas consideradas

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| Regras livres por comprador executadas no frontend | Rapido para prototipar | Duplica engine no cliente, sem versao, autoridade ou auditoria; papel visual vira autorizacao |
| Novo agregado `BuyerEligibilityRule`/`BuyerRule` | Vocabulario dedicado | Duplica `Policy`+`Rule`+governanca, contraria ADR-0049 e cria segunda fonte de verdade |
| Permitir `CONTRACT` desde a Fase 1 | Cobre caso contratual mais cedo | Exige relacao comprador-fornecedor, Sharing e FieldScope que ainda nao existem; valida duas hipoteses ao mesmo tempo |
| Persistir `recognition_boundary` como campo novo em `Policy` agora | Explicito no schema | Sem consumidor de outro valor alem de `INTERNAL_ONLY` nesta fase; campo persistido sem uso real e abstracao prematura |
| BuyerPolicy reaproveitando `Policy`+`RuleIdentity.source_type` homogeneo, sem entidade nova | Reusa governanca e auditoria ja aceitas; menor superficie nova | Exige disciplina de apresentacao (boundary explicito) para nao confundir com Policy regulatoria |

A ultima alternativa foi adotada.

---

## 17. Consequencias

| Tipo | Consequencias |
|---|---|
| Positivas | Nenhuma engine nova; reaproveita auditoria, versionamento e timeline ja aceitos pela ADR-0043; hipotese comercial validavel com o minimo de decisoes novas; isolamento por Organization ja garantido por RLS existente |
| Negativas | Exige disciplina de apresentacao (boundary explicito) em toda superficie que hoje so mostra Policy regulatoria; exige teste de homogeneidade de `source_type` por Policy, ainda inexistente; exige SPEC propria para nomear e testar a capability de avaliacao |

---

## 18. Invariantes

1. `BuyerPolicy` nao e classe, tabela ou motor novos; e um padrao de uso de
   `Policy` + `RuleIdentity` + `RuleAdoption` + `Evaluation` ja existentes.
2. Na Fase 1, toda `RuleIdentity` usada por uma BuyerPolicy declara
   `source_type = INTERNAL_POLICY`.
3. Uma `Policy` com `RuleIdentity`s de `source_type` heterogeneo nao e reconhecida
   como BuyerPolicy e nao recebe boundary `INTERNAL_ONLY`.
4. O boundary de reconhecimento de uma `Evaluation` de BuyerPolicy e sempre
   explicito na apresentacao, nunca implicito.
5. Nenhuma Organization alem da proprietaria da Policy le resultado, razao, Rule
   ou Evidence de uma BuyerPolicy sem `Sharing`/`AuthorizationGrant` explicitos —
   inexistentes nesta fase.
6. BuyerPolicy avalia somente sujeitos e Facts ja autorizadamente visiveis para a
   propria Organization compradora.
7. Nenhuma `Evaluation` de BuyerPolicy entra em `MarketEligibilityPurpose`,
   `MarketProfile` ou na matriz da ADR-0044.
8. Nenhuma `Decision` e emitida a partir de `Evaluation` de BuyerPolicy nesta fase.
9. Nenhuma conclusao agregada combina Policy regulatoria e BuyerPolicy sem Policy
   agregadora publicada e versionada.
10. Revogacao de `RuleVersion`/`Policy` de BuyerPolicy e prospectiva e nao
    reescreve `Evaluation` historica.
11. Nenhuma capability nova de autorizacao e criada por esta ADR.
12. `RuleSourceType.CONTRACT` nao e usado por BuyerPolicy nesta fase.
13. Negacao de acesso cross-Organization a um recurso de BuyerPolicy segue
    `DOMAIN.md` P-198/`ARCHITECTURE.md` (nao distingue recurso inexistente de
    invisivel); esta ADR nao prescreve codigo de status HTTP especifico.
14. "Organization compradora" e papel de negocio, nao gate tecnico; nenhum
    mecanismo hoje restringe quem pode criar/publicar uma BuyerPolicy alem das
    permissions `RULE_GOVERNANCE_*` ja existentes no proprio `OrganizationContext`.

---

## 19. Fora de escopo

- `RuleSourceType.CONTRACT` / criterio bilateral pactuado entre Organizations;
- qualquer relacionamento novo entre Organizations, `Sharing`,
  `AuthorizationGrant`, `AccessPurpose` ou `FieldScope` novos;
- `DecisionAuthorityProfile`, `DecisionProposal` ou `Decision` de BuyerPolicy;
- composicao/agregacao entre Policy regulatoria e Policy do comprador;
- sujeitos ou fact types alem dos ja usados pela elegibilidade Livestock existente;
- DSL livre de autoria de regra ou importacao/integracao externa de criterio;
- qualquer UI de produto — permanece decisao de apresentacao para SPEC futura;
- qualquer alteracao de `DOMAIN.md` ou `ARCHITECTURE.md`.

---

## 20. Impacto em seguranca, auditoria, tenancy e contratos publicos

**Tenancy:** nao amplia superficie de risco existente. `Policy`, `RuleIdentity` e
`Evaluation` ja sao isolados por `organization_id` via RLS (ADR-0002/ADR-0003); a
Fase 1 nao introduz travessia. O risco de vazamento entre Organizations so nasce na
Fase 2 e deve ser tratado por ADR propria antes de qualquer implementacao. Toda
negacao de acesso a recurso de BuyerPolicy fora do escopo da Organization
solicitante segue `DOMAIN.md` P-198 e `ARCHITECTURE.md` (nao distinguir
externamente recurso inexistente de invisivel), reaproveitando o padrao ja usado
em `/v1/rule-governance` hoje (recurso fora do proprio `organization_id` responde
como recurso nao encontrado, e falta de `Permission` no proprio contexto responde
como recusa de permissao — sao dois sinais distintos, nenhum deles revela
existencia de recurso de outra Organization).

**Auditoria:** reaproveita a timeline imutavel de `RuleTimelineEvent` (ADR-0043) e a
identidade dupla de `Evaluation` (`snapshot_hash`/`context_hash`, ADR-0051). Nenhum
novo tipo de evento e necessario para o padrao BuyerPolicy em si, mas a SPEC deve
garantir que a homogeneidade de `source_type` (Decisao 4) seja verificavel a
posteriori — por exemplo, via consulta que junte `Policy` adotada as
`RuleIdentity`s de suas `RuleVersion`s.

**Seguranca:** o principal risco identificado pela Discovery — mistura semantica
entre criterio privado e obrigacao regulatoria — e mitigado pelos invariantes 3 e 4
(homogeneidade de origem e boundary explicito), nao por controle de acesso
adicional. Nenhuma nova credencial, segredo ou superficie de ataque e introduzida.

**Contratos publicos:** nenhum contrato de API existente e alterado por esta ADR. A
SPEC da Fase 1 pode reaproveitar rotas de `/v1/rule-governance` e da avaliacao
existente; qualquer rota nova para acionar `Evaluation` de BuyerPolicy e decisao de
SPEC, nao desta ADR.

---

## 21. Criterios para liberar SPEC/BUILD futuro

Uma SPEC CRITICAL de Fase 1 so pode ser aprovada quando declarar, no minimo:

1. o nome exato da capability server-side de avaliacao ja existente a ser
   reutilizada (Decisao 5), com teste cobrindo seu uso por Organization nao
   operadora;
2. o teste de homogeneidade de `source_type` por Policy (Invariante 3), incluindo
   caso negativo de mistura;
3. onde e como o boundary `INTERNAL_ONLY` e a origem sao expostos na resposta
   tecnica/API (Invariante 4), sem exigir UI nesta fase;
4. o roteiro de `apps/validacao` demonstrando isolamento entre comprador A,
   comprador B e a matriz regulatoria (nenhum vazamento, nenhuma fusao de
   resultado);
5. confirmacao de que nenhuma rota, capability ou schema novo amplia acesso
   cross-Organization além do que ja existe hoje.

Uma futura Fase 2 (compartilhamento bilateral) exige ADR propria antes de SPEC,
cobrindo no minimo: `AccessPurpose` e `FieldScope` para dado de terceiro,
`RuleSourceType.CONTRACT`, revogacao de `Sharing`/relacao comercial e o
tratamento de "Policy aplicavel, dado invisivel" (Decisao 8 desta ADR).

Uma eventual necessidade de persistir `recognition_boundary` como campo proprio de
`Policy` (em vez de derivado de `source_type` homogeneo) so se torna necessaria
quando `BILATERAL_CONTRACTUAL` ou `PUBLISHED_COMMERCIAL_PROFILE` forem
implementados; essa mudanca exige alteracao formal de `DOMAIN.md` e ADR propria,
nao esta.

---

## 22. Fluxo de referencia

```text
Organization compradora (OrganizationContext proprio)
    -> RULE_GOVERNANCE_CRIAR: RuleIdentity(source_type=INTERNAL_POLICY)
    -> RULE_GOVERNANCE_CRIAR/PUBLICAR: RuleVersion (template controlado, fact_type Livestock)
    -> Policy.create_draft(organization_id=compradora) -> publish()
    -> RULE_GOVERNANCE_ADOTAR: RuleAdoption(policy, rule_version)
    -> [homogeneidade de source_type verificada antes de publicar/adotar]
    -> PolicyEvaluationService avalia sujeito ja visivel a propria Organization
    -> Evaluation isolada, boundary INTERNAL_ONLY explicito
    -> leitura restrita a propria Organization; apresentacao nunca fundida
       com MarketEligibilityPurpose/MarketProfile
```

---

## 23. Questoes adiadas

Permanecem para ADR e SPEC proprias, fora do escopo desta decisao:

- Fase 2: compartilhamento bilateral, `RuleSourceType.CONTRACT`,
  `AccessPurpose`/`FieldScope` para dado de terceiro, revogacao de relacao
  comercial;
- Fase 3: composicao/agregacao publicada entre Policy regulatoria e BuyerPolicy;
- `Decision` comercial de BuyerPolicy e eventual `DecisionAuthorityProfile`
  proprio;
- persistencia formal de `recognition_boundary` alem do valor derivado
  `INTERNAL_ONLY`;
- segregacao de funcoes (autor != publicador) para BuyerPolicy, caso um caso real
  de risco elevado surja antes da Fase 2;
- catalogo de templates controlados de autoria (permanece com os templates
  Livestock ja existentes ate SPEC propria decidir expandir);
- se o produto deve restringir formalmente quem pode publicar BuyerPolicy (ex.:
  `OrganizationType`/`EntityType` "comprador" proprio), ja que hoje nenhum
  mecanismo tecnico distingue Organization compradora de qualquer outra
  Organization com as mesmas permissions (ver nota de vocabulario na secao 3).

---

## Conclusao

BuyerPolicy nao introduz mecanismo novo: e o reconhecimento formal de que uma
Organization compradora pode, hoje, usar a governanca de `Policy`/`Rule` ja aceita
pela ADR-0043 para publicar seu proprio criterio interno, avaliado isoladamente e
apresentado com origem e boundary explicitos. A decisao relevante desta ADR nao e
"como construir", mas "onde a fronteira para" — e a fronteira da Fase 1 e: apenas
`INTERNAL_POLICY`, apenas dado ja visivel ao proprio comprador, apenas `Evaluation`,
nunca fundida com a matriz regulatoria.
